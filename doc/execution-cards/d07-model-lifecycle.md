# D07｜Colab開發、GCS模型發布、日週推論及月評估 — AI操作指令
更新：2026-10-21。本輪只寫文件；後續使用者要求執行時，依[TODO](../todo.md)完成同一D07工作包，不創第二套queue。
必讀：AGENTS/PROJECT_RULES、[模型生命週期](../spec/model-lifecycle.md)、[X/Y](../spec/specialist-engines.md)、[因子時間](../spec/model-feature-time-contract.md)、[D07卡](d07-specialist-b9-oos.md)、[Colab README](../../research/colab/README.md)。程序/資料量以生命週期SPEC為唯一權威。

## 1. 整包AI指令（可複製）
> 執行D07模型生命週期。核對main及現有Risk/Colab/Controller，按doc/spec/model-lifecycle.md完成共用採集清洗/as-of/label/features→五角色baseline/challenger→OOS→immutable candidate bundle→GCS上傳與讀回→Mart驗證/shadow/registry→深度股票批次推論與站內模板報告→成熟outcome回收與每月評估。先Risk後Quant，其他角色依資料量及標籤，rules也是合法交付。模型由Colab人工訓練；GCS只存artifact，既有Controller/Mart執行分析，不新增每股Job、不恢復Cloud Run訓練器。新流程工程、model promotion及月評估證據分開；每階段可續跑，整包集中必要驗收，不在每股/每角色任意停等。新付費/重大擴權/大量不可逆刪除依PROJECT_RULES處理，OAuth由本人授權。

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

## 3. 五角色開發指令
每段均沿共用C0–C9；不是新增五份獨立排程。
| 角色 | 可直接交給AI的指令 |
|---|---|
| Risk | 沿用risk_pilot.py五因子/Ridge與vol20 baseline，先補市場交易日缺口/company action/feature parity與成熟20日label；3–5年是擴充目標，已有短史可PROBE。完成時間分組OOS/MAE/RMSE、可信線性模型序列化、影子推論、日更及20交易日回收；分位/回撤後續獨立評估，不混入原Y。 |
| Quant | 共用價量/benchmark X，按5與20交易日、up/outperform/return分target；先Logistic/Ridge對規則，再淺LightGBM。建fold內校準/成本後效用/不可成交與日期purge，鎖定test。用同bundle/registry批次推論，不拿同日收盤成交假設掩蓋前視。 |
| Fundamental | 先月營收，補可追溯公告版次與13/15月warmup；36月可簡單試點、60–84月為目標。建立下一月YoY及季報獨立sample/label，ElasticNet對季節性基準；季資料不足rules。只有新公告/修訂dirty重算，下一公告成熟後評分。 |
| Valuation | 先兩年自身PE/PB與合法cohort；擴3–5年估值/財報/產業。以月末樣本做Ridge/Huber估同業倍數，排除Y代數等價X、金融/非金融分開；輸出相對定價及限制，另追60/120日效用，不稱內在合理價。 |
| Event | 先公告parser/日期/修訂/去重rules；交付人審label指南/抽樣複標/時間及家族切分。取得足量真標籤再TF-IDF+Logistic，不用股價漲跌替語意標籤；人審結果及5/20日市場反應各回收，缺類別仍rules。 |

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

