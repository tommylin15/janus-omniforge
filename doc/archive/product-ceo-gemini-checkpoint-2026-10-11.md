# CEO Gemini 進度 checkpoint（2026-10-11）

目前判定：**PARTIAL，Gemini 已回應，CEO 報告尚未產生。** 文件先回寫，再開始下一次真實驗收；不把部署或 HTTP 202 當作報告成功。

## 已觀測證據

- 來源 `a60db85e179c61896f047fb8c89d1e855fbc1e12`：[完整 Release #38135486739](https://github.com/tommylin15/janus-omniforge/actions/runs/38135486739) SUCCESS，1046 Python tests PASS、2 legacy deselected、Flutter PASS、四公開 GHCR images 與匿名拉取 PASS。
- 同 SHA 的 [CEO build #38135816040](https://github.com/tommylin15/janus-omniforge/actions/runs/38135816040) 與 [worker 部署 #38136081515](https://github.com/tommylin15/janus-omniforge/actions/runs/38136081515) SUCCESS，readback 成功、部署租約已釋放。Job 只執行 Gemini，單次最多 120 秒，無重試／fallback；沿用受限 Job 的 1 CPU／1 GiB、480 秒、0 retry、無 Scheduler。
- 唯一 Gemini 真實請求 `32bbd62c-cde0-48e0-9841-daf243d30416`：2026-10-11 11:40:05 UTC 接受並派送，11:43:01 UTC 終態 BLOCKED。Audit 顯示 `gemini-3.5-flash-lite`、單一 Gemini attempt、10693 ms、有 usage，失敗原因 `invalid_structured_output`，`report_hash=null`。因此 key／模型已有真實回應，但沒有有效 CEO 報告。
- 未保留原始模型回覆，無法從現有證據確定哪個欄位失敗；不能宣稱提示詞不足已是證實的唯一原因。下一修正將格式要求直接加入提示詞，並只記錄安全的失敗欄位名稱。
- 舊 BLOCKED 請求不覆寫。專用 `janus-mart-codex-auth` 已依使用者要求刪除；`omniagent-shared-codex-auth` 未讀取／修改。Gemini key 仍只取自既有 `janus-runtime-bundle`，使用者已確認 AI Studio API Free tier。

## 本機修正與待驗證

- 使用者最新要求：本人每日額度 50、冷卻 300 秒，取代之前每日 1／臨時 2 的安排。Runtime 目前讀回每日 20；052 migration、API 上限 50、Admin 文案與保存設定尚未部署，不標完成。
- 額度相關 targeted tests：46 PASS、5 local PostgreSQL tests SKIPPED、1 warning；隔離 PostgreSQL 必須由後續 CI 驗證。
- 提示詞明列完整 JSON schema、必填欄位、五份 validated specialist hashes 與輸出範例的修正尚在工作區。首輪 provider/product tests 為 43 PASS、2 FAIL（新增診斷變數初始化問題）；已有工作區修正，但尚未重跑確認，不當作 PASS。
- [API 0% candidate #38136187186](https://github.com/tommylin15/janus-omniforge/actions/runs/38136187186) 尚未在本 checkpoint 核對終態，不列 PASS。最後已驗證正式流量仍為 `janus-api-00457-wed` 100%，固定 preview 為 `janus-api-00465-feq` 0%；本 checkpoint 沒有新切流證據。

## 下一入口

1. 完成提示詞／安全格式診斷與額度 50 的 targeted tests、review、同 SHA 完整 Release。
2. 經 GitHub Actions 執行 migration 052、CEO worker／API 候選部署與 readback；Admin 保存本人額度 50。
3. 文件回寫後，執行最少已授權真實 Gemini 呼叫，確認有效報告、不可變 history、usage 與 UI；若失敗保留原紀錄，先判定終態與原因。
4. 完成同工作包的 owner／四排程 Jobs fence、canary、rollback 與 API 正式切流 gate；整批仍 PARTIAL。500 檔研究與 omniAgent 統一 AI 入口後置。
