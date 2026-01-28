#!/bin/bash
# PostgreSQL Backup Script for RAG Admin Application
# This script creates compressed backups of the PostgreSQL database
# and automatically cleans up old backups

set -e  # Exit on error

# Configuration
BACKUP_DIR="$HOME/backups"
DATE=$(date +%Y%m%d_%H%M%S)
COMPOSE_FILE="$HOME/rag-admin/docker-compose.prod.yml"
BACKUP_FILE="$BACKUP_DIR/ragadmin_$DATE.sql.gz"
RETENTION_DAYS=7

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1"
}

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

log "Starting database backup..."

# Check if docker compose is running
if ! docker compose -f "$COMPOSE_FILE" ps postgres | grep -q "running"; then
    error "PostgreSQL container is not running!"
    exit 1
fi

# Create database backup
log "Creating backup: ragadmin_$DATE.sql.gz"
if docker compose -f "$COMPOSE_FILE" exec -T postgres \
    pg_dump -U ragadmin ragadmin | \
    gzip > "$BACKUP_FILE"; then

    # Verify backup was created and has content
    if [ -f "$BACKUP_FILE" ] && [ -s "$BACKUP_FILE" ]; then
        BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
        log "Backup created successfully: $BACKUP_FILE ($BACKUP_SIZE)"
    else
        error "Backup file is empty or was not created"
        rm -f "$BACKUP_FILE"
        exit 1
    fi
else
    error "Backup failed"
    rm -f "$BACKUP_FILE"
    exit 1
fi

# Remove backups older than retention period
log "Cleaning up old backups (keeping last $RETENTION_DAYS days)..."
DELETED_COUNT=$(find "$BACKUP_DIR" -name "ragadmin_*.sql.gz" -mtime +$RETENTION_DAYS -type f -delete -print | wc -l)

if [ "$DELETED_COUNT" -gt 0 ]; then
    log "Removed $DELETED_COUNT old backup(s)"
else
    log "No old backups to remove"
fi

# List all available backups
log "Available backups:"
ls -lh "$BACKUP_DIR"/ragadmin_*.sql.gz 2>/dev/null || log "No backups found"

# Count total backups
TOTAL_BACKUPS=$(ls -1 "$BACKUP_DIR"/ragadmin_*.sql.gz 2>/dev/null | wc -l)
TOTAL_SIZE=$(du -sh "$BACKUP_DIR" 2>/dev/null | cut -f1)

log "Backup completed successfully!"
log "Total backups: $TOTAL_BACKUPS (Total size: $TOTAL_SIZE)"

# Optional: Upload backup to remote storage
# Uncomment and configure if you want to sync backups to S3, rsync, etc.
#
# log "Syncing to remote storage..."
# aws s3 cp "$BACKUP_FILE" s3://your-backup-bucket/ragadmin/ || warn "Remote sync failed"

exit 0
