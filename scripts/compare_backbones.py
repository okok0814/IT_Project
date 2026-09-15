import os

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from PIL import Image

EMBED_DIR = "./embeddings"
IMAGES_DIR = "./data/dataset2/images"
FIGURES_DIR = "./logs/backbone_comparison_figures"  # lưu lại mỗi lưới ảnh — bằng chứng cho báo cáo


QUERY_SET = [
    ("simple_en", "red running shoes"),
    ("simple_vi", "giày chạy bộ màu đỏ"),  # bản dịch câu trên — so sánh trực tiếp EN vs VI
    ("simple_en", "black leather handbag"),
    ("simple_vi", "túi xách da màu đen"),
    ("attribute_en", "a white collared shirt for office wear"),
    ("attribute_vi", "áo sơ mi trắng công sở"),
    
    ("attribute_en", "high waisted wide leg linen pants"),
    ("attribute_vi", "quần ống rộng lưng cao vải linen"),
    ("attribute_en", "waterproof winter coat with faux fur hood"),
    ("attribute_vi", "áo khoác mùa đông chống nước có mũ lông nhân tạo"),
    ("attribute_en", "comfortable slip-on work shoes for standing all day"),
    ("attribute_vi", "giày lười đi làm thoải mái để đứng cả ngày"),

    ("ambiguous_en", "outfit ideas for a summer beach wedding"),
    ("ambiguous_vi", "ý tưởng trang phục đi đám cưới bãi biển mùa hè"),
    ("ambiguous_en", "what to wear for a rainy day first date"),
    ("ambiguous_vi", "mặc gì cho buổi hẹn hò đầu tiên vào ngày mưa"),
    ("ambiguous_en", "minimalist smart casual capsule wardrobe for men"),
    ("ambiguous_vi", "tủ đồ tối giản phong cách smart casual cho nam")
]


def load_embeddings():
    return {
        "ids": np.load(f"{EMBED_DIR}/product_ids.npy", allow_pickle=True),
        "clip_img": np.load(f"{EMBED_DIR}/clip_image_embeddings.npy"),
        "fclip_img": np.load(f"{EMBED_DIR}/fashionclip_image_embeddings.npy"),
    }


def embed_query_clip(text, device="cpu"):
    import clip
    import torch
    model, _ = clip.load("ViT-B/32", device=device)
    with torch.no_grad():
        tokens = clip.tokenize([text], truncate=True).to(device)
        feat = model.encode_text(tokens).float().cpu().numpy()[0]
    return feat


def embed_query_fashionclip(text, device="cpu"):
    from transformers import CLIPModel, CLIPProcessor
    import torch
    model = CLIPModel.from_pretrained("patrickjohncyh/fashion-clip").to(device)
    processor = CLIPProcessor.from_pretrained("patrickjohncyh/fashion-clip")
    with torch.no_grad():
        inputs = processor(text=[text], return_tensors="pt", padding=True, truncation=True).to(device)
        feat = model.get_text_features(**inputs).float().cpu().numpy()[0]
    return feat


def top_k_cosine(query_vec, image_matrix, ids, k=5):
    """Cosine similarity thủ công bằng numpy (không qua FAISS — chỉ 1 truy
    vấn mỗi lần, không cần chỉ mục). CÙNG quy tắc chuẩn hóa như FAISS tuần
    trước: không chuẩn hóa = kết quả thiên vị theo độ lớn vector, không phải
    theo hướng/ý nghĩa ngữ nghĩa."""
    q = query_vec / np.linalg.norm(query_vec)
    m = image_matrix / np.linalg.norm(image_matrix, axis=1, keepdims=True)
    sims = m @ q
    top_idx = np.argsort(-sims)[:k]
    return [(ids[i], float(sims[i])) for i in top_idx]


def retrieve_all(query_set, data, embed_clip_fn=embed_query_clip,
                  embed_fclip_fn=embed_query_fashionclip, device="cpu"):
    """embed_*_fn có thể thay bằng hàm giả khi self-test — xem cuối file."""
    results = {}
    for _, text in query_set:
        clip_q = embed_clip_fn(text, device)
        fclip_q = embed_fclip_fn(text, device)
        results[text] = {
            "clip": top_k_cosine(clip_q, data["clip_img"], data["ids"], k=5),
            "fashionclip": top_k_cosine(fclip_q, data["fclip_img"], data["ids"], k=5),
        }
    return results


