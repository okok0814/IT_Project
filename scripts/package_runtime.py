"""Maintainer: package the existing catalog/index without recalculating embeddings."""
import argparse
import json
from pathlib import Path
import tarfile

import faiss
import numpy as np

from deploy.setup_runtime import digest
from src.backend.metadata import ProductMetadata

ROOT = Path(__file__).resolve().parents[1]
MODEL = 'patrickjohncyh/fashion-clip'
MODEL_FILES = ['config.json', 'preprocessor_config.json', 'tokenizer_config.json',
               'special_tokens_map.json', 'tokenizer.json', 'vocab.json', 'merges.txt', 'model.safetensors']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset-dir', type=Path, required=True)
    parser.add_argument('--embeddings-dir', type=Path, default=ROOT / 'embeddings')
    parser.add_argument('--model-cache-dir', type=Path, default=ROOT / '.cache/huggingface')
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--base-url', required=True, help='HTTPS release download directory')
    args = parser.parse_args()
    if not args.base_url.startswith('https://'):
        parser.error('--base-url must use HTTPS')
    ids = np.load(args.embeddings_dir / 'product_ids.npy', allow_pickle=True).astype(str)
    if ids.ndim != 1 or not len(ids) or len(set(ids)) != len(ids) or any(not p.isdigit() for p in ids):
        parser.error('Expected unique numeric product IDs')
    index_path = args.embeddings_dir / 'index/fashionclip_image_embeddings_flat.index'
    index = faiss.read_index(str(index_path))
    if not isinstance(index, faiss.IndexFlatIP) or index.d != 512 or index.ntotal != len(ids):
        parser.error('Expected matching FashionCLIP FlatIP index/IDs')
    if not np.allclose(np.linalg.norm(index.reconstruct_n(0, index.ntotal), axis=1), 1, atol=1e-3):
        parser.error('Index vectors must be normalized')
    ProductMetadata(args.dataset_dir / 'styles.csv', ids)
    images = [args.dataset_dir / 'images' / f'{p}.jpg' for p in ids]
    if any(not p.is_file() for p in images):
        parser.error('Missing indexed images')
    cache = args.model_cache_dir / 'models--patrickjohncyh--fashion-clip'
    revision = (cache / 'refs/main').read_text().strip()
    if len(revision) != 40 or any(c not in '0123456789abcdef' for c in revision):
        parser.error('Invalid model revision')
    snapshot = cache / 'snapshots' / revision
    for name in MODEL_FILES:
        if not (snapshot / name).is_file():
            parser.error(f'Missing model file: {name}')
    args.output_dir.mkdir(parents=True, exist_ok=False)
    # Avoid distributing a pickle payload: runtime IDs use a plain string array.
    ids_path = args.output_dir / 'product_ids.npy'
    np.save(ids_path, ids, allow_pickle=False)
    assets = []

    def package(name, entries):
        path = args.output_dir / name
        with tarfile.open(path, 'w') as archive:
            for source, target in entries:
                info = archive.gettarinfo(str(source), arcname=target)
                info.uid = info.gid = 0
                info.uname = info.gname = ''
                info.mode = 0o644
                info.mtime = 0
                with source.open('rb') as file:
                    archive.addfile(info, file)
        assets.append({'name': name, 'kind': 'tar', 'url': args.base_url.rstrip('/') + '/' + name,
                       'size': path.stat().st_size, 'sha256': digest(path)})
        print(f'Packaged {name}: {path.stat().st_size:,} bytes', flush=True)

    package('search-artifacts.tar', [(ids_path, 'embeddings/product_ids.npy'),
                                   (index_path, 'embeddings/index/fashionclip_image_embeddings_flat.index'),
                                   (args.dataset_dir / 'styles.csv', 'catalog/styles.csv')])
    batch, size, part = [], 0, 1
    for image in images:
        if batch and size + image.stat().st_size > 1024**3:
            package(f'catalog-{part:03d}.tar', batch)
            batch, size, part = [], 0, part + 1
        batch.append((image, 'catalog/images/' + image.name))
        size += image.stat().st_size
    if batch:
        package(f'catalog-{part:03d}.tar', batch)
    for name in MODEL_FILES:
        path = snapshot / name
        assets.append({'name': name, 'kind': 'file', 'target': 'model/' + name,
                       'url': f'https://huggingface.co/{MODEL}/resolve/{revision}/{name}',
                       'size': path.stat().st_size, 'sha256': digest(path)})
    required = ['catalog/styles.csv', 'embeddings/product_ids.npy',
                'embeddings/index/fashionclip_image_embeddings_flat.index'] + ['model/' + n for n in MODEL_FILES]
    manifest = {'schema': 1, 'product_count': len(ids), 'model': MODEL, 'model_revision': revision,
                'required_files': required, 'assets': assets}
    (args.output_dir / 'runtime-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    ids_path.unlink()
    print('Upload all .tar files to the release, then copy runtime-manifest.json into deploy/.', flush=True)
    print('Model files download from the pinned original Hugging Face revision.', flush=True)


if __name__ == '__main__':
    main()
