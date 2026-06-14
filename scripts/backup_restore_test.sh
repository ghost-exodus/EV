#!/bin/bash
# Database Backup and Restore Verification Script.
#
# Dumps the active database, creates a new database on the same Postgres container,
# restores the backup, and verifies that the row counts of key tables match exactly.
#
# TimescaleDB Considerations:
# - pg_dump is run with --no-owner to avoid permission errors when restoring to a new DB.
# - The timescaledb extension is initialized on the target database before restoration.
# - SELECT timescaledb_pre_restore() is run on the target DB before restoration to
#   suspend catalog constraints, indexing rules, and chunk trigger checks.
# - SELECT timescaledb_post_restore() is run after restoration to re-enable
#   TimescaleDB catalog indexes, metadata sync, and background aggregation workers.

set -e

CONTAINER_NAME="ev_postgres"
DB_USER="ev_user"
DB_PASSWORD="ev_password"
SRC_DB="ev_telemetry"
DST_DB="ev_telemetry_restore"
BACKUP_FILE="ev_telemetry_backup.sql"

echo "=== DATABASE BACKUP AND RESTORE TEST ==="

# 1. Create SQL backup using pg_dump
echo "1. Exporting database backup from '${SRC_DB}' to '${BACKUP_FILE}'..."
docker exec -e PGPASSWORD=${DB_PASSWORD} ${CONTAINER_NAME} \
  pg_dump -U ${DB_USER} -d ${SRC_DB} --no-owner --clean --if-exists > ${BACKUP_FILE}

echo "Backup completed successfully: ${BACKUP_FILE}"

# 2. Re-create clean target database on the same container
echo "2. Re-creating temporary database '${DST_DB}' on container..."
docker exec -e PGPASSWORD=${DB_PASSWORD} -t ${CONTAINER_NAME} \
  psql -U ${DB_USER} -d postgres -c "DROP DATABASE IF EXISTS ${DST_DB};"

docker exec -e PGPASSWORD=${DB_PASSWORD} -t ${CONTAINER_NAME} \
  psql -U ${DB_USER} -d postgres -c "CREATE DATABASE ${DST_DB};"

# 3. Create timescaledb extension and run timescaledb_pre_restore()
echo "3. Creating TimescaleDB extension and running pre-restore hooks on '${DST_DB}'..."
docker exec -e PGPASSWORD=${DB_PASSWORD} -t ${CONTAINER_NAME} \
  psql -U ${DB_USER} -d ${DST_DB} -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"

docker exec -e PGPASSWORD=${DB_PASSWORD} -t ${CONTAINER_NAME} \
  psql -U ${DB_USER} -d ${DST_DB} -c "SELECT timescaledb_pre_restore();"

# 4. Restore database schema and data
echo "4. Restoring backup into '${DST_DB}'..."
docker exec -i ${CONTAINER_NAME} \
  psql -U ${DB_USER} -d ${DST_DB} < ${BACKUP_FILE}

# 4b. Run timescaledb_post_restore() to lock catalog changes
echo "4b. Running TimescaleDB post-restore hooks on '${DST_DB}'..."
docker exec -e PGPASSWORD=${DB_PASSWORD} -t ${CONTAINER_NAME} \
  psql -U ${DB_USER} -d ${DST_DB} -c "SELECT timescaledb_post_restore();"

echo "Restoration completed successfully."

# 5. Count comparison query
echo "5. Verifying database integrity and row counts..."

# Helper function to get row counts
get_count() {
  local db=$1
  local table=$2
  docker exec -e PGPASSWORD=${DB_PASSWORD} -t ${CONTAINER_NAME} \
    psql -U ${DB_USER} -d ${db} -t -A -c "SELECT COUNT(*) FROM ${table};" | tr -d '\r'
}

TABLES=("batteries" "telemetry" "soh_snapshots" "rul_predictions")
FAILED=0

echo -e "\n--------------------------------------------"
printf "%-20s | %-10s | %-10s | %-6s\n" "Table Name" "Original" "Restored" "Status"
echo "--------------------------------------------"

for table in "${TABLES[@]}"; do
  SRC_COUNT=$(get_count ${SRC_DB} ${table})
  DST_COUNT=$(get_count ${DST_DB} ${table})
  
  if [ "${SRC_COUNT}" -eq "${DST_COUNT}" ]; then
    STATUS="OK"
  else
    STATUS="FAIL"
    FAILED=$((FAILED + 1))
  fi
  printf "%-20s | %-10s | %-10s | %-6s\n" "${table}" "${SRC_COUNT}" "${DST_COUNT}" "${STATUS}"
done
echo "--------------------------------------------"

# Clean up local backup file
rm -f ${BACKUP_FILE}

# Drop the restore database to clean up container space
docker exec -e PGPASSWORD=${DB_PASSWORD} -t ${CONTAINER_NAME} \
  psql -U ${DB_USER} -d postgres -c "DROP DATABASE IF EXISTS ${DST_DB};"

if [ ${FAILED} -eq 0 ]; then
  echo -e "\n>>> BACKUP & RESTORE VERIFICATION: PASS <<<\n"
  exit 0
else
  echo -e "\n>>> BACKUP & RESTORE VERIFICATION: FAIL (Mismatched row counts) <<<\n"
  exit 1
fi
