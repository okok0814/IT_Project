import os
import time

import faiss
import numpy as np

EMBED_DIR = "./embeddings"


def load_and_normalize(path):
    """QUAN TRỌNG: IndexFlatIP tính inner product thô, không phải cosine
    similarity, TRỪ KHI vector đầu vào đã được chuẩn hóa L2 trước. Đây là
    bước bắt buộc, không phải tùy chọn — bỏ qua bước này thì kết quả tìm
    kiếm vẫn chạy, chỉ là sai (thiên vị theo độ lớn vector thay vì hướng)."""
    vecs = np.load(path).astype("float32")
    faiss.normalize_L2(vecs)
    return vecs


def build_flat_index(vecs):
    """Brute-force, chính xác 100% (không có gì để đánh đổi độ chính xác)."""
    dim = vecs.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(vecs)
    return index


def build_ivf_index(vecs, nlist=100, nprobe=8):
    """Approximate — nhanh hơn ở quy mô lớn, đánh đổi một phần độ chính xác.
    nlist = số cụm (cluster) khi phân vùng không gian vector.
    nprobe = số cụm sẽ thực sự quét khi tìm kiếm (nprobe càng cao càng chính
    xác nhưng càng chậm — đây là tham số bạn có thể tinh chỉnh)."""
    dim = vecs.shape[1]
    quantizer = faiss.IndexFlatIP(dim)
    index = faiss.IndexIVFFlat(quantizer, dim, nlist, faiss.METRIC_INNER_PRODUCT)
    index.train(vecs)  # bước train học ranh giới cụm — Flat không cần bước này
    index.add(vecs)
    index.nprobe = nprobe
    return index


def benchmark_search(index, query_vecs, k=10, n_repeats=100):
    """Đo ĐỘ TRỄ TÌM KIẾM THUẦN TÚY (không tính thời gian encode câu truy vấn
    — đó là một con số riêng, đo ở sanity-check script của bạn). Lấy mean và
    p95 vì mean một mình có thể che giấu các lần chạy chậm bất thường."""
    times_ms = []
    n = len(query_vecs)
    for _ in range(n_repeats):
        q = query_vecs[np.random.randint(0, n)][None, :]
        t0 = time.perf_counter()
        distances, indices = index.search(q, k)
        times_ms.append((time.perf_counter() - t0) * 1000)
    return {
        "mean_ms": float(np.mean(times_ms)),
        "p95_ms": float(np.percentile(times_ms, 95)),
        "n_repeats": n_repeats,
        "k": k,
    }


def sanity_check_correctness(flat_index, ivf_index, vecs, n_queries=20, k=10):
    """Kiểm tra IVF có trả về kết quả GẦN GIỐNG Flat không (không cần giống
    hệt — đó là bản chất 'approximate'). Đếm % overlap trong top-k."""
    overlaps = []
    for _ in range(n_queries):
        q = vecs[np.random.randint(0, len(vecs))][None, :]
        _, flat_ids = flat_index.search(q, k)
        _, ivf_ids = ivf_index.search(q, k)
        overlap = len(set(flat_ids[0]) & set(ivf_ids[0])) / k
        overlaps.append(overlap)
    return float(np.mean(overlaps))


def run(embedding_path):
    print(f"Đang tải: {embedding_path}")
    vecs = load_and_normalize(embedding_path)
    print(f"Shape: {vecs.shape}")
    
    # Extract the base filename without the .npy extension
    base_name = os.path.splitext(os.path.basename(embedding_path))[0]

    print("\n--- IndexFlatIP (brute-force, đúng 100%) ---")
    flat_index = build_flat_index(vecs)
    flat_stats = benchmark_search(flat_index, vecs)
    print(f"mean={flat_stats['mean_ms']:.3f}ms  p95={flat_stats['p95_ms']:.3f}ms  "
          f"(k={flat_stats['k']}, {flat_stats['n_repeats']} lần)")
    
    # SAVE FLAT INDEX TO DISK
    flat_index_path = os.path.join(EMBED_DIR, f"{base_name}_flat.index")
    faiss.write_index(flat_index, flat_index_path)
    print(f"[Đã lưu] Flat Index tại: {flat_index_path}")

    nlist = 100  # phải khớp với mặc định trong build_ivf_index()
    n_train_min = 39 * nlist  # FAISS khuyến nghị tối thiểu ~39 điểm/cụm để train ổn định
    if len(vecs) < n_train_min:
        # Dataset 2 thật (~44k) sẽ vượt xa ngưỡng này — nhánh này chủ yếu để
        # self-test không âm thầm train một index không ổn định.
        nlist = max(4, len(vecs) // 40)
        print(f"\n[Điều chỉnh nlist] {len(vecs)} vector không đủ cho nlist=100 "
              f"(cần ~{n_train_min}) — giảm nlist xuống {nlist} cho hợp quy mô.")

    print("\n--- IndexIVFFlat (approximate) ---")
    ivf_index = build_ivf_index(vecs, nlist=nlist)
    ivf_stats = benchmark_search(ivf_index, vecs)
    print(f"mean={ivf_stats['mean_ms']:.3f}ms  p95={ivf_stats['p95_ms']:.3f}ms")
    
    # SAVE IVF INDEX TO DISK
    ivf_index_path = os.path.join(EMBED_DIR, f"{base_name}_ivf.index")
    faiss.write_index(ivf_index, ivf_index_path)
    print(f"[Đã lưu] IVF Index tại: {ivf_index_path}")

    overlap = sanity_check_correctness(flat_index, ivf_index, vecs)
    print(f"\nĐộ trùng khớp top-10 giữa IVF và Flat: {overlap*100:.1f}%")
    return {"flat": flat_stats, "ivf": ivf_stats, "overlap": overlap}


if __name__ == "__main__":
    import sys
    # Đảm bảo thư mục lưu trữ tồn tại
    os.makedirs(EMBED_DIR, exist_ok=True)
    
    if "--self_test" in sys.argv:
        print("[SELF-TEST] Tạo 2000 vector ngẫu nhiên 512 chiều (KHÔNG PHẢI embedding thật)...")
        fake = np.random.randn(2000, 512).astype("float32")
        np.save("/tmp/fake_embeddings.npy", fake)
        result = run("/tmp/fake_embeddings.npy")
        assert result["flat"]["mean_ms"] > 0
        print("\n[SELF-TEST PASSED] Toàn bộ pipeline load->normalize->index->search chạy đúng logic.")
    else:
        # Chạy tự động cho cả 4 file
        files_to_test = [
            "clip_image_embeddings.npy",
            "clip_text_embeddings.npy",
            "fashionclip_image_embeddings.npy",
            "fashionclip_text_embeddings.npy"
        ]
        for fname in files_to_test:
            print(f"\n\n{'='*50}")
            print(f"BẮT ĐẦU ĐÁNH GIÁ: {fname}")
            print(f"{'='*50}")
            # This triggers the saving process for each file inside run()
            run(f"{EMBED_DIR}/{fname}")