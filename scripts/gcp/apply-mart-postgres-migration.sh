#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

# Apply the Mart runtime roles and pg_hba update to the existing dev VM.
# Catalog and publication passwords are read from stdin, one raw line each.
image="${1:?immutable PostgreSQL image is required}"
mode="${2:-apply}"
credential_source="${3:-stdin}"
data_dir=/mnt/stateful_partition/postgres
docker_config=/run/janus-mart-migration-docker

if [[ "${image}" != *@sha256:* ]]; then
  echo "Refusing mutable PostgreSQL image: ${image}" >&2
  exit 1
fi

if [[ "${credential_source}" == stdin ]]; then
  read -r mart_catalog_password
  read -r mart_publication_password
elif [[ "${credential_source}" == secret-manager ]]; then
  project="${4:?GCP project is required for Secret Manager credentials}"
  token="$(curl -fsS -H 'Metadata-Flavor: Google' \
    'http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token' \
    | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')"
  access_secret() {
    curl -fsS -H "Authorization: Bearer ${token}" \
      "https://secretmanager.googleapis.com/v1/projects/${project}/secrets/$1/versions/1:access" \
      | python3 -c 'import base64,json,sys; sys.stdout.buffer.write(base64.b64decode(json.load(sys.stdin)["payload"]["data"]))'
  }
  mart_catalog_password="$(access_secret janus-postgres-mart-catalog-password)"
  mart_publication_password="$(access_secret janus-postgres-mart-publication-password)"
  unset token
elif [[ "${credential_source}" == file ]]; then
  credential_file="${4:?credential file is required}"
  case "${credential_file}" in
    /tmp/janus-mart-credentials-*) ;;
    *) echo "Refusing credential file outside the dedicated /tmp prefix." >&2; exit 2 ;;
  esac
  chmod 600 "${credential_file}"
  {
    IFS= read -r mart_catalog_password
    IFS= read -r mart_publication_password
  } < "${credential_file}"
  rm -f -- "${credential_file}"
else
  echo "Unsupported credential source: ${credential_source}" >&2
  exit 2
fi
mart_catalog_password="${mart_catalog_password%$'\r'}"
mart_publication_password="${mart_publication_password%$'\r'}"
if [[ -z "${mart_catalog_password}" || -z "${mart_publication_password}" ]]; then
  echo "Both Mart PostgreSQL passwords are required." >&2
  exit 1
fi
echo "Validated Mart migration inputs."
if [[ "${mode}" == check ]]; then
  exit 0
fi

old_image="$(sudo docker inspect --format '{{.Config.Image}}' janus-postgres)"
switched=false

rollback() {
  local status=$?
  trap - ERR
  echo "Migration failed near line ${BASH_LINENO[0]} (status ${status})." >&2
  if [[ "${switched}" == true ]]; then
    sudo docker rm -f janus-postgres >/dev/null 2>&1 || true
    sudo docker run -d --name janus-postgres --restart=always \
      -p 5432:5432 -v "${data_dir}:/var/lib/postgresql/data" "${old_image}" \
      -c config_file=/opt/janus/postgresql.conf -c hba_file=/opt/janus/pg_hba.conf >/dev/null
  fi
  unset mart_catalog_password mart_publication_password
  sudo rm -rf "${docker_config}" >/dev/null 2>&1 || true
  exit "${status}"
}
trap rollback ERR

token="$(curl -fsS -H 'Metadata-Flavor: Google' \
  'http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token' \
  | sed -n 's/.*"access_token":"\([^"]*\)".*/\1/p')"
sudo mkdir -p "${docker_config}"
printf '%s' "${token}" | sudo docker --config "${docker_config}" login \
  -u oauth2accesstoken --password-stdin us-central1-docker.pkg.dev >/dev/null
unset token
sudo docker --config "${docker_config}" pull "${image}" >/dev/null
sudo rm -rf "${docker_config}"

sudo docker rm -f janus-postgres >/dev/null
sudo docker run -d --name janus-postgres --restart=always \
  -p 5432:5432 -v "${data_dir}:/var/lib/postgresql/data" "${image}" \
  -c config_file=/opt/janus/postgresql.conf -c hba_file=/opt/janus/pg_hba.conf >/dev/null
switched=true

for _ in $(seq 1 60); do
  sudo docker exec --user postgres janus-postgres \
    pg_isready -U postgres -d janus_control >/dev/null 2>&1 && break
  sleep 1
done
sudo docker exec --user postgres janus-postgres pg_isready -U postgres -d janus_control >/dev/null

sudo docker exec --user postgres \
  -e MART_CATALOG_PASSWORD="${mart_catalog_password}" \
  -e MART_PUBLICATION_PASSWORD="${mart_publication_password}" \
  janus-postgres bash -ceu '
    printf "\\getenv mart_catalog_password MART_CATALOG_PASSWORD\n\\getenv mart_publication_password MART_PUBLICATION_PASSWORD\n" > /tmp/mart-vars.sql
    cat /tmp/mart-vars.sql /opt/janus/migrations/008_mart_runtime_roles.sql | psql -U postgres -d janus_control
    psql -U postgres -d janus_control -f /opt/janus/migrations/017_mart_analysis_queue.sql
    psql -U postgres -d janus_control -f /opt/janus/migrations/018_mart_publication.sql
    psql -U postgres -d janus_control -f /opt/janus/migrations/019_core_mart_integration.sql
    psql -U postgres -d janus_control -f /opt/janus/migrations/025_pilot_readiness.sql
    rm -f /tmp/mart-vars.sql
    psql -U postgres -d janus_control -v ON_ERROR_STOP=1 <<"SQL"
SELECT rolname, rolsuper, rolcreatedb, rolcreaterole, rolreplication
FROM pg_roles
WHERE rolname IN ($$janus_mart_catalog$$, $$janus_mart_publication$$)
ORDER BY rolname;
SELECT EXISTS (
  SELECT 1 FROM control.schema_migrations WHERE version = $$019_core_mart_integration$$
) AS migration_recorded;
SELECT EXISTS (
  SELECT 1 FROM control.schema_migrations WHERE version = $$025_pilot_readiness$$
) AS pilot_readiness_recorded;
SQL
  '

switched=false
trap - ERR
unset mart_catalog_password mart_publication_password
echo "Mart PostgreSQL migration applied with immutable image ${image}."
