# Janus｜接手 AI 的唯一工程路由

更新：2026-10-25。唯一順序是 [TODO](todo.md) 的 SEQ-01→08；原多線分派與舊OPS-P0-1待辦已取代。四個模型全部本版正式上線，調校留2027年第一季。

1. 讀 [AGENTS](../AGENTS.md) → [PROJECT_RULES](PROJECT_RULES.md) → [TODO](todo.md)。
2. 選使用者指定的 SEQ-ID／階段，讀 [逐項AI指示](execution-cards/sequential-delivery.md) 的共同指令與該任務卡。
3. 按文件設計、程式開發、測試驗收、部署完成指定範圍；每卡已標建議模型、必要來源、具體交付、依賴、退出條件與失敗處理。
4. SEQ-04集中部署基礎批次；SEQ-08集中發布四模型及報告UI。兩次集中部署各有真實live驗收，不為每個前置任務各發一次版。
5. [統一批次WI](runbook-unified-batch-ai.md)保留可執行測試／migration／VM／Scheduler程序；其C節四模型／完整報告條件歸SEQ-08，基礎條件歸SEQ-04，不能混稱已完成。
6. 只在TODO維護階段進度，Operations記必要收據。遠端長任務只剩等待時依PROJECT_RULES交連結停止，不能盲目重送。

本輪只提交文件，後續由使用者逐條啟動，不自動開始SEQ-01或觸發CI／部署。四模型研究調校、全面研究資料重整與VAL-MIN30後續改善見 [第二版暫緩項](parking-lot.md#v2-2027-q1)，不列當前工程債。
