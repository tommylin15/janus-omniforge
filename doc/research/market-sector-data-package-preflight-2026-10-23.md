# TWSE／TPEx 大盤與產業資料包 Preflight｜2026-10-23

**資料包範圍**：2025-01～2026-09，21 月 × 4 類來源（TWSE/TPEx 的大盤及產業）。
**本次驗證結論**：`PARTIAL / NOT_PUBLISHED`。84/84 月份目錄及月層原始／標準化檔案位置已盤點，但尚未逐一讀回全部月份的 payload、日分區及 SHA。不可將抽樣 PASS 宣稱為全資料包 PASS。

## 已取得的 live Google Drive 證據

- 白名單根：`janusChatGPT/資料源/大盤產業_免費來源_2025H1_試跑/`（[實際目錄](https://drive.google.com/drive/folders/1XozCP8UGKqh_UeL87YxavHTuMYhHyx8t)）。雖保留「2025H1 試跑」歷史目錄名稱，目前四個來源的子目錄都延伸至 2026-09，不能僅由目錄名稱判斷涵蓋期間。
- 月份目錄：`twse_market`、`tpex_market`、`twse_sector`、`tpex_sector` 均為 **21/21**，合計 **84/84**。
- `twse_market` **21/21** 月份目錄均查得 `receipt.json`、`normalized-<sha256>.json`、`raw-<sha256>.json`。
- `tpex_market` **21/21** 月份目錄均有相同三類檔案。`2025-01`～`2026-01` 另留 `error_latest.json`，須將舊錯誤與新的 `VERIFIED` 收據按時間、來源與 checksum 核對，**不能僅憑舊錯誤檔判為現況失敗**。
- `tpex_sector` **21/21** 月份目錄均有相同三類檔案；同樣在 `2025-01`～`2026-01` 發現附帶 `error_latest.json`。
- `twse_sector` 不是月檔：每個月下為交易日分區，總計 **422 個日目錄**（2025-01 15 日、2026-02 12 日、2026-09 20 日等）。目前僅抽樣讀回 2025-01-02 日分區內三類檔案。
- 上述「每月有檔」為**檔案存在性**驗證，不代表 84 月份均已驗 SHA、schema 或資料品質。

## 實際 payload 抽樣驗收

| 樣本 | 實測結果 | 稽核說明 |
| --- | --- | --- |
| TWSE 大盤 2026-09 | 20 個交易日、20 筆，唯一指數 TAIEX | normalized SHA256 與檔名一致；raw SHA256 與檔名一致 |
| TPEx 大盤 2026-09 | 20 個交易日、20 筆，唯一指數 TPEX | normalized SHA256 與檔名一致；raw SHA256 與檔名一致 |
| TPEx 產業 2026-09 | 20 個交易日、19 指數、380 筆 | normalized SHA256 與檔名一致；raw SHA256 與檔名一致 |
| TWSE 產業 2025-01-02 | 37 個指數、37 筆，日期一致 | normalized SHA256 與檔名一致；當日日目錄含 receipt/raw/normalized，當日 raw 未讀回校驗 |

2026-09 三個已抽樣來源的 **交易日集合完全相同**；normalized 資料的 `(trade_date,index_id)` 均無重複、`close` 均為正數。TPEx 產業每個交易日 19 筆，超過既有 10 指數最低檢查門檻。2026-09 TWSE 產業日目錄數亦為 20，但**尚未逐日驗證其內容及與大盤日期完全一致**。

## 全量准入尚未關閉的檢查

1. **原始檔可信度**：84 月份所參照的所有 `receipt.json` 必須為 `VERIFIED`；每個 `raw/normalized` 位元組都重算 SHA256、確認 receipt 宣告的來源、期別、筆數與檔案內容相同，若不存在或 checksum 不符 FAIL。
2. **欄位與合理性**：每筆市場／交易日／指數 ID 不空、日期落在對應月份；同 `market+trade_date+index_id` 不重複、數值有限且正值；大盤 OHLC 必須 `low ≤ open,close ≤ high`；價格指數與報酬指數須分開，不得混欄。
3. **日曆與逐日覆蓋**：各市場大盤交易日必須與其對應產業日期集合完全一致；TPEx 各交易日產業指數至少 10 種；TWSE 產業需逐日日目錄 checksum 與筆數一致。不能僅以工作日推定休市或補填。
4. **研究契約**：保留 URL、取得時間、source hash、schema/adapter 版次、交易日期、原值單位；資料只標 `RESEARCH_ONLY`。來源授權需按實際 API/資料集分別確認，不能把公開可讀等同 ML 使用授權。
5. **下游界線**：完成指數包 preflight 不代表有 `symbol→industry_id→index_id` 的歷史有效期 crosswalk。個股產業因子在 `industry_membership` 的 PIT 檢查未過前保持 BLOCKED；不覆蓋 `canonical/CURRENT.json`、Risk ACTIVE、Core/Mart，亦不開啟模型 publication。

## 判定

- **月目錄存在與主要檔案定位：PASS**（84/84）。
- **抽樣資料 schema／SHA／日曆：PASS（限上述明確樣本）**。
- **完整 84 月份＋422 個 TWSE 日分區全部 payload 讀回及 SHA：PENDING**。
- **資料包供四模型正式 ingestion：NOT READY**；研究用市場指數因子可先設計但不可宣稱已完成全量準入。
- **總狀態：PARTIAL**。此為 2026-10-23 Google Drive 調查收據，非全量 release manifest。

## 權威與後續

- 現行 code：`research/colab/market_sector_trial.py`、`research/colab/market_sector_tpex_v2.py`、`research/colab/official_index_backfill.py`。
- 來源路徑在 Colab：`/content/drive/MyDrive/給ai專用/janusChatGPT`，**不是**`MyDrive/個人用`。
- 完整資料包需從相同 Drive 資料源以唯讀模式建出 pinned manifest（每檔路徑、SHA256、筆數、交易日、來源與版次），生成 `preflight_summary.json` 與 `preflight_issues.csv`，驗收完成才許供 `research/chatgpt` 讀取；不得修改現有成功收檔 receipt。

## 2026-10-23 補充：可重跑 Preflight CLI 與 CI

**完整執行操作手冊（供使用者／另一個 AI）**：[逐月小批次 Preflight SOP](market-sector-preflight-operation-runbook.md)。SOP 為文件交付，不代表正式全量驗證已執行；各批結果以獨立 checkpoint 與 final manifest 讀回判定。


- **實作**：[market_sector_package_preflight.py](../../research/chatgpt/market_sector_package_preflight.py) 已提交 `main`。唯讀掃描全部分區 receipt、原始／標準化 SHA256、schema、rows、OHLC、唯一鍵、月份範圍、來源 URL 及跨資料集交易日集合；輸出 `preflight_summary.json`、`preflight_issues.csv`，不更動原始收檔與模型。
- **回歸測試**：[test_market_sector_package_preflight.py](../../tests/test_market_sector_package_preflight.py) 涵蓋正常 fixture、checksum 篡改、缺漏日分區；[GitHub Actions #39938208461](https://github.com/tommylin15/janus-omniforge/actions/runs/39938208461) `success`，其 selective tests job 亦 `success`。**這是程式測試通過，不是完整 84 月 payload 驗收通過**。
- 2025-01 `tpex_market` 額外實證：`error_latest.json` 更新於 2026-10-23 09:25 UTC，隨後 `receipt.json` 於 10:02 UTC 記錄 `VERIFIED`、15 筆、2025-01-02～22，故該月舊 error 應視為「先前嘗試的留存證據」，不直接推翻較新 verified 收據；其他月份仍需逐檔核對。
- 因 ChatGPT 當前僅個別透過 Drive 連接器讀回檔案，**並未擁有掛載在可執行 Python 的完整 Drive 資料目錄**，無法聲稱 CLI 已對完整資料包跑完。Full-data run 狀態 `PENDING`。

### 完整驗收命令（有 Drive mount 的 Linux／Colab 環境）

```bash
ROOT="/content/drive/MyDrive/給ai專用/janusChatGPT"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
python research/chatgpt/market_sector_package_preflight.py \
  --root "$ROOT/資料源/大盤產業_免費來源_2025H1_試跑" \
  --start-month 2025-01 --end-month 2026-09 \
  --output "$ROOT/資料源/JanusDataset_v3_202610/reports/market_sector_preflight_$STAMP"
```

從 GitHub clone／更新 `main` 後於 repo 根目錄執行；需可讀整批 Drive payload。退出碼 `0` 表示**研究資料包 preflight 的已定義機械 gate** 通過；`2` 表示 `BLOCKED` 並輸出逐分區缺口，仍不等於模型 OOS／歷史 PIT／用途授權／publication PASS。產出應再以 SHA 固定成唯讀的研究 input release，核對跨來源 mapping 才進四模型特徵工廠。
