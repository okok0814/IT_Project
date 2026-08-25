import argparse
import os

import pandas as pd
from PIL import Image

EXPECTED_COLUMNS = [
    "id", "gender", "masterCategory", "subCategory", "articleType",
    "baseColour", "season", "year", "usage", "productDisplayName",
]

def load_and_validate(data_dir: str):
    styles_path = os.path.join(data_dir, "styles.csv")
    images_dir = os.path.join(data_dir, "images")

    df = pd.read_csv(styles_path, on_bad_lines="skip")
    n_rows_loaded = len(df)

    missing_cols = [c for c in EXPECTED_COLUMNS if c not in df.columns]

    df["id"] = df["id"].astype(str)
    image_ids_on_disk = {
        os.path.splitext(f)[0] for f in os.listdir(images_dir)
        if f.lower().endswith((".jpg", ".jpeg", ".png"))
    }

    ids_in_csv = set(df["id"])
    missing_images = ids_in_csv - image_ids_on_disk   # in CSV but no image file
    orphan_images = image_ids_on_disk - ids_in_csv    # image file but no CSV row

    corrupt_images = []
    checked = 0
    for img_id in list(ids_in_csv & image_ids_on_disk)[:2000]:  # cap for speed; raise/remove cap for full run
        path_jpg = os.path.join(images_dir, f"{img_id}.jpg")
        if not os.path.exists(path_jpg):
            continue
        checked += 1
        try:
            with Image.open(path_jpg) as im:
                im.verify()
        except Exception:
            corrupt_images.append(img_id)

    report = {
        "rows_loaded_from_csv": n_rows_loaded,
        "missing_expected_columns": missing_cols,
        "unique_ids_in_csv": len(ids_in_csv),
        "image_files_on_disk": len(image_ids_on_disk),
        "ids_in_csv_missing_image_file": len(missing_images),
        "image_files_with_no_csv_row": len(orphan_images),
        "images_checked_for_corruption": checked,
        "corrupt_images_found": len(corrupt_images),
        "corrupt_image_ids_sample": corrupt_images[:10],
        "category_distribution": df["masterCategory"].value_counts().to_dict() if "masterCategory" in df.columns else None,
        "gender_distribution": df["gender"].value_counts().to_dict() if "gender" in df.columns else None,
    }
    return report, df


def _make_synthetic_test_fixture(tmp_dir: str, n=12, n_missing=2, n_orphan=1, n_corrupt=1):
    """Chỉ dùng để TỰ KIỂM TRA logic script này — không phải dữ liệu thật."""
    os.makedirs(os.path.join(tmp_dir, "images"), exist_ok=True)
    rows = []
    for i in range(n):
        rows.append({
            "id": 1000 + i, "gender": "Men" if i % 2 == 0 else "Women",
            "masterCategory": "Apparel", "subCategory": "Topwear",
            "articleType": "Shirts", "baseColour": "White", "season": "Summer",
            "year": 2024, "usage": "Casual", "productDisplayName": f"Test Shirt {i}",
        })
    pd.DataFrame(rows).to_csv(os.path.join(tmp_dir, "styles.csv"), index=False)

    for i in range(n):
        if i < n_missing:
            continue  # simulate missing image file for this id
        img = Image.new("RGB", (32, 32), color=(200, 200, 200))
        img.save(os.path.join(tmp_dir, "images", f"{1000+i}.jpg"))

    for i in range(n_orphan):
        Image.new("RGB", (32, 32)).save(os.path.join(tmp_dir, "images", f"{9000+i}.jpg"))

    for i in range(n_corrupt):
        with open(os.path.join(tmp_dir, "images", f"{1000+n_missing+i}.jpg"), "wb") as f:
            f.write(b"not a real jpeg")  # corrupt on purpose


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data_dir", default=None, help="Thư mục chứa styles.csv + images/ thật")
    ap.add_argument("--self_test", action="store_true", help="Chạy kiểm thử với dữ liệu giả lập")
    args = ap.parse_args()

    if args.self_test or not args.data_dir:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            print("[SELF-TEST] Tạo dữ liệu giả lập (12 sản phẩm: 2 thiếu ảnh, 1 orphan, 1 hỏng)...")
            _make_synthetic_test_fixture(tmp)
            report, _ = load_and_validate(tmp)
            print("[SELF-TEST] Kết quả (kỳ vọng: missing=2, orphan=1, corrupt=1):")
            for k, v in report.items():
                print(f"  {k}: {v}")
    else:
        report, df = load_and_validate(args.data_dir)
        print("=== Dataset 2 — báo cáo tổ chức & kiểm tra toàn vẹn (DỮ LIỆU THẬT) ===")
        for k, v in report.items():
            print(f"  {k}: {v}")
