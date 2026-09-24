# Janus 文件封存區

`doc/archive/` 只保存已完成、已取代或特定日期的歷史 checkpoint，用於追溯與稽核；不得作為目前 execution queue、runtime 現況或契約的第一來源。

查詢順序：

1. 目前要做什麼：`../todo.md`
2. 目前契約：`../spec.md`、`../wbs.md`、`../ui.md`
3. 目前實作／完成狀態：GitHub `main`、tests／CI、deployment／runtime evidence，以及 `../spec/operations-and-testing.md`
4. 只有需要歷史原因、舊 evidence 或被取代設計時才進本目錄

封存文件可保留當時的 build ID、revision、digest、舊資源名稱與未完成判斷；這些資料只代表該 checkpoint，不能自動外推為目前狀態。
