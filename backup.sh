#!/bin/bash

# Directory paths
BACKUP_DIR="/home/pi/ChannoBot/backups"
DB_PATH="/home/pi/ChannoBot/channobot.db"
DATE=$(date +%Y%m%d_%H%M%S)

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

# Create backup with timestamp
cp "$DB_PATH" "$BACKUP_DIR/channobot_$DATE.db"

# Keep only the last 7 backups
ls -t "$BACKUP_DIR"/channobot_*.db | tail -n +8 | xargs -r rm

# Log the backup
echo "Backup created: channobot_$DATE.db" >> "$BACKUP_DIR/backup.log"

# Optional: Compress older backups to save space
find "$BACKUP_DIR" -name "channobot_*.db" -mtime +1 -exec gzip {} \; 