# Janus｜研究資料 Colab 目前操作入口（2026-10-23）

**請以 [四模型最新版本總索引](../../doc/research/00-四模型最新版本索引.md) 為準。**

- [00A 個股收檔 v3.8.4](00_資料收集_v3.8.4_個股.ipynb)：保留已穩定個股收集 code cells，單獨執行。
- [00B 大盤／產業收檔 v3.8.4](00_資料收集_v3.8.4_大盤產業.ipynb)：單獨執行；首次 `PROBE_ONLY=True` 先核對官方端點真實回應，仍有待修正來源。
- 00B 的 Python helper 是 [official_index_backfill.py](official_index_backfill.py)（v3.8.4）。保留 raw/receipt/不可變分區，未通過來源檢查不能標 VERIFIED。
- 貼標轉由 [ChatGPT 側 label_four_models.py](../chatgpt/label_four_models.py)；產業 PIT 檢查使用 [industry_membership.py](../chatgpt/industry_membership.py)；四模型研究訓練使用 [janus_train.py](../chatgpt/janus_train.py)。以上不在 Colab 收檔過程自動執行。

**過往資料與操作說明** 已保留在 [_archive](_archive/) 與 [原 README](_archive/README_v382_legacy.md)，不再當作目前唯一入口。正式 Risk bundle、Registry 與 canonical CURRENT 不因版本整理改變。
