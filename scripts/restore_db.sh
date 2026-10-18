#!/usr/bin/env bash
# Restore a backup made by backup_db.sh into the database given by DATABASE_URL (must exist and be empty).
set -euo pipefail
: "${DATABASE_URL:?Set DATABASE_URL}"
FILE="${1:?Usage: restore_db.sh path/to/vista_YYYYmmdd_HHMMSS.dump}"
URL="${DATABASE_URL/postgresql+psycopg:/postgresql:}"
pg_restore --no-owner --clean --if-exists -d "$URL" "$FILE"
echo "Restored $FILE"
