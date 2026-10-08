# Janus GitHub Actions → GHCR → Cloud Run dev 驗收紀錄（2026-10-08）

**本文件是實測 checkpoint，不是完整 cutover 完成證明。**

## 完成並讀回

- 原始碼 SHA：`0b93d99d42aaff662a3408d749d70aa9d04b1042`。
- [GHCR 全量 Gate #37769572546](https://github.com/tommylin15/janus-omniforge/actions/runs/37769572546)：**SUCCESS**。Python `623 passed, 2 deselected`；Flutter analyze/test/Web build 成功；四個 Docker build/push 成功；對四個 GHCR package 用未登入匿名 `skopeo inspect --no-creds` 確認 manifest digest。
- 兩個 deselected 是已刪除 `register_baseline` API 與舊備份政策相抵觸的 legacy Pilot assertions；另有五個 `apps.web.*` legacy module 已不存在而被 `--ignore`，**不可宣稱歷史所有測試完全 PASS**。
- [Cloud Run 0% 候選 #37771247779](https://github.com/tommylin15/janus-omniforge/actions/runs/37771247779)：**SUCCESS**。對既有 `janus-api` 建立 `janus-api-00446-luq`，固定 public GHCR digest；候選 tag `ghcr-0b93d99d42aa`，health、公用 health、未登入 private endpoint guard 與 Flutter SHA identity PASS。服務正式流量沒有切換，仍為 `janus-api-g53d655ccb108-config` **100%**。
- [Cloud Run Jobs／GHCR 唯讀盤點 #37771560144](https://github.com/tommylin15/janus-omniforge/actions/runs/37771560144)：四個 GHCR digest 公開可拉取，現役 `janus-ingestion-core`、`janus-batch-controller`、`janus-intelligence-mart`、`janus-private-pipeline`、研究 `janus-research-big-move-500` 仍使用 AR；每個 Job 最近 20 筆 executions `potentiallyActive=0`。這不是全面 schedule／所有歷史 execution clearance。
- Registry digest readback（release SHA 相同）：
  - `api`: `sha256:b4b0d09f5e7a8a6b0b0103027298ed14032c0023af1eca8c11a716b2aa8b573f`
  - `ingestion-core`: `sha256:8bd49a3ede7493192aac80251902c4ffa78078b7ea4ddef85927680120e81ca3`
  - `intelligence-mart`: `sha256:9096ceb14489de3de44fa17ceb1a731edf23d49615361c6332a2897146030fff`
  - `private-pipeline`: `sha256:af9c35ff60448170eed38d33e7396741240b3acdefc64560a8ff5b65b796af7f`

## 必須繼續等待證據的關卡

1. **Authenticated owner／Google OAuth／MCP／PnL** 候選測試尚未用真實授權 owner token 驗證。不可把 HTTP health／401 負向測試充作完整驗收。
2. **Jobs／Scheduler** 現役配置仍指向 AR；廣域 Scheduler list 在第一次 preflight 得到 `UNKNOWN_OR_BLOCKED`。無全部 Scheduler fence／snapshot／回滾，不更新既有 Jobs。已新增已知 Scheduler 名稱的 bounded 唯讀重試。
3. **正式 100% 流量 promotion 與 rollback** 都尚未執行，不能標成 PASS。新的 GHCR 發布與 0% 候選可獨立運作，不代表舊 Cloud Build 已可退休。
4. **10 Revisions 清理** 單元測試 PASS，但 runtime 有大量受流量、歷史 tags 及前版引用保護的 revisions；尚未執行刪除。清理成功可能保留超過 10 個。
5. **舊 Cloud Build Triggers／GCS／AR** 尚有實際引用。只做過一次唯讀盤點，沒有停用 Trigger、刪除 AR/GCS/bucket/revision；備份與業務資料完全排除。

## 切換與清理順序

GHCR full tests/publish PASS → 已完成的 0% 候選探測 → **待完成的**真實 authenticated acceptance、Job Scheduler fence、Jobs digest migration 與 rollback → traffic promotion／rollback readback PASS → 停用 Janus 舊 `janus-dev-v2` Trigger → GCS/AR exact-reference cleanup → Service revision 10+protected cleanup。

參照：[正式 CI/CD 契約](../spec/cicd-v2.md)、[2026-10-08 舊資產唯讀盤點](cicd-cutover-cleanup-inventory-2026-10-08.md)。
