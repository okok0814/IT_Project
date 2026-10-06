import csv
from threading import Lock

import faiss
import numpy as np
import pytest

from src.backend.app import create_app
from src.backend.metadata import ProductMetadata
from src.backend.search import FashionSearch


class RecordingSearch:
    def __init__(self):
        self.calls = []

    def search_text(self, query, top_k, filters):
        self.calls.append((query, top_k, filters))
        return []


@pytest.fixture
def client_service():
    service = RecordingSearch()
    return create_app({"TESTING": True}, service).test_client(), service


@pytest.mark.parametrize("url", ["/search/text", "/api/v1/search/text"])
def test_exact_filter_forwarding(client_service, url):
    client, service = client_service
    response = client.post(url, json={"query": "  white  office shirt ", "top_k": 8,
                                     "gender": " Women ", "category": " Shirts ", "color": "Off  White"})
    assert response.status_code == 200
    assert response.json == {"success": True, "data": [], "error": None}
    assert service.calls == [("white office shirt", 8, {"gender": "Women", "category": "Shirts", "color": "Off White"})]


def test_defaults_empty_filters_and_unicode(client_service):
    client, service = client_service
    assert client.post("/search/text", json={"query": "áo sơ mi trắng", "gender": None, "color": "  "}).status_code == 200
    assert service.calls == [("áo sơ mi trắng", 10, {})]


def test_filter_only_allowed(client_service):
    client, service = client_service
    assert client.post("/search/text", json={"category": "Shirts"}).status_code == 200
    assert service.calls == [("", 10, {"category": "Shirts"})]


@pytest.mark.parametrize("body", [
    {}, [], "text", {"query": "   "}, {"query": None}, {"query": 7},
    {"query": "x" * 1001}, {"query": "shirt", "top_k": 0}, {"query": "shirt", "top_k": 51},
    {"query": "shirt", "top_k": True}, {"query": "shirt", "top_k": 2.5},
    {"query": "shirt", "top_k": "10"}, {"query": "shirt", "gender": ["Men"]},
    {"query": "shirt", "category": {"name": "Shirts"}}, {"query": "shirt", "color": True},
    {"query": "shirt", "color": "x" * 101}, {"query": "shirt", "colour": "Black"},
    {"query": "shirt", "filters": {"gender": "Men"}},
], ids=["missing-input", "array", "string", "blank", "null-query", "numeric-query", "long-query",
        "zero-k", "large-k", "bool-k", "float-k", "string-k", "array-gender", "object-category",
        "bool-color", "long-color", "misspelled-field", "nested-filters"])
def test_invalid_requests_do_not_call_model(client_service, body):
    client, service = client_service
    response = client.post("/search/text", json=body)
    assert response.status_code == 400
    assert response.json["success"] is False
    assert response.json["data"] is None
    assert not service.calls


def test_bad_json_content_type_and_body_limit(client_service):
    client, service = client_service
    for data, content_type, status in [("{", "application/json", 400), ("null", "application/json", 400),
                                       ("hello", "text/plain", 415), ('{"query":"' + "x" * 17000 + '"}', "application/json", 413)]:
        response = client.post("/search/text", data=data, content_type=content_type)
        assert response.status_code == status
        assert response.json["success"] is False
    assert not service.calls


@pytest.mark.parametrize("exc,status", [(FileNotFoundError("private file"), 503),
                                      (ValueError("bad metadata"), 503), (RuntimeError("private tensor"), 500)])
def test_failures_are_json_without_internal_details(exc, status):
    class FailedSearch:
        def search_text(self, *args):
            raise exc
    response = create_app({"TESTING": True}, FailedSearch()).test_client().post("/search/text", json={"query": "shirt"})
    assert response.status_code == status
    assert response.json["success"] is False
    assert "private" not in response.json["error"]


def write_metadata(path, rows, fields=None):
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields or list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


