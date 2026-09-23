# Contracts package

Versioned cross-component schemas, identifiers, enums, and compatibility policy
live here.

`control_plane.v1.json` defines the persisted stock master, dataset collection
configuration, coverage membership, and execution records. Collection configs
carry coverage tier, cadence, authorization, retention, PII, and republishing
constraints. The availability enum distinguishes an empty or stale source
response from an execution failure; execution IDs and trace IDs remain internal
correlation fields.

Janus MCP exposes bounded source and context tools through
`services/api/mcp_adapter.py`. Owner scope, source authorization, PIT/provenance,
sanitization, and output bounds are enforced in `services/api/context_sources.py`.
Generic Agent and Chat contracts are owned by omniAgent.

`mart.v1.json` keeps deterministic analysis outcome separate from publication
lifecycle, and defines PIT evidence, five discriminated role payloads, scoped
analysis, and the metadata-only publication index boundary.
