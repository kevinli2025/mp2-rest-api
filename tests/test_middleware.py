import logging
import re

import pytest
from fastapi.testclient import TestClient

from main import app, storage


@pytest.mark.parametrize(('method', 'path', 'kwargs', 'status', 'level'), [
    ('GET', '/health', {}, 200, logging.INFO),
    ('POST', '/upload', {'files': {'file': ('invalid.txt', b'data')}}, 400, logging.WARNING),
    ('GET', '/datasets/999', {}, 404, logging.WARNING),
    ('GET', '/datasets/999?limit=0', {}, 422, logging.WARNING),
])
def test_request_logging(caplog, method, path, kwargs, status, level):
    with caplog.at_level(logging.INFO, logger='src.middleware'), TestClient(app) as client:
        response = client.request(method, path, **kwargs)
        second = client.get('/health')
    assert response.status_code == status
    request_id = response.headers['X-Request-ID']
    assert re.fullmatch(r'[0-9a-f]{8}', request_id)
    assert second.headers['X-Request-ID'] != request_id
    record = next(r for r in caplog.records if f'request_id={request_id}' in r.getMessage())
    assert record.levelno == level
    assert f'{method} {path.split("?")[0]} status={status}' in record.getMessage()
    assert re.search(r'duration=\d+\.\dms', record.getMessage())


def test_unexpected_exception_is_logged_and_hidden(monkeypatch, caplog):
    def fail(dataset_id):
        raise RuntimeError('internal failure details')

    monkeypatch.setattr(storage, 'get', fail)
    with caplog.at_level(logging.INFO, logger='src.middleware'), TestClient(app) as client:
        response = client.get('/datasets/1')
    assert response.status_code == 500
    assert response.json() == {'detail': 'Internal server error'}
    request_id = response.headers['X-Request-ID']
    records = [r for r in caplog.records if f'request_id={request_id}' in r.getMessage()]
    assert len(records) == 2
    assert all(r.levelno == logging.ERROR for r in records)
    assert records[0].exc_info[0] is RuntimeError
    assert 'GET /datasets/1 status=500' in records[1].getMessage()
