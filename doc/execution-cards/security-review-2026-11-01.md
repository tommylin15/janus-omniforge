# 資安 Code Review 與修補（2026-11-01）

範圍以 GitHub main `77097946` 與現役個人 Dev 為界：公開 API／Flutter 檔案、Google OIDC／MCP OAuth、Owner／Admin 授權、私人查詢 selector、SQL identifiers、前端不可信內容及現役 Python lock 檔。只修補可重現或有正式安全公告的問題；不新增權限／付費資源、不讀取或刪除真實 Owner 資料來示範漏洞。

## Review findings 與修補

| 優先級 | 具體問題與影響 | 最小修補／證據 |
|---|---|---|
| P1 | `/app/{path}` 未檢查檔案目錄邊界，編碼的 `..`、absolute path 或 symlink 可越出 Web 目錄，未登入可讀到其他檔案。 | resolve 後強制在 Flutter Web root 內，越界一律 404。用本機無敏感內容 sentinel 重現；保留合法 asset／User／Admin SPA fallback。 |
| P2 | MCP 的 64 KiB、註冊 4 KiB 都在 `request.body()` 全部讀取後才檢查；其餘 OAuth form 沒有大小上限。大量未登入請求可先耗盡記憶體。 | 同一有界 stream reader；MCP 64 KiB、registration 4 KiB、其餘 OAuth form 16 KiB，超限立刻停止接收。保留 MCP 413 envelope／registration 400；不信任 Content-Length。 |
| P2 | MCP Google OAuth state 生成 nonce，卻未送給 Google 或比對 ID token，缺少登入憑證與本次流程綁定。 | 傳入 nonce 並以 constant-time 比對已驗證 ID token nonce；缺少或不同流程均拒絕，且在 resolve Owner 前停止。既有 PKCE、refresh rotation／revoke、allowlist 保留。 |
| P1／P2 依公告 | API／Jobs 的鎖定依賴含已公開的 Range／parser DoS、TLS CA／proxy 與影像 decoder 等漏洞。 | 見下表；只改有問題套件及必要的 FastAPI 相容依賴，不更動數值模型套件版本。 |

| 套件 | 原版本 → 修復版本 |
|---|---|
| Starlette | 0.47.3 → 1.3.1 |
| FastAPI（相容調整） | 0.116.1 → 0.135.1；新增其必要依賴 annotated-doc 0.0.5 |
| certifi | 2026.7.22 → 2026.10.19 |
| pyasn1 | 0.6.4 → 0.6.5 |
| urllib3 | 2.7.0 → 2.8.0；原已是 2.8.0 的 Mart 保留 |
| opentelemetry-api | 1.45.0 → 1.45.1；原已修復的 probe 保留 |
| Pillow | 12.3.0 → 13.0.0 |
| setuptools | 84.0.0 → 84.1.0 |

