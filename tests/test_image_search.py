import io
from pathlib import Path

import pytest
from PIL import Image
from werkzeug.datastructures import MultiDict

from src.backend.app import MAX_IMAGE_BYTES, create_app


class RecordingSearch:
    def __init__(self):
        self.calls = []

    def search(self, image, top_k):
        self.calls.append((image.copy(), top_k))
        return [{"product_id": "10180", "image_url": "/dataset2/images/10180.jpg", "similarity_score": 0.9}]


@pytest.fixture
def setup():
    service = RecordingSearch()
    app = create_app({"TESTING": True, "IMAGE_DIR": "data/d1/sample_images"}, service)
    return app.test_client(), service


def image_bytes(fmt="JPEG", mode="RGB", size=(32, 48), **kwargs):
    output = io.BytesIO()
    Image.new(mode, size).save(output, format=fmt, **kwargs)
    return output.getvalue()


def post(client, content=None, name="test.jpg", mime="image/jpeg", **fields):
    return client.post("/search/image", data={"image": (io.BytesIO(image_bytes() if content is None else content), name, mime), **fields})


def assert_error(response, status, service):
    assert response.status_code == status
    assert response.json["success"] is False
    assert response.json["data"] is None
    assert isinstance(response.json["error"], str)
    assert not service.calls  # Reject before inference.


@pytest.mark.parametrize("fmt,ext,mime,mode", [
    ("JPEG", "JPG", "image/jpeg", "RGB"), ("JPEG", "jpeg", "image/jpeg", "CMYK"),
    ("PNG", "png", "image/png", "RGBA"), ("PNG", "png", "image/png", "L"),
    ("WEBP", "webp", "image/webp", "RGB"), ("JPEG", "jpg", "application/octet-stream", "RGB"),
])
def test_valid_formats(setup, fmt, ext, mime, mode):
    client, service = setup
    response = post(client, image_bytes(fmt, mode), f"test.{ext}", mime, top_k="5")
    assert response.status_code == 200
    assert response.json["success"] is True
    assert service.calls[0][0].mode == "RGB"
    assert service.calls[0][1] == 5


@pytest.mark.parametrize("path", sorted(Path("data/d1/sample_images").glob("*.jpg")), ids=lambda p: p.name)
def test_real_upload_decoding_with_stub_retrieval(setup, path):
    client, service = setup
    response = post(client, path.read_bytes(), path.name)
    assert response.status_code == 200
    assert service.calls[0][0].width > 0


@pytest.mark.parametrize("value", ["0", "51", "-1", "1.5", "abc", "", "1e2"])
def test_bad_top_k(setup, value):
    client, service = setup
    assert_error(post(client, top_k=value), 400, service)


@pytest.mark.parametrize("content,name,mime,status", [
    (b"", "empty.jpg", "image/jpeg", 400),
    (b"not an image", "fake.jpg", "image/jpeg", 400),
    (b"<svg/>", "image.svg", "image/svg+xml", 415),
    (image_bytes("GIF"), "image.gif", "image/gif", 415),
    (image_bytes("PNG"), "renamed.jpg", "image/jpeg", 415),
    (image_bytes(), "image.jpg", "text/plain", 415),
    (image_bytes(), "image", "image/jpeg", 415),
    (image_bytes()[:-20], "truncated.jpg", "image/jpeg", 400),
    (b"x" * (MAX_IMAGE_BYTES + 1), "large.jpg", "image/jpeg", 413),
    (b"x" * (MAX_IMAGE_BYTES + 100_000), "large.jpg", "image/jpeg", 413),
], ids=["empty", "fake", "svg", "gif", "renamed", "wrong-mime", "no-extension", "truncated", "file-too-large", "request-too-large"])
def test_rejected_files(setup, content, name, mime, status):
    client, service = setup
    assert_error(post(client, content, name, mime), status, service)


def test_exact_byte_limit(setup):
    client, service = setup
    content = image_bytes()
    assert post(client, content + b"\0" * (MAX_IMAGE_BYTES - len(content))).status_code == 200


