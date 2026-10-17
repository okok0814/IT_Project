"""Closed-loop local HTTP load test plus separate, sequential cProfile captures.

Uses real FashionCLIP and catalog artifacts. No traffic is sent to external hosts.
Run as python -m scripts.load_test_api --help. Latencies include the local HTTP
round trip; profiles and startup/warmup are excluded from load measurements.
"""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import cProfile
from datetime import datetime, timezone
import hashlib
import importlib.util
import io
import json
import logging
import os
from pathlib import Path
import platform
import pstats
import subprocess
import sys
import threading
import time

import numpy as np
import requests
from werkzeug.serving import make_server

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    sha = hashlib.sha256()
    with Path(path).open('rb') as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b''):
            sha.update(chunk)
    return sha.hexdigest()


def load_backend(directory):
    # Allows identical measurements of a saved, unmodified backend source tree.
    spec = importlib.util.spec_from_loader('benchmark_backend', loader=None,
                                          origin=str(directory.resolve() / '__init__.py'), is_package=True)
    package = importlib.util.module_from_spec(spec)
    package.__path__ = [str(directory.resolve())]
    sys.modules['benchmark_backend'] = package
    return importlib.import_module('benchmark_backend.app')


def workloads(image_dir):
    paths = sorted((ROOT / 'data/d1/sample_images').glob('*.jpg'))
    if len(paths) < 15:
        raise ValueError('Expected at least 15 sample images')
    images = [{'method': 'POST', 'path': '/api/v1/search/image', 'top_k': 10,
               'image': p.read_bytes(), 'filename': p.name} for p in paths]
    queries = ['white office shirt', 'black running shoes', 'blue jeans',
               'red dress', 'casual cotton tshirt', 'leather handbag',
               'formal black trousers', 'summer sandals', 'pink top',
               'navy blue jacket', 'sports shorts', 'white sneakers',
               'green kurta', 'brown belt', 'women floral skirt',
               'men grey sweater', 'black heels', 'blue polo shirt',
               'yellow dress', 'denim jacket']
    text = [{'method': 'POST', 'path': '/api/v1/search/text',
             'json': {'query': query, 'top_k': 10}} for query in queries]
    filtered = [{'method': 'POST', 'path': '/api/v1/search/text',
                 'json': {'query': query, 'top_k': 10, 'gender': 'Men',
                          'category': 'Shirts', 'color': 'White'}} for query in queries]
    related = [{'method': 'GET', 'path': f'/api/v1/products/{p.stem}/related?top_k=8'}
               for p in paths if (image_dir / p.name).is_file()]
    return {'image_repeat': images[:1], 'image_varied': images,
            'text_repeat': filtered[:1], 'text_varied': text,
            'text_filtered_varied': filtered,
            'related_repeat': related[:1], 'related_varied': related,
            'filter_only': [{'method': 'POST', 'path': '/api/v1/search/text',
                             'json': {'category': 'Shirts', 'gender': 'Men', 'top_k': 50}}]}


def request_args(spec, flask=False):
    if 'image' in spec:
        if flask:
            return {'data': {'image': (io.BytesIO(spec['image']), spec['filename']),
                             'top_k': str(spec['top_k'])}}
        return {'files': {'image': (spec['filename'], spec['image'], 'image/jpeg')},
                'data': {'top_k': spec['top_k']}}
    return {'json': spec['json']} if 'json' in spec else {}


def validate(response, spec):
    if response.status_code != 200:
        raise ValueError(f'HTTP {response.status_code}: {response.text[:200]}')
    body = response.json()
    if body.get('success') is not True or body.get('error') is not None or not isinstance(body.get('data'), list):
        raise ValueError('Invalid success envelope')
    rows = body['data']
    top_k = spec.get('top_k', spec.get('json', {}).get('top_k', 8))
    ids = [r['product_id'] for r in rows]
    if len(ids) > top_k or len(ids) != len(set(ids)):
        raise ValueError('Incorrect result count or duplicate IDs')
    if spec['method'] == 'POST' and not rows:
        raise ValueError('Expected nonempty search result')
    for field in ('gender', 'category', 'color'):
        expected = spec.get('json', {}).get(field)
        if expected and any(r.get(field) != expected for r in rows):
            raise ValueError(f'Incorrect {field} filter')
    if '/related?' in spec['path']:
        source = spec['path'].split('/')[-2]
        if source in ids or any(r.get('source_product_id') != source or r.get('match_type') != 'complementary' for r in rows):
            raise ValueError('Incorrect related-product source')
    return rows


