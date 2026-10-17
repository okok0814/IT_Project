from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import faiss
import numpy as np
import pytest

from src.backend.search import FashionSearch


@pytest.fixture
def catalog():
    rng = np.random.default_rng(4321)
    vectors = rng.normal(size=(103, 16)).astype('float32')
    faiss.normalize_L2(vectors)
    service = object.__new__(FashionSearch)
    service.index = faiss.IndexFlatIP(16)
    service.index.add(vectors)
    service.ids = np.array([str(i) for i in range(len(vectors))])
    service.metadata = SimpleNamespace(rows=[{'name': str(i)} for i in range(len(vectors))])
    return service, vectors


@pytest.mark.parametrize('kind', ['empty', 'one', 'sparse', 'dense', 'all'])
def test_filtered_top_k_matches_independent_numpy(catalog, kind):
    service, vectors = catalog
    mask = {'empty': np.zeros(103, dtype=bool), 'one': np.arange(103) == 102,
            'sparse': np.arange(103) % 13 == 0, 'dense': np.arange(103) % 3 != 0,
            'all': np.ones(103, dtype=bool)}[kind]
    query = vectors[17].reshape(1, -1).copy()
    for k in (1, 8, 50):
        results = service._search_vector(query.copy(), k, mask)
        eligible = np.flatnonzero(mask)
        scores = vectors[eligible] @ query[0]
        order = np.argsort(-scores)[:k]
        assert [r['product_id'] for r in results] == [str(i) for i in eligible[order]]
        assert [r['similarity_score'] for r in results] == pytest.approx(scores[order], abs=2e-6)


def test_concurrent_selectors_do_not_leak_between_requests(catalog):
    service, vectors = catalog
    def query(group):
        mask = np.arange(103) % 4 == group
        result = service._search_vector(vectors[0].reshape(1, -1).copy(), 8, mask)
        eligible = np.flatnonzero(mask)
        expected = eligible[np.argsort(-(vectors[eligible] @ vectors[0]))[:8]]
        assert [r['product_id'] for r in result] == [str(i) for i in expected]
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(query, list(range(4)) * 8))
