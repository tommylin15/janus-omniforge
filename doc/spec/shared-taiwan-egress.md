# Life／Janus 共用台灣出口（2026-10-30）

## 目的與責任

- 重用 Life 現有 `tw-activity-proxy`（`gen-lang-client-0593591102`、`asia-east1`）；禁止另建同功能的付費服務、DB、Scheduler 或常駐實例。
- Life 為共用 Proxy 的程式、來源主機白名單及部署責任方；Janus 只有對 TWSE MIS 的**受限盤中行情讀取權**，不讀寫 Life 使用者、筆記、活動、資料庫或 OAuth。
- 官方 MIS 出口目標僅 `https://mis.twse.com.tw/stock/api/getStockInfo.jsp`，`ex_ch` 限 TWSE／TPEx 明確 Channel；官方行情仍由 Janus 校驗股票代號、交易所、日期與正值。不得將代理回應改稱 canonical EOD。
- 來源直連優先；對 403／500／502／503／504 使用私有台灣代理備援，429 不繞過限流。Janus 現有 60 秒持久化 TTL、10 秒手動硬節流不變，不新增每分鐘 Scheduler。

## 身分、安全與降級

- Janus 呼叫者：`janus-user-api@gen-lang-client-0593591102.iam.gserviceaccount.com`，使用 Cloud Run metadata 身分 ID Token，audience 為 Proxy 正式 base URL。Life 使用既有 `postgres-vm@...`；只用服務身分 IAM，禁止共用公開密鑰。
- Proxy 必須 `roles/run.invoker` 僅授權必要 service accounts，且無 `allUsers`／`allAuthenticatedUsers`；嚴禁任意 URL、GET 以外來源方法、轉址、停用 TLS、向上游轉送 Authorization/Cookie；有界時間、大小、來源 host。
- Proxy 不是 VPN 或保證固定台灣出口 IP。若台灣地區出口仍遭 MIS 拒絕，不自動切成其他未核准付費 API；保留舊行情為 stale，維持 `day_change_amount=null`，顯示缺值原因。
- Life 的 proxy 設計與安全修正以其 GitHub `main` 為準；Janus API runtime 必須逐次讀回 100% revision、身份來源與實際報價日後才可標 PASS。

## 驗收矩陣

1. Life：Proxy unit tests、現役 Life 路由回歸、當前 IAM／100% revision、私有 caller 正向、未登入負向、IP/SSRF 負向、MIS 真實回應、憑證及 environment 不再含舊共享 secret。
2. Janus：本專案 unit tests、真實 API service account 有 Invoker、403/5xx 備援、429 不備援、受限 symbol／交易日、七檔持股當日價格及當日損益／缺值標記、Owner 登入 UI。
3. 兩邊需留下 same-SHA CI、候選、正式 traffic、rollback 基線、runtime 及實際請求結果；若任一環節缺證為 PARTIAL，不得把工程提交與局部測試當成全面恢復。

## 實作與開放條件

- Janus fallback：`services/api/tw_proxy_client.py` 和 `services/api/intraday_quotes.py`，環境 `JANUS_TW_PROXY_ENABLED` 可停用，預設只在原官方來源允許的 HTTPError 時嘗試。
- Life Proxy：`services/tw_activity_proxy/main.py`；Life caller：`backend/app/services/tw_request_router.py`。
- Life 的一次性受控發布：`.github/workflows/shared-tw-proxy-release.yml`；未完成真實 smoke 前不得切流量。
