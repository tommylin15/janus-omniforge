"""Public HTTP boundaries use harmless local files and bounded fake streams."""
import asyncio

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

import services.api.app as module


@pytest.fixture
def web(tmp_path, monkeypatch):
    monkeypatch.setattr(module, '__file__', str(tmp_path / 'services/api/app.py'))
    root = tmp_path / 'apps/user_app/build/web'
    root.mkdir(parents=True)
    (root / 'index.html').write_text('user shell')
    (root / 'admin-index.html').write_text('admin shell')
    (root / 'bundle.js').write_text('public bundle')
    outside = root.parent / 'private.txt'
    outside.write_text('harmless private sentinel')
    return TestClient(module.create_app(object(), object())), root, outside


@pytest.mark.parametrize('path', ['%2e%2e/private.txt', '%2e%2e%2fprivate.txt', '%2fetc/passwd'])
def test_public_assets_reject_directory_escape(web, path):
    client, _, _ = web
    response = client.get('/app/' + path)
    assert response.status_code == 404
    assert 'harmless private sentinel' not in response.text


def test_public_assets_and_spa_fallback_still_work(web):
    client, _, _ = web
    assert client.get('/app/bundle.js').text == 'public bundle'
    assert client.get('/app/stocks/2330').text == 'user shell'
    assert client.get('/app/admin/stocks').text == 'admin shell'


def test_public_assets_reject_symlink_escape(web):
    client, root, outside = web
    try:
        (root / 'link.txt').symlink_to(outside)
    except OSError:
        pytest.skip('Creating symlinks requires local OS privilege; Linux CI covers this.')
    assert client.get('/app/link.txt').status_code == 404


@pytest.mark.parametrize('path,limit,status', [('/mcp', 65536, 413), ('/oauth/register', 4096, 400),
    ('/oauth/token', 16384, 413), ('/oauth/revoke', 16384, 413), ('/oauth/authorize/complete', 16384, 413)])
def test_public_protocol_rejects_stream_before_reading_the_entire_body(path, limit, status):
    app = module.create_app(object(), object())
    endpoint = next(route.endpoint for route in app.routes if getattr(route, 'path', None) == path)
    received = 0

    async def receive():
        nonlocal received
        received += 1
        assert received <= 2, 'Oversized unauthenticated body was drained into memory'
        return {'type': 'http.request', 'body': b'x' * (limit // 2 + 1), 'more_body': True}

    async def check():
        request = Request({'type': 'http', 'method': 'POST', 'path': path, 'headers': []}, receive)
        try:
            response = await endpoint(request)
        except module.HTTPException as error:
            assert error.status_code == status
        else:
            assert response.status_code == status
        assert received == 2

    asyncio.run(check())


@pytest.mark.parametrize('limit', [4096, 16384, 65536])
def test_bounded_body_accepts_exact_limit_without_trusting_content_length(limit):
    async def receive():
        return {'type': 'http.request', 'body': b'x' * limit, 'more_body': False}

    request = Request({'type': 'http', 'method': 'POST', 'path': '/mcp',
                       'headers': [(b'content-length', b'1')]}, receive)
    assert asyncio.run(module._bounded_body(request, limit)) == b'x' * limit
