import json
import sys
import threading
import time
import urllib.error
import urllib.request
import hmac
import hashlib
import os


GATEWAY = sys.argv[1]
SECRET_FILE = sys.argv[2] if len(sys.argv) > 2 else None
TOKEN = os.environ.get("MCP_ACCEPTANCE_TOKEN")
if not TOKEN:
    token_request = urllib.request.Request(
        f"http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/identity?audience={GATEWAY}&format=full",
        headers={"Metadata-Flavor": "Google"},
    )
    with urllib.request.urlopen(token_request, timeout=10) as response:
        TOKEN = response.read().decode()
OWNER = "00000000-0000-4000-8000-000000000001"
KEY = open(SECRET_FILE, "rb").read() if SECRET_FILE else os.environ["MCP_ACCEPTANCE_SECRET"].encode()


def request(method, payload):
    body = json.dumps(payload, separators=(",", ":")).encode()
    stamp = str(int(time.time() * 1000)).encode()
    signature = hmac.new(KEY, stamp + b"." + body, hashlib.sha256).hexdigest()
    req = urllib.request.Request(
        f"{GATEWAY}/internal/v1/mcp/{method}",
        data=body,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
            "X-Janus-Timestamp": stamp.decode(),
            "X-Janus-Signature": f"v1={signature}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=35) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read())


def discover(server):
    status, result = request("discover", {"ownerId": OWNER, "serverId": server, "configRef": server, "toolGrants": []})
    assert status == 200 and result["tools"], (server, status, result)
    return result


for server, era in (("stdio-dev", "modern"), ("http-dev", "modern"), ("sse-dev", "legacy")):
    result = discover(server)
    assert result["protocolEra"] == era, result
    tool = f"{server}__echo"
    status, result = request("call", {"ownerId": OWNER, "serverId": server, "configRef": server, "requestId": f"accept-{server}", "toolName": tool, "toolGrants": [tool], "arguments": {"text": f"gcp-{server}"}})
    assert status == 200 and result["result"]["content"][0]["text"] == f"gcp-{server}", (server, status, result)
    print(f"{server}: discover={era} call=ok")

status, result = request("call", {"ownerId": OWNER, "serverId": "stdio-dev", "configRef": "stdio-dev", "requestId": "accept-redaction", "toolName": "stdio-dev__secret_echo", "toolGrants": ["stdio-dev__secret_echo"], "arguments": {"label": "fixture"}})
assert status == 200 and result["result"]["structuredContent"]["secret"] == "[redacted]", result
print("redaction: ok")

status, result = request("call", {"ownerId": OWNER, "serverId": "stdio-timeout", "configRef": "stdio-timeout", "requestId": "accept-timeout", "toolName": "stdio-timeout__slow", "toolGrants": ["stdio-timeout__slow"], "arguments": {"milliseconds": 1000}})
assert status == 400 and result["error"] == "Request timed out", result
print("timeout: ok")

time.sleep(3)
result = discover("stdio-dev")
assert any(tool["name"] == "stdio-dev__dynamic" for tool in result["tools"]), result
print("tools/list_changed: ok")

slow_payload = {"ownerId": OWNER, "serverId": "stdio-dev", "configRef": "stdio-dev", "requestId": "accept-cancel", "toolName": "stdio-dev__slow", "toolGrants": ["stdio-dev__slow"], "arguments": {"milliseconds": 5000}}
holder = {}


def run_slow():
    holder["result"] = request("call", slow_payload)


thread = threading.Thread(target=run_slow)
thread.start()
status = 400
result = {}
for _ in range(20):
    time.sleep(0.25)
    status, result = request("cancel", {"ownerId": OWNER, "requestId": "accept-cancel"})
    if status == 200 and result.get("cancelled") is True:
        break
thread.join(10)
assert status == 200 and result["cancelled"] is True, (status, result)
assert holder["result"][0] == 400, holder
print("cancel: ok")

status, result = request("disconnect", {"ownerId": OWNER, "serverId": "stdio-dev"})
assert status == 200 and result["disconnected"] is True, (status, result)
print("disconnect: ok")
