# API contract

The current runnable contract is documented in [API_docs.md](API_docs.md).
This replaces the earlier draft that used a `status` field.

- `POST /search/image` and `POST /api/v1/search/image` accept one multipart
  `image` file and optional `top_k` (1–50, default 10).
- JSON envelope: `{ "success": boolean, "data": array | null, "error": string | null }`.
- Product: `{ "product_id": string, "image_url": string, "similarity_score": number }`.
- Relative image URLs resolve through the backend or the Vite `/dataset2` proxy.
- `POST /search/text` and `POST /api/v1/search/text` accept JSON with flat fields
  `query`, `top_k`, `gender`, `category`, `color`. At least query or one filter
  must be nonempty. `top_k` is an integer (1–50, default 10; UI sends 50).
- Text results add metadata (`name`, `gender`, `category`, `color`, `usage`,
  `master_category`, `sub_category`) and `match_type: "semantic"`.
  Filters use case-insensitive exact AND matching before selecting top-k.
- Filter-only requests return `match_type: "metadata"` and
  `similarity_score: null`, ordered by string product ID. Empty results use
  HTTP 200 with `data: []`; invalid requests use the documented error envelope.
- `GET /products/<product_id>/related` and its `/api/v1` alias accept optional
  query `top_k` (1–50, default 8). Results reuse the product metadata/score shape,
  add `source_product_id`, and use `match_type: "complementary"`.
  Candidates must satisfy the backend category/gender rules, and exclude the
  source item, before top-k selection. The score is image-vector cosine.
- Unknown source IDs return 404; unsupported source categories or no eligible
  candidates return 200 with an empty array. Invalid/duplicate/unknown query
  parameters return 400. See [the rules and examples](API_docs.md).
