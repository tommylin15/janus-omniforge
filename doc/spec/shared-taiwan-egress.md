# Life／Janus 共用台灣出口（2026-10-30）

## 2026-10-30｜七檔 Owner 報價修正版 API 100% 與使用者 UAT：CLOSED／PASS

- **2026-10-30 後續使用者 Owner UAT 已完成／PASS：**繼「非盤中手動更新，操作驗收無誤」，使用者明確回報「七檔持股行情與損益的完整驗收，完成」，據此將七檔行情／損益功能的**使用者操作驗收**結案。本紀錄不附逐檔價格或損益截圖，故不能視為另有機器產出的全部七檔原始報價、前收、資料日期、損益逐筆核對收據。API 正式發布技術證據仍以 [#41025046594](https://github.com/tommylin15/janus-omniforge/actions/runs/41025046594) 為準；本次未重新部署、修改代理、資料來源或任何 GCP 資源。

- 完整 Python、Flutter、四 GHCR digest [Release #41018544303](https://github.com/tommylin15/janus-omniforge/actions/runs/41018544303) PASS，exact source `1bed368a66e8fdcd2eb61e99d1b9b6921edd0ae6`。
- [0% Candidate #41022750896](https://github.com/tommylin15/janus-omniforge/actions/runs/41022750896) PASS：建立 `ghcr-1bed368a66e8` 候選 tag，固定來源／digest、Ready、health、未登入 401、build SHA、部署 lease 與既有正式 100% 流量不變均通過。
- [同版 Read-only Auth Boundary #41023923246](https://github.com/tommylin15/janus-omniforge/actions/runs/41023923246) PASS：OAuth metadata 200、Owner／Admin 未登入 401、MCP Bearer challenge 401、Candidate build SHA matched；`no_gcp_mutation=true`。此收據不涵蓋登入 Owner 的真正七檔更新、當日損益、OAuth callback 或 owner isolation 正向。
- **API-only 100% Dev promotion [#41025046594](https://github.com/tommylin15/janus-omniforge/actions/runs/41025046594) PASS**：GitHub Actions `promote-api-only` success，已下載保護性 artifact `ghcr-api-only-promote.json` 並核對 `phase=PASS_API_ONLY_100_PERCENT`、`traffic_mutation=true`、`lease_released=true`，新版正式 Revision `janus-api-00636-lek`、來源 SHA `1bed368a66e8fdcd2eb61e99d1b9b6921edd0ae6`、不可變映像 `ghcr.io/tommylin15/janus-api@sha256:e8f86fbc258def1e185e3d2f5d10408bdf0c3e924929f4776c793c9b70ae9369`。正式切流前舊版 `janus-api-00634-nop`／`ea6466738d25a5f86772b34f0366e0b1fd34040f` 經 live preflight 驗證後保留作 rollback 基準。此直接切流的收據顯示 `rollback_exercised=false`（本次未要求演練），`jobs_mutated=false`、`scheduler_mutated=false`、`storage_mutated=false`、`iam_mutated=false`。**此行是當時 API 切流時點的歷史驗收邊界**：當時尚未提供 Owner UAT；其後使用者已正式確認七檔行情與損益操作驗收完成。技術發布收據與使用者操作驗收仍為各自不同的來源。

## 2026-10-30｜Janus API × Life 台灣代理部署後獨立讀回：API 切換 CLOSED／PASS

- Janus 官方 API 早已由 [API-only promotion #41012198081](https://github.com/tommylin15/janus-omniforge/actions/runs/41012198081) 完成一次正式切流；沒有必要為 Life Proxy 改版而重複部署既有 GHCR API image。
- Life TLS 修復後，新的 [唯讀 Live 收據 #41015413975](https://github.com/tommylin15/janus-omniforge/actions/runs/41015413975) 驗證 Janus `janus-api-00634-nop` 是唯一 100% serving revision、`/app/build-id.txt` 為 `ea6466738d25a5f86772b34f0366e0b1fd34040f`、`JANUS_MIS_QUOTES_ENABLED=true`、Life 共用代理 `tw-activity-proxy-00011-zip` Ready、兩個明確 `roles/run.invoker` service identities、無 `allUsers`／`allAuthenticatedUsers`，未登入 Owner quote API 正確拒絕（401／403）。
- Janus `JANUS_TW_PROXY_ENABLED` 未特別設定，使用程式預設 true；Life Proxy URL 未改變，直接指向新版代理，不需要重建 Janus candidate 或新 GCP 資源。這個功能設定推論不等於已取得 owner 的當日成交行情。
- **本工項完成邊界**：Dev API 安全升流與跨服務目前版本／權限讀回 CLOSED／PASS；**此為當次舊版本切流時尚無 Owner 驗收的歷史記錄；已於同日後續修正版切流與使用者確認七檔行情／損益 UAT 完成後結案**。不能把未登入負向測試算成 Owner 正向。

**最新狀態：Life 官方觀光署來源可信 TLS 連線已恢復，100% 現役 Proxy `tw-activity-proxy-00011-zip`。** 安全發布 [#41014398927](https://github.com/tommylin15/life_assistant/actions/runs/41014398927) 與正式讀回 [#41014672520](https://github.com/tommylin15/life_assistant/actions/runs/41014672520) 均 PASS；官方 ZIP 200／503922 bytes／有效，MIS、私有 IAM 與無舊 Secret PASS。先前 502、BLOCKED 內容為歷史事件。**Janus Owner 七檔盤中行情／損益功能已於當日後續修正版使用者 UAT 確認完成；Life VM 自身下游仍為獨立待辦**，不因本次結案自動判 PASS。

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

## 2026-10-30 Live 交付狀態

- Proxy：Life `asia-east1` 既有服務安全發布 [#41010462296](https://github.com/tommylin15/life_assistant/actions/runs/41010462296) PASS，100% `tw-activity-proxy-00006-dep`、MIS private request 200/rtcode 0000、SSRF 負向與未登入拒絕 PASS。授予 Janus API 本身的 Cloud Run Invoker，無 public Invoker。
- Janus API：完整 GHCR [#41010601470](https://github.com/tommylin15/janus-omniforge/actions/runs/41010601470)、0% 候選 [#41011762417](https://github.com/tommylin15/janus-omniforge/actions/runs/41011762417)、auth boundary [#41012042952](https://github.com/tommylin15/janus-omniforge/actions/runs/41012042952)、可回復 API-only promotion [#41012198081](https://github.com/tommylin15/janus-omniforge/actions/runs/41012198081) PASS；後讀回 [#41012409231](https://github.com/tommylin15/janus-omniforge/actions/runs/41012409231) 100% revision `janus-api-00634-nop`、source SHA `ea6466738d25a5f86772b34f0366e0b1fd34040f`、`JANUS_MIS_QUOTES_ENABLED=true`。
- Life 官方觀光署來源 `media.taiwan.net.tw` 在新版私有代理仍回 `502 upstream_unavailable / ConnectError`；保護性新候選 [#41011718029](https://github.com/tommylin15/life_assistant/actions/runs/41011718029) 因未通過 Life 正向資料門檻而 FAIL，不改現役流量。不允許使用 `verify=False` 解除 TLS 安全限制。
- **2026-10-30 早期狀態（歷史）**：此時 Janus Owner E2E 尚未取得，Life 活動 ZIP／VM 各子項也尚待完成；**後續狀態以本頁頂部同日使用者完整 UAT PASS 與 Life ZIP TLS 修復收據為準**。Life VM 定時任務／下游匯入並未因此視為 PASS。

### 2026-10-30 Life 官方來源 TLS 差異收據

- Life 新 0% 候選 [#41012831462](https://github.com/tommylin15/life_assistant/actions/runs/41012831462) 對 `media.taiwan.net.tw` 返回 `tls_certificate`；GitHub runner [#41012955722](https://github.com/tommylin15/life_assistant/actions/runs/41012955722) 以 OpenSSL 驗證同網站為 PASS，不能推論各出口／CA store 相同。
- 安全 OS CA context 測試 PASS，但候選 [#41013128130](https://github.com/tommylin15/life_assistant/actions/runs/41013128130) Life ZIP 仍 502、MIS PASS，故發布 FAIL；保留既有 Live Proxy 100% `tw-activity-proxy-00006-dep`。此來源 **PARTIAL／BLOCKED**，未擅自關閉 TLS 或新增付費資源。
- Janus API 100% `janus-api-00634-nop` 與 private IAM 已獨立 readback PASS；此時 Owner 7 檔 quote／損益尚待本人驗收；**同日後續使用者已回報完整 UAT 完成**。Janus MCP positions 的 `as_of=2026-10-29` 僅為最近已發布持股快照，不是 intraday-refresh 端點，不能據此聲稱新路徑故障或已恢復。

### 2026-10-30 Life 官方 TLS 修復：CLOSED／PASS

- [鏈驗證比對 #41014131479](https://github.com/tommylin15/life_assistant/actions/runs/41014131479)：嚴格 Python X.509 檢查對官方 `media.taiwan.net.tw` 回 `verify_code=86 / Missing Subject Key Identifier`，不是失去可信根 CA；[相容性探測 #41014255690](https://github.com/tommylin15/life_assistant/actions/runs/41014255690) 只取消該格式檢查的 `VERIFY_X509_STRICT` 可建立經 CA／hostname 驗證的 TLS，憑證 Issuer TWCA。
- Life `_origin_tls_context(host)` 僅對精確觀光署主機調整舊式憑證 SKI 延伸欄位的嚴格格式判斷；MIS 與其他 Life host 保持完整嚴格模式。仍有 TLS 1.2+、CA 鏈、簽章、有效期限與 Hostname 驗證；不使用 `verify=False`，也不引入未知根憑證。專用 CI [#41014344340](https://github.com/tommylin15/life_assistant/actions/runs/41014344340) PASS。
- [受控發布 #41014398927](https://github.com/tommylin15/life_assistant/actions/runs/41014398927)：先 0% 候選，Life ZIP／MIS 真實正向、無授權與 SSRF 負向全 PASS，之後才將 `tw-activity-proxy-00011-zip` 切至 100%。[獨立 Live readback #41014672520](https://github.com/tommylin15/life_assistant/actions/runs/41014672520)：ZIP HTTP 200／503922 bytes／有效 ZIP、MIS PASS、無公開 Invoker、原靜態憑證環境變數不存在。
- 完成邊界：**代理讀取 Life 觀光署官方來源的可信 TLS 已修復**；Life VM 排程自身版本／下游匯入仍未驗；Janus Owner 七檔報價與損益已於後續使用者 UAT 確認完成，不得借此聲稱兩個應用全面驗收完成。
