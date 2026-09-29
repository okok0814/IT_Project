# API contract

The current runnable contract is documented in [API_docs.md](API_docs.md).
This replaces the earlier draft that used a `status` field.

- `POST /search/image` and `POST /api/v1/search/image` accept one multipart
  `image` file and optional `top_k` (1–50, default 10).
- JSON envelope: `{ "success": boolean, "data": array | null, "error": string | null }`.
- Product: `{ "product_id": string, "image_url": string, "similarity_score": number }`.
- Relative image URLs resolve through the backend or the Vite `/dataset2` proxy.
- Text search is not yet integrated in the runnable app; do not treat the
  historical notebook response format as this frontend's contract.
