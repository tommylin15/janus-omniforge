"""Existing Janus market caller identity for the private omniAgent Gateway."""
AUDIENCE = 'https://omniagent-agent-gateway-2oo7qbkd5q-uc.a.run.app'
PRINCIPAL = 'omniagent-codex-market-client@gen-lang-client-0593591102.iam.gserviceaccount.com'


def mint_gateway_token():
    import google.auth
    from google.auth import impersonated_credentials
    from google.auth.transport.requests import Request
    source, _ = google.auth.default(scopes=['https://www.googleapis.com/auth/cloud-platform'])
    target = impersonated_credentials.Credentials(
        source_credentials=source, target_principal=PRINCIPAL,
        target_scopes=['https://www.googleapis.com/auth/cloud-platform'], lifetime=300)
    credentials = impersonated_credentials.IDTokenCredentials(
        target_credentials=target, target_audience=AUDIENCE, include_email=True)
    credentials.refresh(Request())
    if not credentials.token:
        raise ValueError('gateway_identity_unavailable')
    return credentials.token


def probe_gateway():
    """Authenticated malformed request: rejects before any model execution."""
    import json
    from urllib.request import Request, urlopen
    from urllib.error import HTTPError
    try:
        token = mint_gateway_token()
    except Exception:
        raise ValueError('gateway_identity_unavailable') from None
    request = Request(AUDIENCE + '/v1/gemini/execute', data=b'{}', method='POST',
                      headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
    try:
        with urlopen(request, timeout=15):
            pass
    except HTTPError as error:
        if error.code == 400 and json.loads(error.read(4096)).get('error') == 'invalid_request':
            return
        raise ValueError('gateway_authenticated_probe_failed') from None
    raise ValueError('gateway_malformed_request_not_rejected')
