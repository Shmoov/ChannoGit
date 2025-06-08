import shutil
from datetime import datetime
import os
from pathlib import Path

def backup_database():
    # Ensure backup directory exists
    backup_dir = Path("data/backups")
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    # Source database
    source = Path("data/channobot.db")
    if not source.exists():
        print("No database file found to backup!")
        return
    
    # Create timestamped backup
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"channobot_{timestamp}.db"
    
    # Create backup
    shutil.copy2(source, backup_path)
    
    # Keep only last 5 backups
    backups = sorted(backup_dir.glob("channobot_*.db"))
    if len(backups) > 5:
        for old_backup in backups[:-5]:
            old_backup.unlink()
    
    print(f"Database backed up to {backup_path}")

if __name__ == "__main__":
    backup_database() 