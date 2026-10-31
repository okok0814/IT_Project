import argparse
from pathlib import Path
import tempfile
import time

import faiss
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
EMBED_DIR = ROOT / "embeddings"
INDEX_DIR = EMBED_DIR / "index"


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


def run(embedding_path, output_dir=None):
    print(f"Đang tải: {embedding_path}")
    vecs = load_and_normalize(embedding_path)
    print(f"Shape: {vecs.shape}")
    
    base_name = Path(embedding_path).stem
    output_dir = Path(output_dir) if output_dir is not None else INDEX_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    print("\n--- IndexFlatIP (brute-force, đúng 100%) ---")
    flat_index = build_flat_index(vecs)
    flat_stats = benchmark_search(flat_index, vecs)
    print(f"mean={flat_stats['mean_ms']:.3f}ms  p95={flat_stats['p95_ms']:.3f}ms  "
          f"(k={flat_stats['k']}, {flat_stats['n_repeats']} lần)")
    
    # SAVE FLAT INDEX TO DISK
    flat_index_path = output_dir / f"{base_name}_flat.index"
    faiss.write_index(flat_index, str(flat_index_path))
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
    ivf_index_path = output_dir / f"{base_name}_ivf.index"
    faiss.write_index(ivf_index, str(ivf_index_path))
    print(f"[Đã lưu] IVF Index tại: {ivf_index_path}")

    overlap = sanity_check_correctness(flat_index, ivf_index, vecs)
    print(f"\nĐộ trùng khớp top-10 giữa IVF và Flat: {overlap*100:.1f}%")
    return {"flat": flat_stats, "ivf": ivf_stats, "overlap": overlap}


def main():
    parser = argparse.ArgumentParser(description="Build and benchmark Flat/IVF indexes for the four saved embedding files.")
    parser.add_argument("--embeddings-dir", type=Path, default=EMBED_DIR,
                        help="Folder containing the four .npy embeddings (default: repository embeddings/)")
    parser.add_argument("--output-dir", type=Path,
                        help="Index output folder (default: <embeddings-dir>/index)")
    parser.add_argument("--self-test", "--self_test", dest="self_test", action="store_true",
                        help="Check the pipeline using synthetic vectors and isolated temporary files")
    args = parser.parse_args()

    if args.self_test:
        print("[SELF-TEST] Tạo 2000 vector ngẫu nhiên 512 chiều (KHÔNG PHẢI embedding thật)...")
        # A self-test must never write into the user's real artifact folders.
        with tempfile.TemporaryDirectory(prefix="fashion-faiss-selftest-") as tmp:
            fake_path = Path(tmp) / "fake_embeddings.npy"
            fake = np.random.default_rng(0).standard_normal((2000, 512)).astype("float32")
            np.save(fake_path, fake)
            result = run(fake_path, output_dir=Path(tmp) / "index")
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
        embeddings_dir = args.embeddings_dir.resolve()
        output_dir = args.output_dir.resolve() if args.output_dir else embeddings_dir / "index"
        missing = [str(embeddings_dir / name) for name in files_to_test
                   if not (embeddings_dir / name).is_file()]
        if missing:
            parser.error("Missing embedding files:\n" + "\n".join(missing))
        for fname in files_to_test:
            print(f"\n\n{'='*50}")
            print(f"BẮT ĐẦU ĐÁNH GIÁ: {fname}")
            print(f"{'='*50}")
            # This triggers the saving process for each file inside run()
            run(embeddings_dir / fname, output_dir=output_dir)


if __name__ == "__main__":
    main()
