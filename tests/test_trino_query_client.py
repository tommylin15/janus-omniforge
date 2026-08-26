from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from packages.trino_query.client import QueryClient, QueryError


class Response:
    def __init__(self, payload: dict):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self.payload).encode()

    def __iter__(self):
        return iter(())


def fake_urlopen(request, timeout):
    if request.method == "POST":
        return Response({"id": "q1", "nextUri": "http://trino.test/v1/statement/q1/1"})
    if request.method == "GET":
        return Response({"id": "q1", "data": [["2330", 100]],
                         "stats": {"state": "FINISHED"}})
    return Response({})


def test_submit_poll_and_wait_keeps_query_state():
    client = QueryClient("http://trino.test", poll_interval=0)
    with patch("packages.trino_query.client.urlopen", side_effect=fake_urlopen):
        handle = client.submit("SELECT symbol, close FROM core.ohlcv")
        assert handle.query_id == "q1"
        assert client.wait(handle) == [("2330", 100)]


def test_poll_rejects_cross_origin_next_uri():
    client = QueryClient("http://trino.test")
    with patch("packages.trino_query.client.urlopen", return_value=Response({
        "id": "q1", "nextUri": "https://evil.test/steal"
    })):
        with pytest.raises(QueryError, match="unsafe polling URL"):
            client.submit("SELECT 1")


def test_wait_cancels_on_deadline_without_leaking_sql():
    client = QueryClient("http://trino.test", max_poll_seconds=-1)
    def never_finishes(request, timeout):
        if request.method == "POST":
            return Response({"id": "q1", "nextUri": "http://trino.test/v1/statement/q1/1"})
        if request.method == "GET":
            return Response({"id": "q1", "nextUri": "http://trino.test/v1/statement/q1/2",
                             "stats": {"state": "RUNNING"}})
        return Response({})

    with patch("packages.trino_query.client.urlopen", side_effect=never_finishes) as opened:
        handle = client.submit("SELECT secret_column FROM private_table")
        with pytest.raises(QueryError, match="polling timed out"):
            client.wait(handle)
        assert any(call.args[0].method == "DELETE" for call in opened.call_args_list)
