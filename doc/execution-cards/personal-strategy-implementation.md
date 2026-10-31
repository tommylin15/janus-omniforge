# 個人策略 PS-01～04：AI 實作與接手指示

2026-10-31 使用者授權：先寫本指示，再完成程式並提交；本輪不執行測試、lint、build、migration、API付費呼叫、驗收或部署。舊「僅文件」限制由本輪覆蓋，其他工程不擴張。

## 本輪實作 AI 指示

讀 AGENTS、PROJECT_RULES、個人策略 SPEC、工程卡及現行 API／Flutter。以現役 main 為底，不替換四模型，不新增排程／服務。依序完成：
1. PostgreSQL migration、完整股市／價值／GARP／趨勢／自訂樣板；先策略再風險、預覽、每台北ISO週成功一次。未部署migration不能假稱可用。
2. A/B/C手動分級、鎖定、S帳本推導；週六送出前明確選sync，版本衝突跳過同步，保護手動更動。
3. 持久請求＋既有private-pipeline Job按需啟動；四種報告各日一次、週報僅週六；有限重試、token fencing與中斷續跑。公開資料搜尋不送私人資訊；關閉搜尋後再合併持股、觀察、策略、既有四模型與現金。
4. Gemini Flash-only：模型目錄與已核准清單交集選新版，禁止Pro或其他provider回退；不推定AI Pro含API額度。TradingAgents只借鑑正反論點與策略一致性檢查；不新增依賴、交易執行或長期反思記憶。
5. 獨立個人策略頁、唯讀安全Markdown卡片、設定表單、移除持股筆記UI；每類3份，第4份成功才清理；失敗不刪舊。配額與報告內容分開保存，刪正文不可重置配額。
6. 支援私人Markdown種子預覽／明確套用／匯出；無法解析部分保留原文，不自動改帳本，不把私人內容提交Git。
7. 寫入接手文件、具體環境需求與未執行項。提交main使用[skip ci]，停止。

## 下一位 AI：測試與驗收指示（本輪禁止執行）

先核對main實作差異與本SPEC，補寫定向測試，再執行；不得以文件或commit宣稱PASS。
- Python：週一跨週、同週雙裝置、冪等key不同payload、失敗保留active、並行請求唯一配額、租約逾時／重送fence、外部來源失敗partial、截斷／非法LLM輸出、Pro拒絕、搜尋無私人欄位。
- PostgreSQL：在獲准Dev以版本化migration先驗證表／權限，測策略成功週鎖、四種日額度、每類第4份僅留3、失敗不刪舊、Owner A/B隔離、刪除帳號清理、備份還原留存。檢查交易鎖順序及週同步與手動名單／帳本並行。
- 同步：sync=false零寫入；true合法增刪升降排序；鎖定永不變、容量50／股市B池8、全域deep-tracking限制、失效symbol／任一版本變動跳過整批；重試不重套。
- 策略：三學派有來源、規則與資料門檻；不足65個可比較日線不得聲稱趨勢訊號成立；缺EPS成長不硬算PEG；股市保護池、網格錨點與研究／執行分離。長期策略不強迫每日交易。
- Flutter：設定選策略→風險→預覽→生成；週鎖、報告進度／錯誤／重試、四類切換、週六sync選擇、ABC分組／鎖定、S標示、無筆記入口、MD粗體／標題／安全連結／複製、390px及深色模式。登入Owner實測，不用401代替驗收。
- 契約：人工檢視日報六章／週報七章；支持、反對、失效與一致性都有；全部持股與觀察有涵蓋狀態；來源時間不當最新成交；AI數值不能覆寫帳本／canonical。
- 執行相關pytest與Flutter測試／分析；Release全gate通過後才依既有發布流程部署。API與private-pipeline使用相同程式版本，migration先行，啟用開關最後才開。
- 沒有API key／模型核准清單／Search使用額度時先測可測範圍，列實際阻擋，不擅啟付費。Cloud Run overrides權限沿既有通道，不擴IAM。

測試、驗收、部署全數待接手。結果逐項填TODO，失敗先修正再重驗，不自動開新研究／稽核工作線。

## 接手時的檔案與環境

- `services/api/personal_strategy_contract.py`：五個選項（股市、三學派、自訂）、風險及結構化輸出契約。
- `services/api/personal_strategy.py`：Owner API、週／日額度、凍結快照、手動調池、seed與匯出。
- `services/api/personal_research_worker.py`：Flash模型目錄交集、公開搜尋、私人合成、一次正反檢查、checkpoint、原子同步及留存。
- `services/api/private_pipeline_runtime.py`：`PERSONAL_RESEARCH_REQUEST_ID`有值時只執行該請求，不執行交易補登或原定時主鏈。
- `infra/postgres/migrations/071_personal_strategy.sql`：向前新增表與觀察欄位；migration只寫入Git，尚未套用。
- `apps/user_app/lib/personal_strategy.dart`：個人策略頁與個人設定；正式Web導覽在`final_visual.dart`。原`final_ledger.dart`筆記UI移除，資料／其他既有筆記API仍在。