def judge_blind(results, images_dir=IMAGES_DIR, figures_dir=FIGURES_DIR, input_fn=input):
    """input_fn có thể thay bằng hàm giả khi self-test (trả lời tự động
    thay vì chờ người gõ) — xem cuối file."""
    os.makedirs(figures_dir, exist_ok=True)
    judgments = {}

    for query, model_results in results.items():
        seen = {}
        for model_name in ["clip", "fashionclip"]:
            for pid, _ in model_results[model_name]:
                if pid not in seen:
                    seen[pid] = True
        candidate_ids = list(seen.keys())
        labels = [chr(65 + i) for i in range(len(candidate_ids))]

        fig, axes = plt.subplots(1, len(candidate_ids), figsize=(3 * len(candidate_ids), 3.3))
        if len(candidate_ids) == 1:
            axes = [axes]
        for ax, label, pid in zip(axes, labels, candidate_ids):
            img_path = os.path.join(images_dir, f"{pid}.jpg")
            if os.path.exists(img_path):
                ax.imshow(Image.open(img_path))
            else:
                ax.text(0.5, 0.5, "(thiếu ảnh)", ha="center", va="center")
            ax.set_title(label)
            ax.axis("off")
        fig.suptitle(f"Truy vấn: '{query}'")
        safe_name = "".join(c if c.isalnum() else "_" for c in query)[:40]
        fig.savefig(f"{figures_dir}/{safe_name}.png", bbox_inches="tight")
        plt.show()
        plt.close(fig)

        answer = input_fn(f"Ảnh nào LIÊN QUAN đến '{query}'? (vd: A,C,E — Enter nếu không có): ")
        relevant = set(x.strip().upper() for x in answer.split(",") if x.strip())
        for label, pid in zip(labels, candidate_ids):
            judgments[(query, pid)] = 1 if label in relevant else 0

    return judgments


def compute_precision_at_5(results, judgments):
    rows = []
    for query, model_results in results.items():
        for model_name in ["clip", "fashionclip"]:
            top5_ids = [pid for pid, _ in model_results[model_name]]
            n_relevant = sum(judgments[(query, pid)] for pid in top5_ids)
            rows.append({"query": query, "model": model_name,
                         "precision_at_5": n_relevant / 5, "n_relevant": n_relevant})
    df = pd.DataFrame(rows)
    summary = df.groupby("model")["precision_at_5"].agg(["mean", "std", "count"])
    return df, summary


if __name__ == "__main__":
    import sys

    if "--self_test" in sys.argv:
        # Kiểm thử toàn bộ luồng: retrieve -> gộp candidate duy nhất -> vẽ
        # lưới -> thu thập judgment -> tính precision — bằng dữ liệu và ảnh
        # GIẢ, và input_fn TRẢ LỜI TỰ ĐỘNG thay vì chờ người gõ.
        import tempfile

        N_PRODUCTS = 30
        rng = np.random.RandomState(0)

        with tempfile.TemporaryDirectory() as tmp:
            fake_ids = np.array([f"P{i:03d}" for i in range(N_PRODUCTS)])
            fake_clip_img = rng.randn(N_PRODUCTS, 512).astype("float32")
            fake_fclip_img = rng.randn(N_PRODUCTS, 512).astype("float32")
            data = {"ids": fake_ids, "clip_img": fake_clip_img, "fclip_img": fake_fclip_img}

            images_dir = os.path.join(tmp, "images")
            os.makedirs(images_dir)
            for pid in fake_ids:
                Image.new("RGB", (32, 32)).save(os.path.join(images_dir, f"{pid}.jpg"))

            def fake_embed_clip(text, device="cpu"):
                return rng.randn(512).astype("float32")

            def fake_embed_fclip(text, device="cpu"):
                return rng.randn(512).astype("float32")

            fake_queries = [("test", "query one"), ("test", "query two")]
            results = retrieve_all(fake_queries, data, fake_embed_clip, fake_embed_fclip)

            assert set(results.keys()) == {"query one", "query two"}
            for q in results:
                assert len(results[q]["clip"]) == 5
                assert len(results[q]["fashionclip"]) == 5

            answers = iter(["A,B", ""])  # trả lời giả cho 2 truy vấn: query 1 có A,B liên quan; query 2 không có gì

            def fake_input(prompt):
                return next(answers)

            figures_dir = os.path.join(tmp, "figures")
            judgments = judge_blind(results, images_dir=images_dir,
                                     figures_dir=figures_dir, input_fn=fake_input)

            assert os.path.exists(os.path.join(figures_dir, "query_one.png")), "Không lưu được hình!"
            assert os.path.exists(os.path.join(figures_dir, "query_two.png"))

            df, summary = compute_precision_at_5(results, judgments)
            assert len(df) == 4  # 2 truy vấn x 2 model
            assert (df[df["query"] == "query two"]["n_relevant"] == 0).all(), \
                "query two trả lời rỗng nhưng vẫn tính ra có ảnh liên quan — sai logic!"

            print("[SELF-TEST PASSED] retrieve -> judge (mù, input giả) -> lưu hình -> tính precision đều đúng.")
            print("\nBảng kết quả (dữ liệu GIẢ, chỉ để minh họa định dạng output):")
            print(df)
            print("\nTổng hợp:")
            print(summary)
    else:
        assert len(QUERY_SET) >= 15, "Cần tối thiểu 15 truy vấn — hiện chỉ có " + str(len(QUERY_SET))
        data = load_embeddings()
        results = retrieve_all(QUERY_SET, data)
        judgments = judge_blind(results)
        df, summary = compute_precision_at_5(results, judgments)
        df.to_csv("./logs/backbone_comparison_results.csv", index=False)
        print("\n=== Kết quả chi tiết ===")
        print(df)
        print("\n=== Tổng hợp theo model ===")
        print(summary)
        print("\nĐã lưu: ./logs/backbone_comparison_results.csv")
        print(f"Đã lưu lưới ảnh từng truy vấn vào: {FIGURES_DIR}/")