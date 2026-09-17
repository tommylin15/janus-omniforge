# WBS-6-CHATGPT-MCP-CONTRACT — 完成紀錄（2026-09-17）

## 完成內容

- 依官方 OpenAI remote MCP／OAuth requirements 固定 stable HTTPS Streamable HTTP、protected-resource metadata、authorization-code + PKCE `S256`、`resource` audience／scope 驗證、tool `securitySchemes` 與 401 challenge 邊界。
- 固定三個 read-only logical tools：`janus_sources`、`janus_market_context`、`janus_private_context`；定義 closed JSON inputs、allowlisted resources、owner binding、bounded output、provenance、quota 與 disclosure。
- 禁止 arbitrary SQL／table／URI／offset／raw query、client-selected owner、mutation、storage locator、free-form notes 與 placeholder；private profile 仍受 `ai_context_opt_in=true` 保護。
- 判定現有 Google browser OIDC ID-token boundary 不能直接安全接受 ChatGPT resource-bound OAuth access token；`WBS-6-CHATGPT-MCP-ADAPTER` 維持 `auth_blocked`，不得以 anonymous、shared bearer 或 email mapping 繞過。

## 驗證

- `git diff --check`：通過。
- `python -m pytest -q tests/contract/test_contract_registry.py`：3 passed。
- 未部署或建立任何 GCP／auth resource；未執行 GCP MCP endpoint acceptance，因 adapter 尚未存在且本 WBS 明定新 auth／GCP component 只能記錄 blocked decision，不得部署。

官方參考：[Authenticate users](https://developers.openai.com/plugins/build/auth)、[Build an MCP server](https://developers.openai.com/plugins/build/mcp-server)、[Connect and test](https://developers.openai.com/plugins/deploy/connect-chatgpt)。
