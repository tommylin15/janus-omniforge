# WBS-6-PILOT-USEFULNESS-FEEDBACK — 完成紀錄（2026-09-16）

已完成 bounded usefulness feedback。既有 `GET/PUT /api/v1/me/analysis-feedback`
從 authenticated user 取得 owner，不接受 client 指定 user；request 僅接受
`useful`／`neutral`／`misleading` 與 bounded reason。Feedback 存於獨立 private table，
並從 publishable analysis target 綁定 deterministic hash；不更新分析結果、分數或
publication input。Flutter 個股 analysis card 載入既有選擇並支援更新；既有 private
export／deletion 也涵蓋 feedback。

驗收結果：

- `python -m pytest -q tests/test_user_api.py tests/test_pilot_readiness.py`：**28 passed**。
- Flutter Cloud Build `c83cab17-862f-44f9-b722-f57b701a0fb5`：**SUCCESS**；analyze
  通過（`--no-fatal-infos`）、widget tests **8 passed**、release web build 通過。
  Widget coverage 驗證個股卡片掛載、讀取已選值及送出新 feedback。
- GCP dev `janus-postgres-dev`：在單一 transaction 以兩個合成 owner 和一筆合成
  publishable report 驗證 owner records 分離、更新為 version 2、analysis hash 與
  deterministic hash 一致、API role 無 DELETE 權限；交易以 `ROLLBACK` 結束，未留資料。
  Migration `025_pilot_readiness` 已由先前 WBS-8 acceptance 套用，本次未重跑 migration。
- `git diff --check` 通過。首次 Flutter run 找出測試在捲過卡片後才尋找 widget；已將
  可視性 assertion 移至捲動前並補上互動測試，最終完整 Flutter verify 通過。

部署界線：dev `janus-api-00077-6s9` 使用的 image build 日期為 2026-09-13，早於
feedback API 變更；Artifact Registry 現行 cleanup policy 僅保留每個 package 最新
tagged image。本次未部署 Cloud Run 或宣稱 live authenticated HTTP 已驗收，以免在沒有
rollback image 保留方案時淘汰目前 image。Dev API rollout／真人 Google OAuth journey
仍待安全部署窗口處理；無 production deployment 或新增 GCP resource。
