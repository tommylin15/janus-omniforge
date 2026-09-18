#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

image="${1:?immutable PostgreSQL image is required}"
data_dir=/mnt/stateful_partition/postgres
docker_config=/run/janus-private-storage-migration-docker
[[ "${image}" == *@sha256:* ]] || { echo "Refusing mutable PostgreSQL image: ${image}" >&2; exit 1; }

old_image="$(sudo docker inspect --format '{{.Image}}' janus-postgres)"
switched=false
rollback() {
  status=$?
  trap - ERR
  if [[ "${switched}" == true ]]; then
    sudo docker rm -f janus-postgres >/dev/null 2>&1 || true
    sudo docker run -d --name janus-postgres --restart=always -p 5432:5432 \
      -v "${data_dir}:/var/lib/postgresql/data" "${old_image}" \
      -c config_file=/opt/janus/postgresql.conf -c hba_file=/opt/janus/pg_hba.conf >/dev/null
  fi
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
sudo docker run -d --name janus-postgres --restart=always -p 5432:5432 \
  -v "${data_dir}:/var/lib/postgresql/data" "${image}" \
  -c config_file=/opt/janus/postgresql.conf -c hba_file=/opt/janus/pg_hba.conf >/dev/null
switched=true
for _ in $(seq 1 60); do
  sudo docker exec --user postgres janus-postgres pg_isready -U postgres -d janus_control >/dev/null 2>&1 && break
  sleep 1
done
sudo docker exec --user postgres janus-postgres pg_isready -U postgres -d janus_control >/dev/null
sudo docker exec --user postgres janus-postgres bash -ceu '
    psql -U postgres -d janus_control -f /opt/janus/migrations/016_private_assistant_storage.sql
    psql -U postgres -d janus_control -f /opt/janus/migrations/026_mcp_oauth_codes.sql
    psql -U postgres -d janus_control -f /opt/janus/migrations/027_pipeline_acl_repair.sql
  '
sudo docker exec --user postgres janus-postgres \
  psql -U postgres -d janus_control -f /opt/janus/private-storage-acceptance.sql

switched=false
trap - ERR
echo "Private assistant storage migration and PostgreSQL acceptance passed for ${image}."
