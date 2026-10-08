# Janus CI/CD V2 — 轉換期契約

本次使用者明確指定四元件改造；不改 B7／B8／B9 業務範圍。目前是 **PARTIAL**，GitHub Actions 仍是已啟用的 canonical controller。V2 Trigger 在四元件 live gate 與切換完成前保持停用。

## 已實作邊界

- `cloudbuild-v2.yaml`：固定 SHA 取源 → tests/security → 四元件 target build/push → digest receipt；預設 shadow-only，不更新 runtime。
- `scripts/gcp/cicd-v2.py`：變更選擇、共用依賴展開、legacy bucket inventory、image digest 引用 dry-run。文件不選 runtime。
- `scripts/gcp/cicd-v2-candidate.py`：既有 regional bucket generation-precondition mutex；拒絕舊 main SHA；短暫暫停既有 enabled Janus Scheduler，確認 Job／Controller 無 active execution；API no-traffic 候選；Job 受控 image 更新與 bounded smoke；Job 回復原 image、Scheduler 恢復原狀態。
- API 候選 gate 驗 health、未登入 User/Admin 拒絕、Flutter User/Admin SHA。**尚未驗 authenticated OAuth／A-B owner isolation／真實持股損益，不得升流量。**
- Ingestion `JANUS_CICD_READINESS=check|apply-missing` 使用既有 DB identities，按 041～050 支援順序只補缺少 marker，讀回 schema／ACL；050 的 publication ACL 在 publication owner connection 下驗，不授予 control identity 額外權限。
- Mart smoke 使用既有 `specialist-smoke`；Private smoke 只讀 mobile queue availability／owner binding，不觸發大量重算。
- `cloudbuild.yaml` 原 tag-based 自動刪 image 已移除。dry-run 保護所有盤點到的 revision／Job／execution／明確候選 digest；permission、mutable reference、欄位缺失都 fail-closed。跨區引用與完整 acceptance receipt 尚未補齊前，不允許 delete。

## 尚待驗收／實作

1. Repository Trigger 新版本 build、四元件 candidate 與 authenticated live acceptance。
2. canonical promotion、各元件已發布 SHA 的持久化 baseline、same-SHA 冪等 readback、每次 promotion 前 SHA fence、失敗 rollback 與人工指定 SHA/component 重跑。
3. legacy GitHub controller 切換／退役與真實 main push V2 全鏈驗收。
4. 跨區引用盤點、candidate receipt 保留集合、可審核 dry-run → bounded image delete → 容量 readback。

上述未完成之前不得標記 V2 CLOSED。既有 owner queue、Secret／IAM／資源規格／Scheduler 契約與資料治理不變。Cloud Build logs 使用 `CLOUD_LOGGING_ONLY`，所有 build／trigger 固定 `us-central1`；只使用既有 regional bucket 保存小型 evidence／mutex，不新增 staging／logs bucket，不啟用 Artifact Analysis。

## 證據

目前 checkpoint 見 [V2 盤點](../archive/cicd-v2-inventory-2026-10-08.md)。Runbook 只記可重跑操作，不固定 SHA／Build ID。
