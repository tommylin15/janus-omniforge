# Janus — UI Specification

版本：1.6
狀態：索引；頁面與元件契約依下列切片為準

## AI 最小讀取規則

所有 UI 工作先讀 foundations，再只讀目標頁面、元件或 API 狀態切片。Admin 工作不需讀 User App 頁面；純後端工作不需讀 UI；release 驗收才讀 A11y 與 checklist。

## UI 路由

| 任務 | 必讀切片 | 條件增讀 |
|---|---|---|
| 所有 UI、視覺、responsive、Navigation／Shell | [UI Foundations](ui/foundations.md) | 再讀一個目標功能切片 |
| 今日、關注、個股、記帳／筆記、AI、資產、我的 | [User App 頁面](ui/user-app.md) | 實作元件時讀 Components；串 API 時讀 States/API |
| Flutter／Web 共用呈現元件 | [元件契約](ui/components.md) | 只增讀元件所在頁面 |
| loading／error 等狀態與 FastAPI endpoints | [狀態語意與 API 契約](ui/states-and-api.md) | 不需預讀 Admin |
| Admin tabs、tables、governance、reports | [Admin UI](ui/admin.md) | 只在全域 layout 時讀 Foundations |
| Dialog、鍵盤、讀屏、實機與 release checklist | [A11y 與 Release](ui/accessibility-and-release.md) | release 前依入口增讀 User 或 Admin |

執行優先序見 [TODO](todo.md)，領域規格見 [SPEC](spec.md)，WBS 驗收見 [WBS](wbs.md)。
