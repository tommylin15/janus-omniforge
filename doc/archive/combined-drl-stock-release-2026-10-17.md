# DRL-01 與個股修正合併發布（2026-10-17）

## 範圍與來源

使用者明確授權：兩項個股修正與 DRL-01 本年度 EPS／營收以同一完整 SHA 發布，完整 Release、候選、自動 auth、適用 Jobs／Preview 通過且資料讀回後，切正式 dev API。D01～D05 保持 PASS／CLOSED；既有嚴格驗證豁免不重開。

發布來源：`becb6a15496959c1f5d3d4985d7b523b652bd3ee`，包含 DRL 實作、個股修正 `cc3729b690514f941e76987c7f75b4c893a9a761` 與 inert 發布模板基準一致性修復。後續請求／證據 commit 不取代映像來源 SHA。

API immutable image：`ghcr.io/tommylin15/janus-api@sha256:a745346a1e1910024ed8b52e98d0b2a6e6959d5ffb400fe2604bc3cbb73d20e4`。

## 發布證據

| 關卡 | GitHub Actions | 結果 |
|---|---|---|
| 完整 Release | [#39019392917](https://github.com/tommylin15/janus-omniforge/actions/runs/39019392917) | SUCCESS；Python 1397 passed／2 deselected、Flutter、四映像發布與公開 digest 驗證通過 |
| 0% 候選 | [#39019791707](https://github.com/tommylin15/janus-omniforge/actions/runs/39019791707) | SUCCESS；tag `ghcr-becb6a154969` |
| 自動 auth | [#39019942041](https://github.com/tommylin15/janus-omniforge/actions/runs/39019942041) | SUCCESS；同來源 metadata／private negative boundary，非新的人工作業登入證明 |
| 固定 Preview | [#39020138003](https://github.com/tommylin15/janus-omniforge/actions/runs/39020138003) | SUCCESS；保留正式流量與其他 tags |
| 四 Jobs | [#39020285128](https://github.com/tommylin15/janus-omniforge/actions/runs/39020285128) | SUCCESS；receipt phase=PASS，8 個不同 execution canary 全 PASS、回滾基準可用、Scheduler 恢復 ENABLED |
| 正式 API | [#39021547612](https://github.com/tommylin15/janus-omniforge/actions/runs/39021547612) | SUCCESS；receipt phase=PASS、rollback_rehearsal=PASS，正式 `janus-api-00533-yah` 100% |

## 切流前資料讀回

候選、固定 Preview、Jobs 完成後切流前第二次 Preview 的 `/app/build-id.txt` 均精確匹配完整發布 SHA。六檔 `1513,2327,2382,3231,3711,5876` 的 EPS／營收共 12 路 visual-series 全部 available：每檔 2026 Q1／Q2 `eps_current_year.status=ready`，營收各 13 期。來源為 MOPS；歷史四季／TTM 保持 `not_certified`。

5876 `stock-header.price_status=available`、行情日 2026-10-16、有效價格；kline `available` 且 66 筆。這是公開資料路徑與同 SHA build 讀回，不冒稱新增真人登入或完整截圖矩陣。

## 正式切流後讀回：PASS

API 真實新版→前版→新版 100% traffic 演練成功，最終 revision `janus-api-00533-yah`。每次 switch 都核對唯一 100% revision、Ready／observedGeneration、原 tags 與非 traffic 設定；health 200、未登入 Owner profile 401、完整 build-id 正確。固定 Preview 與候選 tag 均指向相同 revision，舊 tags 保留。正式 run 完成後 Git 遠端 lease ref 查詢為空，部署鎖已安全釋放。

隨後獨立唯讀正式網址與固定 Preview，再次逐一驗證同一完整 SHA、六股 EPS＋營收 12／12 available、2026 Q1／Q2 ready、每股營收13期、5876 報價 available／行情日存在與66筆 kline available，全部 PASS。正式14個資料請求約322～475ms，只是本次逐筆觀察，不冒稱端到端或P95。

結論：使用者指定的合併發布與正式 API 切流 **PASS／完成**；兩項個股修正與 DRL-01 本年度 EPS／營收在相同已驗證映像上線。

## 回滾與邊界

API 前版為 `d739107aa26ae4641d6f3e1b9c80f2e9aa1a57b6`／`janus-api-00524-tot`；Jobs 實際前版為 `50af946df64b3ee25d2d0a74b73c5584a0a90ff3`，依先前成功 rollout #39017773941 的固定 digest／config hash，再由新 rollout 鎖內驗證。API 與 Jobs 回滾來源獨立，不能用一邊替代另一邊。

新 Jobs receipt `rollback_available=true`、`rollback_baseline_verified=true`，`old_image_rollback_exercised=false`：證明前版可回復，沒有冒稱本次真的回切過 Jobs。四個新 image 固定 digest 與五個既有 Job 設定雜湊均由 receipt／live readback 核對；research Job 保持原映像。Scheduler 原配置雜湊 `830859868274a5761bd934492ede934e3b4d3cda07355fcd13449d213ada8299` 未變。

不更改 Owner ledger／現金、不新增資源、權限、付費來源或 Scheduler。保留共用 Actions concurrency、owner-fenced Git-ref lease、執行終態／Scheduler fence、固定 digest 與失敗恢復。

個股首次載入的原始偶發失敗未重現；已修復可重現的 serving 共用鎖阻塞並有回歸測試，不宣稱找到當次事件唯一根因。D01～D05 已接受豁免不新增補做義務；DRL-01 其它 Ledger／五年估值等整體範圍不因本次發布一併結案。