### 環境與發布次序（待另一位AI執行）

1. 先測試程式與SQL。071涉及既有watchlist ALTER及users REFERENCES，必須使用現有PostgreSQL表擁有者operator路徑；不要把它送入目前不支援071的serving-schema-migration allowlist，不為此授予API schema owner。於獲准GCP通道用`psql -v ON_ERROR_STOP=1 -f infra/postgres/migrations/071_personal_strategy.sql`，連線資訊只用既有安全環境設定；不得在命令／日誌放密碼。
2. API與既有`janus-private-pipeline`發布同一已測試版本。Job維持原entrypoint；每個手動請求以taskCount=1及request UUID override派送。核對API對既有Job的runWithOverrides權限；不另建Job或Scheduler。
3. API設`PERSONAL_STRATEGY_ENABLED=true`前，確認migration、Job與私人AI同意畫面就緒。未啟用前生成入口明確拒絕。
4. Worker沿`JANUS_API_POSTGRES_BUNDLE`讀`database_url`及`gemini_api_key`（如已用環境注入`GEMINI_API_KEY`可沿用）；不可用pipeline-only DB role代替。金鑰只在Secret或安全env，不入Git；原損益工作維持pipeline role，不擴權。
5. 先確認Google API及Search額度／授權，再設`PERSONAL_RESEARCH_API_APPROVED=true`。`PERSONAL_RESEARCH_FLASH_MODELS`為逗號分隔、經接手驗證的穩定Flash型號；預設僅gemini-2.5-flash。系統從API models.list與此清單交集選數字版本最新者，每請求固定版本，禁止Pro／preview／跨provider回退。新增3.8等需先確認generateContent搜尋／結構化能力與帳戶成本；AI Pro訂閱不能當API授權證據。
6. 外部Google Search只傳symbol／時間，最多200個symbol、每批10個；標準50觀察加少量持股約6批搜尋＋1次私人合成。每次呼叫timeout90秒，LLM實際執行最多兩次claim，checkpoint避免重跑已完成步驟；20分鐘租約逐步延長。Job timeout需涵蓋有界整輪。搜尋失敗仍可出partial，不自動無限重試。
7. 以Owner登入做WI驗收後才宣稱可用。備份需確認包含新private表；還原後先執行`scripts/gcp/personal_report_restore_retention.sql`，再開放讀報告；不要清除配額收據。
8. 回復時先關PERSONAL_STRATEGY_ENABLED，再回復API／Job既有可用版本；保留新表與私人資料，不用DROP清理。舊程式不依賴新欄位，無須刪資料回退。

### 明確的產品界線

- 趨勢樣板可產生研究報告；目前快照未提供已驗證調整日線，因此不宣稱已計算65日／60日訊號。缺值會明列待確認；後續驗收不可將搜尋摘要當完整序列。
- MD種子目前完整原文保存、預覽與匯出；未解析內容全部明示，不自動把私人價格／例外轉成公共規則或改帳本。自訂條文由使用者在設定套入預覽後才生效。
- Rich卡片採原生安全Markdown子集（標題、粗體、條列、分隔線、來源連結），無HTML／外部圖片；Web點連結開新頁，其他平台複製URL。匯出可複製Markdown與完整JSON，不直接寫Drive。
- 數值只引用快照與來源，不讓LLM產生可自動執行股數／金額；缺有效參考價／失效價或預算時說明無法計算。無券商與交易寫入。
- 原TradingAgents程式未複製、未新增LangGraph依賴、未實作長期決策反思。只是本專案自行實作固定的一輪支持／反對／失效與策略一致性輸出。
- 本輪未作測試／lint／build／migration／Gemini連線／Google Search呈現要求／帳戶授權／Live UI驗收。下一位需補這些驗證後再發布，不能拿靜態閱讀當PASS。

## 本輪靜態審閱紀錄

只閱讀diff、API／SQL／UI接線及文件一致性；環境沒有/ponytail-review，未假稱執行。移除筆記時保留紀錄／報表共用載入元件；維持既有名單鎖順序；策略歷史清理保留仍被報告或在途請求引用版本。沒有執行應用程式、測試、lint或build，因此這不是功能／安全／效能PASS。
