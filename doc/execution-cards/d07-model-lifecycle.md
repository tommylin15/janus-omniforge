# D07｜Colab開發、GCS模型發布、日週推論及月評估 — AI操作指令
更新：2026-10-23。本輪寫入三模型 ChatGPT 試訓及四模型快取決策；後續使用者要求執行時，依[TODO](../todo.md)完成同一D07工作包，不創第二套queue。
必讀：AGENTS/PROJECT_RULES、[模型生命週期](../spec/model-lifecycle.md)、[X/Y](../spec/specialist-engines.md)、[因子時間](../spec/model-feature-time-contract.md)、[D07卡](d07-specialist-b9-oos.md)、[Colab README](../../research/colab/README.md)。程序/資料量以生命週期SPEC為唯一權威。

## 1. 整包AI指令（可複製）
> 執行D07模型生命週期。核對main及現有Risk/Colab/Controller，按doc/spec/model-lifecycle.md完成共用採集清洗/as-of/label/features→五角色baseline/challenger→OOS→immutable candidate bundle→GCS上傳與讀回→Mart驗證/shadow/registry→深度股票批次推論與站內模板報告→成熟outcome回收與每月評估。先Risk後Quant，其他角色依資料量及標籤，rules也是合法交付。Risk 既有模型不動，三個未發布角色優先由 ChatGPT 研究環境試訓（Colab 可選）；GCS只存artifact，既有Controller/Mart執行分析，不新增每股Job、不恢復Cloud Run訓練器。新流程工程、model promotion及月評估證據分開；每階段可續跑，整包集中必要驗收，不在每股/每角色任意停等。新付費/重大擴權/大量不可逆刪除依PROJECT_RULES處理，OAuth由本人授權。

## 2. 共用Colab入口必須交付的cells
C0掛Drive/checkout固定Git SHA/安裝鎖定依賴→C1選role/start/end/cutoff/cohort→C2採集與resume→C3清洗/品質→C4features/as-of→C5labels/maturity→C6time folds/preprocessor/train→C7OOS/evaluation/model card→C8export→C9候選上傳/readback。
主要程式放repository共享模組；Notebook只呼叫，cell顯示不敏感進度/hash/缺口。斷線後從Drive manifest續跑，不重新抓全歷史。不同角色共用raw/features，不五份重複採集。

### 目前已存在、可照README執行的OHLCV與Risk試點
初次掛載/clone依research/colab/README.md。更新code後固定SHA作本run來源；不要在同run中途pull。
```python
from google.colab import drive
drive.mount('/content/drive')
```
```bash
!python /content/janus-omniforge/research/colab/collect_tw_equities.py --drive-root '/content/drive/MyDrive/給ai專用/janusChatGPT/資料源' --start 2025-01 --end 2026-09 --revision r1 --max-requests 20 --max-minutes 10 --interval 2
!python /content/janus-omniforge/research/colab/run_risk_folder_pilot.py --cutoff 2026-03-31 --result '/content/drive/MyDrive/給ai專用/janusChatGPT/資料源/risk-r1-oos.json' /content/drive/MyDrive/給ai專用/janusChatGPT/資料源/2025-*/ /content/drive/MyDrive/給ai專用/janusChatGPT/資料源/2026-*/
```
這是已有研究試點命令，不是五角色新pipeline已存在；資料夾須有合格manifest且選定同版，實際月份不足時改明確清單。2025以前歷史採集先補程式交易日曆/來源支援再延伸，不僅改start。
新clean/label/train/export指令與notebook由本工項建立，完成後將真實路徑和測試命令回寫README；不能寫不存在的CLI讓使用者直接貼。

## 3. 四角色獨立 XGBoost Notebook 與完整 AI 指令
2026-10-22 使用者要求本輪先交四份開發文件，各文件內已包含可直接貼給AI的完整指令、Colab儲存格、資料/X/Y、baseline、切分、驗收與輸出。這是文件交付，不等於Notebook已開發或模型已訓練。