def test_missing_and_duplicate_files(setup):
    client, service = setup
    assert_error(client.post("/search/image", data={"top_k": "10"}, content_type="multipart/form-data"), 400, service)
    assert_error(client.post("/search/image", json={"image": "x"}), 400, service)
    files = MultiDict([("image", (io.BytesIO(image_bytes()), "a.jpg")), ("image", (io.BytesIO(image_bytes()), "b.jpg"))])
    assert_error(client.post("/search/image", data=files), 400, service)


def test_excessive_pixels(setup):
    client, service = setup
    assert_error(post(client, image_bytes("PNG", "L", (5001, 5000)), "big.png", "image/png"), 413, service)


def test_animation(setup):
    client, service = setup
    output = io.BytesIO()
    Image.new("RGB", (20, 20), "red").save(output, "PNG", save_all=True,
        append_images=[Image.new("RGB", (20, 20), "blue")], duration=100, loop=0)
    assert_error(post(client, output.getvalue(), "animated.png", "image/png"), 415, service)


def test_orientation_and_alpha(setup):
    client, service = setup
    exif = Image.Exif()
    exif[274] = 6
    assert post(client, image_bytes(exif=exif)).status_code == 200
    assert service.calls[-1][0].size == (48, 32)
    assert post(client, image_bytes("PNG", "RGBA"), "alpha.png", "image/png").status_code == 200
    assert service.calls[-1][0].getpixel((0, 0)) == (255, 255, 255)


def test_alias_and_image_serving(setup):
    client, service = setup
    response = client.post("/api/v1/search/image", data={"image": (io.BytesIO(image_bytes()), "test.jpg")})
    assert response.status_code == 200
    response = client.get(response.json["data"][0]["image_url"])
    assert response.status_code == 200
    assert response.mimetype == "image/jpeg"
    assert client.get("/dataset2/images/../../requirements.txt").status_code == 404
    assert client.get("/dataset2/images/missing.jpg").json["success"] is False


def test_unavailable_model_and_inference_failure():
    class FailedSearch:
        def search(self, image, top_k):
            raise RuntimeError("private server detail")

    app = create_app({"TESTING": True}, FailedSearch())
    response = post(app.test_client())
    assert response.status_code == 500
    assert "private" not in response.json["error"]
    app = create_app({"TESTING": True, "IMAGE_DIR": "does-not-exist"})
    assert post(app.test_client()).status_code == 503


def test_cors_and_http_errors(setup):
    client, _ = setup
    response = client.options("/search/image", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"})
    assert response.headers["Access-Control-Allow-Origin"] == "http://localhost:5173"
    assert "Access-Control-Allow-Origin" not in client.get("/health", headers={"Origin": "https://unrelated.example"}).headers
    assert client.get("/search/image").status_code == 405
    assert client.get("/search/image").json["success"] is False


def test_teammate_configuration_aliases(monkeypatch, tmp_path):
    for key in ["IMAGE_DIR", "INDEX_PATH", "MODEL_PATH"]:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("FASHION_IMAGES_DIR", str(tmp_path))
    monkeypatch.setenv("FASHION_INDEX_PATH", "teammate.index")
    monkeypatch.setenv("MODEL_HF_NAME", "local-fashionclip")
    config = create_app().config
    assert config["IMAGE_DIR"] == str(tmp_path.resolve())
    assert config["INDEX_PATH"] == "teammate.index"
    assert config["MODEL_PATH"] == "local-fashionclip"


def test_primary_configuration_takes_precedence(monkeypatch, tmp_path):
    monkeypatch.setenv("FASHION_IMAGES_DIR", "other-images")
    monkeypatch.setenv("FASHION_INDEX_PATH", "other.index")
    monkeypatch.setenv("MODEL_HF_NAME", "other-model")
    monkeypatch.setenv("IMAGE_DIR", str(tmp_path))
    monkeypatch.setenv("INDEX_PATH", "primary.index")
    monkeypatch.setenv("MODEL_PATH", "primary-model")
    config = create_app().config
    assert config["IMAGE_DIR"] == str(tmp_path.resolve())
    assert config["INDEX_PATH"] == "primary.index"
    assert config["MODEL_PATH"] == "primary-model"


def test_direct_ip_frontend_origin(setup):
    client, _ = setup
    response = client.options("/search/image", headers={"Origin": "http://127.0.0.1:5173", "Access-Control-Request-Method": "POST"})
    assert response.headers["Access-Control-Allow-Origin"] == "http://127.0.0.1:5173"
