"""Verify a running Docker deployment through its public Nginx URL; save evidence."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import time

import requests

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='http://localhost:8080')
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--with-ui', action='store_true')
    args = parser.parse_args()
    base = args.base_url.rstrip('/')
    output = args.output_dir or ROOT / 'logs' / (datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%SZ') + '-deployment')
    output.mkdir(parents=True, exist_ok=False)
    checks, records = [], []
    session = requests.Session()
    session.trust_env = False

    def save():
        (output / 'results.json').write_text(json.dumps({'base_url': base, 'checks': checks, 'records': records},
                                                       indent=2, ensure_ascii=False), encoding='utf-8')

    def passed(name):
        checks.append(name)
        line = f'{datetime.now(timezone.utc).isoformat()} PASS: {name}'
        print(line, flush=True)
        with (output / 'live.txt').open('a', encoding='utf-8') as log:
            log.write(line + '\n')
        save()

    def call(method, path, status=200, **kwargs):
        start = time.perf_counter()
        response = session.request(method, base + path, timeout=180, **kwargs)
        record = {'method': method, 'path': path, 'status': response.status_code,
                  'elapsed_ms': round((time.perf_counter() - start) * 1000, 2),
                  'content_type': response.headers.get('Content-Type'),
                  'cache': response.headers.get('X-Search-Cache')}
        if 'application/json' in response.headers.get('Content-Type', ''):
            record['body'] = response.json()
        records.append(record)
        save()
        assert response.status_code == status, (path, response.status_code, response.text[:300])
        return response

    try:
        assert call('GET', '/ready').json()['data']['status'] == 'ready'
        assert call('GET', '/health').json()['data']['model_loaded'] is True
        passed('Nginx proxies readiness and health; model is loaded before serving')
        for path in ['/', '/search/image', '/search/text', '/results']:
            page = call('GET', path)
            assert 'text/html' in page.headers['Content-Type'] and '<div id="root">' in page.text
        script = re.search(r'src="(/assets/[^" ]+\.js)"', page.text)[1]
        assert 'javascript' in call('GET', script).headers['Content-Type']
        call('GET', '/assets/does-not-exist.js', status=404)
        passed('Built frontend, nested-route refresh and static asset handling')

        body = {'query': 'white office shirt', 'gender': 'Men', 'category': 'Shirts', 'color': 'White', 'top_k': 3}
        text = call('POST', '/api/v1/search/text', json=body).json()
        assert text['success'] and text['error'] is None and len(text['data']) == 3
        assert all(r['gender'] == 'Men' and r['category'] == 'Shirts' and r['color'] == 'White' for r in text['data'])
        again = call('POST', '/api/v1/search/text', json=body)
        assert again.headers['X-Search-Cache'] == 'HIT' and again.json() == text
        assert call('POST', '/search/text', json=body).json() == text
        passed('Real filtered text inference, cache hit and legacy POST route')
        browse = call('POST', '/api/v1/search/text', json={'category': 'Shirts', 'top_k': 3}).json()['data']
        assert len(browse) == 3 and all(r['similarity_score'] is None and r['match_type'] == 'metadata' for r in browse)
        assert call('POST', '/api/v1/search/text', json={'category': 'not-a-category'}).json()['data'] == []
        passed('Filter-only and empty-result semantics')

        sample = ROOT / 'data/d1/sample_images/10180.jpg'
        with sample.open('rb') as image:
            result = call('POST', '/api/v1/search/image', files={'image': (sample.name, image, 'image/jpeg')},
                          data={'top_k': '3'}).json()['data']
        assert len(result) == 3 and result[0]['product_id'] == '10180'
        for row in result:
            assert call('GET', row['image_url']).headers['Content-Type'].startswith('image/')
        passed('Real uploaded-image inference and catalog thumbnails through Nginx')

        source = text['data'][0]['product_id']
        related = call('GET', f'/api/v1/products/{source}/related?top_k=3').json()['data']
        assert len(related) == 3
        assert all(r['product_id'] != source and r['source_product_id'] == source and r['match_type'] == 'complementary'
                   and r['category'] != 'Shirts' for r in related)
        passed('Related products reuse source ID and complementary candidates')

        invalid = [call('POST', '/api/v1/search/text', status=400, json={'query': 'shirt', 'top_k': 0}),
                   call('POST', '/api/v1/search/image', status=415, files={'image': ('bad.gif', b'GIF89a', 'image/gif')}),
                   call('POST', '/api/v1/search/image', status=400, files={'image': ('bad.jpg', b'broken', 'image/jpeg')}),
                   call('GET', '/api/v1/products/not-in-catalog/related', status=404),
                   call('GET', '/api/v1/missing', status=404)]
        assert all(r.json()['success'] is False and r.json()['data'] is None for r in invalid)
        passed('Validation and unknown API routes retain JSON errors through proxy')
        for size in [10 * 1024 * 1024 + 1, 11 * 1024 * 1024 + 1]:
            response = call('POST', '/api/v1/search/image', status=413,
                            files={'image': ('large.jpg', b'x' * size, 'image/jpeg')})
            assert response.json()['success'] is False
        passed('Flask and Nginx upload-size limits both return JSON 413')

        if args.with_ui:
            from playwright.sync_api import sync_playwright, expect
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(channel='chrome', headless=True)
                try:
                    page = browser.new_page(viewport={'width': 1440, 'height': 1000})
                    errors = []
                    page.on('pageerror', lambda exc: errors.append(str(exc)))
                    page.goto(base + '/search/text', wait_until='networkidle')
                    page.locator('#query').fill('white office shirt')
                    page.get_by_role('button', name=re.compile('DISCOVER', re.I)).click()
                    expect(page.locator('.product-grid .product-card').first).to_be_visible(timeout=180000)
                    expect(page.locator('.related-section .product-card').first).to_be_visible(timeout=180000)
                    page.screenshot(path=str(output / 'docker-desktop.png'), full_page=True)
                    page.goto(base + '/search/image', wait_until='networkidle')
                    page.locator('input[type="file"]').set_input_files(str(sample))
                    page.get_by_role('button', name=re.compile('DISCOVER MATCHES', re.I)).click()
                    expect(page.locator('.product-grid .product-card').first).to_be_visible(timeout=180000)
                    page.set_viewport_size({'width': 390, 'height': 844})
                    page.screenshot(path=str(output / 'docker-mobile.png'), full_page=True)
                    assert not errors, errors
                    (output / 'browser.json').write_text(json.dumps({'page_errors': errors, 'text_and_image_flows': 'passed'}, indent=2))
                finally:
                    browser.close()
            passed('Chrome uses built frontend for text/image search and related results; desktop/mobile screenshots')
        paths = [ROOT / 'compose.yaml', ROOT / '.dockerignore', *ROOT.glob('deploy/*'),
                 *ROOT.glob('src/backend/*.py'), Path(__file__), ROOT / 'requirements.txt', ROOT / 'package-lock.json']
        provenance = {'timestamp_utc': datetime.now(timezone.utc).isoformat(),
                      'source_sha256': {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.is_file()},
                      'sample_sha256': hashlib.sha256(sample.read_bytes()).hexdigest(),
                      'note': 'Smoke/integration verification of the running deployment; timings are not a load benchmark.'}
        (output / 'provenance.json').write_text(json.dumps(provenance, indent=2), encoding='utf-8')
        print(f'Passed {len(checks)} checks. Evidence: {output}', flush=True)
    except Exception as exc:
        (output / 'failure.txt').write_text(f'{type(exc).__name__}: {exc}', encoding='utf-8')
        raise
    finally:
        session.close()


if __name__ == '__main__':
    main()
