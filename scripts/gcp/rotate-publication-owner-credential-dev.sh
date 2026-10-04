#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

password=''
IFS= read -r password
if [[ ! "${password}" =~ ^[A-Za-z0-9_-]{40,}$ ]]; then
  echo 'publication owner credential input is invalid' >&2
  exit 1
fi

pgpass_host="$(mktemp /tmp/janus-publication-pgpass.XXXXXX)"
container_pgpass=/tmp/janus-publication.pgpass
cleanup() {
  rm -f "${pgpass_host}"
  sudo docker exec --user postgres janus-postgres rm -f "${container_pgpass}" >/dev/null 2>&1 || true
  password=''
}
trap cleanup EXIT

# Keep the credential off argv, deployment metadata, and logs. The generated
# credential alphabet excludes SQL quoting characters; SQL reaches psql only on
# stdin, and statement-duration logging is disabled for this privileged session.
printf "SET log_min_duration_statement = -1;\nALTER ROLE janus_publication PASSWORD '%s';\n" "${password}" \
  | sudo docker exec -i --user postgres janus-postgres \
      psql -U postgres -d janus_control -v ON_ERROR_STOP=1 >/dev/null

# Verify through PostgreSQL's local Unix socket. pg_hba.conf intentionally
# rejects TCP loopback; the local rule requires scram-sha-256, so this still
# proves the new password authenticates without opening a network path.
printf 'localhost:5432:janus_control:janus_publication:%s\n' "${password}" > "${pgpass_host}"
chmod 600 "${pgpass_host}"
sudo docker cp "${pgpass_host}" "janus-postgres:${container_pgpass}" >/dev/null
sudo docker exec --user postgres janus-postgres chmod 600 "${container_pgpass}"

identity="$(sudo docker exec --user postgres -e PGPASSFILE="${container_pgpass}" janus-postgres \
  psql -U janus_publication -d janus_control -Atqc \
  "SELECT current_user || '|' || has_schema_privilege(current_user,'publication','CREATE')::text")"
if [[ "${identity}" != 'janus_publication|true' && "${identity}" != 'janus_publication|t' ]]; then
  echo 'publication owner credential verification failed' >&2
  exit 1
fi

echo 'janus_publication login and bounded publication ownership verified.'
