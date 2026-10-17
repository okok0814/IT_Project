from concurrent.futures import Future, ThreadPoolExecutor
import io
from threading import Barrier, Event, Lock

from PIL import Image
import pytest

from src.backend.app import create_app
from src.backend.cache import ResultCache
import src.backend.cache as cache_module


def test_ttl_lru_empty_results_and_defensive_copies():
    clock = [0.0]
    cache = ResultCache(2, 10, clock=lambda: clock[0])
    value, status = cache.get_or_compute('a', lambda: [{'id': 'a'}])
    assert status == 'MISS'
    value[0]['id'] = 'changed'
    assert cache.get_or_compute('a', lambda: pytest.fail('hit')) == ([{'id': 'a'}], 'HIT')
    cache.get_or_compute('b', lambda: [])
    cache.get_or_compute('a', lambda: None)  # a becomes most recently used
    cache.get_or_compute('c', lambda: [])  # b is evicted
    assert cache.get_or_compute('b', lambda: [1]) == ([1], 'MISS')
    assert len(cache._entries) == 2
    clock[0] = 10.0  # boundary expires; reads do not extend the TTL
    assert cache.get_or_compute('b', lambda: []) == ([], 'MISS')
    assert cache.get_or_compute('b', lambda: pytest.fail('empty is cached')) == ([], 'HIT')
    cache.clear()
    assert cache.get_or_compute('b', lambda: [2]) == ([2], 'MISS')


@pytest.mark.parametrize('size,ttl', [(0, 10), (10, 0)])
def test_disable_cache(size, ttl):
    cache = ResultCache(size, ttl)
    for _ in range(2):
        assert cache.get_or_compute('key', lambda: []) == ([], 'BYPASS')
    assert not cache._entries and not cache._pending


@pytest.mark.parametrize('size,ttl', [(-1, 1), (1, -1), (1, float('nan')), (1, float('inf'))])
def test_invalid_configuration(size, ttl):
    with pytest.raises(ValueError):
        ResultCache(size, ttl)


@pytest.mark.parametrize('fail', [False, True])
def test_concurrent_identical_requests_share_work_and_release_on_failure(monkeypatch, fail):
    entered, waiters_ready, release = Event(), Event(), Event()
    counter_lock = Lock()
    waiters = []
    class ObservedFuture(Future):
        def result(self, timeout=None):
            with counter_lock:
                waiters.append(1)
                if len(waiters) == 3:
                    waiters_ready.set()
            return super().result(timeout=5)
    monkeypatch.setattr(cache_module, 'Future', ObservedFuture)
    cache = ResultCache()
    calls = []
    def compute():
        calls.append(1)
        entered.set()
        assert release.wait(5)
        if fail:
            raise ValueError('temporary')
        return [{'id': 'x'}]
    with ThreadPoolExecutor(max_workers=4) as pool:
        owner = pool.submit(cache.get_or_compute, 'x', compute)
        assert entered.wait(5)
        others = [pool.submit(cache.get_or_compute, 'x', compute) for _ in range(3)]
        try:
            assert waiters_ready.wait(5)
        finally:
            release.set()
        if fail:
            for task in [owner, *others]:
                with pytest.raises(ValueError, match='temporary'):
                    task.result(timeout=5)
            assert cache.get_or_compute('x', lambda: 'retry') == ('retry', 'MISS')
        else:
            values = [task.result(timeout=5) for task in [owner, *others]]
            assert sorted(status for _, status in values) == ['COALESCED'] * 3 + ['MISS']
            values[0][0][0]['id'] = 'mutated'
            assert all(value == [{'id': 'x'}] for value, _ in values[1:])
    assert calls == [1]
    assert not cache._pending


def test_distinct_keys_can_compute_concurrently():
    cache = ResultCache()
    barrier = Barrier(2)
    def compute():
        barrier.wait(timeout=5)
        return 1
    with ThreadPoolExecutor(max_workers=2) as pool:
        tasks = [pool.submit(cache.get_or_compute, key, compute) for key in ['a', 'b']]
        assert [task.result(timeout=5) for task in tasks] == [(1, 'MISS'), (1, 'MISS')]


def test_clear_during_computation_cannot_restore_old_result():
    cache = ResultCache()
    entered, release = Event(), Event()
    def old_compute():
        entered.set()
        assert release.wait(5)
        return 'old'
    with ThreadPoolExecutor(max_workers=1) as pool:
        old = pool.submit(cache.get_or_compute, 'x', old_compute)
        try:
            assert entered.wait(5)
            cache.clear()
            assert cache.get_or_compute('x', lambda: 'new') == ('new', 'MISS')
        finally:
            release.set()
        assert old.result(timeout=5) == ('old', 'MISS')
    assert cache.get_or_compute('x', lambda: None) == ('new', 'HIT')


