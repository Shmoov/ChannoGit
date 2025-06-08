import sqlite3
import os
import sys
from pathlib import Path

def migrate_database():
    # Ensure data directory exists
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)

    # Set database path
    db_path = data_dir / "channobot.db"

    # Remove existing database if it exists
    if db_path.exists():
        try:
            os.remove(db_path)
            print(f"Removed existing database at {db_path}")
        except Exception as e:
            print(f"Error removing existing database: {e}")
            return False

    print(f"Creating new database at {db_path}")
    
    try:
        # Create new database with updated schema
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Create users table with guild_id support
        cursor.execute('''
            CREATE TABLE users (
                user_id INTEGER,
                guild_id INTEGER,
                username TEXT,
                points INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, guild_id)
            )
        ''')

        conn.commit()
        print("Database schema created successfully!")
        return True

    except Exception as e:
        print(f"Error creating database: {e}")
        if os.path.exists(db_path):
            os.remove(db_path)
        return False

    finally:
        conn.close()

if __name__ == "__main__":
    success = migrate_database()
    sys.exit(0 if success else 1) 