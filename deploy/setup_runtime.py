"""Install pinned runtime artifacts into a Docker volume; no model inference here."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import tarfile
import time
import urllib.request
from urllib.parse import urlparse


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def safe_path(name):
    if (not isinstance(name, str) or not name or '\\' in name or ':' in name
            or any(p in ('', '.', '..') for p in name.split('/'))
            or PurePosixPath(name).is_absolute()):
        raise ValueError(f'Unsafe artifact path: {name!r}')
    return name


def read_manifest(path):
    raw = Path(path).read_bytes()
    manifest = json.loads(raw)
    if manifest.get('schema') != 1 or not manifest.get('assets'):
        raise ValueError('Expected schema 1 and a nonempty assets list')
    names = set()
    for item in manifest['assets']:
        name = safe_path(item['name'])
        if '/' in name or name in names:
            raise ValueError('Asset names must be unique filenames')
        names.add(name)
        if item['kind'] not in ('tar', 'file') or item['size'] <= 0:
            raise ValueError('Invalid asset kind or size')
        sha = item['sha256']
        if len(sha) != 64 or any(c not in '0123456789abcdef' for c in sha):
            raise ValueError('Invalid SHA256')
        url = urlparse(item['url'])
        if url.scheme != 'https' and not (url.scheme == 'http' and url.hostname in ('127.0.0.1', 'localhost')):
            raise ValueError('Downloads require HTTPS (HTTP allowed only on localhost for tests)')
        if item['kind'] == 'file':
            safe_path(item['target'])
    for name in manifest['required_files']:
        safe_path(name)
    return manifest, hashlib.sha256(raw).hexdigest()


def download(item, destination):
    """Never promote an incomplete or corrupt download to a usable artifact."""
    temporary = destination.with_suffix(destination.suffix + '.partial')
    for attempt in range(3):
        try:
            request = urllib.request.Request(item['url'], headers={'User-Agent': 'FashionSearch-Setup/1'})
            with urllib.request.urlopen(request, timeout=60) as response, temporary.open('wb') as output:
                size = 0
                checksum = hashlib.sha256()
                while chunk := response.read(1024 * 1024):
                    size += len(chunk)
                    if size > item['size']:
                        raise ValueError('Download exceeds expected size')
                    checksum.update(chunk)
                    output.write(chunk)
            if size != item['size'] or checksum.hexdigest() != item['sha256']:
                raise ValueError(f'Size/SHA256 mismatch for {item["name"]}')
            temporary.replace(destination)
            return
        except Exception:
            temporary.unlink(missing_ok=True)
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def extract(archive, destination, max_bytes):
    files = []
    seen = set()
    total = 0
    with tarfile.open(archive, 'r:') as stream:
        for member in stream:
            name = safe_path(member.name)
            if not member.isfile() or name in seen or member.size < 0:
                raise ValueError('Archives must contain unique regular files only')
            seen.add(name)
            total += member.size
            if total > max_bytes:
                raise ValueError('Archive exceeds expected unpacked size')
            target = destination / name
            # A setup-owned volume must not redirect writes via preexisting links.
            if not target.resolve().is_relative_to(destination.resolve()) or target.is_symlink():
                raise ValueError('Artifact path escapes destination')
            target.parent.mkdir(parents=True, exist_ok=True)
            with stream.extractfile(member) as source, target.open('wb') as output:
                shutil.copyfileobj(source, output)
            target.chmod(0o644)
            files.append({'path': name, 'size': member.size})
    return files


def intact(directory, files):
    return bool(files) and all((directory / safe_path(f['path'])).is_file()
                               and not (directory / f['path']).is_symlink()
                               and (directory / f['path']).stat().st_size == f['size'] for f in files)


def prepare(manifest_path, root, activate=True):
    manifest, version = read_manifest(manifest_path)
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    directory = root / 'versions' / version
    directory.mkdir(parents=True, exist_ok=True)
    state = root / 'state' / version
    state.mkdir(parents=True, exist_ok=True)
    all_files = set()
    for item in manifest['assets']:
        receipt = state / (item['name'] + '.json')
        try:
            files = json.loads(receipt.read_text()) if receipt.is_file() else []
        except (ValueError, OSError):
            files = []
        if not intact(directory, files):
            receipt.unlink(missing_ok=True)
            print(f'Downloading {item["name"]} ({item["size"] / 1024**2:.1f} MiB)...', flush=True)
            archive = state / item['name']
            try:
                download(item, archive)
            except Exception as exc:
                raise RuntimeError(f'Cannot download {item["name"]}. The maintainer must publish the '
                                   f'assets referenced by deploy/runtime-manifest.json. Retry after checking '
                                   f'network access and the release. URL: {item["url"]}') from exc
            if item['kind'] == 'tar':
                files = extract(archive, directory, item['size'])
                archive.unlink()
            else:
                target = directory / safe_path(item['target'])
                if not target.resolve().is_relative_to(directory.resolve()) or target.is_symlink():
                    raise ValueError('Artifact path escapes destination')
                target.parent.mkdir(parents=True, exist_ok=True)
                archive.replace(target)
                target.chmod(0o644)
                files = [{'path': item['target'], 'size': item['size']}]
            pending = receipt.with_suffix('.tmp')
            pending.write_text(json.dumps(files), encoding='utf-8')
            pending.replace(receipt)
        else:
            print(f'Reusing {item["name"]}', flush=True)
        paths = {f['path'] for f in files}
        if paths & all_files:
            raise ValueError('Assets contain overlapping paths')
        all_files.update(paths)
    for name in manifest['required_files']:
        if safe_path(name) not in all_files:
            raise ValueError(f'Missing required file: {name}')
    if 'product_count' in manifest:
        count = sum(p.startswith('catalog/images/') and p.endswith('.jpg') for p in all_files)
        if count != manifest['product_count']:
            raise ValueError('Catalog image count does not match the manifest')
    if activate:
        link = root / '.current-next'
        link.unlink(missing_ok=True)
        link.symlink_to(Path('versions') / version, target_is_directory=True)
        link.replace(root / 'current')
    print('Setup complete. Backend will validate the catalog/index and warm the model.', flush=True)
    return directory


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o022)
    # Compose normally runs one setup container. Lock also protects manual invocations.
    import fcntl
    args.root.mkdir(parents=True, exist_ok=True)
    with (args.root / '.setup.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        prepare(args.manifest, args.root)


if __name__ == '__main__':
    main()
