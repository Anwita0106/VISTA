#!/usr/bin/env bash
# NFR09 – daily backup. Example cron entry (02:30 every day):
#   30 2 * * * /path/to/VISTA/scripts/backup_db.sh >> /var/log/vista-backup.log 2>&1
set -euo pipefail
: "${DATABASE_URL:?Set DATABASE_URL (postgresql://user:pass@host:5432/vista)}"
BACKUP_DIR="${BACKUP_DIR:-./backups}"
KEEP_DAYS="${KEEP_DAYS:-14}"
mkdir -p "$BACKUP_DIR"
URL="${DATABASE_URL/postgresql+psycopg:/postgresql:}"
FILE="$BACKUP_DIR/vista_$(date +%Y%m%d_%H%M%S).dump"
pg_dump -Fc -f "$FILE" "$URL"
find "$BACKUP_DIR" -name 'vista_*.dump' -mtime +"$KEEP_DAYS" -delete
echo "Backup written to $FILE ($(du -h "$FILE" | cut -f1))"
