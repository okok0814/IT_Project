# Fashion Search API — Week 8

Local backend: `http://localhost:5000`. Start with `python -m src.backend.app`.
The runnable app is Flask; previous FastAPI notebook experiments are historical.

JSON responses use the Week 6 envelope:

```json
{"success": true, "data": [], "error": null}
```

Errors use `success: false`, `data: null`, and a human-readable `error` string.
HTTP errors such as 404, 405 and 413 also use this envelope. Image file responses
are binary, not JSON.

## POST /search/image

Alias: `POST /api/v1/search/image` (used by the frontend).

Send `multipart/form-data`:

| Field | Type | Rule |
| --- | --- | --- |
| image | file | Exactly one file, required |
| top_k | integer | Optional; default 10; range 1–50 |

Only these fields are accepted by image search. Metadata filters are supported
by the text-search endpoint described below.

The integrated frontend explicitly sends `top_k=8`, preserving the teammate's
layout. The backend default remains 10 when the field is omitted.

Allowed extensions: `.jpg`, `.jpeg`, `.png`, `.webp` (case insensitive).
The MIME type and decoded file format must agree with the extension. Missing
MIME or `application/octet-stream` is accepted only if the actual image validates.
The server verifies and fully decodes image contents, applies EXIF orientation,
composites alpha on white, and converts to RGB before encoding.

Limits: image bytes ≤ 10 × 1024 × 1024; pixels ≤ 25,000,000. Animated images
are rejected. Total multipart request limit is 10 MiB + 64 KiB for headers and
fields; oversized requests are rejected before inference. Uploaded files are
not retained by the application (the multipart parser may spool temporarily).

```powershell
curl.exe -F "image=@data/d1/sample_images/10180.jpg" -F "top_k=5" http://localhost:5000/search/image
```

Example schema (illustrative score):

```json
{
  "success": true,
  "data": [
    {"product_id": "10180", "image_url": "/dataset2/images/10180.jpg", "similarity_score": 0.98}
  ],
  "error": null
}
```

Results are sorted by decreasing cosine similarity; up to `min(top_k, catalog size)`
results are returned. Scores are in `[-1, 1]`, not calibrated percentages.
The model/index load once per process. The service validates index dimensions,
row counts, unique IDs, normalized vectors and catalog image availability.
Model files must already exist locally; serving requests never downloads them.

| HTTP | Meaning |
| --- | --- |
| 200 | Search succeeded |
| 400 | Missing/duplicate/empty file, malformed form, invalid top_k, corrupt/truncated image |
| 413 | File/request/pixel limit exceeded |
| 415 | Unsupported, animated or mismatched image format |
| 503 | Model, index, product IDs or catalog images unavailable/incompatible |
| 500 | Unexpected inference failure; details logged on server |

## GET /dataset2/images/\<filename\>

Serves catalog images from `IMAGE_DIR` with traversal-safe directory handling.
Uploads are never saved or served by this route.

## GET /health

```json
{"success": true, "data": {"status": "ok", "model_loaded": false}, "error": null}
```

This checks process liveness, not complete search readiness. A successful search
is the end-to-end readiness check. `model_loaded` becomes true after loading.

## POST /search/text

Alias: `POST /api/v1/search/text` (used by the frontend).

Send an `application/json` object with these **flat** fields:

| Field | Type | Rule |
| --- | --- | --- |
| query | string | Optional, default empty; at most 1,000 characters |
| top_k | integer | Optional, default 10; range 1–50; strings and booleans are rejected |
| gender | string or null | Optional, at most 100 characters; e.g. `Women` |
| category | string or null | Optional, at most 100 characters; e.g. `Dresses` |
| color | string or null | Optional, at most 100 characters; e.g. `Red` |

At least a nonempty query or one filter is required. Empty/null filters impose
no constraint. Filters are combined with AND, matched exactly after whitespace
normalization and case folding. `category` maps to Dataset 2 **articleType**,
not masterCategory. Color aliases `off-white` and `navy` are accepted.
Unknown values or impossible combinations return HTTP 200 with `data: []`.
Unknown fields (including nested `filters`) return 400 to catch integration mistakes.

```json
{"query":"summer dress","top_k":50,"gender":"Women","category":"Dresses","color":"Red"}
```

```powershell
$body = @{ query = 'summer dress'; top_k = 10; gender = 'Women'; category = 'Dresses'; color = 'Red' } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://localhost:5000/search/text -ContentType 'application/json; charset=utf-8' -Body $body
```

FashionCLIP encodes the query and ranks the existing image embeddings by cosine
similarity. The tokenizer truncates to the model's context limit (77 tokens for
the current checkpoint). Filters restrict eligible products **before top_k is
selected**. Metadata is joined by product ID, independently of CSV row order.

Each result contains `product_id`, `image_url`, `similarity_score`, `name`,
`gender`, `category`, `color`, `usage`, `master_category`, `sub_category`, and
`match_type`. A nonempty query returns `match_type: "semantic"` and numeric cosine
scores in decreasing order. With only filters, results use string product-ID
ordering, `match_type: "metadata"`, and `similarity_score: null`; no embedding
score is invented. The response envelope is the same as image search.

The UI sends `top_k: 50` and paginates the returned subset eight products per
page. This is not server-side pagination of every matching catalog product.

Metadata defaults to `styles.csv` next to the configured `IMAGE_DIR` directory.
Set `METADATA_PATH` (or alias `FASHION_METADATA_PATH`) for another CSV. Accepted
schemas are raw Dataset 2 `id/gender/articleType/baseColour` or normalized
`product_id/gender/category/color`. Optional descriptive columns are included
when available. Malformed-width rows are skipped; missing indexed IDs, duplicate
IDs and incompatible headers cause a configuration error. Image search does not
require the metadata CSV.

| HTTP | Meaning |
| --- | --- |
| 200 | Search succeeded, possibly with no matches |
| 400 | Invalid JSON/object, unknown field, invalid query/filter/top_k, or no search input |
| 413 | JSON request exceeds 16 KiB |
| 415 | Request is not JSON |
| 503 | Model, index, product IDs, images or metadata unavailable/incompatible |
| 500 | Unexpected inference failure; details logged on server |

These checks establish request/filter correctness. They do not establish relevance
quality or Vietnamese-language retrieval accuracy; those require labeled evaluation.

## Frontend / CORS

Vite development and preview proxy `/api` and `/dataset2` to `127.0.0.1:5000`.
Set `BACKEND_URL` before starting Vite to change that proxy destination.
For direct API calls, CORS allows `http://localhost:5173` by default; configure
`ALLOWED_ORIGIN` for another frontend origin. The frontend sends browser-generated
multipart boundaries, shows loading/errors, and renders the real returned images.

The teammate's API helper supports `VITE_API_BASE_URL` (backend origin) as an
optional override. Direct calls from `http://127.0.0.1:5173` are also allowed.
Server configuration supports `FASHION_IMAGES_DIR`, `FASHION_INDEX_PATH` and
`MODEL_HF_NAME` as aliases; the primary `IMAGE_DIR`, `INDEX_PATH`, `MODEL_PATH`
variables take precedence. `npm run backend` uses `python -m src.backend.app`;
activate the virtual environment first.

Implementation references: [Flask upload limits](https://flask.palletsprojects.com/en/stable/patterns/fileuploads/)
and [CLIP image features](https://huggingface.co/docs/transformers/model_doc/clip).
