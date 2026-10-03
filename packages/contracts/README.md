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

`specialist.v1.json` 是新的五分析師 strict artifact contract；角色為 fundamental、valuation、quant、risk、event，不授予 publication authority。
`ceo.v1.json` 只描述保留 provider transport 的輸出 shape，尚不代表手動 CEO command 或語意 validator 完成。
`mart.v2.json` 保存公開報告／publication metadata 的讀取型別，已移除舊 role payload／Fact Pack defs。既有 persisted v1 artifacts 不覆寫或大量刪除；新 specialist artifacts 使用獨立契約，不把未驗證模型冒充已發布公開報告。
