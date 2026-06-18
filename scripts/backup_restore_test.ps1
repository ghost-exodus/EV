# Database Backup and Restore Verification Script (Windows PowerShell).
#
# Dumps the active database, creates a new database on the same Postgres container,
# restores the backup, and verifies that the row counts of key tables match exactly.

$ErrorActionPreference = "Stop"

$ContainerName = "ev_postgres"
$DbUser = "ev_user"
$DbPassword = "ev_password"
$SrcDb = "ev_telemetry"
$DstDb = "ev_telemetry_restore"
$BackupFile = "ev_telemetry_backup.sql"

Write-Host "=== DATABASE BACKUP AND RESTORE TEST (POWERSHELL) ==="

# 1. Create SQL backup using pg_dump
Write-Host "1. Exporting database backup from '$SrcDb' to '$BackupFile'..."
docker exec -e PGPASSWORD=$DbPassword $ContainerName pg_dump -U $DbUser -d $SrcDb --no-owner --clean --if-exists > $BackupFile

Write-Host "Backup completed successfully."

# 2. Re-create clean target database on the same container
Write-Host "2. Re-creating temporary database '$DstDb' on container..."
docker exec -e PGPASSWORD=$DbPassword -t $ContainerName psql -U $DbUser -d postgres -c "DROP DATABASE IF EXISTS $DstDb;"
docker exec -e PGPASSWORD=$DbPassword -t $ContainerName psql -U $DbUser -d postgres -c "CREATE DATABASE $DstDb;"

# 3. Create timescaledb extension and run timescaledb_pre_restore()
Write-Host "3. Creating TimescaleDB extension and running pre-restore hooks on '$DstDb'..."
docker exec -e PGPASSWORD=$DbPassword -t $ContainerName psql -U $DbUser -d $DstDb -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"
docker exec -e PGPASSWORD=$DbPassword -t $ContainerName psql -U $DbUser -d $DstDb -c "SELECT timescaledb_pre_restore();"

# 4. Restore database schema and data
Write-Host "4. Restoring backup into '$DstDb'..."
Get-Content $BackupFile -Raw | docker exec -i $ContainerName psql -U $DbUser -d $DstDb

# 4b. Run timescaledb_post_restore() to lock catalog changes
Write-Host "4b. Running TimescaleDB post-restore hooks on '$DstDb'..."
docker exec -e PGPASSWORD=$DbPassword -t $ContainerName psql -U $DbUser -d $DstDb -c "SELECT timescaledb_post_restore();"

Write-Host "Restoration completed successfully."

# 5. Count comparison query
Write-Host "5. Verifying database integrity and row counts..."

function Get-RowCount($Db, $Table) {
    $Result = docker exec -e PGPASSWORD=$DbPassword -t $ContainerName psql -U $DbUser -d $Db -t -A -c "SELECT COUNT(*) FROM $Table;"
    return [int]($Result.Trim())
}

$Tables = @("batteries", "telemetry", "soh_snapshots", "rul_predictions")
$Failed = 0

Write-Host "--------------------------------------------"
Write-Host "Table Name           | Original   | Restored   | Status"
Write-Host "--------------------------------------------"

foreach ($Table in $Tables) {
    $SrcCount = Get-RowCount $SrcDb $Table
    $DstCount = Get-RowCount $DstDb $Table
    
    if ($SrcCount -eq $DstCount) {
        $Status = "OK"
    } else {
        $Status = "FAIL"
        $Failed++
    }
    
    $Line = "{0,-20} | {1,-10} | {2,-10} | {3,-6}" -f $Table, $SrcCount, $DstCount, $Status
    Write-Host $Line
}
Write-Host "--------------------------------------------"

# Clean up local backup file
if (Test-Path $BackupFile) {
    Remove-Item $BackupFile
}

# Drop the restore database to clean up container space
docker exec -e PGPASSWORD=$DbPassword -t $ContainerName psql -U $DbUser -d postgres -c "DROP DATABASE IF EXISTS $DstDb;"

if ($Failed -eq 0) {
    Write-Host "`n>>> BACKUP & RESTORE VERIFICATION: PASS <<<`n"
    exit 0
} else {
    Write-Host "`n>>> BACKUP & RESTORE VERIFICATION: FAIL (Mismatched row counts) <<<`n"
    exit 1
}
