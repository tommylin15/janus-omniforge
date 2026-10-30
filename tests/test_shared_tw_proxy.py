"""Life/Janus private Taiwan egress contract, no external network calls."""
import io
import json
from urllib.error import HTTPError
from unittest.mock import patch

import pytest

from services.api.intraday_quotes import MisQuotes
from services.api.tw_proxy_client import fetch_mis_via_tw_proxy


def test_reject_unrelated_or_insecure_url():
    for url in ("http://mis.twse.com.tw/stock/api/getStockInfo.jsp",
                "https://127.0.0.1/admin", "https://example.org/stock/api/getStockInfo.jsp"):
        with pytest.raises(ValueError):
            fetch_mis_via_tw_proxy(url)


def test_service_identity_token_used_and_no_static_secret(monkeypatch):
    monkeypatch.setenv("JANUS_TW_PROXY_ENABLED", "true")
    target = "https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch=tse_2382.tw&json=1&delay=0"
    calls = []
    def fake_open(request, timeout):
        calls.append((request, timeout))
        if len(calls) == 1:
            assert request.get_header("Metadata-flavor") == "Google"
            return io.BytesIO(b"test-id-token")
        assert request.get_header("Authorization") == "Bearer test-id-token"
        data = json.loads(request.data)
        assert data["url"] == target and data["method"] == "GET"
        return io.BytesIO(b'{"rtcode":"0000","msgArray":[]}')
    with patch("services.api.tw_proxy_client.urlopen", fake_open):
        assert fetch_mis_via_tw_proxy(target)["rtcode"] == "0000"
    assert len(calls) == 2


def test_mis_uses_taiwan_hop_only_on_allowed_http_errors(monkeypatch):
    monkeypatch.setenv("JANUS_MIS_QUOTES_ENABLED", "true")
    payload = {"rtcode":"0000","msgArray":[{
        "c":"2382", "ex":"tse", "d":"20261030", "t":"10:01:00",
        "z":"300.00", "y":"305.00",
    }]}
    service = MisQuotes()
    error = HTTPError("https://mis.twse.com.tw", 403, "forbidden", None, None)
    with patch("services.api.intraday_quotes.urlopen", side_effect=error), \
         patch("services.api.tw_proxy_client.fetch_mis_via_tw_proxy",
               return_value=payload) as backup:
        quote = service.prices({"2382": {"market":"TWSE"}})["2382"]
    assert quote["transport"] == "tw_proxy"
    assert quote["price"] == "300.00" and quote["previous_close"] == "305.00"
    backup.assert_called_once()

    service = MisQuotes()
    limited = HTTPError("https://mis.twse.com.tw", 429, "rate limited", None, None)
    with patch("services.api.intraday_quotes.urlopen", side_effect=limited), \
         patch("services.api.tw_proxy_client.fetch_mis_via_tw_proxy") as backup:
        with pytest.raises(HTTPError):
            service.prices({"2382": {"market":"TWSE"}})
        backup.assert_not_called()
