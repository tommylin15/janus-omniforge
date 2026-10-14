# Janus CEO → omniAgent P0-V Gateway（獨立整合）

更新：2026-10-13。此工作只授權 Janus CEO 請求鏈；**不解除持股／Private Recalc P0 的 PAUSED BY USER**，不重啟四個排程 Jobs、不修改已存在的交易帳本、不切換正式 API／omniAgent Gateway 流量。

## 目標與實作

Janus 手動 CEO API 依既有 capability、profile、quota/cooldown、latest validated baseline 與 Specialist hashes 產生 `private.ceo_requests`。既有 `janus-ceo-analysis` Job（仍使用 `intelligence-mart@...` 身分，保留原有 PostgreSQL/GCS 存取）藉由 Google IAMCredentials **受限 impersonation** 取得專用 `omniagent-codex-market-client@gen-lang-client-0593591102.iam.gserviceaccount.com` 的 audience-bound ID token，向 omniAgent Gateway 0% 試驗標籤 `POST /v1/gemini/execute` 發起單次 `project=market-mart` 請求。Gateway 經已存在的 Gemini Flash-Lite 服務回傳文字。

Janus 只接受 HTTP 200、`status=completed`、相同 project/ownerId/requestId/model 和有界非空 text，並在 Janus 原有 `OUTPUT_MODELS.ceo` Pydantic JSON schema 解析後，**再執行原有 `validate_ceo_output` 的 five hashes、evidence/PIT/numeric claim 檢查**。成功才依原機制寫入 immutable GCS JSON、readback、再將 report/hash 寫入 `private.ceo_requests`；FAIL/BLOCKED 不產生報告。Gateway 沒有 canonical number／publication authority。

- Provider 實作：`jobs/intelligence-mart/intelligence_mart/provider_routing.py` 的 `OmniGatewayGeminiProvider`，只在 CEO bounded manual 且 `MART_CEO_GEMINI_ONLY=true` + `MART_CEO_GEMINI_VIA_OMNIAGENT=true` 使用；**不讀 Janus Gemini API key**；不影響正常 deterministic Specialist（0 LLM）。
- Job 設定：`scripts/gcp/ceo_worker_template.py`，既有 `janus-ceo-analysis`、1 CPU／1Gi、480 秒、maxRetries=0、無 Scheduler，pilot URL pinned；`ceo_worker_deploy.py` 僅允許這兩個環境變數的可審計增補，保留原有身分、網路、Secret 與 rollback。
- Gateway 已驗證之專用硬限制：**market-mart prompt ≤32768 UTF-8 bytes**（其他兩 consumer 仍 ≤8192 B），**HTTP envelope ≤131072 B**、單次模型產生 **≤512 tokens**、回覆文字長度 **≤32000**；超過 prompt 閾值拒絕，**不能截去金融事實或數字**。512 tokens 不保證能產出完整 CEO JSON，未通過驗證不得稱 SUCCESS。缺少 response schema 原生強制能力是 upstream P0-V Gateway contract 限制，不宣稱本次已解。
- Fail-closed：身分不可 impersonate、錯誤 audience／project／owner／request/model、429／timeout／空文字／JSON 不符、baseline 過期／權限取消均不落有效報告；無自動重送 uncertain execution。只保存安全錯誤分類與 usage（如有），不存 Gateway provider text、Bearer、API key。
- Gemini model 固定 `gemini-3.5-flash-lite`；不新增付費模型／計費資源。Gateway 的 model 成功不等於帳單免費，需要獨立核對授權與用量。

## 驗收關卡（不要互相代替）

1. **程式與安全回歸**：`tests/test_mart_provider_routing.py`、`tests/test_ceo_worker_template.py`、`tests/test_analysis_product.py`。包含錯誤路由、偽造 response、schema、owner/request identity、超長 input、無 retry、傳統直接 Gemini 與 DB 不回歸。
2. **身分與 Gateway read-only preflight**：`.github/workflows/ceo-omniagent-p0v-preflight.yml`。檢查原 Job SA、target Gateway 0% tag、Gateway `roles/run.invoker` 與專用 market caller 的 `roles/iam.serviceAccountTokenCreator`。不需要新金鑰、不能靠 CI 自己 impersonation PASS 代替 Worker runtime 授權。
3. **GHCR 完整 Release**：原有 `ghcr-publish-dev.yml` 同 SHA Python/Flutter/full test，並建置專用 CEO image；失敗不進入 Job rollout。API 0% 候選必須遵守原 Release/lease、完整 SHA、GHCR digest 及自動 OAuth 負測。
4. **真實工作鏈**：先驗證 Mart Worker 實際 impersonation，僅從現有 capability 授權的新 `QUEUED` 手動 CEO request 執行一次；readback Worker final status、Gateway requestId、schema accepted、`report_hash`、immutable GCS 與 PG、錯誤無資料洩漏。未知終態**不得重送**，報告 `PARTIAL`（缺資料）也不能寫成全數 PASS。最後驗證 API 認證讀回同一 immutable history。
5. **部署邊界**：omniAgent pilot `gemini-p0v-b03e5f55` 是 **0%**，不是正式 route。因 Cloud Run Job 沒有 Service 0%-traffic candidate，只能做 digest-fenced 的無 Scheduler canary／受控更新及可復原路徑；未證實 IAM 不得更換既有 CEO Job image，未達 CEO E2E 不得正式切流量。

