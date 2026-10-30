"""Private Cloud Run IAM transport for bounded TWSE MIS fallback.

Never reads Life private data and never uses a static shared secret. Caller
identity is the Janus API runtime service account.
"""
import json
import os
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

SHARED_TW_PROXY_URL = "https://tw-activity-proxy-2oo7qbkd5q-de.a.run.app"
MIS_HOST = "mis.twse.com.tw"
MIS_PATH = "/stock/api/getStockInfo.jsp"
MAX_BYTES = 2 * 1024 * 1024


def fetch_mis_via_tw_proxy(target_url: str) -> dict:
    """Use only as bounded fallback after an upstream HTTP failure."""
    if os.getenv("JANUS_TW_PROXY_ENABLED", "true").lower() != "true":
        raise RuntimeError("Taiwan quote fallback disabled")
    target = urlsplit(target_url)
    if target.scheme != "https" or target.hostname != MIS_HOST or target.path != MIS_PATH:
        raise ValueError("unapproved MIS target")
    proxy = os.getenv("JANUS_TW_PROXY_URL", SHARED_TW_PROXY_URL).rstrip("/")
    parsed = urlsplit(proxy)
    if parsed.scheme != "https" or parsed.hostname != urlsplit(SHARED_TW_PROXY_URL).hostname:
        raise ValueError("unexpected proxy endpoint")
    identity_url = (
        "http://metadata.google.internal/computeMetadata/v1/instance/"
        "service-accounts/default/identity?" +
        urlencode({"audience": proxy, "format": "full"})
    )
    token_request = Request(identity_url, headers={"Metadata-Flavor": "Google"})
    with urlopen(token_request, timeout=2) as response:
        token = response.read(8192).decode("utf-8").strip()
    if not token or len(token) > 8191:
        raise RuntimeError("proxy service identity unavailable")
    payload = json.dumps({"url": target_url, "method": "GET", "timeout": 8}).encode()
    request = Request(
        proxy, data=payload, method="POST",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    with urlopen(request, timeout=12) as response:
        raw = response.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("oversized MIS response")
    data = json.loads(raw)
    if not isinstance(data, dict) or data.get("rtcode") != "0000" or not isinstance(data.get("msgArray"), list):
        raise ValueError("invalid MIS proxy response")
    return data
