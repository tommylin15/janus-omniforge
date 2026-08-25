# Operations and testing

最新驗證日期：2026-08-25

## P0 Stage／Core

- Python unit/contract tests：11 passed。
- Python compileall：passed。
- Terraform validate：passed（Google provider 7.45.0）。
- Terraform apply：4 bucket IAM bindings added，0 changed，0 destroyed。
- Post-apply Terraform plan：No changes。
- Docker image build：未執行；目前工作環境沒有 Docker CLI。

Stage writer 使用 immutable create-if-absent、SHA-256 content hash、受控 ID、
去敏 source URL、execution manifest 與 quarantine sidecar。Core DQ 覆蓋
required key、type、date、duplicate、unit、range、schema drift、null-preserving
merge、欄位語意 zero 與極端漲跌保留警示。
