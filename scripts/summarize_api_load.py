"""Compare raw load-test responses and generate a report table from saved evidence."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence-dir', required=True, type=Path)
    args = parser.parse_args()
    output = args.evidence_dir.resolve()
    summary = json.loads((output / 'summary.json').read_text())
    phases = {label: output / path for label, path in summary['phases'].items()}
    results = {label: json.loads((path / 'results.json').read_text()) for label, path in phases.items()}
    provenances = {label: json.loads((path / 'provenance.json').read_text()) for label, path in phases.items()}
    baseline = results['baseline']
    checked, score_delta = 0, 0.0
    for label, data in results.items():
        assert provenances[label]['artifact_sha256'] == provenances['baseline']['artifact_sha256'], 'Catalog artifacts differ'
        assert provenances[label]['runner_sha256'] == provenances['baseline']['runner_sha256'], 'Load runners differ'
        if label == 'baseline':
            continue
        assert len(data['batches']) == len(baseline['batches'])
        for before, after in zip(baseline['batches'], data['batches']):
            assert (before['scenario'], before['concurrency'], before['requests']) == (after['scenario'], after['concurrency'], after['requests'])
            for old, new in zip(before['records'], after['records']):
                assert old['ok'] and new['ok']
                assert (old['request'], old['case']) == (new['request'], new['case'])
                assert [p['id'] for p in old['products']] == [p['id'] for p in new['products']], (label, before['scenario'], old['case'])
                for a, b in zip(old['products'], new['products']):
                    if a['score'] is None or b['score'] is None:
                        assert a['score'] is b['score']
                    else:
                        delta = abs(a['score'] - b['score'])
                        assert delta <= 2e-5
                        score_delta = max(score_delta, delta)
                checked += 1
    current = provenances['optimized-cache']['source_sha256']
    assert current == provenances['optimized-no-cache']['source_sha256'], 'Optimized backend changed between phases'
    assert all(hashlib.sha256((ROOT / 'src/backend' / name).read_bytes()).hexdigest() == sha
               for name, sha in current.items()), 'Backend changed after measurement'
    checks = {'compared_responses': checked, 'identical_product_order': True,
              'maximum_score_difference': score_delta, 'score_tolerance': 2e-5,
              'same_artifacts_and_load_runner': True, 'current_backend_matches_measured_source': True,
              'sample_image_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                     for p in sorted((ROOT / 'data/d1/sample_images').glob('*.jpg'))},
              'note': 'Exact IDs/order match for this workload. The API does not guarantee ordering between ties in general.'}
    (output / 'comparison-checks.json').write_text(json.dumps(checks, indent=2), encoding='utf-8')
    lines = ['# API load-test comparison', '',
             'Generated from results.json by scripts/summarize_api_load.py. Latency is in milliseconds.', '',
             '| Scenario | Clients | Baseline p50 / p95 | Optimized, cache off p50 / p95 | Cache on p50 / p95 | Baseline / off / on req/s |',
             '| --- | ---: | ---: | ---: | ---: | ---: |']
    for index, before in enumerate(baseline['batches']):
        off = results['optimized-no-cache']['batches'][index]
        on = results['optimized-cache']['batches'][index]
        lines.append(f'| {before["scenario"]} | {before["concurrency"]} | '
                     + ' | '.join(f'{r["p50_ms"]:.1f} / {r["p95_ms"]:.1f}' for r in (before, off, on))
                     + ' | ' + ' / '.join(f'{r["throughput_rps"]:.1f}' for r in (before, off, on)) + ' |')
    lines += ['', f'Response comparisons: {checked}; maximum absolute score difference: {score_delta:.8f}.',
              'All product IDs and ordering matched. HTTP validation passed in all measured phases.', '']
    (output / 'comparison.md').write_text('\n'.join(lines), encoding='utf-8')
    print('\n'.join(lines), flush=True)


if __name__ == '__main__':
    main()
