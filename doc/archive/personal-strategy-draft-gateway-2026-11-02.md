# 個人策略參數保存與 OmniAgent gateway 修正收據

日期：2026-11-02（Asia/Taipei）。工程發布、草稿保存讀回與無模型 gateway 連通驗證：CLOSED／PASS。實際 Gemini 生成與整體 PS-UAT 仍另列，不以接線成功代替模型／報告驗收。

## 問題與修正

- 原設定只讀生效策略／舊投資設定；沒有草稿儲存路徑。新增 Owner 私有 `PUT /api/v1/me/personal-strategy/draft` 與 072 nullable JSONB migration；百分比按表單原始字串保存，未填完或仍衝突的欄位也可先存。產出前仍使用原 StrategyInput 驗證。
- 按「儲存設定草稿」或「預覽」即保存；重開優先讀草稿，畫面明示已儲存／尚未儲存。保存不啟用策略、不呼叫模型、不消耗週額度、不動 active_version／paused／帳本；既有私人 state 刪除路徑涵蓋草稿，策略 export 包含草稿。
- 原 Worker 直連 Google Gemini，private Job 沒有直連所需設定；畫面只留下 RuntimeError。依使用者更正，移除直連／key／provider discovery，改走既有 OmniAgent `/v1/gemini/execute`，固定 market-mart／Flash-Lite，沒有直連 fallback。
- 與既有 CEO 共用 ID token helper；綁定 DB Owner／request，核對 gateway project／Owner／request／model；每步穩定 requestId、prompt／body／response 界限、無自動 provider retry。失敗以安全分類中文顯示，不洩漏 provider body、token 或私人 prompt。

## 權限與上游契約

使用者於本對話明確批准一筆限定 binding：在 `omniagent-codex-market-client@gen-lang-client-0593591102.iam.gserviceaccount.com` 上，授予 `janus-private-pipeline@gen-lang-client-0593591102.iam.gserviceaccount.com` `roles/iam.serviceAccountOpenIdTokenCreator`。角色只有 `iam.serviceAccounts.getOpenIdToken`；前後 policy 比對只增加此一 binding，其他不變。不新增 project role、金鑰或付費路由。

實際 gateway caller map 與模型讀回符合既有 market caller／`gemini-3.5-flash-lite`。目前契約為文字、32 KiB prompt、128 KiB envelope、2048 output tokens；沒有 Google Search／grounding／原生 JSON schema。不能把模型記憶當即時搜尋；外部缺口仍呈現 missing／partial。完整報告仍須通過 Janus schema 與 coverage 驗證。

## 測試與發布收據

- Flutter 定向 9 項、完整 147 項 PASS；分析無 error／warning（109 項既有 info）。保存未完成設定後重建頁面的回歸測試確認數值保留、生效規則不變、沒有生成呼叫。
- 個人策略／既有 gateway provider／Jobs rollout 定向 134 項 PASS；切流／baseline 檢查 28 項 PASS。Windows 的四個 pytest setup／teardown 錯誤 原因是過長參數案例 ID 超出環境變數上限；只縮短 ID，保留原始超限資料與測試，未排除這些測試。
- [完整 Release #41376716082](https://github.com/tommylin15/janus-omniforge/actions/runs/41376716082)：Linux／隔離 PostgreSQL **2119 passed、2 skipped、2 deselected**；Flutter、Web build、四映像 PASS。PG 實測 072 重複套用、Owner roundtrip／隔離及保留 active_version／paused。
- [072 migration #41376788029](https://github.com/tommylin15/janus-omniforge/actions/runs/41376788029) PASS，版本／JSONB 欄位讀回通過。最初自動審查因未釐清測試錯誤拒絕 migration；修正測試案例名稱、全數通過並提供隔離 PG 證據後重新核准，未繞過拒絕。
- [0% Candidate #41377424872](https://github.com/tommylin15/janus-omniforge/actions/runs/41377424872)、[OAuth boundary #41377736095](https://github.com/tommylin15/janus-omniforge/actions/runs/41377736095) PASS；另讀回候選與正式入口的 build SHA、安全 body bound、路徑拒絕與 nonce 綁定。草稿 GET／PUT 未登入均為 401。
- [四 Jobs #41377891528](https://github.com/tommylin15/janus-omniforge/actions/runs/41377891528) PASS，**8 個 distinct canary**；完整配置 hash 未變，Scheduler 恢復 ENABLED／`30 */2 * * *`。private 兩次為 `janus-private-pipeline-qg28k`、`janus-private-pipeline-h72fp`，真實 Job 身分取得 ID token，向 gateway 送 `{}`，只接受 authenticated 400 invalid_request；在模型執行前拒絕，無模型呼叫。
- [正式切流 #41380286035](https://github.com/tommylin15/janus-omniforge/actions/runs/41380286035) PASS，100% `janus-api-00650-koz`；source **5fdcdd9288d6305758935d4413f5ab92776a735e**、API digest **sha256:a83b35f4b1fe2c24fcffc0d1b3f03e3090f98e0ff19d5f9f44379217c2ab54a9**。direct 模式，rollback rehearsal NOT_REQUESTED。
- 前次 [#41379840074](https://github.com/tommylin15/janus-omniforge/actions/runs/41379840074) 在 traffic write 前被 guard 擋下：active-baseline 尚為更早 daf 版本。重新核對實際 3890ba62／00647-dul／GHCR digest，更新 baseline 及 inert templates（維持 approved=false）後重送；沒有放寬 guard。發布完成後再將目前可回復基準更新為 5fdcdd92，避免留下陳舊指標。
- [MCP／既有入口同步 #41380673884](https://github.com/tommylin15/janus-omniforge/actions/runs/41380673884) PASS；19 個公開 tag 全指向正式新版，只保留一個 ghcr 版本 tag；global lease 已釋放。

## 正式頁面驗收與範圍

- 在已登入正式 `/app` 的「我的」，直接保存當前欄位，顯示「設定草稿已儲存」。沒有替使用者填風險偏好或 Gemini 同意，也沒有點擊生成／重試。
- 原分頁關閉後重新開啟正式網站、登入並進入「我的」，再次觀察到從 GET summary 還原的「設定草稿已儲存；重新登入會自動帶回。尚未變更生效策略。」狀態。確認不是只存在原頁記憶體；未將 Owner payload 或數值納入本收據。
- 本輪工具沒有重送使用者失敗的策略生成，也沒有呼叫實際 Gemini 生成。既有 FAILED 保留歷史狀態，不能改寫成成功；可由使用者在個人策略頁有限重試原請求。
- 未宣稱完整四報告、Google Search、原生 JSON schema 或模型輸出完整率通過。PS-UAT 仍依使用者實際生成／報告操作結果判定。
