"""Real-model Week 8 HTTP checks, independent metadata/ranking oracle and browser demo."""
import argparse
import csv
import io
import json
import logging
import os
import shutil
import socket
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import requests
from PIL import Image
from werkzeug.serving import make_server

from src.backend.app import ROOT, create_app

CASES = [
    {"query": "black shirt"},
    {"query": "white office shirt", "gender": "Men", "category": "Shirts", "color": "White"},
    {"query": "summer dress", "gender": "Women", "category": "Dresses", "color": "Red"},
    {"query": "red running shoes", "category": "Sports Shoes", "color": "Red"},
    {"query": "black leather handbag", "gender": "Women", "category": "Handbags", "color": "Black"},
    {"query": "blue denim jeans", "gender": "Men", "category": "Jeans", "color": "Blue"},
    {"query": "linen trousers", "category": "Trousers"},
    {"query": "winter coat with hood", "category": "Jackets"},
    {"query": "silver watch", "category": "Watches", "color": "Silver"},
    {"query": "comfortable cotton t shirt", "gender": "Women"},
    {"query": "formal shoes", "color": "Brown"},
    {"query": "a lightweight bag for carrying books to school", "category": "Backpacks"},
    {"query": "  white   shirt ", "gender": " men ", "category": " SHIRTS ", "color": " white "},
    {"query": "áo sơ mi trắng", "category": "Shirts", "color": "White"},
    {"query": "red running shoes " * 25, "category": "Sports Shoes"},
    {"query": "shirt", "gender": "Boys", "category": "Lipstick", "color": "Gold"},
    {"query": "shirt", "color": "no-such-color"},
    {"query": "", "gender": "Men", "category": "Shirts", "color": "Black"},
    {"category": "Basketballs", "top_k": 50},
    {"query": "black shirt", "gender": None, "category": "", "color": "  ", "top_k": 1},
]


def read_oracle(path, ids):
    """Independent CSV reading; do not use the production ProductMetadata class."""
    with Path(path).open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        normalized = "product_id" in reader.fieldnames
        keys = ("product_id", "category", "color") if normalized else ("id", "articleType", "baseColour")
        rows = {}
        for row in reader:
            if None in row or any(row[key] is None for key in reader.fieldnames):
                continue
            rows[row[keys[0]].strip()] = {
                "gender": " ".join((row.get("gender") or "Unknown").split()).title(),
                "category": " ".join((row.get(keys[1]) or "Unknown").split()).title(),
                "color": " ".join((row.get(keys[2]) or "Unknown").split()).title(),
            }
    return {str(pid): rows[str(pid)] for pid in ids}