| 角色 | 獨立開發文件／AI指令 | Notebook交付名稱 |
|---|---|---|
| Quant | [趨勢建模](../colab-models/01-quant-xgboost.md) | `01_Quant趨勢_XGBoost.ipynb` |
| Risk | [波動建模](../colab-models/02-risk-xgboost.md) | `02_Risk風險_XGBoost.ipynb` |
| Fundamental | [營運建模](../colab-models/03-fundamental-xgboost.md) | `03_Fundamental營運_XGBoost.ipynb` |
| Valuation | [估值建模](../colab-models/04-valuation-xgboost.md) | `04_Valuation估值_XGBoost.ipynb` |

四份皆只讀 `JanusDataset_v3_202610/canonical/CURRENT.json` 指定的Parquet release，共用Python模組但可各自Run all；不要求先執行另一模型。新版訓練不得使用上節舊r1 CLI作主要入口，舊命令只供歷史試點重現。Risk沿用既有XGBoost8／八因子，不接手現行部署工項；其他角色以XGBoost為challenger且保留baseline。Event／新聞與人工標註另討論；不在本輪建立第五份Notebook。

### 2026-10-23 新執行路徑：ChatGPT 三角色試訓 → 可部署 → Risk + 三角色快取整併

1. 已確認 Drive `janusChatGPT/CoLab程式` 三份 Notebook：`01_Quant趨勢_XGBoost.ipynb`、`03_Fundamental營運_XGBoost.ipynb`、`04_Valuation估值_XGBoost.ipynb`。用 ChatGPT 可用 Python／研究環境依三份原模型契約直接試做，不強制 Colab；無完整原始 Parquet 授權讀取時回報 BLOCKED，不拿片段摘要冒充實收。固定 CURRENT/manifest/SHA 與 Git source、依賴/seed。
2. 每角色真實訓練與 time-purged OOS/baseline，保留 mature-at/PIT/公司行動/授權、防洩漏、清洗及缺值；輸出模型卡、研究報告、UBJ、安全重新載入與固定向量、版本/hash。完成 GCS 不可變候選與受控 shadow/發布接口相容評估；個別以有證據的 DEPLOYABLE/RESEARCH_ONLY/INCONCLUSIVE/BLOCKED 呈現，不自動切 ACTIVE。
3. 三者**全部可部署**前，不重訓 Risk v1、不修改 Risk 正式 Job/ACTIVE/rollback，不開四角色共同快取工程；可規劃 interface，但不能把規劃當作完成。
4. 三者都達標後，才在既有 Janus Mart 整合四角色共用版本化 loader/cache。Cloud Run 不同 Job execution 無共享 RAM；GCS immutable UBJ/manifest/hash 是權威，每 execution 同角色載入一次+RAM cache 為基線，image layer 固定模型為待實測替代；不新增付費/常駐服務，模型與程式 SHA/digest 及 rollback 一起受控。
5. 對相同 Core snapshot/target/X 量測模型 fetch/load/predict/Job 全程時間、GCS GET/bytes、CPU/RAM、成本；核 fixed vector、一致輸出、失效/換版/併發、ETF、Owner、真實日批與回退。未通過原定實測不標 CLOSED；沒有顯著效益則保留基線。

**執行 AI 指令（覆蓋本卡較早 Colab-only 要求）**：只處理 D07 的 Quant、Fundamental、Valuation，從三份現成 Drive Notebook 出發，以 ChatGPT 執行環境做真資料試訓、OOS 與候選驗證，允許模型個別不足。三模型具可部署證據後，才把 Risk v1 一起納入共同跨 Job 版本快取優化；使用既有 GCS、Cloud Run Mart、Controller、PG，無付費擴張。保留 provenance、source authorization、PIT、hash、rollback，別把 Notebook/文件/研究準入當正式發布。

