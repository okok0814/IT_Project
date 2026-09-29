# Fashion image search — Week 7

React/Vite frontend + Flask API. Upload a JPG, PNG or WEBP; FashionCLIP encodes
the image and the integrated UI requests eight similar catalog products (the
API default is ten when `top_k` is omitted). The index
contains 44,419 products. The research scripts and notebooks remain available
for the separate thesis experiments.

## Setup (PowerShell, repository root)

Python 3.11 and Node.js 22.12+ are suitable for this project.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-backend.txt
.\.venv\Scripts\python.exe -m scripts.download_search_model
npm ci
```

The one-time model download goes into `.cache/huggingface`. Search requests use
local model files only. `requirements.txt` also includes the earlier notebook
and CLIP research dependencies; they are not all needed to run this Flask app.

Keep the existing, matching artifacts:

- `embeddings/index/fashionclip_image_embeddings_flat.index`
- `embeddings/product_ids.npy`
- Dataset 2 `images/` containing `<product_id>.jpg` for every indexed product.

## Run

Terminal 1:

```powershell
$env:IMAGE_DIR = 'D:\code\dataset\Fashion Product Images Dataset\archive\fashion-dataset\images'
.\.venv\Scripts\python.exe -m src.backend.app
```

Terminal 2:

```powershell
npm run dev
```

Open `http://localhost:5173/search/image`. The first search loads the model;
later searches reuse it. Vite proxies `/api` and `/dataset2` to port 5000.
`npm run build` builds `dist/`; `npm run preview` also uses those proxies.
A deployed static site needs equivalent proxy routes to the backend.

In this workspace a portable Node runtime is available under
`.cache/node/node-v22.23.3-win-x64`. If `npm` is not on PATH, run this in terminal 2:

```powershell
$env:PATH = (Resolve-Path '.cache/node/node-v22.23.3-win-x64').Path + ';' + $env:PATH
npm run dev
```

The image flow uses real API results. Text search, filters in the static text
demo, and related products still belong to later integration milestones.

## Verify / reproduce the deliverable

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-test.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m scripts.verify_image_search --image-dir 'D:\code\dataset\Fashion Product Images Dataset\archive\fashion-dataset\images'
```

The second command tests validation using a recording encoder stub. The third
starts its own temporary HTTP server and tests 20 distinct real photographs
with the actual FashionCLIP model, full index and result thumbnails. It exits
with a failure if any request fails. Use `--queries PATH` for a different set
of at least 15 unique photos and `--output PATH` to preserve earlier evidence.

To reproduce the instructor-facing report with live console logs, pytest XML,
per-image results, environment versions and source/artifact hashes, run:

```powershell
.\.venv\Scripts\python.exe -m scripts.collect_week7_evidence --image-dir 'D:\code\dataset\Fashion Product Images Dataset\archive\fashion-dataset\images'
```

Add `--with-ui --with-build` to include browser tests and the frontend build.
For these options keep Vite running on port 5173 and leave backend port 5000
free; the browser test starts and stops its own backend.

Each run creates a new UTC-stamped directory under `notebooks/logs/` and keeps
earlier runs. The report links to one specific run so its measurements can be
checked without mixing results. See the latest [integration report](docs/week7_integration_report.md)
and [Word version](docs/week7_integration_report.docx). The earlier Week 7 report
and its evidence remain available as the pre-integration record.

For browser checks, keep Vite running, stop the separate backend on port 5000,
and run (the script starts/stops its own backend):

```powershell
.\.venv\Scripts\python.exe -m scripts.verify_image_search_ui --image-dir 'D:\code\dataset\Fashion Product Images Dataset\archive\fashion-dataset\images'
```

This uses installed Chrome; add `--channel msedge` to use Edge. See
[the integrated Week 7 report](docs/week7_integration_report.md),
[API documentation](docs/API_docs.md), and
[raw real-image results](docs/week7_image_search_results.json).

## Configuration / troubleshooting

- `IMAGE_DIR`: absolute path to Dataset 2's **images** folder, not its parent.
- `INDEX_PATH`, `PRODUCT_IDS_PATH`: override the default matching artifacts.
- `MODEL_PATH`: local FashionCLIP checkpoint directory or the cached default model ID.
- `FASHION_IMAGES_DIR`, `FASHION_INDEX_PATH`, `MODEL_HF_NAME`: teammate-compatible
  aliases; `IMAGE_DIR`, `INDEX_PATH`, `MODEL_PATH` take precedence when set.
- `PORT`: backend port, default 5000. Change the Vite proxy target too if changed.
- `VITE_API_BASE_URL`: optional backend origin in `.env.local` for the frontend;
  by default the API helper uses Vite's same-origin `/api` and `/dataset2` proxies.
- `ALLOWED_ORIGIN`: direct API CORS origin, default `http://localhost:5173`.
- Direct API calls from `http://127.0.0.1:5173` are also allowed. With the virtual
  environment activated, `npm run backend` starts the backend as a Python module.
- HTTP 503: inspect the backend console for missing/mismatched artifacts or model files.
- `/health` is a liveness check; `model_loaded: false` is expected before the first valid search.
- Input limit: 10 MiB per image, 25 million pixels, still JPG/PNG/WEBP only.
- Scores are cosine similarities in `[-1, 1]`, not probabilities of relevance.