@pytest.fixture
def ranking_service(tmp_path):
    # Highest unfiltered vectors do NOT match. This catches filtering after top-k.
    service = object.__new__(FashionSearch)
    service.ids = np.array(["10", "20", "30", "40"])
    vectors = np.array([[1, 0], [.9, .1], [.6, .8], [0, 1]], dtype="float32")
    faiss.normalize_L2(vectors)
    service.index = faiss.IndexFlatIP(2)
    service.index.add(vectors)
    service.metadata_path = tmp_path / "metadata.csv"
    # Deliberately reversed CSV rows: alignment must use IDs.
    write_metadata(service.metadata_path, [
        {"product_id": "40", "gender": "Women", "category": "Shirts", "color": "Off White"},
        {"product_id": "30", "gender": "Women", "category": "Shirts", "color": "Off White"},
        {"product_id": "20", "gender": "Men", "category": "Shirts", "color": "Black"},
        {"product_id": "10", "gender": "Men", "category": "Shoes", "color": "Black"},
    ])
    service.metadata = None
    service.metadata_lock = Lock()
    service._embed_text = lambda query: np.array([[10, 0]], dtype="float32")
    return service


def test_filters_apply_before_top_k_and_rows_align(ranking_service):
    result = ranking_service.search_text("shirt", 1, {"gender": " women ", "category": "SHIRTS", "color": "off-white"})
    assert [r["product_id"] for r in result] == ["30"]
    assert result[0]["similarity_score"] == pytest.approx(.6)
    assert result[0]["gender"] == "Women"
    assert result[0]["color"] == "Off White"


def test_fewer_than_k_and_unknown_combination(ranking_service):
    result = ranking_service.search_text("shirt", 50, {"gender": "Women"})
    assert [r["product_id"] for r in result] == ["30", "40"]
    ranking_service._embed_text = lambda query: pytest.fail("No-match filters should not encode")
    assert ranking_service.search_text("shirt", 10, {"gender": "Women", "category": "Shoes"}) == []
    assert ranking_service.search_text("shirt", 10, {"color": "nonexistent"}) == []


def test_filter_only_does_not_invent_scores(ranking_service):
    ranking_service._embed_text = lambda query: pytest.fail("Filter-only must not encode")
    result = ranking_service.search_text("", 50, {"gender": "Men"})
    assert [r["product_id"] for r in result] == ["10", "20"]
    assert all(r["similarity_score"] is None and r["match_type"] == "metadata" for r in result)


def test_unfiltered_text_and_image_rank_regression(ranking_service):
    text = ranking_service.search_text("shirt", 2, {})
    image = ranking_service._search_vector(np.array([[1, 0]], dtype="float32"), 2)
    assert [r["product_id"] for r in text] == [r["product_id"] for r in image] == ["10", "20"]
    assert all("gender" in r for r in text)
    assert all("gender" not in r for r in image)


@pytest.mark.parametrize("vector", [np.array([[0, 0]]), np.array([[np.nan, 1]]), np.array([[1, 0, 0]])])
def test_invalid_query_embedding_rejected(ranking_service, vector):
    with pytest.raises(ValueError, match="Invalid query embedding"):
        ranking_service._search_vector(vector, 10)


def test_raw_styles_schema_and_missing_values(tmp_path):
    path = tmp_path / "styles.csv"
    write_metadata(path, [{"id": "10", "gender": "Men", "articleType": "Shirts", "baseColour": "navy", "productDisplayName": "A navy shirt"},
                          {"id": "20", "gender": "", "articleType": "Tshirts", "baseColour": "", "productDisplayName": ""}])
    metadata = ProductMetadata(path, ["20", "10"])
    assert metadata.rows[0]["color"] == "Unknown"
    assert metadata.rows[1]["name"] == "A navy shirt"
    assert metadata.mask({"color": "Navy Blue"}).tolist() == [False, True]


def test_metadata_failures(tmp_path):
    path = tmp_path / "metadata.csv"
    row = {"product_id": "10", "gender": "Men", "category": "Shirts", "color": "Black"}
    write_metadata(path, [row])
    with pytest.raises(ValueError, match="missing"):
        ProductMetadata(path, ["10", "20"])
    write_metadata(path, [row, row])
    with pytest.raises(ValueError, match="Duplicate"):
        ProductMetadata(path, ["10"])
    write_metadata(path, [{"unrelated": "x"}])
    with pytest.raises(ValueError, match="must contain"):
        ProductMetadata(path, ["10"])


def test_metadata_env_alias(monkeypatch):
    monkeypatch.delenv("METADATA_PATH", raising=False)
    monkeypatch.setenv("FASHION_METADATA_PATH", "alias.csv")
    assert create_app().config["METADATA_PATH"] == "alias.csv"
    monkeypatch.setenv("METADATA_PATH", "primary.csv")
    assert create_app().config["METADATA_PATH"] == "primary.csv"
