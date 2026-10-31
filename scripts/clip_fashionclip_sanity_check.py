import argparse
from pathlib import Path
import time

import torch
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SAMPLE_IMAGE_DIR = ROOT / "data/d1/sample_images"
SAMPLE_TEXT_QUERIES = [
    "a white collared shirt",
    "áo sơ mi trắng công sở",
    "a pair of blue denim jeans",
]


def sample_image_paths(images_dir=None):
    folder = Path(images_dir) if images_dir is not None else Path(SAMPLE_IMAGE_DIR)
    paths = sorted(path for path in folder.glob("*.jpg") if path.is_file())[:20]
    if not paths:
        raise FileNotFoundError(f"No JPEG sample images found in {folder.resolve()}")
    return paths


def run_clip(images_dir=None):
    image_paths = sample_image_paths(images_dir)
    import clip
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[CLIP] device = {device}")

    model, preprocess = clip.load("ViT-B/32", device=device)  # tải trọng số ở đây

    t0 = time.time()
    images = torch.stack([preprocess(Image.open(p)) for p in image_paths]).to(device)
    with torch.no_grad():
        image_features = model.encode_image(images)
        text_tokens = clip.tokenize(SAMPLE_TEXT_QUERIES).to(device)
        text_features = model.encode_text(text_tokens)
    elapsed = time.time() - t0

    image_features /= image_features.norm(dim=-1, keepdim=True)
    text_features /= text_features.norm(dim=-1, keepdim=True)
    similarity = (text_features @ image_features.T)  # [num_queries, num_images]

    print(f"[CLIP] Encoded {len(image_paths)} ảnh + {len(SAMPLE_TEXT_QUERIES)} câu truy vấn "
          f"trong {elapsed:.2f}s ({elapsed/len(image_paths)*1000:.1f} ms/ảnh)")
    print(f"[CLIP] Kích thước embedding ảnh: {image_features.shape}, văn bản: {text_features.shape}")

    for qi, query in enumerate(SAMPLE_TEXT_QUERIES):
        top_idx = similarity[qi].topk(min(3, len(image_paths))).indices.tolist()
        top_files = [image_paths[i].name for i in top_idx]
        print(f"[CLIP] Query: '{query}' -> top-{len(top_files)}: {top_files}")


def run_fashionclip(images_dir=None):
    image_paths = sample_image_paths(images_dir)
    from transformers import CLIPModel, CLIPProcessor
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[FashionCLIP] device = {device}")

    model = CLIPModel.from_pretrained("patrickjohncyh/fashion-clip").to(device)  # tải checkpoint ở đây
    processor = CLIPProcessor.from_pretrained("patrickjohncyh/fashion-clip")

    images = [Image.open(p) for p in image_paths]
    t0 = time.time()
    inputs = processor(text=SAMPLE_TEXT_QUERIES, images=images, return_tensors="pt", padding=True).to(device)
    with torch.no_grad():
        outputs = model(**inputs)
    elapsed = time.time() - t0

    logits_per_text = outputs.logits_per_text  # [num_queries, num_images]
    print(f"[FashionCLIP] Encoded {len(image_paths)} ảnh + {len(SAMPLE_TEXT_QUERIES)} câu truy vấn "
          f"trong {elapsed:.2f}s ({elapsed/len(image_paths)*1000:.1f} ms/ảnh)")

    for qi, query in enumerate(SAMPLE_TEXT_QUERIES):
        top_idx = logits_per_text[qi].topk(min(3, len(image_paths))).indices.tolist()
        top_files = [image_paths[i].name for i in top_idx]
        print(f"[FashionCLIP] Query: '{query}' -> top-{len(top_files)}: {top_files}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compare CLIP and FashionCLIP on up to 20 local JPEG sample images.")
    parser.add_argument("--images-dir", type=Path, default=SAMPLE_IMAGE_DIR,
                        help="JPEG sample folder (default: repository data/d1/sample_images)")
    args = parser.parse_args()
    try:
        sample_image_paths(args.images_dir)
    except FileNotFoundError as exc:
        parser.error(str(exc))
    print("=" * 60)
    run_clip(args.images_dir)
    print("=" * 60)
    run_fashionclip(args.images_dir)
