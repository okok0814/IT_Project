"""Run from the repository root: python -m src.backend.app."""
import io
import os
import re
import warnings
from pathlib import Path
from threading import Lock

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from PIL import Image, ImageOps, UnidentifiedImageError
from werkzeug.exceptions import HTTPException, RequestEntityTooLarge

from .search import FashionSearch, ProductNotFoundError
from .metadata import FILTER_FIELDS

ROOT = Path(__file__).resolve().parents[2]
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_IMAGE_PIXELS = 25_000_000
FORMATS = {".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG", ".webp": "WEBP"}
MIME_TYPES = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}


def create_app(config=None, search_service=None):
    app = Flask(__name__)
    app.config.from_mapping(
        MAX_CONTENT_LENGTH=MAX_IMAGE_BYTES + 64 * 1024,
        # Must exceed Werkzeug's 64 KiB multipart parser buffer, including file chunks.
        MAX_FORM_MEMORY_SIZE=512 * 1024,
        MAX_FORM_PARTS=10,
        IMAGE_DIR=os.environ.get("IMAGE_DIR") or os.environ.get("FASHION_IMAGES_DIR") or str(ROOT / "data/dataset2/images"),
        INDEX_PATH=os.environ.get("INDEX_PATH") or os.environ.get("FASHION_INDEX_PATH") or str(ROOT / "embeddings/index/fashionclip_image_embeddings_flat.index"),
        PRODUCT_IDS_PATH=os.environ.get("PRODUCT_IDS_PATH", str(ROOT / "embeddings/product_ids.npy")),
        MODEL_PATH=os.environ.get("MODEL_PATH") or os.environ.get("MODEL_HF_NAME") or "patrickjohncyh/fashion-clip",
        MODEL_CACHE=str(ROOT / ".cache/huggingface"),
        METADATA_PATH=os.environ.get("METADATA_PATH") or os.environ.get("FASHION_METADATA_PATH"),
    )
    if config:
        app.config.update(config)
    app.config["IMAGE_DIR"] = str(Path(app.config["IMAGE_DIR"]).resolve())
    CORS(app, origins=[os.environ.get("ALLOWED_ORIGIN", "http://localhost:5173"), "http://127.0.0.1:5173"])
    app.extensions["search_service"] = search_service
    load_lock = Lock()

    def success(data):
        return jsonify(success=True, data=data, error=None)

    def error(message, status):
        return jsonify(success=False, data=None, error=message), status

    @app.errorhandler(HTTPException)
    def http_error(exc):
        message = exc.description
        if isinstance(exc, RequestEntityTooLarge):
            message = "Text search request is too large. Maximum is 16 KiB." if request.path.endswith("/search/text") else "Upload is too large. Maximum image size is 10 MiB."
        return error(message, exc.code)

    def get_search_service():
        with load_lock:
            if app.extensions["search_service"] is None:
                app.extensions["search_service"] = FashionSearch(app.config)
        return app.extensions["search_service"]

    @app.get("/health")
    def health():
        return success({"status": "ok", "model_loaded": app.extensions["search_service"] is not None})

    @app.post("/search/image")
    @app.post("/api/v1/search/image")
    def search_image():
        if request.mimetype != "multipart/form-data":
            return error("Send multipart/form-data with one image file.", 400)
        files = list(request.files.items(multi=True))
        if len(files) != 1 or files[0][0] != "image" or not files[0][1].filename:
            return error("Provide exactly one file in the image field.", 400)
        if set(request.form) - {"top_k"} or len(request.form.getlist("top_k")) > 1:
            return error("Only one optional top_k field is supported for image search.", 400)
        try:
            top_k = int(request.form.get("top_k", "10"))
        except ValueError:
            return error("top_k must be an integer from 1 to 50.", 400)
        if not 1 <= top_k <= 50:
            return error("top_k must be an integer from 1 to 50.", 400)
        upload = files[0][1]
        expected_format = FORMATS.get(Path(upload.filename).suffix.lower())
        if expected_format is None:
            return error("Unsupported format. Use JPG, PNG or WEBP.", 415)
        if upload.mimetype not in {MIME_TYPES[expected_format], "application/octet-stream", ""}:
            return error("File type does not match its extension.", 415)
        contents = upload.read(MAX_IMAGE_BYTES + 1)
        if not contents:
            return error("The image file is empty.", 400)
        if len(contents) > MAX_IMAGE_BYTES:
            return error("Upload is too large. Maximum image size is 10 MiB.", 413)
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(contents)) as source:
                    if source.format != expected_format:
                        return error("Image content does not match its extension.", 415)
                    if source.width * source.height > MAX_IMAGE_PIXELS:
                        return error("Image dimensions are too large. Maximum is 25 megapixels.", 413)
                    if getattr(source, "n_frames", 1) != 1:
                        return error("Animated images are not supported. Upload a still image.", 415)
                    source.verify()
                with Image.open(io.BytesIO(contents)) as source:
                    source.load()
                    oriented = ImageOps.exif_transpose(source)
                    rgba = oriented.convert("RGBA")
                    rgb = Image.new("RGB", rgba.size, "white")
                    rgb.paste(rgba, mask=rgba.getchannel("A"))
        except (Image.DecompressionBombError, Image.DecompressionBombWarning):
            return error("Image dimensions are too large. Maximum is 25 megapixels.", 413)
        except (UnidentifiedImageError, OSError, ValueError, SyntaxError):
            return error("Cannot decode this image. It may be corrupt or truncated.", 400)
        try:
            return success(get_search_service().search(rgb, top_k))
        except (OSError, ImportError, ValueError):
            app.logger.exception("Image search configuration or data failure")
            return error("Image search is unavailable. Check the model, index, product IDs and IMAGE_DIR on the server.", 503)
        except Exception:
            app.logger.exception("Image search failed")
            return error("Image search failed. Please try again.", 500)
        finally:
            rgb.close()

    @app.get("/dataset2/images/<filename>")
    def product_image(filename):
        if Path(filename).suffix.lower() not in FORMATS:
            return error("Image not found.", 404)
        return send_from_directory(app.config["IMAGE_DIR"], filename)

    @app.post("/search/text")
    @app.post("/api/v1/search/text")
    def search_text():
        request.max_content_length = 16 * 1024
        if not request.is_json:
            return error("Send an application/json object for text search.", 415)
        body = request.get_json()
        if not isinstance(body, dict):
            return error("Text search body must be a JSON object.", 400)
        if set(body) - {"query", "top_k", *FILTER_FIELDS}:
            return error("Supported fields are query, top_k, gender, category and color.", 400)
        query = body.get("query", "")
        if not isinstance(query, str) or len(query) > 1000:
            return error("query must be a string of at most 1000 characters.", 400)
        query = " ".join(query.split())
        top_k = body.get("top_k", 10)
        if type(top_k) is not int or not 1 <= top_k <= 50:
            return error("top_k must be an integer from 1 to 50.", 400)
        filters = {}
        for field in FILTER_FIELDS:
            value = body.get(field)
            if value is None:
                continue
            if not isinstance(value, str) or len(value) > 100:
                return error(f"{field} must be a string of at most 100 characters or null.", 400)
            value = " ".join(value.split())
            if value:
                filters[field] = value
        if not query and not filters:
            return error("Enter a text query or choose at least one filter.", 400)
        try:
            return success(get_search_service().search_text(query, top_k, filters))
        except (OSError, ImportError, ValueError):
            app.logger.exception("Text search configuration or data failure")
            return error("Text search is unavailable. Check the model, index, product IDs, IMAGE_DIR and METADATA_PATH on the server.", 503)
        except Exception:
            app.logger.exception("Text search failed")
            return error("Text search failed. Please try again.", 500)

    @app.get("/products/<product_id>/related")
    @app.get("/api/v1/products/<product_id>/related")
    def related_products(product_id):
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", product_id):
            return error("product_id must contain 1 to 64 letters, digits, underscores or hyphens.", 400)
        if set(request.args) - {"top_k"} or len(request.args.getlist("top_k")) > 1:
            return error("Only one optional top_k parameter is supported for related products.", 400)
        raw_k = request.args.get("top_k", "8")
        if not re.fullmatch(r"[0-9]{1,3}", raw_k) or not 1 <= int(raw_k) <= 50:
            return error("top_k must be an integer from 1 to 50.", 400)
        try:
            return success(get_search_service().related_products(product_id, int(raw_k)))
        except ProductNotFoundError:
            return error("Product not found in the search catalog.", 404)
        except (OSError, ImportError, ValueError):
            app.logger.exception("Related products configuration or data failure")
            return error("Related products are unavailable. Check the index, product IDs, images, metadata and model configuration on the server.", 503)
        except Exception:
            app.logger.exception("Related products failed")
            return error("Related products failed. Please try again.", 500)

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5000")), debug=False)
