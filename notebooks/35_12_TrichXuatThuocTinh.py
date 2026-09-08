"""
    python 35_12_523H0026_TrichXuatThuocTinh.py 
    --styles_csv "C:/Users/Nguyen Ho Vinh  Hien/Downloads/FashionProductImagesDataset/fashion-dataset/styles.csv" 
    --images_dir "C:/Users/Nguyen Ho Vinh  Hien/Downloads/FashionProductImagesDataset/fashion-dataset/images" 
    --dieu_ids_csv "C:/Users/Nguyen Ho Vinh  Hien/Downloads/DUAN/product_ids.npy" --out_prefix metadata

Schema đầu ra:
    product_id, gender, category, color, usage, master_category, sub_category
"""

import argparse
import os
import sqlite3

import numpy as np
import pandas as pd


def load_dieu_ids(dieu_ids_path: str) -> set:
    """
    Trả về một set các id đã được ép về kiểu số nguyên, để so sánh
    được với product_id bên bảng metadata.
    """
    ext = os.path.splitext(dieu_ids_path)[1].lower()

    if ext == ".npy":
        raw_ids = np.load(dieu_ids_path, allow_pickle=True)
    elif ext == ".csv":
        raw_ids = pd.read_csv(dieu_ids_path)["id"].to_numpy()
    else:
        raise ValueError(
            f"KHÔNG HỖ TRỢ ĐỊNH DẠNG FILE ID CỦA DIỆU: {ext}."
            " CHỈ HỖ TRỢ .csv HOẶC .npy"
        )

    # Ép về số nguyên dù id gốc là chuỗi hay số
    return set(int(x) for x in raw_ids)



# Từ đIển đồng nghĩa màu sắc dùng để gộp các biến thể cùng nghĩa về 1 giá trị
COLOR_SYNONYMS = {
    "off-white": "Off White",
    "off  white": "Off White",
    "navy": "Navy Blue",
    "grey melange": "Grey Melange",
}

# Từ đIển đồng nghĩa mục đích sử dụng
USAGE_SYNONYMS = {
    "smart casual": "Smart Casual",
    "formal": "Formal",
}


def normalize_text_value(value, synonym_map: dict) -> str:
    """
    Chuẩn hóa một giá trị văn bản để tránh các biến thể khác nhau của
    cùng một ý nghĩa như là khoảng trắng thừa, viết hoa/thường lẫn lộn,
    hoặc các cách viết khác nhau của cùng một màu/mục đích sử dụng
    """
    if not isinstance(value, str):
        return "Unknown"

    collapsed = " ".join(value.strip().split())
    if not collapsed:
        return "Unknown"

    lowered = collapsed.lower()
    if lowered in synonym_map:
        return synonym_map[lowered]

    return collapsed.title()


def load_styles(styles_csv_path: str) -> pd.DataFrame:
    """Đọc styles.csv sau đó bỏ qua các dòng bị lỗi định dạng như thiếu / thừa cột"""
    df = pd.read_csv(
        styles_csv_path,
        on_bad_lines="skip",   # Đoạn này bỏ qua dòng lỗi thay vì crash
        engine="python",
    )
    return df


