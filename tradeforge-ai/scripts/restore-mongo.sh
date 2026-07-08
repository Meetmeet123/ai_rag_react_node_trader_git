#!/usr/bin/env bash
# Restore a mongodump archive into the TradeForge MongoDB container.
# Usage: ./scripts/restore-mongo.sh <backup_path> [--drop]

set -euo pipefail

CONTAINER_NAME="${MONGO_CONTAINER:-tradeforge-mongo}"
DB_NAME="${MONGO_DB_NAME:-tradeforge}"

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <backup_path> [--drop]" >&2
  exit 1
fi

BACKUP_PATH="$1"
DROP_FLAG=""
if [[ "${2:-}" == "--drop" ]]; then
  DROP_FLAG="--drop"
fi

if [[ ! -d "${BACKUP_PATH}" ]]; then
  echo "Backup path not found: ${BACKUP_PATH}" >&2
  exit 1
fi

REMOTE_DIR="/tmp/restore_$(date +%s)"

echo "Copying backup into container ${CONTAINER_NAME} ..."
docker cp "${BACKUP_PATH}" "${CONTAINER_NAME}:${REMOTE_DIR}"

echo "Restoring database '${DB_NAME}' ..."
docker exec "${CONTAINER_NAME}" mongorestore \
  --db "${DB_NAME}" \
  ${DROP_FLAG} \
  "${REMOTE_DIR}/$(basename "${BACKUP_PATH}")/${DB_NAME}"

docker exec "${CONTAINER_NAME}" rm -rf "${REMOTE_DIR}"

echo "Restore complete."
