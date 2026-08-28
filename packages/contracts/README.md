# Contracts package

Versioned cross-component schemas, identifiers, enums, and compatibility policy
live here.

`control_plane.v1.json` defines the persisted stock master, dataset collection
configuration, coverage membership, and execution records. Collection configs
carry coverage tier, cadence, authorization, retention, PII, and republishing
constraints. The availability enum distinguishes an empty or stale source
response from an execution failure; execution IDs and trace IDs remain internal
correlation fields.
