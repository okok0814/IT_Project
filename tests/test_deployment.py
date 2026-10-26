import runpy

import pytest

import src.backend.app as app_module
import src.backend.search as search_module


def test_model_cache_is_configurable(monkeypatch, tmp_path):
    monkeypatch.setenv('MODEL_CACHE', str(tmp_path))
    assert app_module.create_app().config['MODEL_CACHE'] == str(tmp_path)


def test_liveness_does_not_claim_readiness():
    app = app_module.create_app({'TESTING': True})
    client = app.test_client()
    assert client.get('/health').status_code == 200
    response = client.get('/ready')
    assert response.status_code == 503
    assert response.json['success'] is False
    app.extensions['search_ready'] = True
    assert client.get('/ready').json == {
        'success': True, 'data': {'status': 'ready', 'model_loaded': True}, 'error': None}


@pytest.mark.parametrize('failure', [None, 'load', 'metadata', 'text', 'image'])
def test_wsgi_only_marks_ready_after_complete_warmup(monkeypatch, failure):
    app = app_module.create_app({'TESTING': True})
    calls = []

    def step(name):
        assert app.extensions['search_ready'] is False
        calls.append(name)
        if failure == name:
            raise ValueError('invalid deployment artifact')

    class FakeSearch:
        ids = ['1']
        device = 'cpu'

        def __init__(self, config): step('load')
        def _ensure_metadata(self): step('metadata')
        def search_text(self, query, k, filters): step('text')
        def search(self, image, k):
            assert image.mode == 'RGB'
            step('image')

    monkeypatch.setattr(app_module, 'create_app', lambda: app)
    monkeypatch.setattr(search_module, 'FashionSearch', FakeSearch)
    if failure:
        with pytest.raises(ValueError, match='invalid deployment artifact'):
            runpy.run_module('src.backend.wsgi')
        assert app.extensions['search_ready'] is False
        assert app.extensions['search_service'] is None
    else:
        loaded = runpy.run_module('src.backend.wsgi')['app']
        assert calls == ['load', 'metadata', 'text', 'image']
        assert loaded is app
        assert app.test_client().get('/ready').status_code == 200
