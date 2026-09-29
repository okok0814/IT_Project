# Fashion Search API — Week 7

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

Only these fields are accepted in this week's runnable endpoint. The Week 5
metadata-filter notebook remains available; its filters are not silently applied
or ignored here. Text/filter UI integration is the next milestone.

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

Still returns 501 in the runnable Flask app. The existing notebooks demonstrate
text retrieval and metadata filters; connecting that flow is outside Week 7.

## Frontend / CORS

Vite development and preview proxy `/api` and `/dataset2` to `127.0.0.1:5000`.
For direct API calls, CORS allows `http://localhost:5173` by default; configure
`ALLOWED_ORIGIN` for another frontend origin. The frontend sends browser-generated
multipart boundaries, shows loading/errors, and renders the real returned images.

Implementation references: [Flask upload limits](https://flask.palletsprojects.com/en/stable/patterns/fileuploads/)
and [CLIP image features](https://huggingface.co/docs/transformers/model_doc/clip).
