# Cài đặt và chạy bằng Docker Desktop

Ứng dụng chạy tại **http://localhost:8080**. Docker Compose tạo hai container:

- `frontend`: build React/Vite bằng `npm ci`, phục vụ bằng Nginx và proxy API.
- `backend`: Flask chạy bằng Gunicorn, một worker và bốn thread dùng chung FashionCLIP, FAISS và cache kết quả. Bản đóng gói này dùng CPU.

Ảnh catalog, metadata, FAISS và model nằm ngoài image, được mount **read-only**. Không cần bật Vite hoặc Flask development server khi dùng Docker. Backend không mở cổng ra host; trình duyệt dùng cùng origin cho trang web, API và ảnh.

## 1. Chuẩn bị

Mở Docker Desktop và dùng **Linux containers**. Từ PowerShell tại thư mục repository:

```powershell
docker version
docker compose version
```

`docker version` phải có cả Client và Server. Cần Docker Compose có hỗ trợ `up --wait` và long-syntax bind mount. Lần đầu build cần Internet để tải image/dependencies; lúc phục vụ, FashionCLIP chỉ dùng checkpoint local.

Chuẩn bị các artifact cùng một lần tạo embedding:

```text
<DATASET_DIR>/
  styles.csv
  images/
    10180.jpg
    ... ảnh của mọi ID trong index ...

<EMBEDDINGS_DIR>/
  product_ids.npy
  index/
    fashionclip_image_embeddings_flat.index

<MODEL_CACHE_DIR>/
  models--patrickjohncyh--fashion-clip/
    refs/main
    snapshots/<revision>/...
    blobs/...  (nếu snapshot dùng symlink)
```

Index phải là FashionCLIP `IndexFlatIP`, vector 512 chiều chuẩn hóa L2; IDs, ảnh và metadata phải khớp. Backend kiểm tra các điều kiện này khi khởi động. Không đổi tên một index IVF thành Flat để vượt kiểm tra. Dữ liệu thực nghiệm hiện tại có 44.419 sản phẩm; code kiểm tra tính nhất quán chứ không cố định số lượng đó.

Git clone **không** tự tải dataset, embeddings hoặc checkpoint vì các file lớn này không nằm trong Git. Lấy artifact từ thành viên nhóm hoặc tạo lại theo [hướng dẫn dự án](../README.md), [pipeline embedding](../scripts/embed_dataset2.py) và [script index](../scripts/faiss_index_and_latency.py). Chỉ dùng các file `product_ids.npy` đáng tin cậy do nhóm tạo; định dạng hiện tại được nạp với `allow_pickle=True`.

## 2. Khai báo đường dẫn trên máy

Trên máy hiện tại, file `.env.docker` đã được tạo với dataset:

```text
D:/code/dataset/Fashion Product Images Dataset/archive/fashion-dataset
```

Đó là thư mục **chứa** `images` và `styles.csv`, không phải chính thư mục ảnh.

Trên máy khác, không cần Python local để cấu hình. Sao chép mẫu rồi sửa:

```powershell
Copy-Item .env.docker.example .env.docker
notepad .env.docker
```

Ví dụ:

```dotenv
DATASET_DIR='D:/datasets/fashion-dataset'
EMBEDDINGS_DIR='./embeddings'
MODEL_CACHE_DIR='./.cache/huggingface'
APP_PORT=8080
SEARCH_CACHE_SIZE=256
SEARCH_CACHE_TTL_SECONDS=300
```

Dùng dấu `/` trên Windows. Đường dẫn có khoảng trắng được hỗ trợ. Trên Linux/macOS, thay bằng đường dẫn local tương ứng. Các đường dẫn tương đối được giải từ thư mục chứa `compose.yaml`. `.env.docker` bị Git bỏ qua vì chứa cấu hình riêng của máy; luôn truyền `--env-file .env.docker` trong các lệnh Compose.

