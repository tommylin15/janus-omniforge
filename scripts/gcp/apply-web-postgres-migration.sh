#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

# Apply only the Web runtime role migration to the existing dev PostgreSQL VM.
# The three passwords are read from stdin in this order:
#   janus-postgres-web-control-password
#   janus-postgres-web-catalog-password
#   janus-postgres-web-publication-password

image="${1:?immutable PostgreSQL image is required}"
mode="${2:-apply}"
credential_source="${3:-stdin}"
data_dir=/mnt/stateful_partition/postgres
docker_config=/run/janus-web-migration-docker
credential_file="${4:-}"

if [[ "${image}" != *@sha256:* ]]; then
  echo "Refusing mutable PostgreSQL image: ${image}" >&2
  exit 1
fi

if [[ "${credential_source}" == stdin ]]; then
  credential_file="/tmp/janus-web-credentials-$$"
  { IFS= read -r web_control_password; IFS= read -r web_catalog_password; IFS= read -r web_publication_password; } || true
  printf '%s\n%s\n%s\n' "${web_control_password%$'\r'}" "${web_catalog_password%$'\r'}" "${web_publication_password%$'\r'}" > "${credential_file}"
elif [[ "${credential_source}" == file ]]; then
  case "${credential_file}" in
    /tmp/janus-web-credentials-*) ;;
    *) echo "Refusing credential file outside the dedicated /tmp prefix." >&2; exit 2 ;;
  esac
  chmod 600 "${credential_file}"
  { IFS= read -r web_control_password; IFS= read -r web_catalog_password; IFS= read -r web_publication_password; } < "${credential_file}"
else
  echo "Unsupported credential source: ${credential_source}" >&2
  exit 2
fi
web_control_password="${web_control_password%$'\r'}"
web_catalog_password="${web_catalog_password%$'\r'}"
web_publication_password="${web_publication_password%$'\r'}"
if [[ -z "${web_control_password}" || -z "${web_catalog_password}" || -z "${web_publication_password}" ]]; then
  echo "All Web PostgreSQL passwords are required." >&2
  exit 1
fi
echo "Validated Web migration inputs."
if [[ "${mode}" == "check" ]]; then
  exit 0
fi

old_image="$(sudo docker inspect --format '{{.Image}}' janus-postgres)"
switched=false

