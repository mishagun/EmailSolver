#!/bin/bash
set -euo pipefail

if [ $# -ne 1 ]; then
    echo "Usage: $0 <backup-file>"
    echo "Example: $0 backups/emailsolver_20260310_120000.sql.gz"
    exit 1
fi

BACKUP_FILE="$1"

if [ ! -f "$BACKUP_FILE" ]; then
    echo "Error: Backup file not found: $BACKUP_FILE"
    exit 1
fi

echo "Restoring from: $BACKUP_FILE"
echo "WARNING: This will overwrite the current database. Press Ctrl+C to cancel."
read -r -p "Continue? [y/N] " confirm
if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 0
fi

gunzip -c "$BACKUP_FILE" | docker compose exec -T postgres pg_restore -U emailsolver -d emailsolver --clean --if-exists

if [ $? -eq 0 ]; then
    echo "Restore completed successfully."
else
    echo "Restore failed."
    exit 1
fi