Nếu có môi trường Python dự án, helper sau kiểm tra sự tồn tại của artifact và tạo env file mới:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m scripts.configure_docker --dataset-dir "D:/code/dataset/Fashion Product Images Dataset/archive/fashion-dataset"
```

Helper không ghi đè file có sẵn. Nếu file đã tồn tại, sửa nó trực tiếp; không cần chạy helper mỗi lần mở ứng dụng. Có thể thêm `--embeddings-dir`, `--model-cache-dir`, `--port` hoặc `--output`.

### Khi chưa có checkpoint

Nếu đang dùng môi trường Python của dự án:

```powershell
.\.venv\Scripts\python.exe -m scripts.download_search_model
```

Hoặc dùng Docker sau khi đã tạo `.env.docker` và build backend:

```powershell
docker compose --env-file .env.docker build backend
New-Item -ItemType Directory -Force .cache/huggingface | Out-Null
$fashionCache = (Resolve-Path .cache/huggingface).Path
docker run --rm --user 0 -e HF_HUB_OFFLINE=0 -e TRANSFORMERS_OFFLINE=0 --mount "type=bind,source=$fashionCache,target=/models/cache" fashion-search-backend python -c "from huggingface_hub import snapshot_download; print(snapshot_download('patrickjohncyh/fashion-clip', cache_dir='/models/cache', allow_patterns=['*.json','*.txt','*.safetensors','pytorch_model.bin']))"
```

Lệnh này tải vào cache của repository. Nếu dùng `MODEL_CACHE_DIR` khác, thay đường dẫn `$fashionCache` tương ứng. Mount ghi chỉ dành cho bước tải một lần; Compose phục vụ ứng dụng mount cache read-only. Khi chuyển cache giữa máy, sao chép đầy đủ `refs`, `snapshots` và `blobs`, giữ các liên kết hợp lệ.

## 3. Build và chạy

```powershell
docker compose --env-file .env.docker config --quiet
docker compose --env-file .env.docker up --build -d --wait --wait-timeout 300
docker compose --env-file .env.docker ps
```

Chờ cả hai service báo `healthy`, rồi mở:

```text
http://localhost:8080
```

`/search/image`, `/search/text` và `/results` tải được trực tiếp hoặc sau refresh. `/api/v1/...` được Nginx chuyển tới backend. Các alias POST `/search/image` và `/search/text` vẫn dùng được; GET cùng đường dẫn mở trang React. Thử truy vấn `white office shirt`, chọn bộ lọc hoặc upload `data/d1/sample_images/10180.jpg`.

Backend khởi động theo trình tự: đọc artifact → kiểm tra index/IDs/ảnh → nạp FashionCLIP → nạp metadata → chạy thử text và image encoder → đánh dấu ready. Đây có thể là bước tốn thời gian nhất, nhất là khi đọc nhiều file qua Windows bind mount.

```powershell
Invoke-RestMethod http://localhost:8080/ready
Invoke-RestMethod http://localhost:8080/health
```

`/health` là liveness; `/ready` chỉ trả 200 sau khi startup checks hoàn tất trong entrypoint Gunicorn. Chạy bằng `python -m src.backend.app` vẫn là chế độ phát triển với lazy load; `/ready` trong chế độ đó trả 503 vì không chạy startup warmup.

## 4. Dừng, mở lại và cập nhật

```powershell
# Xem log; Ctrl+C chỉ dừng theo dõi log
docker compose --env-file .env.docker logs -f --tail 100

# Dừng container nhưng giữ cấu hình/container
docker compose --env-file .env.docker stop

# Mở lại, chờ kiểm tra sẵn sàng
docker compose --env-file .env.docker up -d --wait --wait-timeout 300

# Sau khi pull code hoặc sửa dependency
docker compose --env-file .env.docker up --build -d --wait --wait-timeout 300

# Khi muốn gỡ các container và network của project
docker compose --env-file .env.docker down
```

Các lệnh này không xóa dataset/model/artifact trên host. Khi thay file dữ liệu, model hoặc quy tắc, restart/recreate backend để nạp lại snapshot; TTL cache không tự reload artifact:

```powershell
docker compose --env-file .env.docker up -d --force-recreate --no-deps --wait --wait-timeout 300 backend
```

Nginx dùng Docker DNS với chu kỳ refresh 10 giây để tìm lại backend sau khi IP container đổi. Nếu đổi `APP_PORT` trong `.env.docker`, chạy `up -d --wait` rồi dùng cổng mới. Compose mặc định chỉ bind `127.0.0.1`, phù hợp demo trên máy này. Đây chưa phải public hosting, chưa cấu hình domain/TLS.

## 5. Kiểm thử và lưu bằng chứng

Khi các container đang healthy, dùng môi trường test trên host:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -X utf8 -m pytest -q
.\.venv\Scripts\python.exe -X utf8 -m scripts.verify_deployment --base-url http://localhost:8080 --with-ui
```

Browser test dùng Google Chrome local. Bỏ `--with-ui` nếu chỉ kiểm chứng HTTP. Runner tạo `logs/<UTC timestamp>-deployment/`, lưu log sống, request/response, hash mã nguồn và ảnh desktop/mobile. Nó không tự dừng stack đang chạy. Các probe kiểm tra ready/health, build assets, SPA refresh, text có lọc/cache, filter-only, image upload thật, thumbnail, related và lỗi 400/404/413/415 qua proxy. Đây là smoke/integration test, không thay benchmark tải tuần trước.

