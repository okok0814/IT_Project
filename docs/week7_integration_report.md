# BÁO CÁO TUẦN 7 — BẢN TÍCH HỢP FRONTEND VÀ BACKEND

**Đề tài:** Gợi ý sản phẩm thời trang dựa trên hình ảnh và mô tả văn bản.

**Hạng mục báo cáo:** Hoàn thiện endpoint `/search/image` và kiểm thử luồng tìm kiếm bằng ảnh upload.

**Thời điểm thực nghiệm:** Xem dấu thời gian UTC trong [provenance.json](../notebooks/logs/20260929-111025Z-week7/provenance.json). Báo cáo sử dụng riêng lượt chạy `20260929-111025Z-week7`, không ghép thời gian đo của các lượt trước.

**Repository của nhóm:** https://github.com/okok0814/IT_Project. Các đường dẫn dưới đây là đường dẫn tương đối trong repository. Bản tích hợp nằm trên nhánh local `integration/week7-image-search`; chưa push lên GitHub. Tại thời điểm đo, mã nguồn đang được xử lý merge, nên hash từng file trong provenance xác định bản được thử. Commit nền trong provenance là checkpoint trước merge, không phải commit công bố bản tích hợp.

## 1. Mục tiêu và phạm vi thực hiện

Mục tiêu của hạng mục là nhận ảnh từ người dùng, kiểm tra tính hợp lệ, trích xuất embedding bằng FashionCLIP và truy vấn chỉ mục FAISS để trả về sản phẩm tương tự. Ngoài trường hợp thành công, hệ thống cần trả lỗi rõ ràng khi file quá lớn, định dạng không được hỗ trợ hoặc nội dung ảnh bị hỏng. Tiêu chí của kế hoạch là kiểm thử với ít nhất 15 ảnh thực tế; script kiểm thử cũng kiểm tra điều kiện tối thiểu này trước khi chạy. [Code/Script: scripts/verify_image_search.py#L25](../scripts/verify_image_search.py#L25).

Phạm vi báo cáo là tìm kiếm tương đồng bằng ảnh và kiểm thử chức năng. Báo cáo không kết luận về chất lượng gợi ý cá nhân hóa, khả năng phối đồ hoặc kết quả fine-tuning của khóa luận. Giao diện tìm kiếm văn bản và bộ lọc chưa được tích hợp vào luồng này.

## 2. Nội dung đã hiện thực

### Phân công và cách tích hợp

Frontend lấy implementation của thành viên phụ trách UI làm nền, gồm trang upload,
trang kết quả, product card, các panel loading/lỗi, API helper và chỉnh sửa trang chủ.
Các thay đổi này đến từ commit `0da4457` và `97d2dbe` của nhánh `origin/main`.
Backend giữ phiên bản đã kiểm thử upload và FAISS; phần tích hợp bổ sung kiểm tra
file ở client, hủy request, kiểm tra response và tương thích cấu hình. Không thay
implementation frontend của thành viên bằng prototype cũ.

UI gửi `top_k=8`; backend vẫn mặc định `top_k=10` khi không có tham số. Đây là
lựa chọn trình bày khác nhau, không phải lỗi contract. [Code UI](../src/pages/ImageSearchPage.jsx);
[API helper](../src/api/fashionApi.js); [Code backend](../src/backend/app.py).

Các biến `FASHION_IMAGES_DIR`, `FASHION_INDEX_PATH`, `MODEL_HF_NAME` được hỗ trợ
như alias; `IMAGE_DIR`, `INDEX_PATH`, `MODEL_PATH` có ưu tiên cao hơn. Lệnh
`npm run backend` đã chuyển sang chạy module để import đúng package.
[Code](../src/backend/app.py); [Test alias/ưu tiên](../tests/test_image_search.py);
[package.json](../package.json).


### 2.1. Endpoint và luồng truy xuất

Endpoint nhận form chứa file `image` và tham số `top_k`, kiểm tra file trước khi gọi bộ mã hóa. Ảnh hợp lệ được giải mã, xử lý hướng xoay EXIF, chuyển về RGB và đưa vào FashionCLIP. Vector truy vấn được chuẩn hóa rồi tìm kiếm trong chỉ mục FAISS. Kết quả trả về gồm mã sản phẩm, đường dẫn ảnh và điểm tương đồng; frontend sử dụng dữ liệu này để dựng lưới sản phẩm. [Code: src/backend/app.py#L59](../src/backend/app.py#L59); [Code: src/backend/search.py#L38](../src/backend/search.py#L38); [Code: src/pages/ImageSearchPage.jsx](../src/pages/ImageSearchPage.jsx); [Code: src/pages/ResultsPage.jsx](../src/pages/ResultsPage.jsx).

Model được dùng là `patrickjohncyh/fashion-clip`. Bộ kiểm thử ghi nhận chỉ mục đang phục vụ **44.419 vector**. Đây là số phần tử của chỉ mục nạp trong lượt chạy, không phải số lượng ảnh truy vấn. [Code đo: scripts/verify_image_search.py](../scripts/verify_image_search.py); [Kết quả: trường index_vectors trong image-search.json](../notebooks/logs/20260929-111025Z-week7/image-search.json).

Model và chỉ mục được nạp khi có truy vấn hợp lệ đầu tiên, sau đó được tái sử dụng trong tiến trình. Bộ phục vụ chỉ dùng checkpoint đã có trên máy. Các file ảnh trả về được đọc từ thư mục catalog được cấu hình bằng `IMAGE_DIR`. [Code: src/backend/app.py](../src/backend/app.py); [Code: src/backend/search.py#L9](../src/backend/search.py#L9).

### 2.2. Xử lý trường hợp biên

Các ngưỡng dưới đây là **giá trị cấu hình**, không phải kết quả benchmark.

| Trường hợp | Hành vi đã cài đặt | Mã nguồn kiểm chứng |
| --- | --- | --- |
| File lớn hơn 10 MiB hoặc ảnh lớn hơn 25.000.000 pixel | Từ chối trước inference; trả HTTP 413 | [app.py#L16](../src/backend/app.py#L16), [test_image_search.py#L85](../tests/test_image_search.py#L85), [test_image_search.py#L104](../tests/test_image_search.py#L104) |
| File ngoài JPG/JPEG, PNG, WEBP; ảnh động; MIME hoặc nội dung không khớp phần mở rộng | Trả HTTP 415 | [app.py#L59](../src/backend/app.py#L59), [test_image_search.py](../tests/test_image_search.py) |
| Thiếu file, file rỗng, nhiều file, ảnh hỏng hoặc bị cắt cụt | Trả HTTP 400 và thông báo lỗi | [app.py#L59](../src/backend/app.py#L59), [test_image_search.py#L85](../tests/test_image_search.py#L85) |
| top_k ngoài khoảng 1–50 hoặc không phải số nguyên | Trả HTTP 400; mặc định top_k là 10 | [app.py#L59](../src/backend/app.py#L59), [test_image_search.py](../tests/test_image_search.py) |
| Ảnh có EXIF, grayscale, CMYK hoặc vùng trong suốt | Xử lý EXIF, chuyển RGB, ghép alpha trên nền trắng | [app.py#L94](../src/backend/app.py#L94), [test_image_search.py#L117](../tests/test_image_search.py#L117) |
| Thiếu tài nguyên phục vụ hoặc lỗi inference | Trả HTTP 503 hoặc 500; ghi chi tiết vào log server | [app.py](../src/backend/app.py), [test_image_search.py](../tests/test_image_search.py) |

## 3. Thiết kế kiểm thử và cách lưu bằng chứng

### 3.1. Kiểm thử validation bằng bộ mã hóa giả lập

Test tự động sử dụng `RecordingSearch` thay cho model để kiểm tra mã phản hồi, dữ liệu đầu vào sau tiền xử lý và việc từ chối file lỗi trước inference. Việc test này thành công không chứng minh chất lượng embedding. [Code: tests/test_image_search.py#L11](../tests/test_image_search.py#L11).

Kết quả pytest được ghi trực tiếp trong lúc chạy vào [pytest.txt](../notebooks/logs/20260929-111025Z-week7/pytest.txt), đồng thời xuất [pytest.xml](../notebooks/logs/20260929-111025Z-week7/pytest.xml) để truy xuất từng test. [Code lưu log: scripts/collect_week7_evidence.py](../scripts/collect_week7_evidence.py).

### 3.2. Kiểm thử HTTP bằng ảnh và model thật

Script chọn ảnh trong `data/d1/sample_images`, kiểm tra tính phân biệt bằng SHA-256, gửi multipart qua HTTP tới server tạm và chạy FashionCLIP thật trên chỉ mục đầy đủ. Với mỗi truy vấn, script kiểm tra envelope phản hồi, số lượng kết quả, ID không trùng, điểm hữu hạn theo thứ tự giảm dần và khả năng tải các ảnh kết quả. Ảnh chuyển sang PNG/WEBP là biến thể của ảnh đã có, không được tính thêm vào số ảnh thực tế riêng biệt. [Code: scripts/verify_image_search.py#L25](../scripts/verify_image_search.py#L25); [Code điều kiện đạt: scripts/verify_image_search.py#L58](../scripts/verify_image_search.py#L58).

Mỗi file truy vấn có SHA-256 và danh sách kết quả trong [image-search.json](../notebooks/logs/20260929-111025Z-week7/image-search.json). Đầu ra console và mã thoát của lệnh được lưu vào [image-search.txt](../notebooks/logs/20260929-111025Z-week7/image-search.txt). Script thu thập còn lưu phiên bản Python, hệ điều hành, các gói đã cài và hash của mã nguồn/chỉ mục để nhận diện chính xác tài nguyên được thử. [Code: scripts/collect_week7_evidence.py](../scripts/collect_week7_evidence.py); [Môi trường](../notebooks/logs/20260929-111025Z-week7/environment.txt); [Provenance](../notebooks/logs/20260929-111025Z-week7/provenance.json).

## 4. Kết quả thực nghiệm có thể kiểm chứng

### 4.1. Kết quả chức năng

| Chỉ tiêu | Kết quả của lượt chạy | Code và bằng chứng tại chỗ |
| --- | --- | --- |
| Test validation/API đạt | 54/54 | [Code test](../tests/test_image_search.py), [log pytest](../notebooks/logs/20260929-111025Z-week7/pytest.txt) |
| Ảnh thực tế riêng biệt đạt điều kiện kiểm thử | 20/20 | [Code HTTP](../scripts/verify_image_search.py), [từng ảnh và SHA-256](../notebooks/logs/20260929-111025Z-week7/image-search.json) |
| Yêu cầu tải ảnh kết quả nhận HTTP 200 | 200/200 yêu cầu | [Code đếm](../scripts/collect_week7_evidence.py), [summary.json](../notebooks/logs/20260929-111025Z-week7/summary.json) |
| Biến thể PNG/WEBP đạt | 2/2 | [Code biến thể](../scripts/verify_image_search.py#L78), [trường variants](../notebooks/logs/20260929-111025Z-week7/image-search.json) |

Số yêu cầu tải thumbnail ở bảng trên có thể gồm ảnh sản phẩm lặp giữa các truy vấn; không diễn giải thành số sản phẩm duy nhất. Kết quả đạt nghĩa là thỏa các điều kiện chức năng trong script, không có nghĩa toàn bộ sản phẩm trả về đã được gán nhãn liên quan thủ công.

### 4.2. Thời gian phản hồi

Thời gian được đo từ trước khi mở file truy vấn đến khi nhận phản hồi HTTP. Phép đo bao gồm gửi ảnh, tiền xử lý, embedding, tìm kiếm và truyền phản hồi về client; không bao gồm vòng tải thumbnail. Truy vấn đầu được tách riêng vì bao gồm nạp model/chỉ mục. [Code đo: scripts/verify_image_search.py](../scripts/verify_image_search.py); [Code tổng hợp: scripts/collect_week7_evidence.py](../scripts/collect_week7_evidence.py).

| Chỉ tiêu | Kết quả | Bằng chứng |
| --- | --- | --- |
| Request đầu, có nạp tài nguyên | 11.896,22 ms | [summary.json: cold_ms](../notebooks/logs/20260929-111025Z-week7/summary.json), [log chạy](../notebooks/logs/20260929-111025Z-week7/image-search.txt) |
| Số request dùng để tính thời gian warm | 19 | [summary.json: warm_count](../notebooks/logs/20260929-111025Z-week7/summary.json), [Code](../scripts/collect_week7_evidence.py) |
| Trung bình warm | 226,58 ms | [summary.json: warm_mean_ms](../notebooks/logs/20260929-111025Z-week7/summary.json), [Code](../scripts/collect_week7_evidence.py) |
| Phân vị p95 warm | 308,35 ms | [summary.json: warm_p95_ms](../notebooks/logs/20260929-111025Z-week7/summary.json), [Code](../scripts/collect_week7_evidence.py) |

Đây là phép đo tuần tự trên localhost với môi trường lưu kèm log. Nó không phải kết quả tải đồng thời, không đại diện cho triển khai Internet và không bảo đảm lặp lại đúng thời gian trên máy khác. Toàn bộ thời gian từng ảnh được giữ trong JSON để đối chiếu.

### 4.3. Quan sát lỗi truy xuất và giới hạn kết luận

Có **19/20** ảnh truy vấn trả lại chính mã sản phẩm đó ở hạng đầu; với `31172.jpg`, chính mã đó nằm ở **hạng 3**. [Code đếm: scripts/collect_week7_evidence.py](../scripts/collect_week7_evidence.py); [summary.json: self_rank_1, non_top1](../notebooks/logs/20260929-111025Z-week7/summary.json); [danh sách truy xuất đầy đủ](../notebooks/logs/20260929-111025Z-week7/image-search.json).

Các query là ảnh sản phẩm thuộc catalog. Vì vậy quan sát này chỉ phản ánh việc tìm lại sản phẩm đã có, không phải Precision@K/Recall@K trên tập đánh giá độc lập. Chưa đủ bằng chứng để quy nguyên nhân của trường hợp lệch hạng cho một thuộc tính cụ thể. Bước tiếp theo là xem trực tiếp query và các kết quả đứng trước, sau đó đánh giá bằng ảnh chụp ngoài catalog và nhãn liên quan do người đánh giá xác định.

## 5. Kiểm chứng UI tích hợp và build

Đã chạy **8 nhóm kiểm tra browser** trên UI tích hợp bằng Chrome, không ghi nhận
lỗi JavaScript qua sự kiện `pageerror`. [Code](../scripts/verify_image_search_ui.py);
[Kết quả](../notebooks/logs/20260929-111025Z-week7/browser-results.json); [Log sống](../notebooks/logs/20260929-111025Z-week7/browser.txt).
Luồng upload hợp lệ chạy model thật và trả **8 sản phẩm**, đúng tham số mà UI gửi.
[Code UI](../src/pages/ImageSearchPage.jsx); [Điều kiện kiểm tra](../scripts/verify_image_search_ui.py).

Kiểm tra bao gồm định dạng/kích thước file, retry sau ảnh hỏng, loading/disable,
ảnh kết quả, bố cục mobile, xóa/chọn lại cùng file, lỗi dịch vụ, response sai cấu
trúc và trạng thái không có kết quả. Lỗi dịch vụ, response sai cấu trúc và danh
sách rỗng được giả lập để kiểm tra UI; không xem chúng là truy vấn model thật.
[Code](../scripts/verify_image_search_ui.py); [Log](../notebooks/logs/20260929-111025Z-week7/browser.txt).

Build frontend bằng Vite hoàn tất với **mã thoát 0** sau khi xử lý xung đột;
`dist/` được tạo lại từ source đã tích hợp.
[Code chạy build](../scripts/collect_week7_evidence.py); [Log build](../notebooks/logs/20260929-111025Z-week7/build.txt).

- [Ảnh giao diện desktop của bản tích hợp](../notebooks/logs/20260929-111025Z-week7/desktop.png).
- [Ảnh giao diện mobile của bản tích hợp](../notebooks/logs/20260929-111025Z-week7/mobile.png).

Các hình này là ảnh giao diện web, không phải ảnh chụp terminal. Log văn bản
được ghi trực tiếp trong lúc chạy. Ảnh terminal thật vẫn cần bổ sung khi nộp;
không dùng ảnh dựng lại từ log thay cho ảnh terminal.

## 6. Lệnh tái hiện

Chạy từ thư mục gốc repository bằng môi trường Python của dự án. Để chạy cả browser/build, cần `npm ci`, Vite đang chạy ở port 5173 và port backend 5000 đang trống; script browser tự mở/đóng backend. Dừng backend demo riêng trước khi chạy bộ kiểm thử. Khai báo môi trường tối thiểu nằm ở [requirements-test.txt](../requirements-test.txt), bao gồm backend; môi trường toàn bộ dự án nằm ở [requirements.txt](../requirements.txt). Phiên bản thực đã sử dụng nằm trong [environment.txt](../notebooks/logs/20260929-111025Z-week7/environment.txt). File này ghi môi trường của lượt đo, không khẳng định toàn bộ notebook nghiên cứu đã được chạy.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-test.txt
.\.venv\Scripts\python.exe -m scripts.download_search_model
.\.venv\Scripts\python.exe -m scripts.collect_week7_evidence --image-dir 'D:\code\dataset\Fashion Product Images Dataset\archive\fashion-dataset\images' --with-ui --with-build
```

Script thu thập tự tạo thư mục mới có thời điểm UTC dưới `notebooks/logs`, lưu console trong lúc chạy, rồi xuất JSON tổng hợp. Nếu lệnh kiểm thử lỗi, script dừng với mã lỗi và giữ log. Không ghi đè lượt đo cũ. [Code: scripts/collect_week7_evidence.py](../scripts/collect_week7_evidence.py).

Điều kiện dữ liệu: cần các ảnh mẫu trong repo, checkpoint FashionCLIP đã tải và cặp file `embeddings/index/fashionclip_image_embeddings_flat.index` / `embeddings/product_ids.npy` đang khớp nhau. Hash của cặp artifact được lưu trong provenance. Dataset đầy đủ, embeddings và checkpoint không nằm trong các file được theo dõi bởi Git ở cấu hình hiện tại; phải chuẩn bị hoặc cấp quyền truy cập các artifact này khi bàn giao. Pipeline tạo embedding/chỉ mục nằm tại [embed_dataset2.py](../scripts/embed_dataset2.py) và [faiss_index_and_latency.py](../scripts/faiss_index_and_latency.py); hướng dẫn chạy demo nằm tại [README.md](../README.md).

## 7. Kết luận và các việc cần hoàn tất trước khi nộp

Luồng tìm kiếm ảnh đã có mã nguồn thực thi, kiểm thử validation, kiểm thử HTTP bằng model thật và log có thể đối chiếu. Kết quả chức năng trong mục 4 đáp ứng số lượng ảnh kiểm thử mà kế hoạch đặt ra. Kết luận chỉ áp dụng cho phạm vi và dữ liệu đã thử, chưa thay thế đánh giá chất lượng của khóa luận.

Trước khi nộp, cần đưa báo cáo, script kiểm chứng, log và hình minh chứng lên repository đã chia sẻ với giảng viên; sau đó bổ sung đường dẫn tới commit thực chứa chúng. Cần bổ sung ảnh terminal thật của các mốc kiểm thử và bảo đảm giảng viên truy cập được dữ liệu/artifact cần thiết. Báo cáo chưa đánh dấu các bước công bố và chụp terminal này là đã hoàn tất.

Báo cáo và log trước tích hợp được giữ riêng tại [báo cáo cũ](week7_image_search_report.md); không dùng số liệu cũ để mô tả UI đã merge.
