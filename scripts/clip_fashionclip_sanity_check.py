import glob
import time

import torch
from PIL import Image

SAMPLE_IMAGE_DIR = ".data/d1/sample_images/"
SAMPLE_TEXT_QUERIES = [
    "a white collared shirt",
    "áo sơ mi trắng công sở",
    "a pair of blue denim jeans",
]


def run_clip():
    import clip
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[CLIP] device = {device}")

    model, preprocess = clip.load("ViT-B/32", device=device)  # tải trọng số ở đây

    image_paths = sorted(glob.glob(f"{SAMPLE_IMAGE_DIR}/*.jpg"))[:20]
    if not image_paths:
        print(f"[CLIP] Không tìm thấy ảnh trong {SAMPLE_IMAGE_DIR}")
        return

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
        top_files = [image_paths[i].split("/")[-1] for i in top_idx]
        print(f"[CLIP] Query: '{query}' -> top-{len(top_files)}: {top_files}")


def run_fashionclip():
    from transformers import CLIPModel, CLIPProcessor
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[FashionCLIP] device = {device}")

    model = CLIPModel.from_pretrained("patrickjohncyh/fashion-clip").to(device)  # tải checkpoint ở đây
    processor = CLIPProcessor.from_pretrained("patrickjohncyh/fashion-clip")

    image_paths = sorted(glob.glob(f"{SAMPLE_IMAGE_DIR}/*.jpg"))[:20]
    if not image_paths:
        print(f"[FashionCLIP] Không tìm thấy ảnh trong {SAMPLE_IMAGE_DIR}")
        return

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
        top_files = [image_paths[i].split("/")[-1] for i in top_idx]
        print(f"[FashionCLIP] Query: '{query}' -> top-{len(top_files)}: {top_files}")


if __name__ == "__main__":
    print("=" * 60)
    run_clip()
    print("=" * 60)
    run_fashionclip()
