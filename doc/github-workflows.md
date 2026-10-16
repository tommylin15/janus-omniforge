# GitHub Workflows 開發指南

本文件說明 Janus 專案的 GitHub Actions workflow 架構與開發規範。

## 架構概覽

```
.github/
├── actions/
│   └── setup-janus/          # Composite action：共用 setup 步驟
│       └── action.yml
└── workflows/
    ├── ci-v2.yml             # Selective CI（push 觸發）
    ├── finops-dev.yml        # 統一 FinOps 操作
    ├── ghcr-dev.yml          # 統一 GHCR 發布操作
    ├── *.yml                 # 其他專用 workflow
    └── archive/              # 已取代的舊 workflow
```

## Composite Action：setup-janus

所有需要 Python 或 GCP 認證的 workflow 應使用此 action，避免重複 setup 步驟。

### 使用方式

```yaml
steps:
  - uses: actions/checkout@v4
  - uses: ./.github/actions/setup-janus
    with:
      install-deps: minimal    # none | minimal | test | full
      gcp-auth: 'true'
      wif-provider: ${{ vars.GCP_WIF_PROVIDER }}
      service-account: ${{ vars.GCP_CI_SERVICE_ACCOUNT }}
```

### 參數說明

| 參數 | 預設值 | 說明 |
|---|---|---|
| `python-version` | `3.12` | Python 版本 |
| `install-deps` | `minimal` | 依賴安裝層級 |
| `gcp-auth` | `true` | 是否執行 GCP 認證 |
| `wif-provider` | - | GCP Workload Identity Provider |
| `service-account` | - | GCP Service Account |

### 依賴層級

- `none`：不安裝任何 Python 依賴
- `minimal`：只安裝 `pytest==8.4.2`
- `test`：安裝 `requirements-dev.txt` + `ingestion-core`
- `full`：安裝所有 requirements.lock

## 自動化完整發布（AI 可直接觸發）

### auto-release.yml

AI 可以透過更新單一檔案觸發完整發布流程：

```bash
# 1. 更新 ops/auto-release-request.json
{
  "intent": "automated-full-release",
  "approved": true,
  "release_type": "full",
  "skip_api_promote": false,
  "reason": "說明此次發布的原因"
}

# 2. Commit 並 push
git add ops/auto-release-request.json
git commit -m "release: <說明>"
git push origin main
```

### 發布類型

| release_type | 說明 |
|---|---|
| `full` | 完整發布：tests → GHCR → Jobs → API 100% |
| `jobs-only` | 只更新 Jobs（跳過 API candidate/promote） |
| `api-only` | 只更新 API（跳過 Jobs rollout） |

### 發布流程

```
validate → python-tests → publish (4 images 並行)
              flutter-tests ↗
                              ↘
                           verify-ghcr → api-candidate → auth-boundary → preview
                                                                          ↓
                                                                    jobs-rollout → api-promote
```

### 安全機制

- `approved: false` 時不會觸發發布
- 每個階段都有獨立的驗證和回滾機制
- Jobs rollout 失敗會自動回復
- API promote 包含新→舊→新 traffic rehearsal

## 統一 Workflow 模式

### finops-dev.yml

統一 FinOps 操作，支援以下 operation：

| Operation | 說明 | 觸發檔案 |
|---|---|---|
| `gcs-hourly-io` | GCS I/O 量測 | `ops/finops-gcs-hourly-io.json` |
| `core-reference-audit` | Core 引用掃描 | `ops/finops-core-reference-audit.json` |
| `runtime-references` | Runtime 引用讀取 | `ops/finops-reference-runtime.json` |
| `iceberg-readback` | Iceberg 狀態讀回 | `ops/finops-iceberg-readback-once.json` |
| `gcp-acceptance` | GCP 維護操作 | `ops/finops-gcp-live-acceptance.json` |
| `ci-orphans` | CI orphan 清理 | `ops/finops-ci-orphan-generations.json` |

**觸發方式：**
```bash
# 手動觸發
gh workflow run finops-dev.yml -f operation=gcs-hourly-io

# 自動觸發：push 對應的 ops/*.json 檔案
```