def run_batch(base, specs, count, concurrency, timeout):
    barrier = threading.Barrier(concurrency)
    def worker(worker_id):
        records = []
        with requests.Session() as session:
            session.trust_env = False  # Local requests must not use proxy environment settings.
            barrier.wait(timeout=30)
            for number in range(worker_id, count, concurrency):
                spec = specs[number % len(specs)]
                start = time.perf_counter()
                record = {'request': number, 'case': number % len(specs), 'status': None}
                try:
                    response = session.request(spec['method'], base + spec['path'],
                                               timeout=timeout, **request_args(spec))
                    record['latency_ms'] = (time.perf_counter() - start) * 1000
                    record['status'] = response.status_code
                    rows = validate(response, spec)
                    record.update(ok=True, cache=response.headers.get('X-Search-Cache', 'unavailable'),
                                  products=[{'id': r['product_id'], 'score': r['similarity_score']} for r in rows])
                except Exception as exc:
                    record.update(ok=False, latency_ms=(time.perf_counter() - start) * 1000,
                                  error=f'{type(exc).__name__}: {exc}')
                records.append(record)
        return records
    start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        records = [r for batch in pool.map(worker, range(concurrency)) for r in batch]
    seconds = time.perf_counter() - start
    latency = [r['latency_ms'] for r in records]
    return {'concurrency': concurrency, 'requests': len(records),
            'errors': sum(not r['ok'] for r in records), 'duration_s': seconds,
            'throughput_rps': len(records) / seconds,
            'p50_ms': float(np.percentile(latency, 50)),
            'p95_ms': float(np.percentile(latency, 95)),
            'p99_ms': float(np.percentile(latency, 99)), 'max_ms': max(latency),
            'cache_counts': dict(Counter(r.get('cache', 'error') for r in records)),
            'records': sorted(records, key=lambda r: r['request'])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image-dir', required=True, type=Path)
    parser.add_argument('--metadata-path', type=Path)
    parser.add_argument('--backend-dir', type=Path, default=ROOT / 'src/backend')
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--label', default='current')
    parser.add_argument('--requests', type=int, default=48)
    parser.add_argument('--concurrency', type=int, nargs='+', default=[1, 4, 8])
    parser.add_argument('--cache-size', type=int, default=256)
    parser.add_argument('--timeout', type=float, default=120)
    args = parser.parse_args()
    if args.requests < 1 or not args.concurrency or min(args.concurrency) < 1 or max(args.concurrency) > args.requests:
        parser.error('Require 1 <= concurrency <= requests')
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=False)

    def emit(message):
        line = f'{datetime.now(timezone.utc).isoformat()} {message}'
        print(line, flush=True)
        with (output / 'live.txt').open('a', encoding='utf-8') as log:
            log.write(line + '\n')

    emit(f'COMMAND: {subprocess.list2cmdline([sys.executable, *sys.argv])}')
    backend = load_backend(args.backend_dir)
    metadata = args.metadata_path or args.image_dir.parent / 'styles.csv'
    config = {'IMAGE_DIR': str(args.image_dir.resolve()), 'METADATA_PATH': str(metadata.resolve()),
              'INDEX_PATH': str(ROOT / 'embeddings/index/fashionclip_image_embeddings_flat.index'),
              'PRODUCT_IDS_PATH': str(ROOT / 'embeddings/product_ids.npy'),
              'MODEL_CACHE': str(ROOT / '.cache/huggingface'), 'SEARCH_CACHE_SIZE': args.cache_size}
    app = backend.create_app(config)
    provenance = {'timestamp_utc': datetime.now(timezone.utc).isoformat(), 'label': args.label,
                  'git_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                  'platform': platform.platform(), 'processor': platform.processor(), 'cpu_count': os.cpu_count(),
                  'python': sys.version, 'backend_directory': str(args.backend_dir.resolve()),
                  'source_sha256': {p.name: digest(p) for p in args.backend_dir.glob('*.py')},
                  'runner_sha256': digest(__file__),
                  'artifact_sha256': {key: digest(config[key]) for key in ('INDEX_PATH', 'PRODUCT_IDS_PATH', 'METADATA_PATH')},
                  'config': config, 'requests_per_batch': args.requests, 'concurrency': args.concurrency,
                  'note': 'Source hashes identify working-tree code. Closed-loop client and threaded Werkzeug server share one host/process; not a production capacity claim.'}
    (output / 'provenance.json').write_text(json.dumps(provenance, indent=2), encoding='utf-8')
    (output / 'environment.txt').write_text(subprocess.check_output(
        [sys.executable, '-m', 'pip', 'freeze'], text=True), encoding='utf-8')
    emit(f'Initializing {args.label} with real catalog/model...')
    start = time.perf_counter()
    service = backend.FashionSearch(app.config)
    startup_ms = (time.perf_counter() - start) * 1000
    app.extensions['search_service'] = service
    import torch
    import faiss
    result = {'label': args.label, 'startup_ms': startup_ms, 'device': service.device,
              'index_vectors': int(service.index.ntotal), 'torch_threads': torch.get_num_threads(),
              'faiss_threads': faiss.omp_get_max_threads(), 'warmup': [], 'batches': []}
    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    server = make_server('127.0.0.1', 0, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f'http://127.0.0.1:{server.server_port}'
    cases = workloads(args.image_dir)
    try:
        # One request per family: model kernels and lazy metadata initialize here.
        for name in ('image_repeat', 'text_repeat', 'related_repeat', 'filter_only'):
            record = run_batch(base, cases[name], 1, 1, args.timeout)
            result['warmup'].append({'scenario': name, **record})
            if record['errors']:
                raise RuntimeError(f'Warmup failed: {record}')
        for name, specs in cases.items():
            for concurrency in args.concurrency:
                # Reset between batches: repeated requests start with a real miss.
                cache = app.extensions.get('search_cache')
                if cache is not None:
                    cache.clear()
                batch = {'scenario': name, 'unique_cases': len(specs),
                         **run_batch(base, specs, args.requests, concurrency, args.timeout)}
                result['batches'].append(batch)
                (output / 'results.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
                emit(f'{name:22} c={concurrency} n={batch["requests"]} errors={batch["errors"]} '
                      f'p50={batch["p50_ms"]:.1f} p95={batch["p95_ms"]:.1f} ms '
                      f'rps={batch["throughput_rps"]:.2f} cache={batch["cache_counts"]}')
        # Profile synchronous Flask dispatch separately so cProfile sees backend
        # work rather than only the HTTP client's socket wait. Bypass result cache.
        cache = app.extensions.get('search_cache')
        for name in ('image_repeat', 'text_repeat', 'related_repeat', 'filter_only'):
            spec = cases[name][0]
            profiler = cProfile.Profile()
            with app.test_client() as client:
                for _ in range(5):
                    if cache is not None:
                        cache.clear()
                    response = profiler.runcall(client.open, spec['path'], method=spec['method'], **request_args(spec, flask=True))
                    if response.status_code != 200:
                        raise RuntimeError(f'Profile request failed: {response.status_code}')
            profiler.dump_stats(str(output / f'{name}.prof'))
            with (output / f'{name}-profile.txt').open('w', encoding='utf-8') as file:
                pstats.Stats(profiler, stream=file).strip_dirs().sort_stats('cumulative').print_stats(45)
        result['total_requests'] = sum(b['requests'] for b in result['batches'])
        result['total_errors'] = sum(b['errors'] for b in result['batches'])
        (output / 'results.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    finally:
        server.shutdown()
        thread.join(timeout=10)
        server.server_close()
    emit(f'Evidence: {output}; {result["total_requests"]} requests, {result["total_errors"]} errors')
    if result['total_errors']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