## 2026-10-13 續接：真人授權 IAM 後之實際執行證據

- **真正的 Cloud Run Worker IAM／Gateway 驗證 PASS**：[Janus #38366833454](https://github.com/tommylin15/janus-omniforge/actions/runs/38366833454)。使用既有 `janus-ceo-analysis` Job 原本的 `intelligence-mart` 執行身分，經受限 `omniagent-codex-market-client` impersonation 產生 Gateway audience ID token，對既有 0% private pilot 發出不完整 JSON，只接受 Gateway authenticated `400 invalid_request`；排除 anonymous 401／IAM 403。非模型呼叫、沒有 DB／Job image write；execution terminal readback／lease release PASS。原先 CI 沒有 `iam.serviceAccounts.getIamPolicy` 的讀權仍是 CI 觀察限制，但**不再用它阻擋已被真實 runtime 成功證明的 TokenCreator 呼叫**。
- **CEO Job-only digest-fenced rollout 與 postdeploy signed canary PASS**：[Janus #38367279461](https://github.com/tommylin15/janus-omniforge/actions/runs/38367279461)。重用 full release #38363636133 原 SHA `b63bf350213fa7c3933724fa38006d8ab7b8033f` 專用 CEO image，更新既有 `janus-ceo-analysis`、維持 1 CPU／1Gi、maxRetries=0、無 Scheduler，實際經新版 image 再以 Mart 執行身分完成 authenticated malformed-body Gateway canary；部署共用 lease 已安全釋放。沒有更改另外四個 Job、Janus API 正式 traffic 或 omniAgent Gateway 正式 traffic。
- **真實 Flash-Lite 合成 JSON 回路 PASS**：[Janus #38367878942](https://github.com/tommylin15/janus-omniforge/actions/runs/38367878942) SUCCESS：部署後 CEO Job 透過 Janus ProviderRouter／market-mart 專用 SA → private omniAgent Gateway → Gemini Flash-Lite → Janus Pydantic CEO schema；五份 synthetic Specialist hash 回傳核對、單次呼叫、terminal/readback、global lease release PASS。這是**合成、非個人的最小 end-to-end**；未使用真實 Owner request、完整 Fact Pack／`validate_ceo_output`，未寫 PostgreSQL／GCS CEO 報告，不能宣稱正式 CEO report 功能 PASS。
- **剩餘真正 CEO 業務 gate**：Owner 實際透過原 API/capability 發起**新**手動分析，Worker 讀取真實 validated Fact Pack（market-mart 32 KiB prompt 上限）、Gemini 文字轉 CEO JSON schema + Janus `validate_ceo_output`，再以 immutable GCS + PostgreSQL report/hash + authenticated API history readback 證明。`200 text` 或合成 schema canary 均不能替代。先前任何失敗／未知終態 request 不得重送；除非已有合法新 request，不能冒充 Owner 建立資料。

## 2026-10-13 P0-V 隔離技術驗收總結與剩餘阻塞

**最小垂直鏈路與獨立技術元件 PASS，完整五角色 Fact Pack 容量與真實 Owner CEO 報告仍 PARTIAL。** 原持股／重算 P0 `PAUSED BY USER` 不變。

| 關卡 | 真實驗收證據 | 判定 |
| --- | --- | --- |
| 原 Mart SA → 專用 market-mart IAM token → 0% private Gateway | [#38366833454](https://github.com/tommylin15/janus-omniforge/actions/runs/38366833454) | PASS，模型 0 次 |
| 同來源 GHCR CEO Job-only rollout、postdeploy signed check、原四 Jobs／正式流量不動 | [#38363636133](https://github.com/tommylin15/janus-omniforge/actions/runs/38363636133)、[#38367279461](https://github.com/tommylin15/janus-omniforge/actions/runs/38367279461) | PASS |
| 已部署 CEO Job → Gateway → Gemini Flash-Lite → Janus CEO Pydantic JSON/hashes | [#38367878942](https://github.com/tommylin15/janus-omniforge/actions/runs/38367878942) | PASS，**短合成輸入、沒有發表** |
| 五個合成角色 → 完整 `execute_ceo`／`validate_ceo_output`，負向 evidence/numeric/hash/missing，隔離 CI PG Mart write → Owner API history／hash、隔離 | [#38372494501](https://github.com/tommylin15/janus-omniforge/actions/runs/38372494501)：73 tests PASS | PASS，**CI 專用資料庫** |
| 真實 CEO Job 的 GCS acceptance 專用前綴 create/readback/delete ＋ 真實 PG JSONB non-writing roundtrip | 同 [#38372494501](https://github.com/tommylin15/janus-omniforge/actions/runs/38372494501)，Job terminal／共享 lease readback PASS | PASS，**無正式 PG／canonical 寫入** |
| 完整五角色 Fact Pack 至 Gateway、512 token 真實長報告 | `_prompt` 量測 **29,987 UTF-8 bytes**；omniAgent 新 0% 候選已在 #38389373782 使用 29,987 B real model request PASS | **上游輸入容量 PASS**；Janus 新 Worker 的 full JSON+validator live roundtrip 仍待驗收 |
| 真正 Owner capability → 新 request → model → full report → immutable GCS/PG → authenticated API | 五角色研究尚未就緒，且前一項容量未解 | **NOT VERIFIED** |

**失敗與修正不可消失**：技術測試初版 [#38371376749](https://github.com/tommylin15/janus-omniforge/actions/runs/38371376749) 在既有 PG production Mart 身分執行 `CREATE TEMP` 時 **FAIL**；[#38372150846](https://github.com/tommylin15/janus-omniforge/actions/runs/38372150846) 讀到 `InsufficientPrivilege`。沒有為了測試加權限，改採 live PG JSONB readback，將表寫入／權限交由獨立 CI PostgreSQL 真實測試，最後 [#38372494501](https://github.com/tommylin15/janus-omniforge/actions/runs/38372494501) SUCCESS。不可把後者宣稱為 live Owner 私有表 write PASS。

**2026-10-13 上游容量契約已實現**：omniAgent 32 KiB market-only、Life／Chat 8 KiB 與 128 KiB envelope 已通過 [真實 0% 候選 #38389373782](https://github.com/tommylin15/omniAgent/actions/runs/38389373782)，超限與 IAM 測試亦 PASS。Janus 已同步 adapter 並 pin 新 tag `ghcr-965b05542a35`；新來源 CI／Job rollout／完整 CEO JSON＋validator 必須獨立驗收。512 output tokens 仍是另外限制。

**不得把** 0% API candidate [#38364240675](https://github.com/tommylin15/janus-omniforge/actions/runs/38364240675) 與 synthetic smoke 當正式上線；Janus API／omniAgent Gateway 正式流量、四個排程 Jobs、持股 P0 均未因此切換或恢復。

## 2026-10-13 32 KiB 完整合成 CEO Prompt 最新驗收（PARTIAL）

- **上游容量 PASS**：omniAgent `market-mart` 專用 32,768 B prompt／131,072 B JSON envelope；其他 consumer 不變。[omniAgent #38389373782](https://github.com/tommylin15/omniAgent/actions/runs/38389373782) 真實 29,987 B 輸入取得 200/COMPLETED。
- **Janus full Release PASS**：[ #38392237542](https://github.com/tommylin15/janus-omniforge/actions/runs/38392237542) Python／Flutter、原四映像＋CEO image/public digest。只更新 CEO Job，不切正式 API／四排程 Jobs。原 rollout [#38392891696](https://github.com/tommylin15/janus-omniforge/actions/runs/38392891696) 因 operation wait 超時 **FAIL**；[ #38393696263](https://github.com/tommylin15/janus-omniforge/actions/runs/38393696263) 確認 executions 全部 terminal 並安全釋放原 owner lease；[ #38394294374](https://github.com/tommylin15/janus-omniforge/actions/runs/38394294374) 真實 Job SHA、候選 URL、服務身分及 signed preflight 日誌讀回 **PASS**。
- **30 KiB 合成五角色離線 full CEO validator PASS**：[ #38401261530](https://github.com/tommylin15/janus-omniforge/actions/runs/38401261530) 真正執行 `_prompt`、`execute_ceo`、五份 hash、`metrics`、缺值與 numeric/evidence guard，不呼叫模型、不建立 Owner 報告。最初 [#38394571293](https://github.com/tommylin15/janus-omniforge/actions/runs/38394571293) **FAIL**；唯讀診斷 [#38395032007](https://github.com/tommylin15/janus-omniforge/actions/runs/38395032007) 讀到 `KeyError`，確認合成 fixture 缺 `metrics`，已補齊並加上離線前置測試。
- **完整模型回路 FAIL（已取得安全根因範圍）**：新的單次 [#38401658102](https://github.com/tommylin15/janus-omniforge/actions/runs/38401658102) 真實工作負載終態 FAIL，共用部署鎖由原持有者安全釋放，無 Owner／canonical 資料寫入。Janus [#38402397865](https://github.com/tommylin15/janus-omniforge/actions/runs/38402397865) 為 `provider_unavailable`；Gateway [#38402703001](https://github.com/tommylin15/janus-omniforge/actions/runs/38402703001) 觀察到同視窗 **1 次** POST `/v1/gemini/execute` 回 **HTTP 502**；[ #38402961256](https://github.com/tommylin15/janus-omniforge/actions/runs/38402961256) structured log 為 `market-mart failed:gemini_execution_failed`，耗時 **20,558 ms**。Gateway 此碼涵蓋非 quota upstream 失敗、空模型文字或 invalid reply；**沒有證據證明是 512-token 截斷、上游 HTTP 5xx 或 timeout 其中任何一項**，不得假設。
- **下一個必要依賴**：omniAgent Gateway 在維持 prompt/key/raw-response 不記錄的前提下，補齊受限的 provider safe failure subtype／upstream HTTP status／finishReason 觀察；查明再有界修正、重新驗證 0% 候選並由 Janus 驗收 full Prompt → Gemini → CEO JSON + original validator。暫不盲目第三次呼叫、不放寬模型／付費額度。**P0-V 技術驗收 PARTIAL；真實 Owner CEO 報告 NOT VERIFIED。**


## 2026-10-13 market-mart 2,048-token 候選與 Janus 再驗收（PARTIAL）

- omniAgent 已獨立完成 `market-mart` 專屬輸出 cap **2,048 maxOutputTokens**、保留 Life／Chat **512**、不開啟付費模型，並提供 fail-closed `MAX_TOKENS` 等安全子類別。[上游 GHCR／Node／候選真實驗收 #38409577652](https://github.com/tommylin15/omniAgent/actions/runs/38409577652) **PASS**；私人 0% Gateway 候選是 `p0v-market2048-227a0bdc`，不是正式流量服務。上游候選只驗證 revision／設定／身份，**未發出本次 CEO 推論**。
- Janus 將完整合成五角色原生 Prompt／`execute_ceo` 無模型測試延續至 [#38421876332](https://github.com/tommylin15/janus-omniforge/actions/runs/38421876332) **PASS**。為避免打亂已簽章的實際 CEO Job 與舊候選，只在一次性 Cloud Run `RunJob containerOverrides.env` 指定新 2,048-token Gateway tag；**永久 Job env／image／Service Account／Scheduler／正式 API 與 Gateway 流量全部維持原狀**，參照原不可變 CEO image SHA `a05f1f4dea80ecbd947829cd2751e1253f822cee`。
- [Janus 真實完整 CEO 一次性驗收 #38422168730](https://github.com/tommylin15/janus-omniforge/actions/runs/38422168730) **FAIL**；來源／offline／WIF PASS、Cloud Run execution terminal failure、global lease 已釋放，未寫任何正式 Owner 或 canonical 報告。不同於前次 512-token 無細分 502，本次由 [安全診斷 #38423028775](https://github.com/tommylin15/janus-omniforge/actions/runs/38423028775) 證明同一時段 Gateway 僅 **1 次** market-mart POST，約 **881 ms**，回 HTTP **502**，安全 subtype 為 `provider_unavailable`；[upstream HTTP 唯讀 readback #38423305926](https://github.com/tommylin15/janus-omniforge/actions/runs/38423305926) 進一步確證 **Gemini Provider 實際收到 HTTP 503**。不是證據充分的 output cap、JSON schema 或 hash validator 失敗；失敗發生於上游生成結果可被驗證之前。
- **目前技術結論**：上游 Gateway 32 KiB／2,048 output 的程式、CI、私有候選部署與安全錯誤分類 **PASS**；真正 Janus 原始五角色完整 Prompt → Gemini → 有效 CEO JSON／`validate_ceo_output` **仍 FAIL／PARTIAL**，因這筆 Gemini HTTP 503。保留無盲重送規則；待上游可用性有獨立正向證據，方以**新合成 request ID**受控重做一次，不能把 503、部分成功或無有效報告包裝為 PASS。
- **Owner 業務 E2E 仍 NOT VERIFIED**：五角色真實資料就緒後，須另用新 capability 授權手動請求完成 immutable GCS + PostgreSQL report/hash + authenticated Owner API history。持股／Private Recalc P0 保持 PAUSED BY USER，不能因本任務恢復。


## 2026-10-14 新版 Gateway 實際合成五角色 CEO 技術驗收 — PASS

**技術接線已通過；真實 Owner 報告／研究模型品質仍是獨立 OPEN gate。**

- **上游核准的恢復候選（未切正式流量）**：`p0v-market2048-00d45861`；實際 endpoint 為 `https://p0v-market2048-00d45861---omniagent-agent-gateway-2oo7qbkd5q-uc.a.run.app/v1/gemini/execute`。Google ID Token audience **仍是** `https://omniagent-agent-gateway-2oo7qbkd5q-uc.a.run.app`。omniAgent 私有候選 [#38488277144](https://github.com/tommylin15/omniAgent/actions/runs/38488277144) PASS；Gemini 503 改善後唯一短呼叫可用性 smoke [#38488547115](https://github.com/tommylin15/omniAgent/actions/runs/38488547115) PASS。
- **Janus 同來源離線測試 PASS**：[Analysis Product CI #38490691563](https://github.com/tommylin15/janus-omniforge/actions/runs/38490691563) 經由實際 `_prompt` 與 `execute_ceo` 重新驗證完整五角色合成 Fact Pack（29,500–32,768 UTF-8 bytes）、`metrics`、五份 hash、JSON／numeric／evidence guard、單次 Cloud Run Job env override；原有 release image SHA `a05f1f4dea80ecbd947829cd2751e1253f822cee` 不變。
- **真實模型端到端驗收 PASS**：[Janus workflow #38490887562](https://github.com/tommylin15/janus-omniforge/actions/runs/38490887562) **SUCCESS**（workflow HEAD `05ec632fa44424f216e400da3c508d0d822245f5`，一輪）。使用已部署 `janus-ceo-analysis` 與原本 `intelligence-mart` 執行身分；僅於本輪 `RunJob containerOverrides.env.MART_OMNI_GATEWAY_URL` 覆寫至新 0% Gateway，完整 `_prompt` → market-mart signed Gemini Flash-Lite → Janus original `execute_ceo`／CEO Pydantic／五角色 hash／evidence／numeric validator。必須是 `PARTIAL`（合成資料不足、不具 publication authority）才通過，拒絕假造正式結論。Workflow 有效 terminal／模型呼叫數=1／無 Owner request、GCS/PG 正式報告／無正式流量修改與永久 Job 更新的 receipt；artifact `p0v-janus-32k-real-ceo-contract` 已上傳。共用 release lease 在確認 CEO execution terminal 後由原 owner 正常釋放。
- **失敗歷史不覆寫**：舊 2,048-token 候選 `227a0bdc` 的實際測試 [#38422168730](https://github.com/tommylin15/janus-omniforge/actions/runs/38422168730) 為 **FAIL**，其 Gateway HTTP 502／上游 Gemini 503 仍是歷史證據；這次在已成功上游可用性驗收的新 `00d45861` 候選上完成新的單次請求，不是重送同一個 request。
- **已涵蓋的隔離持久層 contract**：[原 P0-V CI＋dev 合成測試 #38372494501](https://github.com/tommylin15/janus-omniforge/actions/runs/38372494501) 73 tests PASS：隔離 PostgreSQL 的 CEO report/hash、Owner API 讀回與跨 Owner denied、immutable terminal；dev 真實 GCS 專用測試前綴 create／readback／cleanup、dev PG JSONB non-writing roundtrip。**本次 live full Prompt 測試刻意不建立正式 DB/GCS 報告**，不能稱作真實 Owner DB write 完成。
- **目前 gate 判定**：`P0-V 跨專案技術整合 PASS（合成 full Fact Pack／真實模型／完整 CEO validator＋既有隔離持久層測試）`。`真實五 Specialist 模型品質、真實 Owner capability 新 request、immutable GCS+PostgreSQL report publication 與 authenticated Owner history` **仍 OPEN／NOT VERIFIED**，不因本次合成 PASS 自動解封。持股與 Private Recalc P0 保持使用者暫停狀態；Janus API、四 Jobs、固定 Preview 與 omniAgent Gateway 正式流量沒有切換。