### ghcr-dev.yml

統一 GHCR 發布操作，支援以下 operation：

| Operation | 說明 | 觸發檔案 |
|---|---|---|
| `release` | 完整測試 + 4 image 並行 build | `ops/ghcr-release-request.json` |
| `candidate` | 0% 候選部署 | `ops/ghcr-candidate-request.json` |
| `preview` | Preview tag 更新 | `ops/ghcr-preview-request.json` |
| `auth-boundary` | OAuth 邊界驗證 | `ops/ghcr-candidate-boundary-request.json` |
| `jobs-rollout` | 四 Jobs 部署 | `ops/ghcr-jobs-rollout-request.json` |
| `promote` | API 100% 切流 | `ops/ghcr-api-promote-request.json` |

**觸發方式：**
```bash
# 手動觸發
gh workflow run ghcr-dev.yml -f operation=release
gh workflow run ghcr-dev.yml -f operation=jobs-rollout -f release-run=12345678

# 自動觸發：push 對應的 ops/*.json 檔案
```

## 新增 Workflow 規範

### 1. 優先使用統一 workflow

新增操作時，優先考慮加入現有統一 workflow（finops-dev.yml 或 ghcr-dev.yml），而非建立新檔案。

### 2. 使用 composite action

```yaml
# ✅ 正確
- uses: ./.github/actions/setup-janus
  with:
    install-deps: minimal
    wif-provider: ${{ vars.GCP_WIF_PROVIDER }}
    service-account: ${{ vars.GCP_CI_SERVICE_ACCOUNT }}

# ❌ 避免重複
- uses: actions/setup-python@v5
  with:
    python-version: '3.12'
- run: pip install pytest==8.4.2
- uses: google-github-actions/auth@v2
  ...
```

### 3. 統一 workflow 結構

```yaml
name: Janus [Category] operations
on:
  workflow_dispatch:
    inputs:
      operation:
        type: choice
        options: [op1, op2, op3]
  push:
    branches: [main]
    paths: ['ops/[category]-*.json']

jobs:
  detect:
    # 偵測要執行的 operation
    outputs:
      operation: ${{ steps.detect.outputs.operation }}

  op1:
    needs: detect
    if: needs.detect.outputs.operation == 'op1'
    # ...

  op2:
    needs: detect
    if: needs.detect.outputs.operation == 'op2'
    # ...
```

### 4. Request JSON 格式

每個操作對應一個 `ops/*.json` 檔案：

```json
{
  "intent": "operation-specific-intent",
  "no_gcp_mutation": true,
  "purpose": "說明此次操作目的",
  "attempt": 1
}
```

### 5. Concurrency 設定

```yaml
concurrency:
  group: janus-[category]-${{ github.event.inputs.operation || 'push' }}
  cancel-in-progress: false  # 部署操作不可取消
```

## 效能優化

### 1. 並行 build

```yaml
strategy:
  fail-fast: false
  matrix:
    component: [ingestion-core, intelligence-mart, private-pipeline, api]
```

### 2. 依賴快取

composite action 已內建 pip cache：
```yaml
cache: pip
cache-dependency-path: |
  requirements-dev.txt
  jobs/ingestion-core/requirements.lock
  ...
```

### 3. 條件執行

```yaml
# 只在需要時安裝
- name: Install skopeo
  if: needs.detect.outputs.operation == 'candidate'
  run: sudo apt-get install -y skopeo
```

## 遷移舊 Workflow

1. 將舊 workflow 移至 `archive/`：
   ```bash
   git mv .github/workflows/old-workflow.yml .github/workflows/archive/
   ```

2. 在統一 workflow 中新增對應 job

3. 更新 `ops/*.json` 的 path trigger

4. 測試新舊觸發方式都能正常運作

## 相關文件

- [CI/CD 規格](spec/cicd-v2.md)
- [Dev 部署 Runbook](runbook-dev-deploy.md)
- [PROJECT_RULES.md](PROJECT_RULES.md) §12
