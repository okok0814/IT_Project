from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import tarfile
from threading import Thread

import pytest

from deploy import setup_runtime as setup


@pytest.fixture
def release(tmp_path, monkeypatch):
    monkeypatch.setattr(setup.time, 'sleep', lambda _: None)
    assets = tmp_path / 'release'
    assets.mkdir()
    payload = {'catalog/images/1.jpg': b'image', 'catalog/styles.csv': b'id\n1\n',
               'embeddings/product_ids.npy': b'ids', 'embeddings/index/catalog.index': b'index'}
    archive = assets / 'catalog.tar'
    with tarfile.open(archive, 'w') as stream:
        for name, data in payload.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            stream.addfile(info, io.BytesIO(data))
    model = assets / 'model.bin'
    model.write_bytes(b'example model')
    requests = []

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(assets), **kwargs)

        def do_GET(self):
            requests.append(self.path)
            super().do_GET()

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    items = []
    for file, kind in ((archive, 'tar'), (model, 'file')):
        items.append({'name': file.name, 'kind': kind, 'size': file.stat().st_size,
                      'sha256': setup.digest(file), 'url': f'http://127.0.0.1:{server.server_port}/{file.name}'})
    items[-1]['target'] = 'model/model.bin'
    manifest = tmp_path / 'manifest.json'
    manifest.write_text(json.dumps({'schema': 1, 'product_count': 1,
                                   'assets': items, 'required_files': [*payload, 'model/model.bin']}))
    yield manifest, tmp_path / 'volume', requests, assets
    server.shutdown()
    server.server_close()
    thread.join()


def test_first_install_reuse_and_missing_file_repair(release):
    manifest, volume, requests, _ = release
    installed = setup.prepare(manifest, volume, activate=False)
    assert len(requests) == 2
    assert (installed / 'catalog/images/1.jpg').read_bytes() == b'image'
    assert (installed / 'model/model.bin').read_bytes() == b'example model'
    setup.prepare(manifest, volume, activate=False)
    assert len(requests) == 2
    (installed / 'catalog/images/1.jpg').unlink()
    setup.prepare(manifest, volume, activate=False)
    assert requests == ['/catalog.tar', '/model.bin', '/catalog.tar']


def test_failed_download_retry_reuses_completed_parts(release):
    manifest, volume, requests, assets = release
    model = assets / 'model.bin'
    original = model.read_bytes()
    model.write_bytes(b'wrong')
    with pytest.raises(RuntimeError, match='Cannot download'):
        setup.prepare(manifest, volume, activate=False)
    assert not (volume / 'current').exists()
    assert not list(volume.rglob('*.partial'))
    model.write_bytes(original)
    setup.prepare(manifest, volume, activate=False)
    assert requests.count('/catalog.tar') == 1
    assert requests.count('/model.bin') == 4


def test_same_size_corrupt_download_is_rejected(release):
    manifest, volume, _, assets = release
    model = assets / 'model.bin'
    model.write_bytes(b'x' * model.stat().st_size)
    with pytest.raises(RuntimeError) as error:
        setup.prepare(manifest, volume, activate=False)
    assert 'SHA256' in str(error.value.__cause__)


@pytest.mark.parametrize('name,kind', [('../escape', 'file'), ('/absolute', 'file'),
                                     ('C:/escape', 'file'), ('..\\escape', 'file'),
                                     ('safe/link', 'symlink'), ('safe/hard', 'hardlink')])
def test_unsafe_archives_are_rejected(tmp_path, name, kind):
    archive = tmp_path / 'unsafe.tar'
    with tarfile.open(archive, 'w') as stream:
        info = tarfile.TarInfo(name)
        if kind != 'file':
            info.type = tarfile.SYMTYPE if kind == 'symlink' else tarfile.LNKTYPE
            info.linkname = '../../outside'
        stream.addfile(info)
    destination = tmp_path / 'destination'
    destination.mkdir()
    with pytest.raises(ValueError):
        setup.extract(archive, destination, archive.stat().st_size)
    assert not (tmp_path / 'escape').exists()


def test_changed_manifest_preserves_previous_files(release):
    manifest, volume, _, assets = release
    old = setup.prepare(manifest, volume, activate=False)
    model = assets / 'model.bin'
    model.write_bytes(b'new model version')
    data = json.loads(manifest.read_text())
    data['assets'][-1].update(sha256=setup.digest(model), size=model.stat().st_size)
    manifest.write_text(json.dumps(data))
    new = setup.prepare(manifest, volume, activate=False)
    assert old != new
    assert (old / 'model/model.bin').read_bytes() == b'example model'
    assert (new / 'model/model.bin').read_bytes() == b'new model version'


def test_incomplete_catalog_not_accepted(release):
    manifest, volume, _, _ = release
    data = json.loads(manifest.read_text())
    data['product_count'] = 2
    manifest.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='count'):
        setup.prepare(manifest, volume, activate=False)


def test_oversized_download_is_rejected(release):
    manifest, volume, _, _ = release
    data = json.loads(manifest.read_text())
    data['assets'][0]['size'] = 10
    manifest.write_text(json.dumps(data))
    with pytest.raises(RuntimeError) as error:
        setup.prepare(manifest, volume, activate=False)
    assert 'exceeds expected size' in str(error.value.__cause__)
