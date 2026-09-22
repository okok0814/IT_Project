# API Docs — Đồ án CNTT Backend

**Base URL (dev):** `http://localhost:5000`
**CORS:** chỉ chấp nhận request từ `http://localhost:5137` (đổi qua biến môi trường `ALLOWED_ORIGIN` nếu frontend chạy ở port khác, ví dụ Vite mặc định 5173).

## Quy ước response — áp dụng cho MỌI endpoint

Mọi endpoint, kể cả khi lỗi, trả về đúng khuôn dạng này:

```json
{
  "success": true,
  "data": { ... },
  "error": null
}
```

Khi lỗi: `success: false`, `data: null`, `error` chứa thông điệp lỗi dạng chuỗi. Frontend chỉ cần kiểm tra `success` một lần, không cần đoán khuôn dạng lỗi khác nhau giữa các endpoint.

---

## `GET /health`

**Trạng thái:** Đã triển khai.
Kiểm tra server còn sống — dùng để frontend xác nhận backend đã chạy trước khi tích hợp các endpoint khác.

**Response 200:**
```json
{"success": true, "data": {"status": "ok"}, "error": null}
```

**Ví dụ:**
```bash
curl http://localhost:5000/health
```

---

## `POST /search/image`

**Trạng thái:** CHƯA triển khai (dự kiến Tuần 7 — hiện trả về 501 để frontend có endpoint thật để gọi thử ngay từ tuần này).

**Kế hoạch:** nhận 1 ảnh upload, encode bằng FashionCLIP, truy vấn FAISS index, trả về top-k sản phẩm gần nhất.

**Request (dự kiến):** `multipart/form-data`, field `image` chứa file ảnh.

**Response 200 (dự kiến):**
```json
{
  "success": true,
  "data": [
    {"product_id": "10180", "score": 0.87, "image_path": "images/10180.jpg"}
  ],
  "error": null
}
```


**Response hiện tại (chưa triển khai):**
```json
{"success": false, "data": null, "error": "Chưa triển khai — dự kiến Tuần 7."}
```
HTTP status: `501`

---

## `POST /search/text`

**Trạng thái:** CHƯA triển khai (dự kiến Tuần 7 — hiện trả về 501, cùng lý do như trên).

**Kế hoạch:** nhận câu truy vấn văn bản, encode bằng FashionCLIP, truy vấn CÙNG FAISS index ảnh.

**Request (dự kiến):** `application/json`, `{"query": "áo sơ mi trắng công sở"}`.

**Response:** cùng khuôn dạng như `/search/image`.

**Response hiện tại (chưa triển khai):**
```json
{"success": false, "data": null, "error": "Chưa triển khai — dự kiến Tuần 7."}
```
HTTP status: `501`