Để ghi build log sạch vào báo cáo, có thể chạy `docker compose --env-file .env.docker --progress plain build` và lưu stdout/stderr. `docker compose logs --no-color` ghi nhận startup/warmup; `docker compose exec -T backend pip freeze` ghi phiên bản Python trong container. Kết quả xác nhận của phiên đóng gói nằm trong [báo cáo triển khai](deployment_report.md).

## 6. Lỗi thường gặp

| Hiện tượng | Cách kiểm tra / xử lý |
| --- | --- |
| Không kết nối Docker engine | Mở Docker Desktop, chờ engine hoạt động; kiểm tra Linux containers và `docker version` |
| Compose yêu cầu DATASET_DIR | Tạo/sửa `.env.docker`; truyền đúng `--env-file` |
| Bind source path does not exist | Sửa path thực của dataset/index/cache. Compose không tự tạo thư mục rỗng thay cho dữ liệu bị thiếu |
| Backend unhealthy hoặc liên tục restart | Xem `logs backend`; kiểm tra checkpoint, index Flat 512 chiều, IDs và ảnh/metadata; không chỉ tăng timeout để bỏ qua lỗi artifact |
| Không tìm thấy checkpoint khi offline | Tải model một lần hoặc sao chép đủ cache; kiểm tra `refs/main` trỏ đúng snapshot |
| Gunicorn bị kill/OOM | Kiểm tra RAM được Docker Desktop cấp và các ứng dụng khác đang dùng RAM; giữ một worker để tránh nhân bản model; gói này không dùng GPU |
| Port 8080 đang bận | Đổi APP_PORT trong `.env.docker`, rồi chạy lại `up -d --wait` |
| Ảnh trả lỗi 404 | Kiểm tra IMAGE_DIR trong container qua log và file ảnh tương ứng dưới DATASET_DIR/images |
| SPA trang sâu hoặc API sai URL | Dùng port Nginx, không dùng port Vite/8000. VITE_API_BASE_URL trong bản build Docker là chuỗi rỗng để gọi cùng origin |
| Browser cũ còn hiển thị lỗi sau rebuild | Hard-refresh; index.html không cache lâu, còn asset có tên hash được cache dài hạn |

## 7. Tính tái lập và phạm vi

Danh sách dependency Python hiện được gộp vào một file [requirements.txt](../requirements.txt).
Docker dùng [runtime_requirements.py](../deploy/runtime_requirements.py) để trích phần
giữa `# BEGIN RUNTIME` và `# END RUNTIME` thành file tạm trong lúc build, rồi áp dụng
constraints. Vì vậy, cài toàn bộ môi trường trên host chỉ cần `pip install -r requirements.txt`,
còn image backend không chứa dependency notebook/test. Ba file requirements phụ đã được
loại bỏ; khi thêm package backend, đặt nó trong phần runtime và cập nhật constraints nếu cần.

Base image được pin theo digest; npm dùng package-lock.json; Python deployment dùng [constraints.txt](../deploy/constraints.txt). Torch CPU trong container được pin riêng, không ép môi trường notebook/Windows đổi phiên bản. File apt trong base Debian vẫn được lấy từ repository khi build; artifact dataset/model được cung cấp ngoài image. Để chuyển nguyên build đã kiểm thử sang máy khác, có thể dùng `docker image save`/`docker image load` và cung cấp cùng artifact/config; không chỉ chuyển container filesystem rồi kỳ vọng dataset đi kèm.

Frontend vẫn có cảnh báo bundle lớn do catalog import; packaging không xử lý lại nội dung đó. Cần đánh giá tài nguyên và latency trên môi trường hosting thật trước khi công bố năng lực chịu tải. Khi triển khai public, bổ sung reverse proxy/TLS, cấu hình bind phù hợp và kiểm tra lại quyền truy cập dữ liệu. Hướng dẫn này hoàn tất phương án Docker Desktop demo local.

Tham khảo kỹ thuật: [Docker Compose services](https://docs.docker.com/reference/compose-file/services/), [startup order](https://docs.docker.com/compose/how-tos/startup-order/), [Flask với Gunicorn](https://flask.palletsprojects.com/en/stable/deploying/gunicorn/), [Nginx proxy module](https://nginx.org/en/docs/http/ngx_http_proxy_module.html).
