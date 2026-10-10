"""Week 9 real-catalog oracle, HTTP regression and browser integration checks."""
import argparse
import json
import logging
import os
import shutil
import socket
import subprocess
import threading
import time
from pathlib import Path
from unittest.mock import patch

import numpy as np
import requests
from werkzeug.serving import make_server

from src.backend.app import ROOT, create_app
from src.backend.search import FashionSearch
from scripts.verify_text_search import read_oracle

# Contract expectations maintained independently from the production rule module.
TOPS = set("Shirts|Tshirts|Tops|Sweatshirts|Sweaters|Jackets|Blazers|Waistcoat|Tunics|Rain Jacket|Shrug|Nehru Jackets".split("|"))
BOTTOMS = set("Jeans|Trousers|Shorts|Skirts|Capris|Leggings|Jeggings|Track Pants|Tights|Rain Trousers".split("|"))
SHOES = set("Casual Shoes|Formal Shoes|Sports Shoes|Flats|Heels|Sandals|Sports Sandals|Flip Flops".split("|"))
OUTFITS = set("Dresses|Jumpsuit|Sarees|Kurta Sets|Suits|Clothing Set".split("|"))
CASES = [
    ("Shirts", "Men", BOTTOMS | SHOES), ("Tshirts", "Men", BOTTOMS | SHOES),
    ("Tops", "Women", BOTTOMS | SHOES), ("Sweaters", "Women", BOTTOMS | SHOES),
    ("Jeans", "Women", TOPS | SHOES), ("Trousers", "Men", TOPS | SHOES),
    ("Skirts", "Women", TOPS | SHOES), ("Leggings", "Women", TOPS | SHOES),
    ("Sports Shoes", "Men", TOPS | BOTTOMS | OUTFITS | {"Kurtas", "Kurtis"}),
    ("Heels", "Women", TOPS | BOTTOMS | OUTFITS | {"Kurtas", "Kurtis"}),
    ("Casual Shoes", "Unisex", TOPS | BOTTOMS | OUTFITS | {"Kurtas", "Kurtis"}),
    ("Shirts", "Boys", BOTTOMS | SHOES), ("Dresses", "Girls", SHOES | {"Handbags", "Clutches"}),
    ("Dresses", "Women", SHOES | {"Handbags", "Clutches"}),
    ("Sarees", "Women", SHOES | {"Handbags", "Clutches"}),
    ("Handbags", "Women", OUTFITS | TOPS | SHOES),
    ("Kurtas", "Women", {"Churidar", "Salwar", "Patiala", "Leggings", "Jeans", "Trousers"} | SHOES),
    ("Churidar", "Women", {"Kurtas", "Kurtis"} | SHOES),
    ("Watches", "Men", set()), ("Lipstick", "Women", set()),
]


