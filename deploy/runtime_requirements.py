"""Extract Docker's runtime dependencies from the single project requirements file."""
from pathlib import Path


def extract_runtime(text):
    lines = text.splitlines()
    start, end = '# BEGIN RUNTIME', '# END RUNTIME'
    if lines.count(start) != 1 or lines.count(end) != 1:
        raise ValueError('requirements.txt must contain exactly one pair of runtime markers')
    first, last = lines.index(start), lines.index(end)
    if first >= last:
        raise ValueError('Runtime markers must be ordered BEGIN then END')
    entries = [line.strip() for line in lines[first + 1:last]
               if line.strip() and not line.lstrip().startswith('#')]
    if not entries or any(line.startswith('-') for line in entries):
        raise ValueError('Runtime section must contain dependencies without pip options or includes')
    return '\n'.join(entries) + '\n'


if __name__ == '__main__':
    source = Path(__file__).resolve().parents[1] / 'requirements.txt'
    Path('/tmp/requirements-runtime.txt').write_text(
        extract_runtime(source.read_text(encoding='utf-8')), encoding='utf-8')
