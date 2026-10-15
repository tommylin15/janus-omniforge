# Janus 最新驗收證據索引

更新：2026-10-15。此頁只保留最近適用的業務判定與來源；各次原始記錄完整搬至 [歷史 ledger](../archive/documentation-baseline-2026-10-15-operations-and-testing.md)。舊PASS只適用其來源／scope，不替後續main背書。執行授權另看TODO。

| 驗收範圍 | 證據 | 判定與限制 |
|---|---|---|
| 全市場Bootstrap | [#38575674367](https://github.com/tommylin15/janus-omniforge/actions/runs/38575674367) | 2026-10-13，TWSE1095／TPEx893；必要dataset分市場PASS |
| 同日Cached | [#38651225144](https://github.com/tommylin15/janus-omniforge/actions/runs/38651225144) | 17/17 cache_hit，staged=0／published=0；不是新日期完整性 |
| migration057 | [#38555862109](https://github.com/tommylin15/janus-omniforge/actions/runs/38555862109) | migration PASS；不等於snapshot生成PASS |
| 00719B身份／估值 | [#38652846263](https://github.com/tommylin15/janus-omniforge/actions/runs/38652846263)、[#38653250200](https://github.com/tommylin15/janus-omniforge/actions/runs/38653250200) | 058及單Owner readback PASS；當時ledger170 |
| 費稅更正 | [#38680770336](https://github.com/tommylin15/janus-omniforge/actions/runs/38680770336) | 88筆append-only、ledger176→352，8持股股數不變；00697B缺價不算完整PnL |
| 既有四Jobs／Preview | [#38676820532](https://github.com/tommylin15/janus-omniforge/actions/runs/38676820532)、[#38675180575](https://github.com/tommylin15/janus-omniforge/actions/runs/38675180575) | 當時來源4d058c47… PASS；後續Jobs rollout須另查 |
| 公開API效能 | [#38677467684](https://github.com/tommylin15/janus-omniforge/actions/runs/38677467684) | 30/30，P50 65.1ms／P95 72.1ms／max6673.38ms；不是authenticated手機／冷啟動驗收 |
| Iceberg compact | [#38684081267](https://github.com/tommylin15/janus-omniforge/actions/runs/38684081267) | 9 tables、9,429,711 bytes重寫；8162→8225 objects，刪除0；未證物件縮減 |
| retention dry-run | [#38684726748](https://github.com/tommylin15/janus-omniforge/actions/runs/38684726748) | 預計74 snapshots／403 orphans；不是已刪除 |
| 引用盤點 | [#38684978645](https://github.com/tommylin15/janus-omniforge/actions/runs/38684978645)、[#38685692925](https://github.com/tommylin15/janus-omniforge/actions/runs/38685692925) | PARTIAL_NOT_AUTHORIZED_FOR_DELETION；19 oversized未完整讀取，private／PG未全面驗證 |
| I/O觀察 | [#38685092023](https://github.com/tommylin15/janus-omniforge/actions/runs/38685092023) | 已有方法級小時觀測；窗口不等量，節省率unknown |
| audit-only新版發布前置 | [Release #38685404805](https://github.com/tommylin15/janus-omniforge/actions/runs/38685404805)、[candidate #38685839070](https://github.com/tommylin15/janus-omniforge/actions/runs/38685839070)、[auth #38686018183](https://github.com/tommylin15/janus-omniforge/actions/runs/38686018183) | 既有記錄PASS；不等於後續Jobs／cleanup PASS |
| 當輪Jobs／audit cleanup | [#38686125420](https://github.com/tommylin15/janus-omniforge/actions/runs/38686125420)、[#38686337134](https://github.com/tommylin15/janus-omniforge/actions/runs/38686337134) | 本輪API觀察in_progress／pending、conclusion=null；以後必須重讀終態 |
| omniAgent P0-V | [#38490887562](https://github.com/tommylin15/janus-omniforge/actions/runs/38490887562) | 合成full Fact Pack／真實Gemini／validator技術PASS，0正式Owner報告；publication仍OPEN |

## 實作與文件差異

- `jobs/ingestion-core/ingestion_core/__main__.py` 已呼叫 `materialize_home_market_snapshot`；舊「只有test caller」敘述失效。最新版本的runtime產生／readback仍需證據。
- `scripts/gcp/b9-specialist-oos-quality.py` 的歷史診斷仍列硬編碼PIT／baseline blockers。正式研究協議允許標示strict_pit=false的財報比較，不能把此診斷當成禁止研究；也不能用文件將它改判品質PASS。
- 本輪未重新跑產品測試或GCP workload。文件驗證結果見 [盤點](../documentation-review-2026-10-15.md)。

## 已結案及詳細入口

A／B0～B8保留原結案；[B7 freshness](../archive/group-b-b7-derived-cache-freshness-closure-2026-10-10.md)、[B8](../archive/group-b-b8-closure-2026-10-10.md)、[CI/CD](../archive/cicd-ghcr-api-promotion-2026-10-10.md)。產品暫停交接見 [checkpoint](../archive/pause-checkpoint-2026-10-15.md)，CEO技術詳情見 [P0-V](../ceo-omniagent-p0v-integration.md)，六個月自然觀察仍見 [Pilot evidence](../pilot-operational-evidence.md)。不得為整理文件重做自然週期或更改歷史FAIL。