def verify_api(app, base, output, metadata_path):
    ids = np.load(app.config["PRODUCT_IDS_PATH"], allow_pickle=True).astype(str)
    oracle = read_oracle(metadata_path, ids)
    id_to_pos = {pid: i for i, pid in enumerate(ids)}
    # Independently rank the saved vectors with NumPy, rather than calling FAISS again.
    vectors = np.load(ROOT / "embeddings/fashionclip_image_embeddings.npy").astype("float32")
    assert vectors.shape == (len(ids), 512)
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
    records = []
    for number, case in enumerate(CASES):
        payload = {"top_k": 10, **case}
        route = "/search/text" if number % 2 == 0 else "/api/v1/search/text"
        started = time.perf_counter()
        response = requests.post(base + route, json=payload, timeout=180)
        elapsed = (time.perf_counter() - started) * 1000
        body = response.json()
        assert response.status_code == 200, body
        assert body["success"] and body["error"] is None
        result = body["data"]
        filters = {key: " ".join(payload[key].split()).casefold() for key in ["gender", "category", "color"] if payload.get(key) and payload[key].strip()}
        eligible = [pid for pid in ids if all(oracle[pid][key].casefold() == value for key, value in filters.items())]
        expected_count = min(payload["top_k"], len(eligible))
        assert len(result) == expected_count
        result_ids = [row["product_id"] for row in result]
        assert len(set(result_ids)) == len(result_ids)
        for row in result:
            assert row["product_id"] in eligible
            assert all(row[key] == oracle[row["product_id"]][key] for key in ["gender", "category", "color"])
        query = " ".join(payload.get("query", "").split())
        if query and result:
            service = app.extensions["search_service"]
            q = service._embed_text(query).reshape(-1)
            q /= np.linalg.norm(q)
            positions = [id_to_pos[pid] for pid in eligible]
            scores = vectors[positions] @ q
            actual_scores = [row["similarity_score"] for row in result]
            assert actual_scores == sorted(actual_scores, reverse=True)
            for row in result:
                assert abs(row["similarity_score"] - float(vectors[id_to_pos[row["product_id"]]] @ q)) < 2e-5
            # Ties may be ordered differently; no strictly higher-scoring eligible ID may be omitted.
            higher_ids = {eligible[i] for i in np.flatnonzero(scores > actual_scores[-1] + 2e-5)}
            assert higher_ids <= set(result_ids)
        elif not query:
            assert result_ids == sorted(eligible)[:payload["top_k"]]
            assert all(row["similarity_score"] is None and row["match_type"] == "metadata" for row in result)
        thumbnails = [requests.get(base + row["image_url"], timeout=20).status_code for row in result]
        assert all(status == 200 for status in thumbnails)
        records.append({"request": payload, "route": route, "status": response.status_code,
                        "elapsed_ms": round(elapsed, 2), "includes_model_load": number == 0,
                        "eligible_count": len(eligible), "thumbnail_statuses": thumbnails,
                        "passed": True, "response": body})
        print(f"Case {number + 1}: HTTP 200, {len(result)}/{len(eligible)} candidates, {elapsed:.0f} ms; oracle PASS", flush=True)
    for payload in [{}, {"query": "shirt", "top_k": True}, {"query": "shirt", "filters": {"gender": "Men"}}]:
        response = requests.post(base + "/search/text", json=payload, timeout=20)
        assert response.status_code == 400 and response.json()["success"] is False
    with (ROOT / "data/d1/sample_images/10180.jpg").open("rb") as file:
        image = requests.post(base + "/search/image", files={"image": ("10180.jpg", file, "image/jpeg")}, data={"top_k": "8"}, timeout=180)
    assert image.status_code == 200 and len(image.json()["data"]) == 8
    assert image.json()["data"][0]["product_id"] == "10180"
    service = app.extensions["search_service"]
    warm = [record["elapsed_ms"] for record in records[1:]]
    report = {"timestamp_utc": datetime.now(timezone.utc).isoformat(), "real_encoder": True,
              "model": app.config["MODEL_PATH"], "model_revision": getattr(service.model.config, "_commit_hash", None),
              "device": service.device, "index_vectors": service.index.ntotal,
              "metadata_path": str(Path(metadata_path).resolve()), "metadata_skipped_rows": service.metadata.skipped_rows,
              "passed_cases": len(records), "warm_mean_ms": round(float(np.mean(warm)), 2),
              "warm_p95_ms": round(float(np.percentile(warm, 95)), 2),
              "image_regression": {"status": image.status_code, "response": image.json()},
              "invalid_http_requests_passed": 3, "records": records,
              "note": "Functional/filter/ranking correctness, not a labeled relevance evaluation. Vietnamese case checks Unicode handling only."}
    (output / "text-search.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def verify_browser(base, output, node, record_video, record_demo=False):
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(ROOT / ".cache/playwright"))
    from playwright.sync_api import expect, sync_playwright

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        frontend_port = sock.getsockname()[1]
    frontend = f"http://127.0.0.1:{frontend_port}"
    checks, requests_seen, errors = [], [], []
    demo_frames = []

    def capture_demo(page):
        if record_demo:
            with Image.open(io.BytesIO(page.screenshot())) as screenshot:
                demo_frames.append(screenshot.convert("RGB").resize((960, 675)))
    with (output / "vite.txt").open("w", encoding="utf-8") as log:
        vite = subprocess.Popen([node, str(ROOT / "node_modules/vite/bin/vite.js"), "--host", "127.0.0.1", "--port", str(frontend_port), "--strictPort"],
                                cwd=ROOT, env={**os.environ, "BACKEND_URL": base, "VITE_API_BASE_URL": ""}, stdout=log, stderr=subprocess.STDOUT)
        try:
            for _ in range(80):
                try:
                    if requests.get(frontend, timeout=1).status_code == 200:
                        break
                except requests.RequestException:
                    pass
                if vite.poll() is not None:
                    raise RuntimeError("Vite exited; see vite.txt")
                time.sleep(.25)
            else:
                raise RuntimeError("Vite did not start; see vite.txt")
            with sync_playwright() as p:
                browser = p.chromium.launch(channel="chrome", headless=True)
                options = {"viewport": {"width": 1280, "height": 900}}
                if record_video:
                    options.update(record_video_dir=str(output), record_video_size={"width": 1280, "height": 900})
                context = browser.new_context(**options)
                try:
                    page = context.new_page()
                    page.on("pageerror", lambda exc: errors.append(str(exc)))
                    page.goto(frontend + "/search/text")
                    page.locator("#query").fill("summer dress")
                    page.get_by_label("Gender", exact=True).select_option("Women")
                    page.get_by_label("Category", exact=True).select_option("Dresses")
                    page.get_by_label("Color", exact=True).select_option("Red")
                    capture_demo(page)
                    pending = []
                    page.route("**/api/v1/search/text", lambda route: pending.append(route))
                    page.get_by_role("button", name="DISCOVER", exact=True).click()
                    expect(page.get_by_role("status")).to_be_visible()
                    expect(page.get_by_role("button", name="SEARCHING...")).to_be_disabled()
                    capture_demo(page)
                    request_json = pending[0].request.post_data_json
                    assert request_json == {"query": "summer dress", "top_k": 50, "gender": "Women", "category": "Dresses", "color": "Red"}
                    requests_seen.append(request_json)
                    with page.expect_response("**/api/v1/search/text") as response_info:
                        pending[0].continue_()
                    results = response_info.value.json()["data"]
                    page.unroute("**/api/v1/search/text")
                    page.wait_for_url("**/results")
                    assert results and all(row["gender"] == "Women" and row["category"] == "Dresses" and row["color"] == "Red" for row in results)
                    expect(page.locator(".product-grid .product-card")).to_have_count(min(8, len(results)))
                    expect(page.get_by_label("Applied filters")).to_contain_text("Women")
                    expect(page.locator(".result-count")).to_contain_text(str(len(results)))
                    for image in page.locator(".product-grid .product-image").all():
                        image.scroll_into_view_if_needed()
                        expect(image).to_have_js_property("complete", True)
                        assert image.evaluate("img => img.naturalWidth > 0")
                    checks.append("Real text retrieval: exact JSON filters, loading/disable, metadata, chips and thumbnails")
                    page.evaluate("window.scrollTo(0,0)")
                    page.screenshot(path=str(output / "text-desktop.png"), full_page=True)
                    capture_demo(page)
                    if len(results) > 8:
                        first_ids = page.locator(".product-grid .product-id").all_text_contents()
                        page.get_by_role("button", name="Next page", exact=True).click()
                        assert page.locator(".product-grid .product-id").all_text_contents() != first_ids
                        checks.append("Pagination operates on returned top-k results")
                    page.set_viewport_size({"width": 390, "height": 844})
                    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
                    page.screenshot(path=str(output / "text-mobile.png"), full_page=True)
                    checks.append("Mobile results fit viewport")
                    page.set_viewport_size({"width": 1280, "height": 900})
                    page.goto(frontend + "/search/text")
                    page.get_by_role("button", name="CLEAR", exact=True).click()
                    expect(page.get_by_role("button", name="DISCOVER", exact=True)).to_be_disabled()
                    page.get_by_label("Category", exact=True).select_option("Backpacks")
                    with page.expect_request("**/api/v1/search/text") as request_info:
                        page.get_by_role("button", name="DISCOVER", exact=True).click()
                    requests_seen.append(request_info.value.post_data_json)
                    page.wait_for_url("**/results")
                    expect(page.locator(".product-grid .match-row").first).to_contain_text("FILTER MATCH")
                    expect(page.locator(".product-grid .meter")).to_have_count(0)
                    capture_demo(page)
                    checks.append("Filter-only selection sends empty query and displays no invented score")
                    page.goto(frontend + "/search/text")
                    page.get_by_label("Gender", exact=True).select_option("Boys")
                    page.get_by_label("Category", exact=True).select_option("Lipstick")
                    page.get_by_label("Color", exact=True).select_option("Gold")
                    page.get_by_role("button", name="DISCOVER", exact=True).click()
                    page.wait_for_url("**/results")
                    expect(page.get_by_role("status")).to_contain_text("No products matched")
                    expect(page.locator(".product-grid .product-card")).to_have_count(0)
                    capture_demo(page)
                    page.get_by_role("button", name="TRY ANOTHER SEARCH").click()
                    checks.append("Impossible filter combination returns empty results and retries text search")
                    page.route("**/api/v1/search/text", lambda route: route.fulfill(status=503, json={"success": False, "data": None, "error": "Text search unavailable"}))
                    page.get_by_role("button", name="DISCOVER", exact=True).click()
                    expect(page.get_by_role("alert")).to_contain_text("Text search unavailable")
                    expect(page.get_by_role("button", name="DISCOVER", exact=True)).to_be_enabled()
                    page.unroute("**/api/v1/search/text")
                    page.route("**/api/v1/search/text", lambda route: route.fulfill(json={"success": True, "data": {"wrong": "shape"}, "error": None}))
                    page.get_by_role("button", name="DISCOVER", exact=True).click()
                    expect(page.get_by_role("alert")).to_contain_text("invalid search results")
                    page.unroute("**/api/v1/search/text")
                    checks.append("503 and malformed response show errors with retry enabled (simulated responses)")
                    page.goto(frontend + "/search/image")
                    page.locator('input[type="file"]').set_input_files(str(ROOT / "data/d1/sample_images/10180.jpg"))
                    capture_demo(page)
                    page.get_by_role("button", name="DISCOVER MATCHES").click()
                    page.wait_for_url("**/results", timeout=120000)
                    expect(page.locator(".product-grid .product-card")).to_have_count(8)
                    for image in page.locator(".product-grid .product-image").all():
                        image.scroll_into_view_if_needed()
                        expect(image).to_have_js_property("complete", True)
                        assert image.evaluate("img => img.naturalWidth > 0")
                    page.evaluate("window.scrollTo(0,0)")
                    page.screenshot(path=str(output / "image-regression.png"), full_page=True)
                    capture_demo(page)
                    checks.append("Image upload still returns eight real results through the shared API helper")
                    assert not errors, errors
                    video = page.video
                finally:
                    context.close()
                    browser.close()
                report = {"checks": checks, "outgoing_text_requests": requests_seen, "page_errors": errors,
                          "video": Path(video.path()).name if video else None}
                if demo_frames:
                    demo_frames[0].save(output / "week8_demo.gif", save_all=True, append_images=demo_frames[1:], duration=1600, loop=0)
                    report["demo_gif"] = "week8_demo.gif"
                    report["demo_note"] = "Sequence of actual browser screenshots, resized for viewing; playback timing is illustrative, not a latency measurement."
                (output / "browser-results.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
                print(json.dumps(report, indent=2), flush=True)
        finally:
            vite.terminate()
            vite.wait(timeout=20)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image-dir", required=True)
    parser.add_argument("--metadata-path")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--with-ui", action="store_true")
    parser.add_argument("--record-video", action="store_true")
    parser.add_argument("--record-demo", action="store_true", help="Save an animated GIF of actual browser checkpoints; no video encoder needed")
    args = parser.parse_args()
    output = Path(args.output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    metadata_path = args.metadata_path or str(Path(args.image_dir).parent / "styles.csv")
    app = create_app({"IMAGE_DIR": args.image_dir, "METADATA_PATH": metadata_path})
    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    server = make_server("127.0.0.1", 0, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        verify_api(app, base, output, metadata_path)
        if args.with_ui:
            node = shutil.which("node") or next(str(p) for p in (ROOT / ".cache/node").glob("*/node.exe"))
            verify_browser(base, output, node, args.record_video, args.record_demo)
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


if __name__ == "__main__":
    main()
