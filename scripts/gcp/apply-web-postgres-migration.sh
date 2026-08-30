#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

# Apply only the Web runtime role migration to the existing dev PostgreSQL VM.
# The two passwords are read from stdin in this order:
#   janus-postgres-web-control-password
#   janus-postgres-web-catalog-password

image="${1:?immutable PostgreSQL image is required}"
mode="${2:-apply}"
data_dir=/mnt/stateful_partition/postgres
docker_config=/run/janus-web-migration-docker

if [[ "${image}" != *@sha256:* ]]; then
  echo "Refusing mutable PostgreSQL image: ${image}" >&2
  exit 1
fi

read -r web_control_password
read -r web_catalog_password
# PowerShell/OpenSSH may deliver CRLF even though the remote shell splits on LF.
web_control_password="${web_control_password%$'\r'}"
web_catalog_password="${web_catalog_password%$'\r'}"
if [[ -z "${web_control_password}" || -z "${web_catalog_password}" ]]; then
  echo "Both Web PostgreSQL passwords are required." >&2
  exit 1
fi
echo "Validated Web migration inputs."
if [[ "${mode}" == "check" ]]; then
  exit 0
fi

old_image="$(sudo docker inspect --format '{{.Config.Image}}' janus-postgres)"
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
  unset web_control_password web_catalog_password
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

sudo docker exec --user postgres \
  -e WEB_CONTROL_PASSWORD="${web_control_password}" \
  -e WEB_CATALOG_PASSWORD="${web_catalog_password}" \
  janus-postgres bash -ceu '
    printf "\\getenv web_control_password WEB_CONTROL_PASSWORD\n\\getenv web_catalog_password WEB_CATALOG_PASSWORD\n" > /tmp/web-vars.sql
    cat /tmp/web-vars.sql /opt/janus/migrations/007_web_runtime_roles.sql | psql -U postgres -d janus_control
    rm -f /tmp/web-vars.sql
    psql -U postgres -d janus_control -v ON_ERROR_STOP=1 <<"SQL"
SELECT rolname, rolsuper, rolcreatedb, rolcreaterole, rolreplication
FROM pg_roles
WHERE rolname IN ($$janus_web_control$$, $$janus_web_catalog$$)
ORDER BY rolname;
SELECT current_setting($$default_transaction_read_only$$) = $$off$$ AS server_default_writable;
SELECT EXISTS (
  SELECT 1 FROM control.schema_migrations WHERE version = $$007_web_runtime_roles$$
) AS migration_recorded;
SQL
  '

switched=false
trap - ERR
unset web_control_password web_catalog_password
echo "Web PostgreSQL migration applied with immutable image ${image}."
