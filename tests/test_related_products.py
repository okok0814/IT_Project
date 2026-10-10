import csv
from threading import Lock

import faiss
import numpy as np
import pytest

from src.backend.app import create_app
from src.backend.search import FashionSearch, ProductNotFoundError
from src.backend.related import COMPLEMENTARY_CATEGORIES, COMPATIBLE_GENDERS


class RecordingSearch:
    def __init__(self):
        self.calls = []

    def related_products(self, product_id, top_k):
        self.calls.append((product_id, top_k))
        return []


@pytest.fixture
def client_service():
    service = RecordingSearch()
    return create_app({"TESTING": True}, service).test_client(), service


@pytest.mark.parametrize("prefix", ["", "/api/v1"])
def test_routes_defaults_and_forwarding(client_service, prefix):
    client, service = client_service
    response = client.get(f"{prefix}/products/10180/related")
    assert response.status_code == 200
    assert response.json == {"success": True, "data": [], "error": None}
    assert client.get(f"{prefix}/products/10180/related?top_k=50").status_code == 200
    assert service.calls == [("10180", 8), ("10180", 50)]


@pytest.mark.parametrize("query", ["top_k=0", "top_k=51", "top_k=-1", "top_k=1.5", "top_k=true",
                                 "top_k=", "top_k=no", "top_k=1000000000000", "top_k=2&top_k=3",
                                 "category=Shirts", "gender=Men", "top_k=8&color=Black"])
def test_invalid_parameters_rejected_before_search(client_service, query):
    client, service = client_service
    response = client.get("/products/10180/related?" + query)
    assert response.status_code == 400
    assert response.json["success"] is False and response.json["data"] is None
    assert not service.calls


@pytest.mark.parametrize("product_id", ["has%20spaces", "x" * 65, "..", "%3Cscript%3E"])
def test_invalid_ids(client_service, product_id):
    client, service = client_service
    assert client.get(f"/products/{product_id}/related").status_code == 400
    assert not service.calls


def test_wrong_method(client_service):
    client, service = client_service
    assert client.post("/products/10180/related").status_code == 405
    assert not service.calls


@pytest.mark.parametrize("exc,status", [(ProductNotFoundError("secret"), 404),
    (FileNotFoundError("secret path"), 503), (ValueError("secret metadata"), 503),
    (RuntimeError("secret internal failure"), 500)])
def test_errors_are_sanitized(exc, status):
    class Failed:
        def related_products(self, *args):
            raise exc
    response = create_app({"TESTING": True}, Failed()).test_client().get("/products/10180/related")
    assert response.status_code == status
    assert response.json["success"] is False and "secret" not in response.json["error"]


@pytest.fixture
def service(tmp_path):
    # Highest neighbors are self, another shirt, a women's item and a child's shoe.
    # Valid complementary adult products are lower in the global ranking.
    specs = [
        ("seed", "Shirts", "Men", 1), ("shirt", "Shirts", "Men", .999),
        ("women", "Jeans", "Women", .99), ("child", "Sports Shoes", "Boys", .98),
        ("pants", "Trousers", "Men", .8), ("shoes", "Casual Shoes", "Men", .6),
        ("unisex", "Sports Shoes", "Unisex", .4), ("watch", "Watches", "Men", .9),
        ("girl", "Dresses", "Girls", .3), ("girl-shoes", "Flats", "Girls", .2),
        ("unknown", "Tops", "", .1),
    ]
    service = object.__new__(FashionSearch)
    service.ids = np.array([row[0] for row in specs])
    vectors = np.array([[score, np.sqrt(1-score**2)] for _, _, _, score in specs], dtype="float32")
    service.index = faiss.IndexFlatIP(2)
    service.index.add(vectors)
    service.metadata_path = tmp_path / "metadata.csv"
    with service.metadata_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["product_id", "category", "gender", "color"])
        writer.writerows((pid, category, gender, "Black") for pid, category, gender, _ in reversed(specs))
    service.metadata = None
    service.metadata_lock = Lock()
    service._embed_text = lambda *_: pytest.fail("Related retrieval must reuse the stored vector")
    service.search = lambda *_: pytest.fail("Related retrieval must not encode images")
    return service


def test_filter_before_k_and_id_alignment(service):
    results = service.related_products("seed", 2)
    assert [r["product_id"] for r in results] == ["pants", "shoes"]
    assert [r["similarity_score"] for r in results] == pytest.approx([.8, .6])
    assert [r["category"] for r in results] == ["Trousers", "Casual Shoes"]
    assert all(r["source_product_id"] == "seed" and r["match_type"] == "complementary" for r in results)


def test_underfilled_k_excludes_self_same_category_and_incompatible_gender(service):
    results = service.related_products("seed", 50)
    assert [r["product_id"] for r in results] == ["pants", "shoes", "unisex"]
    assert all(r["similarity_score"] <= 1 for r in results)


def test_children_are_not_mixed_with_adults(service):
    assert [r["product_id"] for r in service.related_products("girl", 8)] == ["girl-shoes"]
    assert service.related_products("child", 8) == []


def test_unisex_can_recommend_adult_men_and_women(service):
    ids = {r["product_id"] for r in service.related_products("unisex", 50)}
    assert {"seed", "shirt", "pants", "women"} == ids


def test_unsupported_category_unknown_gender_and_unknown_id(service):
    assert service.related_products("watch", 8) == []
    assert service.related_products("unknown", 8) == []
    with pytest.raises(ProductNotFoundError):
        service.related_products("absent", 8)


@pytest.mark.parametrize("source,target", [
    ("shirts", "jeans"), ("tshirts", "sports shoes"), ("jeans", "shirts"),
    ("dresses", "heels"), ("dresses", "handbags"), ("casual shoes", "trousers"),
    ("kurtas", "churidar"), ("salwar", "kurtis"), ("clutches", "dresses"),
])
def test_documented_rule_examples(source, target):
    assert target in COMPLEMENTARY_CATEGORIES[source]


def test_rule_invariants():
    assert all(source not in targets and targets for source, targets in COMPLEMENTARY_CATEGORIES.items())
    assert "watches" not in COMPLEMENTARY_CATEGORIES
    assert not COMPATIBLE_GENDERS["boys"] & COMPATIBLE_GENDERS["unisex"]
