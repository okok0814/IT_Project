"""Gunicorn entrypoint: validate artifacts and warm both encoders before serving."""
from PIL import Image

from .app import create_app
from .search import FashionSearch


def create_ready_app():
    app = create_app()
    app.logger.warning("Loading local FashionCLIP, FAISS and catalog metadata...")
    service = FashionSearch(app.config)
    service._ensure_metadata()
    service.search_text("white shirt", 1, {})
    with Image.new("RGB", (224, 224), "white") as sample:
        service.search(sample, 1)
    app.extensions["search_service"] = service
    app.extensions["search_ready"] = True
    app.logger.warning("Search ready: %s catalog products; device=%s", len(service.ids), service.device)
    return app


app = create_ready_app()
