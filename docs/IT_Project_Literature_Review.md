# Ghi chú Khảo sát Tài liệu & Phân tích Kiến trúc Baseline
**Dự án:** Hệ thống gợi ý sản phẩm thời trang bằng hình ảnh và văn bản (IT Project)
**Mục tiêu tuần 1:** Đọc kỹ 2 bài báo tổng quan (Deldjoo et al. 2023, Ding et al. 2023) và bài báo FashionCLIP (Chia et al. 2022); đọc lướt 6 bài báo còn lại (chỉ abstract + sơ đồ phương pháp, đọc sâu dành cho Khóa luận).

## 1. Phân tích các mô hình Gợi ý Thời trang hiện đại (Deldjoo et al. 2023 & Ding et al. 2023)
Thông qua khảo sát 2 bài báo tổng quan, hệ thống dự kiến sẽ tập trung vào tác vụ **Complementary/Similarity Recommendation** (Gợi ý tương đồng/bổ sung). 
*   **Vấn đề Dữ liệu:** Các mô hình dựa trên tương tác truyền thống (Collaborative Filtering) gặp lỗi "cold-start" (sản phẩm mới không có lượt mua).
*   **Quyết định Kỹ thuật:** Đồ án sẽ đi theo hướng **Content-based Multimodal Retrieval**. Bắt buộc phải chuyển hóa cả ảnh (Visual) và text (Metadata/Description) thành các vector số học (embeddings) để tính toán.

## 2. Phân tích Baseline Model: FashionCLIP (Chia et al., 2022)
Đây là kiến trúc trọng tâm sẽ được sử dụng làm Baseline cho hệ thống trong các tuần tới (sử dụng thư viện của `patrickjohncyh/fashion-clip`).
*   **Cơ chế hoạt động (Dual-Encoder):** 
    *   Mô hình tách biệt hoàn toàn Image Encoder (ViT/ResNet) và Text Encoder (Transformer).
    *   Đầu ra của 2 nhánh được phóng chiếu (project) vào cùng một không gian vector (Shared Latent Space).
*   **Ưu điểm cho hệ thống (Tại sao chọn mô hình này):**
    *   Do 2 nhánh độc lập (Late Fusion), ta có thể tính trước (pre-compute) toàn bộ vector ảnh của kho hàng (Offline Indexing).
    *   Khi người dùng nhập câu truy vấn (ví dụ: "áo sơ mi trắng"), chỉ cần chạy qua Text Encoder rồi quét Cosine Similarity với kho ảnh. Tốc độ sẽ cực kỳ nhanh, phù hợp làm Web Demo (so với các mô hình Early Fusion).

## 3. Khảo sát cấu trúc các hệ thống Vision-Language (VLP, ViL, SAP, FAME-ViL, ERN, UniFashion)
Đã đọc lướt abstract và trích xuất sơ đồ phương pháp của 6 mô hình này. 
*   **Phát hiện kỹ thuật:** Đa số các mô hình SOTA (State-of-the-art) này đều dùng cơ chế **Cross-Attention** (Early/Mid Fusion) – tức là cho ảnh và chữ tương tác với nhau ngay ở các lớp mạng bên dưới để tìm ra "sự chú ý" chi tiết (ví dụ: chữ "cổ áo" map với pixel của cổ áo). 
*   **Đánh giá rủi ro cho IT Project:** Các mô hình này cho độ chính xác rất cao trên các tác vụ khó như *Composed Image Retrieval* (tìm ảnh = ảnh gốc + text phản hồi). Tuy nhiên, chi phí tính toán O(N) theo thời gian thực (Online Query) là quá lớn, khó đáp ứng cho một Web Demo truy xuất hàng ngàn sản phẩm thông thường.
*   **Quyết định:** IT Project sẽ giữ nguyên kiến trúc Dual-Encoder (CLIP/FashionCLIP) kết hợp với FAISS để ưu tiên tốc độ tìm kiếm. Phân tích sâu hơn về các cơ chế chú ý chéo (Cross-Attention) này sẽ được dồn sang viết lý thuyết định lượng cho Khóa luận Tốt nghiệp.