def select_and_clean(df: pd.DataFrame) -> pd.DataFrame:
    """Đoạn này chỉ giữ id và 4 thuộc tính và làm sạch dữ liệu"""

    needed_cols = [
        "id",
        "gender",
        "masterCategory",
        "subCategory",
        "articleType",
        "baseColour",
        "usage",
    ]

    missing = [c for c in needed_cols if c not in df.columns]
    if missing:
        raise ValueError(
            f"KHÔNG TÌM THẤY CÁC CỘT TRONG styles.csv: {missing}. "
            "CHECK LẠI CÁC CỘT THỰC TẾ TRONG styles.csv"
        )

    clean = df[needed_cols].copy()

    # Chuẩn hóa kiểu dữ liệu, id phải là số nguyên
    clean = clean.dropna(subset=["id"])
    clean["id"] = clean["id"].astype(int)

    # Nếu id trùng lập thì chỉ giữ lại id đầu tiên
    clean = clean.drop_duplicates(subset=["id"], keep="first")

    # Chèn unknown cho các ô bị trống ở các cột text
    text_cols = ["gender", "masterCategory", "subCategory", "articleType",
                 "baseColour", "usage"]
    for col in text_cols:
        clean[col] = clean[col].fillna("Unknown")

    # Chuẩn hóa từng cột bằng từ điển đồng nghĩa tương ứng (nếu có), các
    # cột không có từ điển riêng sẽ chỉ được chuẩn hóa khoảng trắng và
    # viết hoa chữ cái đầu như bình thường
    clean["gender"] = clean["gender"].apply(normalize_text_value, args=({},))
    clean["masterCategory"] = clean["masterCategory"].apply(normalize_text_value, args=({},))
    clean["subCategory"] = clean["subCategory"].apply(normalize_text_value, args=({},))
    clean["articleType"] = clean["articleType"].apply(normalize_text_value, args=({},))
    clean["baseColour"] = clean["baseColour"].apply(normalize_text_value, args=(COLOR_SYNONYMS,))
    clean["usage"] = clean["usage"].apply(normalize_text_value, args=(USAGE_SYNONYMS,))

    # ĐổI tên cột theo đúng schema chuẩn của nhóm
    clean = clean.rename(columns={
        "id": "product_id",
        "articleType": "category",
        "baseColour": "color",
        "masterCategory": "master_category",
        "subCategory": "sub_category",
    })

    # Sắp xếp lạI thứ tự cột cho dễ đọc, 5 cột chuẩn đứng trước
    clean = clean[["product_id", "gender", "category", "color", "usage",
                    "master_category", "sub_category"]]

    # In số lượng giá trị duy nhất của color và usage sau chuẩn hóa
    # để hiển dễ kiểm tra xem còn biến thể nào cần gộp thêm vào
    # color_synonyms / usage_synonyms ở trên không
    print(f"    SỐ GIÁ TRỊ color DUY NHẤT SAU CHUẨN HÓA: {clean['color'].nunique()}")
    print(f"    SỐ GIÁ TRỊ usage DUY NHẤT SAU CHUẨN HÓA: {clean['usage'].nunique()}")

    return clean


def filter_by_existing_images(df: pd.DataFrame, images_dir: str) -> pd.DataFrame:
    """Chỉ giữ lai các ìd có file tương ứng trong thư mục images"""
    if not images_dir or not os.path.isdir(images_dir):
        print("CẢNH BÁO KHÔNG TÌM THẤY THƯ MỤC ẢNH BỎ QUA CÁC BƯỚC ĐỐI CHIẾU ẢNH")
        return df

    existing_ids = set()
    for filename in os.listdir(images_dir):
        name, _ext = os.path.splitext(filename)
        if name.isdigit():
            existing_ids.add(int(name))

    before = len(df)
    df = df[df["product_id"].isin(existing_ids)]
    after = len(df)
    print(f"    LỌC THEO ẢNH THỰC TẾ {before} THÀNH {after} DÒNG"
          f" | BỎ {before - after} DÒNG KHÔNG CÓ ẢNH TƯƠNG ỨNG")
    return df


def check_alignment_with_dieu(df: pd.DataFrame, dieu_ids_path: str) -> pd.DataFrame:
    """
    Hàm này dùng để đối chiếu tập product_id của bảng metadata với danh sách id trong
    file embedding của Diệu
    Nếu hai bên khớp hoàn toàn thì giữ nguyên bảng. Nhưng nếu lệch nhau thì
    tự động lọc lại, chỉ giữ phần giao nhau, để đảm bảo metadata và
    embedding luôn đi cùng một tập sản phẩm với nhau.
    """
    if not dieu_ids_path or not os.path.isfile(dieu_ids_path):
        print("    CHƯA CÓ FILE ID CỦA DIỆU NÊN BỎ QUA BƯỚC ĐỐI CHIẾU NÀY,"
              " NHỚ CHẠY LẠI VỚI --dieu_ids_csv KHI DIỆU ĐÃ CÓ FILE")
        return df

    dieu_ids = load_dieu_ids(dieu_ids_path)
    hien_ids = set(df["product_id"].astype(int))

    only_in_hien = hien_ids - dieu_ids
    only_in_dieu = dieu_ids - hien_ids

    if not only_in_hien and not only_in_dieu:
        print(f"    ĐỐI CHIẾU ID: KHỚP HOÀN TOÀN VỚI {len(hien_ids)} SẢN PHẨM CỦA DIỆU")
        return df

    print(f"    ĐỐI CHIẾU ID: LỆCH NHAU | CHỈ CÓ Ở METADATA: {len(only_in_hien)}"
          f" | CHỈ CÓ Ở EMBEDDING CỦA DIỆU: {len(only_in_dieu)}")
    print("    TỰ ĐỘNG LỌC LẠI THEO PHẦN GIAO NHAU ĐỂ ĐẢM BẢO METADATA VÀ EMBEDDING KHỚP 1-1")

    common_ids = hien_ids & dieu_ids
    df = df[df["product_id"].isin(common_ids)]
    print(f"    SAU KHI LỌC GIAO NHAU CÒN LẠI {len(df)} SẢN PHẨM KHỚP CẢ HAI BÊN")
    return df


