from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
from threading import Thread

with tempfile.TemporaryDirectory() as tmp:
    source = Path(tmp)
    asset = source / 'payload.tar'
    with tarfile.open(asset, 'w') as tar:
        for name, data in {'catalog/images/1.jpg': b'fixture-image', 'model/config.json': b'{}'}.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(SimpleHTTPRequestHandler, directory=tmp))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    item = {'name': asset.name, 'kind': 'tar', 'size': asset.stat().st_size,
            'sha256': hashlib.sha256(asset.read_bytes()).hexdigest(),
            'url': f'http://127.0.0.1:{server.server_port}/{asset.name}'}
    manifest = source / 'manifest.json'
    manifest.write_text(json.dumps({'schema': 1, 'product_count': 1, 'assets': [item],
                                   'required_files': ['catalog/images/1.jpg', 'model/config.json']}))
    command = [sys.executable, '/app/setup_runtime.py', '--manifest', str(manifest), '--root', '/data']
    subprocess.run(command, check=True)
    current = Path('/data/current').resolve()
    assert (current / 'catalog/images/1.jpg').read_bytes() == b'fixture-image'
    server.shutdown()
    server.server_close()
    thread.join()
    # Server is gone: a second process must reuse its persisted receipts offline.
    subprocess.run(command, check=True)
    def as_appuser():
        os.setgid(10001)
        os.setuid(10001)
    subprocess.run([sys.executable, '-c', "from pathlib import Path; assert Path('/data/current/catalog/images/1.jpg').read_bytes()==b'fixture-image'"],
                   preexec_fn=as_appuser, check=True)
    print('PASS: real setup entrypoint/lock, atomic activation, offline rerun and uid 10001 read access')