class RecordingService:
    def __init__(self):
        self.calls = []

    def search_text(self, query, top_k, filters):
        self.calls.append(('text', query, top_k, filters))
        return [{'query': query, 'top_k': top_k, **filters}]

    def related_products(self, product_id, top_k):
        self.calls.append(('related', product_id, top_k))
        return [{'product_id': product_id, 'top_k': top_k}]

    def search(self, image, top_k):
        self.calls.append(('image', image.getpixel((0, 0)), top_k))
        return [{'pixel': image.getpixel((0, 0)), 'top_k': top_k}]


def test_text_cache_normalization_aliases_and_parameter_isolation():
    service = RecordingService()
    client = create_app({'TESTING': True}, service).test_client()
    body = {'query': 'white   shirt', 'color': 'off-white', 'top_k': 8}
    first = client.post('/search/text', json=body)
    second = client.post('/api/v1/search/text', json={**body, 'query': ' white shirt ', 'color': 'Off White'})
    assert first.headers['X-Search-Cache'] == 'MISS'
    assert second.headers['X-Search-Cache'] == 'HIT'
    assert first.json == second.json
    for delta in [{'query': 'black shirt'}, {'top_k': 9}, {'color': 'Black'}, {'gender': 'Men'}, {'category': 'Shirts'}]:
        assert client.post('/search/text', json={**body, **delta}).headers['X-Search-Cache'] == 'MISS'
    assert len(service.calls) == 6
    assert client.post('/search/text', json={**body, 'unexpected': 'x'}).status_code == 400
    assert len(service.calls) == 6


def test_related_keys_and_apps_are_isolated():
    service = RecordingService()
    app = create_app({'TESTING': True}, service)
    client = app.test_client()
    assert client.get('/products/123/related').headers['X-Search-Cache'] == 'MISS'
    assert client.get('/api/v1/products/123/related?top_k=08').headers['X-Search-Cache'] == 'HIT'
    assert client.get('/products/123/related?top_k=9').headers['X-Search-Cache'] == 'MISS'
    assert client.get('/products/124/related').headers['X-Search-Cache'] == 'MISS'
    assert client.get('/products/123/related?top_k=8&top_k=8').status_code == 400
    other = create_app({'TESTING': True}, service).test_client()
    assert other.get('/products/123/related').headers['X-Search-Cache'] == 'MISS'
    assert len(service.calls) == 4


def test_image_keys_use_bytes_and_top_k_and_never_skip_validation():
    service = RecordingService()
    client = create_app({'TESTING': True}, service).test_client()
    def upload(color, filename='photo.png', top_k='10', mime='image/png'):
        stream = io.BytesIO()
        Image.new('RGB', (8, 8), color).save(stream, format='PNG')
        stream.seek(0)
        return client.post('/search/image', data={'image': (stream, filename, mime), 'top_k': top_k})
    assert upload('red').headers['X-Search-Cache'] == 'MISS'
    assert upload('red', filename='renamed.png').headers['X-Search-Cache'] == 'HIT'
    assert upload('blue').headers['X-Search-Cache'] == 'MISS'
    assert upload('red', top_k='8').headers['X-Search-Cache'] == 'MISS'
    assert upload('red', filename='photo.jpg', mime='image/jpeg').status_code == 415
    assert upload('red', mime='text/plain').status_code == 415
    assert len(service.calls) == 3


def test_api_failure_is_not_cached_and_cache_can_be_disabled():
    class Transient(RecordingService):
        def related_products(self, *args):
            if not self.calls:
                self.calls.append('failure')
                raise ValueError('temporary configuration error')
            return super().related_products(*args)
    service = Transient()
    client = create_app({'TESTING': True}, service).test_client()
    assert client.get('/products/123/related').status_code == 503
    assert client.get('/products/123/related').headers['X-Search-Cache'] == 'MISS'
    assert client.get('/products/123/related').headers['X-Search-Cache'] == 'HIT'
    disabled = create_app({'TESTING': True, 'SEARCH_CACHE_SIZE': 0}, service).test_client()
    for _ in range(2):
        assert disabled.get('/products/123/related').headers['X-Search-Cache'] == 'BYPASS'
