#!/usr/bin/env bash
# Creates the PostgreSQL role and databases used by VISTA (run once).
# Needs a PostgreSQL superuser; by default connects as 'postgres' on localhost.
#   PGUSER=postgres PGPASSWORD=... ./scripts/setup_databases.sh
set -euo pipefail
APP_USER="${APP_USER:-vista}"
APP_PASSWORD="${APP_PASSWORD:-vista_dev_pw}"
PSQL=(psql -h "${PGHOST:-localhost}" -p "${PGPORT:-5432}" -U "${PGUSER:-postgres}" -v ON_ERROR_STOP=1 -q)

"${PSQL[@]}" -tc "SELECT 1 FROM pg_roles WHERE rolname='${APP_USER}'" | grep -q 1 \
  || "${PSQL[@]}" -c "CREATE ROLE ${APP_USER} LOGIN PASSWORD '${APP_PASSWORD}' CREATEDB"
for db in vista vista_test vista_e2e vista_perf; do
  "${PSQL[@]}" -tc "SELECT 1 FROM pg_database WHERE datname='${db}'" | grep -q 1 \
    || "${PSQL[@]}" -c "CREATE DATABASE ${db} OWNER ${APP_USER}"
  echo "database ${db} ready"
done
echo "Role '${APP_USER}' (password '${APP_PASSWORD}') owns: vista (app), vista_test (pytest), vista_e2e (Playwright), vista_perf (load tests)."
