"""Run API performance comparisons and correctness checks with live evidence logs."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image-dir', required=True)
    parser.add_argument('--metadata-path')
    parser.add_argument('--baseline-ref', default='483bf44d6837639608a0a20e5943b0a77fddcd26')
    parser.add_argument('--baseline-output', type=Path, help='Reuse a completed load_test_api baseline run')
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--requests', type=int, default=48)
    parser.add_argument('--concurrency', type=int, nargs='+', default=[1, 4, 8])
    parser.add_argument('--with-ui', action='store_true')
    args = parser.parse_args()
    output = args.output_dir or ROOT / 'logs' / (datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%SZ') + '-week10')
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    env = {**os.environ, 'PYTHONIOENCODING': 'utf-8', 'PYTHONUNBUFFERED': '1'}

    def run(name, command):
        with (output / name).open('w', encoding='utf-8') as log:
            log.write(f'UTC: {datetime.now(timezone.utc).isoformat()}\nCOMMAND: {subprocess.list2cmdline(command)}\n\n')
            log.flush()
            process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace')
            try:
                for line in process.stdout:
                    print(line, end='', flush=True)
                    log.write(line)
                    log.flush()
                code = process.wait()
            finally:
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=30)
            log.write(f'\nEXIT_CODE: {code}\nUTC_END: {datetime.now(timezone.utc).isoformat()}\n')
        if code:
            raise SystemExit(f'Failed; see {output / name}')

    sources = [*ROOT.glob('src/backend/*.py'), *ROOT.glob('tests/*.py'), *ROOT.glob('scripts/*.py'),
               *ROOT.glob('requirements*.txt')]
    provenance = {'timestamp_utc': datetime.now(timezone.utc).isoformat(),
                  'git_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                  'source_sha256': {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
                  'note': 'Source hashes identify the working tree; baseline is an unmodified earlier Git snapshot.'}
    (output / 'provenance.json').write_text(json.dumps(provenance, indent=2), encoding='utf-8')
    run('environment.txt', [sys.executable, '-m', 'pip', 'freeze'])
    run('pytest.txt', [sys.executable, '-m', 'pytest', '-q', f'--junitxml={output / "pytest.xml"}'])
    command = [sys.executable, '-X', 'utf8', '-m', 'scripts.load_test_api', '--image-dir', args.image_dir,
               '--requests', str(args.requests), '--concurrency', *map(str, args.concurrency)]
    if args.metadata_path:
        command += ['--metadata-path', args.metadata_path]
    if args.baseline_output:
        baseline_dir = args.baseline_output.resolve()
        baseline_provenance = json.loads((baseline_dir / 'provenance.json').read_text())
        if (baseline_provenance['requests_per_batch'] != args.requests or
                baseline_provenance['concurrency'] != args.concurrency or
                baseline_provenance['runner_sha256'] != hashlib.sha256((ROOT / 'scripts/load_test_api.py').read_bytes()).hexdigest()):
            raise ValueError('Reused baseline must have the same runner, request count and concurrency')
    else:
        baseline_dir = output / 'baseline'
        backend_dir = output / 'baseline-source'
        backend_dir.mkdir()
        names = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', args.baseline_ref,
                                         '--', 'src/backend'], cwd=ROOT, text=True).splitlines()
        for name in names:
            if name.endswith('.py'):
                data = subprocess.check_output(['git', 'show', f'{args.baseline_ref}:{name}'], cwd=ROOT)
                (backend_dir / Path(name).name).write_bytes(data)
        if not (backend_dir / 'app.py').exists():
            raise ValueError('Baseline ref must contain src/backend/app.py')
        run('baseline.txt', [*command, '--backend-dir', str(backend_dir), '--output-dir', str(baseline_dir),
                             '--label', 'baseline', '--cache-size', '0'])
    phases = {'baseline': baseline_dir}
    for label, size in [('optimized-no-cache', '0'), ('optimized-cache', '256')]:
        phases[label] = output / label
        run(label + '.txt', [*command, '--output-dir', str(phases[label]), '--label', label, '--cache-size', size])
    regression_dir = output / 'regression'
    regression_dir.mkdir()
    regression = [sys.executable, '-X', 'utf8', '-m', 'scripts.verify_related_products', '--image-dir', args.image_dir,
                  '--output-dir', str(regression_dir)]
    if args.metadata_path:
        regression += ['--metadata-path', args.metadata_path]
    if args.with_ui:
        regression.append('--with-ui')
    run('regression.txt', regression)
    node = shutil.which('node') or next(str(p) for p in (ROOT / '.cache/node').glob('*/node.exe'))
    run('build.txt', [node, str(ROOT / 'node_modules/vite/bin/vite.js'), 'build'])
    phases_data = {key: json.loads((path / 'results.json').read_text()) for key, path in phases.items()}
    # Persist all comparison rows, keeping raw records in the individual files.
    comparison = {label: [{key: val for key, val in batch.items() if key != 'records'}
                           for batch in result['batches']] for label, result in phases_data.items()}
    cases = ET.parse(output / 'pytest.xml').getroot().findall('.//testcase')
    api = json.loads((regression_dir / 'related-products.json').read_text(encoding='utf-8'))
    browser_file = regression_dir / 'browser-results.json'
    summary = {'unit_tests': len(cases),
               'unit_passed': sum(not any(c.find(tag) is not None for tag in ['failure', 'error', 'skipped']) for c in cases),
               'load_requests': sum(r['total_requests'] for r in phases_data.values()),
               'load_errors': sum(r['total_errors'] for r in phases_data.values()),
               'phases': {key: os.path.relpath(path, output).replace('\\', '/') for key, path in phases.items()},
               'comparison': comparison, 'real_catalog_cases_passed': api['passed_cases'],
               'browser_checks_passed': len(json.loads(browser_file.read_text())['checks']) if browser_file.exists() else None,
               'build_passed': True}
    (output / 'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in summary.items() if k != 'comparison'}, indent=2), flush=True)
    print(f'Evidence: {output}', flush=True)
    if summary['load_errors']:
        raise SystemExit('Load test had failures')


if __name__ == '__main__':
    main()
