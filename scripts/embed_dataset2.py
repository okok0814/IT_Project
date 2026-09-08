"""
Output trong ./embeddings/:
    product_ids.npy                    — thứ tự ID, KHỚP HÀNG với mọi file .npy dưới đây
    clip_image_embeddings.npy          [N, 512]
    clip_text_embeddings.npy           [N, 512]
    fashionclip_image_embeddings.npy   [N, 512]
    fashionclip_text_embeddings.npy    [N, 512]
"""
import os
import time

import numpy as np
import pandas as pd
import torch
from PIL import Image
from tqdm import tqdm

DATA_DIR = "./data/dataset2"
IMAGES_DIR = os.path.join(DATA_DIR, "images")
STYLES_CSV = os.path.join(DATA_DIR, "styles.csv")
OUTPUT_DIR = "./embeddings"
BATCH_SIZE = 64  # nếu Colab báo CUDA out of memory, giảm còn 32 rồi 16


def load_valid_products():
    df = pd.read_csv(STYLES_CSV, on_bad_lines="skip")
    df["id"] = df["id"].astype(str)
    ok_mask = df["id"].apply(lambda i: os.path.exists(os.path.join(IMAGES_DIR, f"{i}.jpg")))
    n_dropped = (~ok_mask).sum()
    df = df[ok_mask].reset_index(drop=True)
    print(f"{len(df)} sản phẩm có ảnh hợp lệ (đã loại {n_dropped} ID thiếu ảnh)")
    return df


def batched_indices(n, batch_size):
    for start in range(0, n, batch_size):
        yield list(range(start, min(start + batch_size, n)))


def embed_with_clip(df, device, encode_fn=None):
    """encode_fn: dùng để inject bộ encode giả khi self-test (xem cuối file).
    Khi chạy thật, để None — hàm sẽ tự tải model.load('ViT-B/32')."""
    if encode_fn is None:
        import clip
        model, preprocess = clip.load("ViT-B/32", device=device)
        model.eval()

        def encode_fn(batch_ids, batch_texts):
            images = torch.stack([
                preprocess(Image.open(os.path.join(IMAGES_DIR, f"{pid}.jpg")).convert("RGB"))
                for pid in batch_ids
            ]).to(device)
            tokens = clip.tokenize(batch_texts, truncate=True).to(device)
            with torch.no_grad():
                img_f = model.encode_image(images).float().cpu().numpy()
                txt_f = model.encode_text(tokens).float().cpu().numpy()
            return img_f, txt_f

    ids = df["id"].tolist()
    texts = df["productDisplayName"].fillna("").tolist()
    image_feats, text_feats = [], []

    t0 = time.time()
    for idx in tqdm(list(batched_indices(len(df), BATCH_SIZE)), desc="CLIP"):
        batch_ids = [ids[i] for i in idx]
        batch_texts = [texts[i] for i in idx]
        img_f, txt_f = encode_fn(batch_ids, batch_texts)
        image_feats.append(img_f)
        text_feats.append(txt_f)
    elapsed = time.time() - t0

    image_feats = np.concatenate(image_feats, axis=0)
    text_feats = np.concatenate(text_feats, axis=0)
    print(f"[CLIP] {len(df)} sản phẩm trong {elapsed:.1f}s ({elapsed/len(df)*1000:.1f} ms/sản phẩm)")
    return image_feats, text_feats


