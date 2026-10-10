"""Browser checks with a real backend. Requires the Vite dev server on port 5173."""
import argparse
import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import expect, sync_playwright
from werkzeug.serving import make_server

from src.backend.app import create_app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image-dir", required=True)
    parser.add_argument("--channel", default="chrome")
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args()
    output = Path(args.output_dir) if args.output_dir else Path("notebooks/logs") / (datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%SZ") + "-browser")
    output.mkdir(parents=True, exist_ok=True)
    app = create_app({"IMAGE_DIR": args.image_dir})
    server = make_server("127.0.0.1", 5000, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    checks = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(channel=args.channel, headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            errors = []
            page.on("pageerror", lambda exc: errors.append(str(exc)))
            page.goto("http://localhost:5173/search/image")
            upload = page.locator('input[type="file"]')
            button = page.get_by_role("button", name="DISCOVER MATCHES")
            expect(button).to_be_disabled()
            upload.set_input_files({"name": "bad.gif", "mimeType": "image/gif", "buffer": b"GIF89a"})
            expect(page.get_by_role("alert")).to_contain_text("Unsupported format")
            upload.set_input_files({"name": "big.jpg", "mimeType": "image/jpeg", "buffer": b"x" * (10 * 1024 * 1024 + 1)})
            expect(page.get_by_role("alert")).to_contain_text("too large")
            checks.append("Client rejects unsupported and oversized uploads")
            upload.set_input_files({"name": "broken.jpg", "mimeType": "image/jpeg", "buffer": b"not-a-jpeg"})
            button.click()
            expect(page.get_by_role("alert")).to_contain_text("Cannot decode", timeout=10000)
            expect(button).to_be_enabled()
            checks.append("Corrupt image shows server error and allows retry")
            upload.set_input_files(str(Path("data/d1/sample_images/10180.jpg").resolve()))
            expect(page.locator(".image-preview")).to_be_visible()
            button.click()
            expect(page.get_by_role("status")).to_contain_text("Finding similar products")
            expect(page.get_by_role("button", name="SEARCHING")).to_be_disabled()
            page.wait_for_url("**/results", timeout=120000)
            expect(page.locator(".product-grid .product-card")).to_have_count(8)
            for img in page.locator(".product-grid .product-image").all():
                img.scroll_into_view_if_needed()
                expect(img).to_be_visible()
                expect(img).to_have_js_property("complete", True)
                assert img.evaluate("img => img.naturalWidth > 0")
            expect(page.locator(".result-count")).to_have_text("8 ITEMS FOUND")
            expect(page.locator(".related-section")).to_be_visible()
            checks.append("Real upload through teammate API helper, loading state, eight ranked results and working thumbnails")
            page.evaluate("window.scrollTo(0, 0)")
            page.screenshot(path=str(output / "desktop.png"), full_page=True)
            page.set_viewport_size({"width": 390, "height": 844})
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
            page.screenshot(path=str(output / "mobile.png"), full_page=True)
            checks.append("Mobile results fit viewport")
            page.goto("http://localhost:5173/search/image")
            upload.set_input_files(str(Path("data/d1/sample_images/10180.jpg").resolve()))
            page.get_by_role("button", name="Remove selected image").click()
            expect(button).to_be_disabled()
            upload.set_input_files(str(Path("data/d1/sample_images/10180.jpg").resolve()))
            expect(button).to_be_enabled()
            checks.append("Remove and reselect the same image")
            page.route("**/api/v1/search/image", lambda route: route.fulfill(status=503, json={"success": False, "data": None, "error": "Search temporarily unavailable"}))
            button.click()
            expect(page.get_by_role("alert")).to_contain_text("temporarily unavailable")
            expect(button).to_be_enabled()
            page.unroute("**/api/v1/search/image")
            checks.append("Service unavailable response is visible and retry remains enabled")
            page.route("**/api/v1/search/image", lambda route: route.fulfill(json={"success": True, "data": {"invalid": True}, "error": None}))
            button.click()
            expect(page.get_by_role("alert")).to_contain_text("invalid search results")
            expect(button).to_be_enabled()
            page.unroute("**/api/v1/search/image")
            checks.append("Malformed API results show an error instead of mock results or a crash")
            page.route("**/api/v1/search/image", lambda route: route.fulfill(json={"success": True, "data": [], "error": None}))
            button.click()
            expect(page.get_by_role("status")).to_contain_text("No products matched")
            expect(page.locator(".product-grid .product-card")).to_have_count(0)
            checks.append("Empty response shows no mock products")
            assert not errors, errors
            browser.close()
        (output / "browser-results.json").write_text(json.dumps({"timestamp_utc": datetime.now(timezone.utc).isoformat(), "checks": checks, "page_errors": errors,
            "note": "Valid upload uses the real model/index. 503 and empty responses are simulated to exercise UI states."}, indent=2), encoding="utf-8")
        print(json.dumps(checks, indent=2))
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


if __name__ == "__main__":
    main()
