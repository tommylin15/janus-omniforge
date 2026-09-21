# Contracts package

Versioned cross-component schemas, identifiers, enums, and compatibility policy
live here.

`control_plane.v1.json` defines the persisted stock master, dataset collection
configuration, coverage membership, and execution records. Collection configs
carry coverage tier, cadence, authorization, retention, PII, and republishing
constraints. The availability enum distinguishes an empty or stale source
response from an execution failure; execution IDs and trace IDs remain internal
correlation fields.

`janus-context.v1.json` is Janus-owned: it describes the current snake_case
source/selector/preview/resolve wire boundary. Janus still enforces owner,
source authorization, PIT/provenance, sanitization, and output bounds in
`services/api/context_sources.py`; the schema does not replace those checks.
`assistant.v1.json` and its registry references remain the live Janus
compatibility contract, including Janus approval denials. Generic Agent
contract ownership is in omniAgent; Janus's `engine_security.py` remains a
compatibility implementation, with the domain deny list owned by
`services/api/janus_approval_policy.py`. No runtime routing has moved.

`mart.v1.json` keeps deterministic analysis outcome separate from publication
lifecycle, and defines PIT evidence, five discriminated role payloads, scoped
analysis, and the metadata-only publication index boundary.
