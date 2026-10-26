"""Validate existing local deployment files and write a Docker Compose env file."""
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset-dir', required=True, type=Path)
    parser.add_argument('--embeddings-dir', type=Path, default=ROOT / 'embeddings')
    parser.add_argument('--model-cache-dir', type=Path, default=ROOT / '.cache/huggingface')
    parser.add_argument('--port', type=int, default=8080)
    parser.add_argument('--output', type=Path, default=ROOT / '.env.docker')
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('Port must be between 1 and 65535')
    dataset, embeddings, cache = (p.resolve() for p in (args.dataset_dir, args.embeddings_dir, args.model_cache_dir))
    required = [dataset / 'images', dataset / 'styles.csv', embeddings / 'product_ids.npy',
                embeddings / 'index/fashionclip_image_embeddings_flat.index']
    missing = [str(p) for p in required if not p.exists()]
    model = cache / 'models--patrickjohncyh--fashion-clip'
    ref = model / 'refs/main'
    if not ref.is_file():
        missing.append(str(ref))
    else:
        revision = ref.read_text().strip()
        if len(revision) != 40 or any(c not in '0123456789abcdef' for c in revision):
            parser.error('Invalid FashionCLIP cache revision')
        snapshot = model / 'snapshots' / revision
        for name in ['config.json', 'preprocessor_config.json', 'tokenizer_config.json', 'vocab.json', 'merges.txt']:
            if not (snapshot / name).is_file(): missing.append(str(snapshot / name))
        if not any((snapshot / name).is_file() for name in ['model.safetensors', 'pytorch_model.bin']):
            missing.append(f'{snapshot}: model.safetensors or pytorch_model.bin')
    if missing:
        parser.error('Missing deployment artifacts:\n' + '\n'.join(missing))
    values = {'DATASET_DIR': dataset.as_posix(), 'EMBEDDINGS_DIR': embeddings.as_posix(), 'MODEL_CACHE_DIR': cache.as_posix()}
    if any("'" in value or '\n' in value or '\r' in value for value in values.values()):
        parser.error('Deployment paths cannot contain quotes or newlines')
    contents = '# Generated local paths; do not commit this file.\n'
    contents += ''.join(f"{key}='{value}'\n" for key, value in values.items())
    contents += f'APP_PORT={args.port}\nSEARCH_CACHE_SIZE=256\nSEARCH_CACHE_TTL_SECONDS=300\n'
    with args.output.open('x', encoding='utf-8', newline='\n') as file:
        file.write(contents)
    print(f'Created {args.output}. Artifacts exist; full validation happens during backend startup.')
    print('docker compose --env-file .env.docker up --build -d --wait --wait-timeout 300')
    print(f'Open http://localhost:{args.port}')


if __name__ == '__main__':
    main()
