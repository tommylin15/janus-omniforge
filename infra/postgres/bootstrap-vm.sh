#!/bin/bash
set -euo pipefail
umask 077

image="$1"
data_dir=/mnt/stateful_partition/postgres
env_file=/run/janus-postgres-bootstrap.env

read -r bootstrap_password
read -r control_password
read -r catalog_password
read -r publication_password
read -r audit_password
read -r web_control_password
read -r web_catalog_password
read -r web_publication_password
read -r mart_catalog_password
read -r mart_publication_password
read -r private_api_password
read -r private_pipeline_password

token="$(curl -fsS -H 'Metadata-Flavor: Google' \
  'http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token' \
  | sed -n 's/.*"access_token":"\([^"]*\)".*/\1/p')"
sudo mkdir -p /run/janus-docker
printf '%s' "$token" | sudo docker --config /run/janus-docker login -u oauth2accesstoken --password-stdin us-central1-docker.pkg.dev >/dev/null
unset token
sudo docker --config /run/janus-docker pull "$image" >/dev/null
sudo rm -rf /run/janus-docker

sudo mkdir -p "$data_dir"
sudo chmod 700 "$data_dir"
printf 'POSTGRES_PASSWORD=%s\nPOSTGRES_DB=postgres\nPGDATA=/var/lib/postgresql/data\n' "$bootstrap_password" | sudo tee "$env_file" >/dev/null

sudo docker rm -f janus-postgres >/dev/null 2>&1 || true
sudo docker run -d --name janus-postgres --restart=no \
  --env-file "$env_file" -v "$data_dir:/var/lib/postgresql/data" "$image" >/dev/null

for _ in $(seq 1 60); do
  if sudo docker exec janus-postgres pg_isready -U postgres -d postgres >/dev/null 2>&1; then break; fi
  sleep 1
done
sudo docker exec janus-postgres pg_isready -U postgres -d postgres >/dev/null

sudo docker exec \
  -e CONTROL_PASSWORD="$control_password" \
  -e CATALOG_PASSWORD="$catalog_password" \
  -e PUBLICATION_PASSWORD="$publication_password" \
  -e AUDIT_PASSWORD="$audit_password" \
  -e WEB_CONTROL_PASSWORD="$web_control_password" \
  -e WEB_CATALOG_PASSWORD="$web_catalog_password" \
  -e WEB_PUBLICATION_PASSWORD="$web_publication_password" \
  -e MART_CATALOG_PASSWORD="$mart_catalog_password" \
  -e MART_PUBLICATION_PASSWORD="$mart_publication_password" \
  -e PRIVATE_API_PASSWORD="$private_api_password" \
  -e PRIVATE_PIPELINE_PASSWORD="$private_pipeline_password" \
  janus-postgres bash -ceu '
    printf "\\getenv control_password CONTROL_PASSWORD\n\\getenv catalog_password CATALOG_PASSWORD\n\\getenv publication_password PUBLICATION_PASSWORD\n\\getenv audit_password AUDIT_PASSWORD\n" > /tmp/vars.sql
    cat /tmp/vars.sql /opt/janus/migrations/001_roles_and_schemas.sql | psql -U postgres -d postgres
    psql -U postgres -d janus_control -f /opt/janus/migrations/002_control_plane.sql
    psql -U postgres -d janus_control -f /opt/janus/migrations/003_iceberg_jdbc_catalog.sql
    psql -U postgres -d janus_control -f /opt/janus/migrations/004_source_coverage.sql
    psql -U postgres -d janus_control -f /opt/janus/migrations/005_source_health_telemetry.sql
    psql -U postgres -d janus_control -f /opt/janus/migrations/006_admin_settings_audit.sql
    printf "\\getenv web_control_password WEB_CONTROL_PASSWORD\n\\getenv web_catalog_password WEB_CATALOG_PASSWORD\n" > /tmp/web-vars.sql
    cat /tmp/web-vars.sql /opt/janus/migrations/007_web_runtime_roles.sql | psql -U postgres -d janus_control
    printf "\\getenv mart_catalog_password MART_CATALOG_PASSWORD\n\\getenv mart_publication_password MART_PUBLICATION_PASSWORD\n" > /tmp/mart-vars.sql
    cat /tmp/mart-vars.sql /opt/janus/migrations/008_mart_runtime_roles.sql | psql -U postgres -d janus_control
    psql -U postgres -d janus_control -f /opt/janus/migrations/017_mart_analysis_queue.sql
    psql -U postgres -d janus_control -f /opt/janus/migrations/018_mart_publication.sql
    psql -U postgres -d janus_control -f /opt/janus/migrations/009_admin_cursor_indexes.sql
    psql -U postgres -d janus_control -f /opt/janus/migrations/010_execution_runtime_options.sql
    psql -U postgres -d janus_control -f /opt/janus/migrations/011_control_settings_ownership.sql
    psql -U postgres -d janus_control -f /opt/janus/migrations/012_first_batch_source_ids.sql
    psql -U postgres -d janus_control -f /opt/janus/migrations/013_membership_versions.sql
    printf "\\getenv private_api_password PRIVATE_API_PASSWORD\n\\getenv private_pipeline_password PRIVATE_PIPELINE_PASSWORD\n" > /tmp/private-vars.sql
    cat /tmp/private-vars.sql /opt/janus/migrations/014_private_workspace.sql | psql -U postgres -d janus_control
    psql -U postgres -d janus_control -f /opt/janus/migrations/015_private_mcp_servers.sql
    psql -U postgres -d janus_control -f /opt/janus/migrations/016_private_assistant_storage.sql
    psql -U postgres -d janus_control -f /opt/janus/migrations/019_core_mart_integration.sql
    psql -U postgres -d janus_control -f /opt/janus/migrations/020_governance_audit.sql
    printf "\\getenv web_publication_password WEB_PUBLICATION_PASSWORD\n" > /tmp/public-vars.sql
    cat /tmp/public-vars.sql /opt/janus/migrations/021_public_api_role.sql | psql -U postgres -d janus_control
    psql -U postgres -d janus_control -f /opt/janus/migrations/022_mart_publication_review.sql
    psql -U postgres -d janus_control -f /opt/janus/migrations/023_public_stock_index.sql
    psql -U postgres -d janus_control -f /opt/janus/migrations/024_private_investment_profile.sql
    rm -f /tmp/vars.sql /tmp/web-vars.sql /tmp/mart-vars.sql /tmp/private-vars.sql /tmp/public-vars.sql
    openssl req -new -x509 -days 365 -nodes -text \
      -subj "/CN=janus-postgres-dev" -keyout "$PGDATA/server.key" -out "$PGDATA/server.crt" >/dev/null 2>&1
    chmod 600 "$PGDATA/server.key"
  '

sudo docker rm -f janus-postgres >/dev/null
sudo rm -f "$env_file"
unset bootstrap_password control_password catalog_password publication_password audit_password web_control_password web_catalog_password web_publication_password mart_catalog_password mart_publication_password private_api_password private_pipeline_password

sudo docker run -d --name janus-postgres --restart=always \
  -p 5432:5432 -v "$data_dir:/var/lib/postgresql/data" "$image" \
  -c config_file=/opt/janus/postgresql.conf -c hba_file=/opt/janus/pg_hba.conf >/dev/null

for _ in $(seq 1 60); do
  if sudo docker exec --user postgres janus-postgres pg_isready -U postgres -d janus_control >/dev/null 2>&1; then break; fi
  sleep 1
done
sudo docker exec --user postgres janus-postgres pg_isready -U postgres -d janus_control
sudo docker exec --user postgres janus-postgres psql -U postgres -d janus_control -f /opt/janus/readiness.sql