## 4. 候選上傳範例（exporter完成及既有權限確認後才可用）
只示範Google Storage client機制；本次沒有上傳或授權變更。runtime須另實作importer/registry。
操作者先在Colab本人完成Google授權；google-cloud-storage依賴由鎖檔提供。bundle目錄由C8建立，manifest結構files=[{name,sha256,size}]，不包含manifest自身。
```python
from google.colab import auth
auth.authenticate_user()  # 本人互動授權；不使用service-account JSON key
from google.cloud import storage
from pathlib import Path
import hashlib, json

bundle = Path('/content/model_bundle').resolve()  # C8 exporter的輸出
manifest_bytes = (bundle / 'bundle_manifest.json').read_bytes()
manifest = json.loads(manifest_bytes)
role, version = manifest['role'], manifest['model_version']
assert role in {'risk', 'quant', 'fundamental', 'valuation', 'event'}
assert version and all(c.isalnum() or c in '-_.' for c in version)
bucket = storage.Client(project='gen-lang-client-0593591102').bucket(
    'gen-lang-client-0593591102-dev-mart')
prefix = f'models/candidates/{role}/{version}/'
for item in manifest['files']:
    name = item['name']
    assert name != 'bundle_manifest.json'
    path = (bundle / name).resolve()
    assert path.is_relative_to(bundle) and path.is_file()
    raw = path.read_bytes()
    assert len(raw) == item['size']
    assert hashlib.sha256(raw).hexdigest() == item['sha256']
    blob = bucket.blob(prefix + name)
    blob.upload_from_string(raw, if_generation_match=0, checksum='auto')
    assert hashlib.sha256(blob.download_as_bytes()).hexdigest() == item['sha256']
last = bucket.blob(prefix + 'bundle_manifest.json')
last.upload_from_string(manifest_bytes, if_generation_match=0, checksum='auto')
assert last.download_as_bytes() == manifest_bytes
print('CANDIDATE_UPLOADED_NOT_ACTIVE')
```
此精簡示例遇同名object會拒絕，不覆寫；正式uploader須處理412：讀回相同hash才重用，不同hash失敗。先驗本地全包再上傳，限制allowlisted平面檔名/size，禁symlink/路徑跳脫。權限或來源失敗停止受影響步驟並明示；不能讓Colab直接改active。
模型匯入須使用已授權既有受控worker/操作入口，具體CLI/route由實作後回寫，不發明現成發布按鈕。

## 5. 批次、回收與月評估AI指令
> 沿既有batch_controller/Janus Mart擴充角色批次推論及outcome/monthly evaluation。以公開deep symbol union去重，模型每角色載一次、按chunk推論、失敗只補缺；全市場screening保留。盤後接同日EOD/screening，盤前建08:30 due與來源截止/延遲降級，不能把09:00 mart冒稱盤前。每週補成熟結果與品質；每月首週以固定cutoff產出成熟cohort、3/6/12月及baseline對照。GCS月壓縮回饋明細36月、熱讀365日，保護active/rollback/未成熟/引用資料，不直接套舊90日/三代清理。新排程/retention/migration先測試與有界dry-run再dev驗收；不建新訓練Job或自動fit。

## 6. 驗收與回報
- 模型資料量必報「實收原始期數、扣warmup/label後可用、train/val/test獨立期數與股票/事件數」，不只報總列。
- Colab跨月續跑、缺日/修訂/退市、資料時點與train-serving一致、成熟Y與purge、各角色baseline/OOS、序列化預測一致。
- candidate完整性/非法格式/錯hash/同版本異內容拒絕，registry CAS、shadow/live同X、模型回退、私人隔離。
- 日/週/月真實或受控clock occurrence冪等；受控clock不能冒稱自然排程已驗收。盤前不準時時正確降級、模型空缺不阻擋facts。
- 回收已知歷史成熟樣本可先驗計算，不等半年才交付管線；上線後120日真實結果按成熟自然累積，不把未成熟算PASS或另立無限待辦。
- 最終回報commit、notebook/CLI、資料量與hash、候選/active版本、CI/dev/報告讀回、月評估收據及具體剩餘；本輪文件完成僅DOC_UPDATED。