安全公告以 `pip-audit 2.10.1` 的 PyPI advisory 回應為依據；[Starlette Range 官方公告](https://github.com/Kludex/starlette/security/advisories/GHSA-7f5h-v6xp-fcq8)確認原版本受影響。[Google OIDC 文件](https://developers.google.com/identity/openid-connect/openid-connect)確認 nonce 的流程綁定用途。FastAPI／Starlette 的 Python 與依賴相容性由官方 PyPI metadata 核對；uv 保留其他已鎖定版本並重新產生 hashes。新 nonce 不擴張 OAuth client／redirect／scope；部署交界的未完成舊登入流程可能需要重新發起。

## 驗證

- 修補前本機安全回歸：9 fail、1 pass，直接重現檔案越界與超量 stream 仍被繼續讀取；沒有對 live 發動檔案讀取或壓力攻擊。
- 使用實際修復版本後，API／OAuth／Owner／Admin／個人策略與安全定向 **129 PASS**；既有 Google client、PKCE、refresh／revoke 與隔離測試保留。
- API、ingestion、Mart、opt-in BigQuery probe 與根目錄 **5 份 lock** 重掃，皆無已知漏洞回報。這是當次 advisory database 掃描結果，不代表不存在未知漏洞；不把 retired research 環境冒稱現役映像。
- 高信心機密格式掃描 1584 個 tracked UTF-8 文字檔，未發現匹配；不輸出敏感值，也未擴張為 Git 全歷史／GCP Secret Manager 盤點。
- Owner 來源仍由驗證後身分決定，私人 selectors 不接受任意 owner；本輪檢查的 SQL 插值來自封閉 identifier／欄位映射，未發現可重現 injection。原始交易／模型數值與資料 schema 不變。

完整 Windows／Linux／隔離 PG、同來源 Release／候選／OAuth／四 Jobs／正式 API／MCP 與獨立 live 驗收尚待收據。未執行的項目不標 PASS；部署前不宣稱漏洞已在 live 修復。


本機最終完整回歸：**2065 passed、21 skipped、8 deselected，exit 0**（124.53 秒）。21 skip 為既有 19 項未配置本機隔離 PG 與 2 項外部 Valuation frozen fixture；8 deselect 為 Release 原有 2 項及 Windows GNU date／signal／resource／環境長度限制 6 項，另 B8 Linux resource module 由 Linux CI 驗證。第一次新 Pillow 安裝選到 CPython 3.14 wheel，已修正為實際 Python 3.12 wheel並重跑，不修改功能測試遮掩錯誤。

提交前 `/ponytail-review` 已追查五個 protocol endpoint、static FileResponse／SPA fallback、OAuth Google／PKCE／refresh／revoke 及 Owner resolver，核對全部 dependency version diff 與新增回歸。以個人 Dev 現役負載為界，沒有未解決 Must fix；可提交進入完整 Linux Release，但不取代 live 證據。


完整 Release [#41278063624](https://github.com/tommylin15/janus-omniforge/actions/runs/41278063624) **PASS**，來源 `60b84395b8fe4edacd7e054f4f3b145d0b298cc0`：Linux／隔離 PG **2095 passed、2 skipped、2 deselected**（87.27 秒），Flutter、四映像建置與公開 fixed digest 驗證成功。selective CI [#41278045887](https://github.com/tommylin15/janus-omniforge/actions/runs/41278045887) 與 PG／runtime contracts [#41278045873](https://github.com/tommylin15/janus-omniforge/actions/runs/41278045873) 也成功。

四 Jobs 唯讀基準 [#41278364781](https://github.com/tommylin15/janus-omniforge/actions/runs/41278364781) PASS，`gcp_writes=0`，來源均為先前 `daf9636e`，image／完整 config hash 保存在該 run 的 `ghcr-jobs-baseline` artifact。下一步僅部署 0% API 候選；尚未以新版承接正式流量。


0% 候選 [#41278547341](https://github.com/tommylin15/janus-omniforge/actions/runs/41278547341) PASS，主流量保留原版、lease `SAFE_TO_RELEASE`。候選獨立安全讀回 PASS：可達的 encoded absolute 越界路徑 404，dot path 在 GCP 邊緣正規化轉址後 404；MCP 413／registration 400／OAuth forms 413，Google authorize nonce 與已簽名 state 一致。只用不存在的檔名與一次有界請求，無 Owner／canonical writes。

### 追加發現：舊公開 tag 仍暴露舊程式

舊 `ghcr-daf9636e34c3` 公開網址對不存在的 encoded absolute 越界路徑仍回 200（舊 SPA fallback），對照同來源原始碼與新版候選 404，證明只切主流量不會移除這條未修補入口。此為具體現役安全暴露，不是重開無證據的歷史資產清理。

既有 MCP route workflow 增加明確 opt-in `seal_legacy_tags`：只能在本次已驗證候選正式單一 100% 後執行；退役其他 `ghcr-*` 公開 tags，將既有固定名稱 URL（含 MCP／Preview）導向修補 revision，保留 revision 與映像本體作回復。不改正式流量百分比、runtime template、Jobs、Scheduler、IAM 或 Owner 資料；保留精確舊 tag map，執行前再次核對基準，失敗完整回復並驗證，未知狀態保留 owned lease。正常只修兩個 MCP tags 的預設行為不變。此輪新增部署工具回歸 **47 PASS**，包含 0% 拒絕／無變更 lease 安全釋放、正式 100% 條件、固定別名保留、設定漂移、成功與精確回復／鎖保留。工具修改不改變已完整 Release 的 runtime image 來源 `60b84395`。


OAuth／private boundary [#41279149226](https://github.com/tommylin15/janus-omniforge/actions/runs/41279149226) **PASS**，同 runtime 來源 `60b84395`；metadata、PKCE／refresh 廣告與未登入 User／Admin／MCP 拒絕均成功。新路由工具 selective CI [#41279149267](https://github.com/tommylin15/janus-omniforge/actions/runs/41279149267) PASS。提交前已對路由工具與 Jobs 請求分別執行 `/ponytail-review`，核對新版正式 100% 前置、既有固定 URL 保留、完整 tag 回復／未知狀態留鎖，以及固定回復 image／hash；沒有未解決阻擋項。


2026-11-02 續接：四 Jobs rollout [#41279333435](https://github.com/tommylin15/janus-omniforge/actions/runs/41279333435) **PASS**，精確來源 `60b84395`、8 distinct canary、完整 config hash 保留、Scheduler 恢復，回復可用；全域 lease 已釋放。

續接路徑 review 另確認，Windows UNC／只有 root 的路徑應在 `Path.resolve()` 前拒絕，避免目錄檢查本身觸碰遠端 share；新增 3 個 mock 檔案 I/O 禁止案例均先重現。已以 `Path.anchor`／`..` 的字面拒絕補強，再保留 resolve 後的 symlink 邊界。這次僅改 API 檔案路由與測試，不更動 worker 或依賴；故後續使用既有 API-only promotion，保留已完成新版依賴 rollout 的四 Jobs，不重複執行它們。最新 API runtime source 必須重新完整 Release、0% 候選與 OAuth gate；舊 60b API 不先切主流量。


API-only 部署工具 review 發現原 gate 只檢查整體／job 綠燈，沒有將 Release HEAD 與候選歷史請求綁定到目標 source；已用 3 個「舊綠燈／錯來源」案例重現。現在重用既有 canonical operation identity／main branch／完整 Release job gate，驗證 Release HEAD、候選當時的 source／release_run／promotion=false 與祖先關係，並重用同來源 OAuth 歷史收據核對。正常正向與拒絕／回復相關 **147 tests PASS**；這是部署工具修改，不改 runtime image。

2026-11-02 重新掃描 API 59、ingestion 43、Mart 84、opt-in probe 26、root 3 個鎖定套件（各環境分別計算，非去重總數），5 份 lock 仍均無已知漏洞回報。最新路徑補強 API／OAuth／授權定向 **115 PASS**。
