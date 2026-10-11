# B9 Event／Catalyst：繁中人工事件標註與 OOS 研究

狀態：**資料管線實作中；人工標註／ML 品質 NOT VERIFIED**。沿用 [Specialist 契約](specialist-engines.md) 和 [B9 品質證據](../b9-quality-evidence.md)，不重做 B7/B8。

## 原始資料、授權和事件識別

- 原始事實及時間戳留在 Core Iceberg immutable snapshot；研究工具唯讀接受由固定 Core fence 匯出的官方 events JSONL，不回寫 canonical、PostgreSQL serving 或 champion。
- 輸入必須具 event_id、symbol、details、source_id、provenance_id、published_at、observed_at 和 core_snapshot_id。限定既有 source allowlist 的 twse／mops／tpex、source_authorization=official，缺值、未授權、時間不明或公告時間晚於接收時間的資料拒收。
- 候選採 stable event_group_id（source＋symbol＋event_id）及 candidate_id（group＋正文 content_sha）；重複候選去重，修訂版保留不同身分，同事件不同修訂不能跨訓練／測試。
- 保存 published_at、observed_at 與 effective_date，各自語意不同。公告之後才生效的法說會，不能拿未來生效日當已經發生的結果。所有時間必須具明確 timezone。
- 既有 Core 官方來源批准**不等於**可供 ML 訓練的授權。training_authorization_reference 必須對照**獨立** event-training-grants-v1 權限紀錄（status=approved、source_id、authorization_reference、scope=local_event_classifier_research、approved_by、verified_at、evidence_uri），不能只在候選資料手填字串就通過。證據 URI 與核准者必須由實際人員驗證，程式檢查其結構與來源 scope，**不自稱已完成法律授權查核**；無已驗證 grant，人工分類完成也拒絕訓練。不可自動補造權利 reference。

## 標籤 schema（event-label-v1）

候選保存 event_id、candidate_id、event_group_id、symbol、source_id、source_authorization、training_authorization_reference、core_snapshot_id、provenance_id、published_at、observed_at、effective_date、content_sha、text、review_status=pending、category=null、direction=null、reviewer=null、label_version=null。

人工 review JSONL 必填 candidate_id、content_sha、status=approved、label_version=event-label-v1、review_method=human、reviewer（可稽核識別）、reviewed_at（含 timezone）、category、direction；可另有 ambiguity_note。必須與固定候選正文 SHA 相符、審核時間不早於原始接收、reviewer 不可空白，且不得有重複或互相衝突批准。

分類：earnings／guidance／investor_meeting／dividend／financing／asset_transaction／governance／regulatory／other。方向：positive／negative／neutral／uncertain。方向是審核者根據**當時公告文字**的語意，不是事後股價報酬。歧義保留 uncertain 與註記，不強填正負，也不能由 Rules／LLM 自動填 human reviewer。

## Chronological holdout

- 固定具 timezone 的 cutoff；train 需要 published_at、reviewed_at **都早於 cutoff**；test 的 published_at 在 cutoff 起，test 真值可以之後審核但不參與 fit。
- 強制 issuer-disjoint（holdout 股票代號不可出現在 train）及 event-revision group 防洩漏，並記錄因此排除的樣本。
- 預設至少 100 train、30 test，且 train/test 的分類與方向均至少兩類；否則回報 insufficient_labeled_data 而非零分。研究指標包含 macro-F1、逐類 precision/recall、Rules baseline、未校準 Brier/ECE、類別分布 drift、CPU elapsed、process peak RSS，並保留 dataset／split hash。
- 現有本機研究基準為 scikit-learn 字元 TF-IDF + LogisticRegression；不呼叫外部 LLM 或遠端模型。本機 multilingual Transformer 的固定權重、授權、版本和 CPU 1 GiB 驗證**尚未完成**，不能把 TF-IDF 當 Transformer 已通過。
- 無論研究 OOS 是否能算出分數，publication_authority=false，classifier_probability=null，不能自動升 champion。

## 有界離線執行

下列指令僅使用**已有來源授權及 Core snapshot fence** 的研究匯出，不代表目前已有符合條件的真人標籤。輸出 create-only、owner-only 0600；最多 2,000 JSONL records，單列最多 512 KiB。

~~~bash
python scripts/gcp/b9-event-labels.py candidates \
  --events-jsonl /secure/research/core-events.jsonl \
  --core-snapshot-id 'sha256:FIXED_CORE_ID' \
  --out /secure/research/event-candidates-v1.json

# 人工閱覽正文、驗證訓練用途授權後填入 reviews.jsonl
python scripts/gcp/b9-event-labels.py oos \
  --candidates-json /secure/research/event-candidates-v1.json \
  --reviews-jsonl /secure/research/reviews-v1.jsonl \
  --training-grants-json /secure/research/source-training-grants-v1.json \
  --cutoff '2026-08-01T00:00:00+08:00' \
  --out /secure/research/event-oos-v1.json
~~~


獨立的 source-training-grants-v1.json 形狀：

~~~json
{"schema_version":"event-training-grants-v1","grants":[{"source_id":"<twse/mops/tpex>","authorization_reference":"<來源權利授權紀錄ID>","status":"approved","scope":"local_event_classifier_research","approved_by":"<權利審核人識別>","verified_at":"<ISO8601 timezone>","evidence_uri":"<核准證據 https:// 或 gs:// 位置>"}]}
~~~

此為**格式範例而非現有授權**。在有真實權利證據之前不得填入假值，也不得將 demo、fixture、空白範例當合法訓練資料。

示例 cutoff 不是 OOS 成功證據。待真正有授權及人工審核資料時，仍需對時間切分、審核者一致性、類別數量、發行人覆蓋、Immutable model/version、GCP dev readback、模型校準及 Champion gate 進行驗收。

## 目前未完成

1. 從既有 exact-snapshot Core public events reader 產出 bounded 真實研究候選及 immutability readback；目前 CLI 是離線 JSONL 入口，**不冒充已完成真實 Core 匯出**。
2. 取得可稽核 source-specific training-use permission，真正人工逐筆標註和複核，檢查類別不均與爭議。真實人工 ground truth 目前仍無 evidence。
3. 使用正式標籤完成 OOS、校準、drift、Transformers 模型 license/CPU 預算、immutable artifacts 與 dev live readback。
4. 正式 Event Parser／Rules、五 Specialist cache、B7/B8、CEO 與 publication 現狀不更動；Event ML、B9 維持 PARTIAL／NOT VERIFIED。

實作入口：jobs/intelligence-mart/intelligence_mart/event_labeling.py、scripts/gcp/b9-event-labels.py、tests/test_event_labeling.py。所有測試 fixture 非真人標籤。
