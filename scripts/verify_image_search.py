"""Real-model HTTP integration check; writes evidence, never substitutes an encoder.

Run: python -m scripts.verify_image_search --image-dir PATH --output docs/week7_image_search_results.json
"""
import argparse
import hashlib
import importlib.metadata
import io
import json
import logging
import platform
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import requests
from PIL import Image
from werkzeug.serving import make_server

from src.backend.app import create_app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image-dir", required=True)
    parser.add_argument("--queries", default="data/d1/sample_images")
    parser.add_argument("--output", default="docs/week7_image_search_results.json")
    args = parser.parse_args()
    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    paths = sorted(p for p in Path(args.queries).iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"})
    if len(paths) < 15:
        raise SystemExit("At least 15 distinct real images are required")
    hashes = {hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    if len(hashes) < 15:
        raise SystemExit("At least 15 unique image contents are required")
    app = create_app({"IMAGE_DIR": args.image_dir})
    server = make_server("127.0.0.1", 0, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    records = []
    failures = []
    try:
        for i, path in enumerate(paths):
            started = time.perf_counter()
            with Image.open(path) as source:
                mime = Image.MIME[source.format]
            with path.open("rb") as file:
                response = requests.post(base + "/search/image", files={"image": (path.name, file, mime)}, data={"top_k": "10"}, timeout=180)
            elapsed = (time.perf_counter() - started) * 1000
            body = response.json()
            results = body.get("data") or []
            scores = [item["similarity_score"] for item in results]
            ids = [item["product_id"] for item in results]
            image_statuses = [requests.get(base + item["image_url"], timeout=30).status_code for item in results]
            passed = (response.status_code == 200 and body["success"] and body["error"] is None
                      and len(results) == 10 and len(set(ids)) == 10
                      and all(np.isfinite(s) and -1 <= s <= 1 for s in scores)
                      and scores == sorted(scores, reverse=True) and all(s == 200 for s in image_statuses))
            record = {"file": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                      "status": response.status_code, "elapsed_ms": round(elapsed, 2),
                      "includes_model_load": i == 0, "passed": bool(passed),
                      "self_rank": ids.index(path.stem) + 1 if path.stem in ids else None,
                      "result_image_statuses": image_statuses, "response": body}
            records.append(record)
            if not passed:
                failures.append(path.name)
            print(f"{path.name}: HTTP {response.status_code}, {elapsed:.0f} ms, passed={passed}", flush=True)
        # Re-encode real photographs to exercise supported container formats through real inference.
        variants = []
        for fmt, extension, mime in [("PNG", "png", "image/png"), ("WEBP", "webp", "image/webp")]:
            with Image.open(paths[0]) as source:
                buffer = io.BytesIO()
                source.convert("RGB").save(buffer, fmt)
            response = requests.post(base + "/api/v1/search/image", files={"image": (f"photo.{extension}", buffer.getvalue(), mime)}, data={"top_k": "5"}, timeout=180)
            passed = response.status_code == 200 and response.json()["success"] and len(response.json()["data"]) == 5
            variants.append({"format": fmt, "status": response.status_code, "passed": passed})
            if not passed:
                failures.append(fmt)
        warm_times = [row["elapsed_ms"] for row in records[1:]]
        report = {"timestamp_utc": datetime.now(timezone.utc).isoformat(), "python": platform.python_version(),
                  "packages": {name: importlib.metadata.version(name) for name in ["flask", "pillow", "torch", "transformers", "faiss-cpu", "numpy"]},
                  "model": app.config["MODEL_PATH"], "real_encoder": True,
                  "index_vectors": app.extensions["search_service"].index.ntotal if app.extensions["search_service"] else None,
                  "image_dir": str(Path(args.image_dir).resolve()), "query_dir": str(Path(args.queries).resolve()),
                  "unique_real_images": len(hashes), "passed": len(records) - len([r for r in records if not r["passed"]]),
                  "warm_mean_ms": round(float(np.mean(warm_times)), 2),
                  "warm_p95_ms": round(float(np.percentile(warm_times, 95)), 2),
                  "variants": variants, "records": records,
                  "note": "Functional catalog-query test, not a held-out relevance evaluation or thesis Recall@K result."}
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Evidence: {output}; failures: {failures}")
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
