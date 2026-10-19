> **封存歷史文件｜不得作為現行 TODO／排程／部署指令。** 最新工作看 [TODO](../todo.md)、[管理入口](../project-management.md)。

# 2026-10-15 文件盤點、風險與修正

基準main：`301e7f7229458e2d1f26818a66b90d0a464fc68f`。範圍：根入口、PROJECT_RULES、TODO／status／WBS／SPEC／UI／runbook的跨文件搜尋，直接相關API／Flutter／ingestion／研究／retention／workflow入口抽查，以及四張PNG實際檢視。**不是逐行全程式安全稽核，也未重新驗收所有runtime。**只修改Markdown；不改程式／migration／workflow／ops請求或PNG，不部署／訓練／刪業務資料。

## 文件已修正

| 問題 | 對AI開發的影響 | 本次處理 |
|---|---|---|
| TODO同時PAUSED／ACTIVE及數輪合併指令，重複列相同工作 | 重跑費稅、誤啟部署、漏看真正gap | 唯一D01～D08工作包；保留授權邊界、產品暫停與獨立FinOps |
| status252行、operations2296行大量「最新」 | 用舊版成功覆蓋新版本失敗 | 當前摘要／索引，三份原檔完整存archive並修相對連結 |
| README重複暫停與工具搬移限制 | 新工具可用仍不整理、狀態漂移 | README只導航；移除已不適用的connector無法搬移敘述 |
| WBS／SPEC／runbook有統一10% | 錯誤拒收上櫃或沿錯分母放行 | TWSE≤10%／TPEx≤30%，逐資料集及期間；未知仍不PASS |
| 500及TWSE-only仍作目前契約 | 與全市場產品方向衝突 | active母體改全上市櫃；歷史artifact／batch size／50 quota保留 |
| 舊模型名被稱已採baseline | 把LightGBM／Qlib存在當有優勢 | 財務／估值／動能／風險／rules基準；ML各自challenger與OOS |
| 30秒與60秒行情契約並存 | 不必要輪詢與測試矛盾 | 對齊程式與Quote Router：前景60秒，手動節流、離頁停止 |
| PNG說明仍健康度優先、紀錄多摘要 | AI按舊圖把通用圖表埋回進階 | 新順序以User App契約為準；PNG bytes不變 |
| 損益減號與會計括號衝突 | 同一金額跨頁顯示不一致 | User損益／漲跌使用減號，保留台股紅綠及文字 |
| CEO待辦「尚未接omniAgent」 | 重新建已存在adapter或誤認上游已切換Janus | 從P0-V技術PASS接正式Owner報告；endpoint執行前核對 |
| AI指示固定舊工作區diff、模型與slash command | 新agent停等不存在的依賴 | 實際git status／main；模型為分工參考，review工具不可用做明示等價檢查 |

## 有證據的工程風險（尚未由文件修復）

| 優先 | 發現／證據 | 下一責任及驗收 |
|---|---|---|
| P0 | 完整持股估值仍缺00697B價格；費稅修正成功不等於完整PnL | D01；最新image及合法來源、Owner checkpoint／aggregate讀回 |
| P0 | 引用盤點仍缺19 oversized及private／PG；一般retention被fence封鎖 | D06；完整引用後才bounded apply；audit-only不可解封一般資料 |
| P0 | API／Preview／四Jobs可能不同來源；現有rollout未終態 | D05／D06；先讀exact execution，未知不重送、各元件分項驗 |
| P1 | operations稱首頁snapshot只有test caller，但main `__main__.py`已有正式caller | D02；更正文件，runtime生成／freshness／readback仍NOT VERIFIED |
| P1 | 公開API暖P95不能代表登入手機冷啟動；曾有6.67秒樣本 | D02／D03；端到端冷暖與失敗率，不能刪timeout樣本 |
| P1 | 備份新executor／restore尚無交接PASS，舊timer仍active | D04；新備份與隔離還原後再停timer，維持既有3代政策 |
| P1 | B9診斷hard-coded PIT／baseline blockers，與允許strict_pit=false研究比較用途不同 | D07；用途分級、來源時間揭露，保持publication guard；不偽造品質PASS |
| P1 | compact後objects增加而不是減少，I/O窗口不等量 | D06；snapshot／orphan／manifest分開驗，固定工作量再估節省 |
| P1 | 合成CEO技術PASS沒有真實Owner immutable publication | D08；有效五角色＋新手動request＋GCS/PG/hash/history讀回 |

## 系統補強規劃

採既有系統漸進改善，未引入新基礎設施。完整兩方案比較、UI與資料契約、逐角色模型評估、成本／安全及工程入口見 [系統建置補強](../spec/system-development-contract.md)。重點是持股可用與低延遲、通用圖表先行、前瞻資料與公平OOS、引用保護及可量測I/O。新唯讀情境影響構想放Parking Lot，不塞進目前發布gate。VF-09模型狀態視覺化仍後置D07，不阻塞D03的VF-00～08。

外部參考採W3C、scikit-learn、Apache Iceberg官方文件；來源連結與本案推論分開記於補強契約。沒有引用外國稅制、沒有承諾獲利／模型優勢或I/O節省率。

## 保留與驗證

- 原TODO、status、operations完整保存為 `archive/documentation-baseline-2026-10-15-*.md`，只加入歷史標頭並校正相對連結；FAIL、歷史授權及run收據不改寫。
- 不重開A／B0～B8；產品／模型／CEO技術／publication各自判定。六個月Pilot自然證據窗口保留。
- 文件review採實際diff、相對連結、歷史原文還原比較、PNG SHA256及語意衝突搜尋；本環境未提供 `/ponytail-review`，依PROJECT_RULES明示替代，不聲稱執行該命令。
- 本輪直接唯讀查GitHub兩筆既有workflow，觀察結果在status；未派新run、未操作GCP。只做文件驗證，不以此宣稱Python／Flutter／產品CI或runtime PASS。
- Git同步前確認diff僅Markdown、main未被覆蓋；同步後讀回commit與文件。文件整理完成不代表上述工程風險已解決。