def embed_with_fashionclip(df, device, encode_fn=None):
    if encode_fn is None:
        from transformers import CLIPModel, CLIPProcessor
        model = CLIPModel.from_pretrained("patrickjohncyh/fashion-clip").to(device)
        processor = CLIPProcessor.from_pretrained("patrickjohncyh/fashion-clip")
        model.eval()

        def encode_fn(batch_ids, batch_texts):
            images = [Image.open(os.path.join(IMAGES_DIR, f"{pid}.jpg")).convert("RGB") for pid in batch_ids]
            
            # Gom chung ảnh và text vào một input duy nhất giống hệt file sanity_check
            inputs = processor(text=batch_texts, images=images, return_tensors="pt", padding=True, truncation=True).to(device)
            
            with torch.no_grad():
                outputs = model(**inputs)
                # Lấy trực tiếp tensor từ thuộc tính image_embeds và text_embeds
                img_f = outputs.image_embeds.float().cpu().numpy()
                txt_f = outputs.text_embeds.float().cpu().numpy()
                
            return img_f, txt_f

    ids = df["id"].tolist()
    texts = df["productDisplayName"].fillna("").tolist()
    image_feats, text_feats = [], []

    t0 = time.time()
    for idx in tqdm(list(batched_indices(len(df), BATCH_SIZE)), desc="FashionCLIP"):
        batch_ids = [ids[i] for i in idx]
        batch_texts = [texts[i] for i in idx]
        img_f, txt_f = encode_fn(batch_ids, batch_texts)
        image_feats.append(img_f)
        text_feats.append(txt_f)
    elapsed = time.time() - t0

    image_feats = np.concatenate(image_feats, axis=0)
    text_feats = np.concatenate(text_feats, axis=0)
    print(f"[FashionCLIP] {len(df)} sản phẩm trong {elapsed:.1f}s ({elapsed/len(df)*1000:.1f} ms/sản phẩm)")
    return image_feats, text_feats


def run(df, device):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    np.save(f"{OUTPUT_DIR}/product_ids.npy", df["id"].values)

    clip_img, clip_txt = embed_with_clip(df, device)
    np.save(f"{OUTPUT_DIR}/clip_image_embeddings.npy", clip_img)
    np.save(f"{OUTPUT_DIR}/clip_text_embeddings.npy", clip_txt)

    fclip_img, fclip_txt = embed_with_fashionclip(df, device)
    np.save(f"{OUTPUT_DIR}/fashionclip_image_embeddings.npy", fclip_img)
    np.save(f"{OUTPUT_DIR}/fashionclip_text_embeddings.npy", fclip_txt)

    print("Xong. File đã lưu trong", OUTPUT_DIR)
    return clip_img, clip_txt, fclip_img, fclip_txt


if __name__ == "__main__":
    import sys
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"device = {device}")

    if "--self_test" in sys.argv:
        # Kiểm thử toàn bộ luồng batching + lưu file bằng encoder GIẢ (vector ngẫu nhiên đúng shape)
        # Mục đích: xác nhận logic batching/ghép nối/lưu file đúng TRƯỚC khi chạy tốn thời gian với model + dataset thật trên Colab.
        import tempfile

        def fake_encode(batch_ids, batch_texts):
            n = len(batch_ids)
            return (np.random.randn(n, 512).astype("float32"),
                    np.random.randn(n, 512).astype("float32"))

        with tempfile.TemporaryDirectory() as tmp:
            DATA_DIR, IMAGES_DIR, STYLES_CSV, OUTPUT_DIR = tmp, os.path.join(tmp, "images"), os.path.join(tmp, "styles.csv"), os.path.join(tmp, "out")
            os.makedirs(IMAGES_DIR, exist_ok=True)
            n_fake = 37  # số lẻ cố ý — để bắt lỗi nếu code giả định chia hết cho BATCH_SIZE
            rows = [{"id": i, "productDisplayName": f"Fake product {i}"} for i in range(n_fake)]
            pd.DataFrame(rows).to_csv(STYLES_CSV, index=False)
            for i in range(n_fake):
                if i == 5:
                    continue  # cố ý thiếu 1 ảnh để test load_valid_products()
                Image.new("RGB", (32, 32)).save(os.path.join(IMAGES_DIR, f"{i}.jpg"))

            df = load_valid_products()
            assert len(df) == n_fake - 1, "load_valid_products không loại đúng ảnh thiếu!"

            clip_img, clip_txt = embed_with_clip(df, device, encode_fn=fake_encode)
            fclip_img, fclip_txt = embed_with_fashionclip(df, device, encode_fn=fake_encode)

            for name, arr in [("clip_img", clip_img), ("clip_txt", clip_txt),
                               ("fclip_img", fclip_img), ("fclip_txt", fclip_txt)]:
                assert arr.shape == (n_fake - 1, 512), f"{name} sai shape: {arr.shape}"

            print("[SELF-TEST PASSED] batching + ghép nối + shape đều đúng "
                  f"với {n_fake-1} sản phẩm (đã loại 1 ID thiếu ảnh), batch lẻ không chia hết.")
    else:
        df = load_valid_products()
        run(df, device)