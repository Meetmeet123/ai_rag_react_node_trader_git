#!/usr/bin/env bash
# Backup the TradeForge MongoDB container to a timestamped archive.
# Usage: ./scripts/backup-mongo.sh [output_dir]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

CONTAINER_NAME="${MONGO_CONTAINER:-tradeforge-mongo}"
DB_NAME="${MONGO_DB_NAME:-tradeforge}"
BACKUP_DIR="${1:-${PROJECT_DIR}/backups}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
OUT="${BACKUP_DIR}/mongo_backup_${DB_NAME}_${TIMESTAMP}"

mkdir -p "${BACKUP_DIR}"

echo "Creating MongoDB backup of '${DB_NAME}' into ${OUT} ..."
docker exec "${CONTAINER_NAME}" mongodump \
  --db "${DB_NAME}" \
  --out "/tmp/backup_${TIMESTAMP}"

docker cp "${CONTAINER_NAME}:/tmp/backup_${TIMESTAMP}" "${OUT}"
docker exec "${CONTAINER_NAME}" rm -rf "/tmp/backup_${TIMESTAMP}"

echo "Backup complete: ${OUT}"
