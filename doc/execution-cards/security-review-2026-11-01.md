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