def save_outputs(df: pd.DataFrame, out_prefix: str) -> None:
    csv_path = f"{out_prefix}.csv"
    db_path = f"{out_prefix}.db"

    df.to_csv(csv_path, index=False)
    print(f"    ĐÃ LƯU FILE CSV {csv_path}")

    conn = sqlite3.connect(db_path)
    df.to_sql("products", conn, if_exists="replace", index=False)
    # Tạo index trên các cột hay được dùng để lọc giúp truy vấn nhanh hơn
    conn.execute("CREATE INDEX IF NOT EXISTS idx_gender ON products(gender);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_category ON products(category);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_color ON products(color);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_usage ON products(usage);")
    conn.commit()
    conn.close()
    print(f"    ĐÃ LƯU FILE SQL {db_path} BẢNG products")


def run_sanity_check(out_prefix: str) -> None:
    """Đoạn này nhập thử 1 câu truy vấn để kiểm tra bảng"""
    db_path = f"{out_prefix}.db"
    conn = sqlite3.connect(db_path)
    query = """
        SELECT COUNT(*) FROM products
        WHERE gender = 'Men' AND color = 'Black'
    """
    count = conn.execute(query).fetchone()[0]
    print(f"    KIỂM TRA: SỐ SẢN PHẨM gender=Men, mau=Black: {count}")
    conn.close()


def main():
    parser = argparse.ArgumentParser(description="TRÍCH XUẤT METADATA FASHION PRODUCT IMAGES DATASET")
    parser.add_argument("--styles_csv", required=True,
                         help="ĐƯỜNG DẪN TỚI FILE styles.csv")
    parser.add_argument("--images_dir", default=None,
                         help="ĐƯỜNG DẪN TỚI THƯ MỤC ẢNH ĐỂ ĐỐI CHIẾU ID")
    parser.add_argument("--out_prefix", default="metadata",
                         help="TÊN FILE ĐẦU RA")
    parser.add_argument("--dieu_ids_csv", default=None,
                         help="ĐƯỜNG DẪN FILE DANH SÁCH ID CỦA DIỆU ĐỂ ĐỐI CHIẾU"
                              " KHỚP 1-1 VỚI EMBEDDING, HỖ TRỢ CẢ FILE .csv (CỘT 'id')"
                              " LẪN FILE .npy (MẢNG ID)")
    args = parser.parse_args()

    print("\nBƯỚC 1 ĐỌC FILE styles.csv")
    raw_df = load_styles(args.styles_csv)
    print(f"    ĐỌC ĐƯỢC {len(raw_df)} DÒNG")

    print("\nBƯỚC 2 CHỌN VÀ LÀM SẠCH 4 THUỘC TÍNH")
    clean_df = select_and_clean(raw_df)
    print(f"    CÒN LẠI {len(clean_df)} DÒNG SAU KHI ĐƯỢC LÀM SẠCH")

    print("\nBƯỚC 3 ĐỐI CHIẾU VỚI ẢNH THỰC TẾ (NẾU CÓ)")
    final_df = filter_by_existing_images(clean_df, args.images_dir)

    print("\nBƯỚC BỔ SUNG ĐỐI CHIẾU ID VỚI EMBEDDING CỦA DIỆU (NẾU CÓ FILE)")
    final_df = check_alignment_with_dieu(final_df, args.dieu_ids_csv)

    print("\nBƯỚC 4 LƯU KẾT QUẢ")
    save_outputs(final_df, args.out_prefix)

    print("\nBƯỚC 5 KIỂM TRA THỬ")
    run_sanity_check(args.out_prefix)

    print("\nHOÀN TẤT")


if __name__ == "__main__":
    main()