rollback() {
  local status=$?
  trap - ERR
  echo "Migration command failed near line ${BASH_LINENO[0]} (status ${status})." >&2
  if [[ "${switched}" == true ]]; then
    echo "Migration failed; restoring the previous PostgreSQL image." >&2
    sudo docker rm -f janus-postgres >/dev/null 2>&1 || true
    sudo docker run -d --name janus-postgres --restart=always \
      -p 5432:5432 -v "${data_dir}:/var/lib/postgresql/data" "${old_image}" \
      -c config_file=/opt/janus/postgresql.conf -c hba_file=/opt/janus/pg_hba.conf >/dev/null
  fi
  unset web_control_password web_catalog_password web_publication_password
  sudo rm -rf "${docker_config}" >/dev/null 2>&1 || true
  rm -f -- "${credential_file}" >/dev/null 2>&1 || true
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
echo "Pulled immutable PostgreSQL image."

sudo docker rm -f janus-postgres >/dev/null
sudo docker run -d --name janus-postgres --restart=always \
  -p 5432:5432 -v "${data_dir}:/var/lib/postgresql/data" "${image}" \
  -c config_file=/opt/janus/postgresql.conf -c hba_file=/opt/janus/pg_hba.conf >/dev/null
switched=true
echo "Started PostgreSQL with the updated configuration."

for _ in $(seq 1 60); do
  if sudo docker exec --user postgres janus-postgres \
    pg_isready -U postgres -d janus_control >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
sudo docker exec --user postgres janus-postgres pg_isready -U postgres -d janus_control >/dev/null

sudo docker cp "${credential_file}" janus-postgres:/tmp/janus-web-migration-credentials
sudo docker exec janus-postgres chown postgres:postgres /tmp/janus-web-migration-credentials
sudo docker exec janus-postgres chmod 600 /tmp/janus-web-migration-credentials

sudo docker exec --user postgres \
  janus-postgres bash -ceu '
    credential_file=/tmp/janus-web-migration-credentials
    IFS= read -r WEB_CONTROL_PASSWORD < "${credential_file}"
    IFS= read -r WEB_CATALOG_PASSWORD < <(sed -n "2p" "${credential_file}")
    IFS= read -r WEB_PUBLICATION_PASSWORD < <(sed -n "3p" "${credential_file}")
    export WEB_CONTROL_PASSWORD WEB_CATALOG_PASSWORD WEB_PUBLICATION_PASSWORD
    printf "\\getenv web_control_password WEB_CONTROL_PASSWORD\n\\getenv web_catalog_password WEB_CATALOG_PASSWORD\n" > /tmp/web-vars.sql
    cat /tmp/web-vars.sql /opt/janus/migrations/007_web_runtime_roles.sql | psql -U postgres -d janus_control
    psql -U postgres -d janus_control -f /opt/janus/migrations/009_admin_cursor_indexes.sql
    psql -U postgres -d janus_control -f /opt/janus/migrations/010_execution_runtime_options.sql
    psql -U postgres -d janus_control -f /opt/janus/migrations/011_control_settings_ownership.sql
    psql -U postgres -d janus_control -f /opt/janus/migrations/012_first_batch_source_ids.sql
    psql -U postgres -d janus_control -f /opt/janus/migrations/013_membership_versions.sql
    psql -U postgres -d janus_control -f /opt/janus/migrations/020_governance_audit.sql
    printf "\\getenv web_publication_password WEB_PUBLICATION_PASSWORD\n" > /tmp/public-vars.sql
    cat /tmp/public-vars.sql /opt/janus/migrations/021_public_api_role.sql | psql -U postgres -d janus_control
    psql -U postgres -d janus_control -f /opt/janus/migrations/022_mart_publication_review.sql
    psql -U postgres -d janus_control -f /opt/janus/migrations/023_public_stock_index.sql
    rm -f /tmp/web-vars.sql /tmp/public-vars.sql "${credential_file}"
    psql -U postgres -d janus_control -v ON_ERROR_STOP=1 <<"SQL"
SELECT rolname, rolsuper, rolcreatedb, rolcreaterole, rolreplication
FROM pg_roles
WHERE rolname IN ($$janus_web_control$$, $$janus_web_catalog$$, $$janus_public_api$$)
ORDER BY rolname;
SELECT current_setting($$default_transaction_read_only$$) = $$off$$ AS server_default_writable;
SELECT EXISTS (
  SELECT 1 FROM control.schema_migrations WHERE version = $$021_public_api_role$$
) AS migration_recorded;
SELECT EXISTS (
  SELECT 1 FROM control.schema_migrations WHERE version = $$022_mart_publication_review$$
) AS publication_review_recorded;
SELECT EXISTS (
  SELECT 1 FROM control.schema_migrations WHERE version = $$023_public_stock_index$$
) AS public_stock_index_recorded;
SELECT tableowner = $$janus_control$$ AS control_settings_owned
FROM pg_tables WHERE schemaname = $$control$$ AND tablename = $$admin_settings$$;
SELECT source_ids = $$["taiex", "tpex-benchmark", "twse", "mops", "finmind"]$$::jsonb
  AS first_batch_sources_canonical
FROM control.collection_configs WHERE config_id = $$first-batch$$;
SQL
  '

switched=false
trap - ERR
unset web_control_password web_catalog_password web_publication_password
rm -f -- "${credential_file}"
echo "Web PostgreSQL migration applied with immutable image ${image}."