def verify_api(app, base, output, metadata_path):
    started = time.perf_counter()
    service = FashionSearch(app.config)
    app.extensions["search_service"] = service
    initialization_ms = round((time.perf_counter() - started) * 1000, 2)
    ids = service.ids
    oracle = read_oracle(metadata_path, ids)
    positions = {pid: i for i, pid in enumerate(ids)}
    vectors = np.load(ROOT / "embeddings/fashionclip_image_embeddings.npy").astype("float32")
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
    records = []
    # A call to either encoder makes these real API checks fail.
    with patch.object(service.model, "get_image_features", side_effect=AssertionError("Unexpected image inference")), \
         patch.object(service.model, "get_text_features", side_effect=AssertionError("Unexpected text inference")):
        for number, (category, gender, allowed) in enumerate(CASES):
            pid = sorted(pid for pid, row in oracle.items() if row["category"] == category and row["gender"] == gender)[0]
            genders = {gender} if gender in {"Boys", "Girls"} else ({"Men", "Women", "Unisex"} if gender == "Unisex" else {gender, "Unisex"})
            eligible = [other for other, row in oracle.items() if other != pid and row["category"] in allowed and row["gender"] in genders]
            top_k = 50 if number == 0 else 1 if number == 1 else 8
            path = f"{'/api/v1' if number % 2 else ''}/products/{pid}/related?top_k={top_k}"
            started = time.perf_counter()
            response = requests.get(base + path, timeout=180)
            elapsed = round((time.perf_counter() - started) * 1000, 2)
            body = response.json()
            assert response.status_code == 200 and body["success"] and body["error"] is None, body
            results = body["data"]
            assert len(results) == min(top_k, len(eligible))
            result_ids = [row["product_id"] for row in results]
            assert len(set(result_ids)) == len(result_ids) and pid not in result_ids
            for row in results:
                assert row["product_id"] in eligible
                assert row["source_product_id"] == pid and row["match_type"] == "complementary"
                assert all(row[key] == oracle[row["product_id"]][key] for key in ["category", "gender", "color"])
            if results:
                scores = vectors[[positions[other] for other in eligible]] @ vectors[positions[pid]]
                actual = [r["similarity_score"] for r in results]
                assert actual == sorted(actual, reverse=True)
                for row in results:
                    expected = vectors[positions[row["product_id"]]] @ vectors[positions[pid]]
                    assert abs(row["similarity_score"] - expected) < 2e-5
                better = {eligible[i] for i in np.flatnonzero(scores > actual[-1] + 2e-5)}
                assert better <= set(result_ids), "Omitted higher-ranking eligible neighbors"
            thumbnails = [requests.get(base + row["image_url"], timeout=20).status_code for row in results]
            assert all(status == 200 for status in thumbnails)
            records.append({"source_product_id": pid, "source_category": category, "source_gender": gender,
                            "allowed_categories": sorted(allowed), "allowed_genders": sorted(genders),
                            "route": path, "eligible_count": len(eligible), "elapsed_ms": elapsed,
                            "thumbnail_statuses": thumbnails, "passed": True, "response": body})
            print(f"Related case {number + 1}: {pid} / {category} / {gender}, {len(results)}/{len(eligible)} candidates, {elapsed} ms: PASS", flush=True)
    invalid = []
    for path, status in [("/products/not-in-catalog/related", 404), ("/products/10180/related?top_k=0", 400),
                         ("/products/10180/related?top_k=8&top_k=9", 400), ("/products/10180/related?gender=Men", 400)]:
        response = requests.get(base + path, timeout=20)
        assert response.status_code == status and response.json()["success"] is False
        invalid.append({"path": path, "status": status})
    text = requests.post(base + "/api/v1/search/text", json={"query": "white shirt", "gender": "Men", "category": "Shirts", "color": "White", "top_k": 8}, timeout=180)
    assert text.status_code == 200 and len(text.json()["data"]) == 8
    assert all(r["gender"] == "Men" and r["category"] == "Shirts" and r["color"] == "White" for r in text.json()["data"])
    with (ROOT / "data/d1/sample_images/10180.jpg").open("rb") as file:
        image = requests.post(base + "/api/v1/search/image", files={"image": ("10180.jpg", file, "image/jpeg")}, data={"top_k": 8}, timeout=180)
    assert image.status_code == 200 and len(image.json()["data"]) == 8 and image.json()["data"][0]["product_id"] == "10180"
    result = {"passed_cases": len(records), "index_vectors": len(ids), "initialization_ms": initialization_ms,
              "encoder_calls_during_related_checks": 0, "device": service.device,
              "model_revision": getattr(service.model.config, "_commit_hash", None),
              "metadata_skipped_rows": service.metadata.skipped_rows, "records": records, "invalid_requests": invalid,
              "image_regression": image.json(), "text_regression": text.json(),
              "note": "Independent NumPy ranking and CSV checks; cosine is not an outfit compatibility probability."}
    (output / "related-products.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def verify_browser(base, output):
    from playwright.sync_api import expect, sync_playwright
    node = shutil.which("node") or next(str(p) for p in (ROOT / ".cache/node").glob("*/node.exe"))
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    frontend = f"http://127.0.0.1:{port}"
    checks, errors, outgoing = [], [], []

    def record_check(description):
        checks.append(description)
        print("Browser PASS: " + description, flush=True)

    pattern = "**/api/v1/products/*/related?*"
    with (output / "vite.txt").open("w", encoding="utf-8") as log:
        vite = subprocess.Popen([node, str(ROOT / "node_modules/vite/bin/vite.js"), "--host", "127.0.0.1", "--port", str(port), "--strictPort"],
                                cwd=ROOT, env={**os.environ, "BACKEND_URL": base, "VITE_API_BASE_URL": ""}, stdout=log, stderr=subprocess.STDOUT)
        try:
            for _ in range(120):
                try:
                    if requests.get(frontend, timeout=1).status_code == 200:
                        break
                except requests.RequestException:
                    pass
                if vite.poll() is not None:
                    raise RuntimeError("Vite failed; see vite.txt")
                time.sleep(.25)
            else:
                raise RuntimeError("Vite startup timeout")
            with sync_playwright() as p:
                browser = p.chromium.launch(channel="chrome", headless=True)
                page = browser.new_page(viewport={"width": 1440, "height": 1000})
                page.on("pageerror", lambda exc: errors.append(str(exc)))
                page.on("request", lambda req: outgoing.append({"method": req.method, "url": req.url}) if "/related?" in req.url else None)
                main_cards = page.locator(".product-grid .product-card")
                panel = page.locator(".related-section")
                cards = panel.locator(".product-card")
                try:
                    page.goto(frontend + "/search/text", wait_until="domcontentloaded")
                    # Hold fetch before it reaches the network, so StrictMode's
                    # aborted mount request is handled by the native AbortSignal.
                    page.evaluate("""() => {
                        const nativeFetch = window.fetch.bind(window);
                        window.__relatedGate = new Promise(resolve => window.__releaseRelated = resolve);
                        window.fetch = async (url, options) => {
                            if (String(url).includes('/related?')) await window.__relatedGate;
                            return nativeFetch(url, options);
                        };
                    }""")
                    page.locator("#query").fill("white office shirt")
                    page.get_by_label("Gender", exact=True).select_option("Women")
                    page.get_by_label("Category", exact=True).select_option("Shirts")
                    page.get_by_label("Color", exact=True).select_option("White")
                    page.get_by_role("button", name="DISCOVER", exact=True).click()
                    page.wait_for_url("**/results", timeout=120000)
                    expect(main_cards).to_have_count(8)
                    expect(panel.get_by_role("status")).to_contain_text("Finding complementary")
                    expect(cards).to_have_count(0)
                    seed = page.locator("#related-source").input_value()
                    with page.expect_response(pattern) as response:
                        page.evaluate("window.__releaseRelated()")
                    assert response.value.request.url.endswith(f"/products/{seed}/related?top_k=8")
                    body = response.value.json()["data"]
                    assert len(body) == 8 and all(r["source_product_id"] == seed and r["category"] in BOTTOMS | SHOES for r in body)
                    expect(cards).to_have_count(8)
                    record_check("Real text results call related endpoint with source ID/top_k; loading and complementary results")
                    for img in panel.locator("img").all():
                        img.scroll_into_view_if_needed()
                        expect(img).to_have_js_property("complete", True)
                        assert img.evaluate("img => img.naturalWidth > 0")
                    panel.screenshot(path=str(output / "related-desktop.png"))

                    page.route(pattern, lambda route: route.fulfill(status=503, json={"success": False, "data": None, "error": "Related service unavailable"}))
                    page.locator("#related-source").select_option(index=1)
                    expect(panel.get_by_role("alert")).to_contain_text("Related service unavailable")
                    expect(main_cards).to_have_count(8)
                    expect(cards).to_have_count(0)
                    page.unroute(pattern)
                    with page.expect_response(pattern) as response:
                        panel.get_by_role("button", name="RETRY RECOMMENDATIONS").click()
                    assert all(r["source_product_id"] == page.locator("#related-source").input_value() for r in response.value.json()["data"])
                    expect(cards).to_have_count(8)
                    record_check("Changing seed, isolated 503 error and successful retry preserve main results")

                    page.route(pattern, lambda route: route.fulfill(json={"success": True, "data": {"wrong": "shape"}, "error": None}))
                    page.locator("#related-source").select_option(index=2)
                    expect(panel.get_by_role("alert")).to_contain_text("invalid search results")
                    expect(cards).to_have_count(0)
                    page.unroute(pattern)
                    page.route(pattern, lambda route: route.abort("failed"))
                    panel.get_by_role("button", name="RETRY RECOMMENDATIONS").click()
                    expect(panel.get_by_role("alert")).to_contain_text("Cannot reach")
                    page.unroute(pattern)
                    record_check("Malformed and network-failure responses show errors without fallback products (simulated)")

                    page.evaluate("() => { window.__relatedGate = new Promise(resolve => window.__releaseRelated = resolve); }")
                    page.locator("#related-source").select_option(index=3)
                    discarded_seed = page.locator("#related-source").input_value()
                    expect(panel.get_by_role("status")).to_contain_text("Finding complementary")
                    page.locator("#related-source").select_option(index=4)
                    latest_seed = page.locator("#related-source").input_value()
                    with page.expect_response(pattern) as response:
                        page.evaluate("window.__releaseRelated()")
                    latest = response.value.json()["data"]
                    expect(cards).to_have_count(8)
                    assert all(r["source_product_id"] == latest_seed for r in latest)
                    assert not any(r["url"].endswith(f"/products/{discarded_seed}/related?top_k=8") for r in outgoing)
                    expect(panel.locator(".product-id")).to_have_text([f"ID: {r['product_id']}" for r in latest])
                    record_check("Rapid source changes cancel stale requests and keep the latest recommendations")

                    page.goto(frontend + "/search/text", wait_until="domcontentloaded")
                    page.get_by_role("button", name="CLEAR", exact=True).click()
                    page.get_by_label("Category", exact=True).select_option("Watches")
                    page.get_by_role("button", name="DISCOVER", exact=True).click()
                    page.wait_for_url("**/results")
                    expect(panel.get_by_role("status")).to_contain_text("No complementary products")
                    expect(cards).to_have_count(0)
                    expect(main_cards).to_have_count(8)
                    record_check("Unsupported source category has a real empty state and preserves filter-only results")

                    page.goto(frontend + "/search/text", wait_until="domcontentloaded")
                    page.get_by_label("Gender", exact=True).select_option("Boys")
                    page.get_by_label("Category", exact=True).select_option("Lipstick")
                    page.get_by_role("button", name="DISCOVER", exact=True).click()
                    page.wait_for_url("**/results")
                    expect(main_cards).to_have_count(0)
                    expect(panel).to_have_count(0)
                    # A reload preserves React Router history state. Navigate away
                    # first to test a fresh catalog entry, not the empty search.
                    page.goto(frontend + "/", wait_until="domcontentloaded")
                    page.goto(frontend + "/results", wait_until="domcontentloaded")
                    expect(main_cards).to_have_count(8)
                    expect(panel).to_have_count(0)
                    record_check("Empty search hides recommendations; direct catalog browsing remains available")

                    page.goto(frontend + "/search/image", wait_until="domcontentloaded")
                    page.locator('input[type="file"]').set_input_files(str(ROOT / "data/d1/sample_images/10180.jpg"))
                    page.get_by_role("button", name="DISCOVER MATCHES").click()
                    page.wait_for_url("**/results", timeout=120000)
                    expect(main_cards).to_have_count(8)
                    expect(cards).to_have_count(8)
                    assert page.locator("#related-source").input_value() == "10180"
                    record_check("Real image upload also loads related products for its first result")
                    page.set_viewport_size({"width": 390, "height": 844})
                    for img in panel.locator("img").all():
                        img.scroll_into_view_if_needed()
                        expect(img).to_have_js_property("complete", True)
                        assert img.evaluate("img => img.naturalWidth > 0")
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                    panel.screenshot(path=str(output / "related-mobile.png"))
                    record_check("Mobile panel, source selector and real thumbnails fit viewport")
                    assert not errors, errors
                except Exception:
                    page.screenshot(path=str(output / "browser-failure.png"), full_page=True)
                    raise
                finally:
                    browser.close()
        finally:
            vite.terminate()
            vite.wait(timeout=20)
    report = {"checks": checks, "page_errors": errors, "outgoing_related_requests": outgoing,
              "note": "Valid/empty searches use real HTTP data; 503, malformed and network failures are simulated."}
    (output / "browser-results.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image-dir", required=True)
    parser.add_argument("--metadata-path")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--with-ui", action="store_true")
    parser.add_argument("--ui-only", action="store_true", help="Rerun browser checks without repeating the API oracle")
    args = parser.parse_args()
    output = Path(args.output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    metadata = args.metadata_path or str(Path(args.image_dir).parent / "styles.csv")
    app = create_app({"IMAGE_DIR": args.image_dir, "METADATA_PATH": metadata})
    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    server = make_server("127.0.0.1", 0, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        if not args.ui_only:
            verify_api(app, base, output, metadata)
        if args.with_ui or args.ui_only:
            verify_browser(base, output)
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


if __name__ == "__main__":
    main()
