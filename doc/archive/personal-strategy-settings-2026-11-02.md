# 個人策略設定表單修正收據

日期：2026-11-02。範圍：使用者截圖回報的設定表單、預覽與產出條件提示；不擴充研究策略、不變更風險偏好或帳本。

## 修正與檢查

- `PersonalStrategySettings` 改用 Flutter Form，先檢查必填、有限百分比與範圍、單股／產業及單筆損失／總損失交叉限制、自訂文字長度與保護池格式，再呼叫 API。後端契約維持原有要求。
- 不將空白資金需求推定為無需求。原始 Pydantic 格式錯誤改為中文提示，修改欄位即清除舊服務錯誤與預覽。
- 預覽顯示中文風險名稱與百分比；未預覽、未同意、預覽衝突、服務停用、週額度鎖定或背景產出中，均明示產出停用原因。
- 增加只讀狀態更新，保留草稿；設定讀取有 25 秒上限。沒有新增相依套件或修改 API／DB schema。
- 提交與推送前均執行 `/ponytail-review`，涵蓋唯一呼叫端、後端契約、widget tests 與發布來源；無必修發現。

## 測試與發布

- 定向 Flutter：8 項 PASS；完整 Flutter：146 項 PASS。分析 exit 0，無 error／warning；109 項既有 info 提示保留。Web release build PASS。
- [完整 Release #41372987736](https://github.com/tommylin15/janus-omniforge/actions/runs/41372987736)：Linux／隔離 PostgreSQL 2113 passed、2 skipped、2 deselected；Flutter、Web build 與四映像 PASS。
- [0% Candidate #41373618403](https://github.com/tommylin15/janus-omniforge/actions/runs/41373618403)、[OAuth boundary #41373877474](https://github.com/tommylin15/janus-omniforge/actions/runs/41373877474) PASS。
- [API-only promotion #41374045030](https://github.com/tommylin15/janus-omniforge/actions/runs/41374045030)：`PASS_API_ONLY_100_PERCENT`、lease released；Jobs／Scheduler／storage／IAM mutated=false。上一版 `janus-api-00644-yud` 保留；本次未執行 rollback 演練。
- [入口同步 #41374206459](https://github.com/tommylin15/janus-omniforge/actions/runs/41374206459) PASS；19 個公開 tag 全指向新版，其中只保留一個 `ghcr-*` 版本 tag。
- 程式來源 `3890ba62219b7d9f79e6197d8e489c420a7797fe`；API digest `sha256:7f86358216651a314d7c470e9ea32be87d307d79b45f4cd6cbf2fe04ccfce58d`；100% revision `janus-api-00647-dul`。

## Live 驗證與限制

- 已登入正式 `/app` 的「我的」：重現空白資金需求及單筆損失預算高於可承受總損失，顯示中文欄位提示，不再出現原始例外。
- 使用明確標示為測試的暫時內容呼叫合法 preview，成功呈現策略 Markdown、五項中文風險百分比與未勾同意的停用原因；修改後舊預覽消失。測試文字已清除、原數值還原，沒有點擊產出並生效或送出 Gemini 同意。
- 候選與正式入口獨立安全讀回：build SHA、health、OAuth metadata／負向 Owner／MCP challenge、路徑越界拒絕、body 大小限制與 nonce 綁定 PASS；無 Owner／canonical 寫入。
- 四 Jobs 的 image 與既有 rollback config fingerprints 一致、最後執行狀態為成功；Scheduler ENABLED，`30 */2 * * *`。本次未重新部署 Jobs 或重跑 canary。
- **未測試付費 Gemini 實際產出、完整四時段報告或整體 PS-UAT**；既有待驗項保留。不把表單與 preview 成功宣稱為全功能驗收。
