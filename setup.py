import os
import sys
import sqlite3
import shutil
from pathlib import Path

def setup_bot():
    print("Setting up ChannoBot...")
    
    # 1. Create data directory
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)
    print("✓ Data directory created")
    
    # 2. Remove old database if it exists
    db_path = data_dir / "channobot.db"
    if db_path.exists():
        try:
            os.remove(db_path)
            print("✓ Old database removed")
        except Exception as e:
            print(f"! Error removing old database: {e}")
            return False
    
    # 3. Create new database
    try:
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
        print("✓ Database created with new schema")
        
        # Test the database
        cursor.execute("INSERT INTO users (user_id, guild_id, username, points) VALUES (?, ?, ?, ?)",
                      (123, 456, "test_user", 100))
        conn.commit()
        
        cursor.execute("SELECT * FROM users WHERE user_id = ? AND guild_id = ?", (123, 456))
        result = cursor.fetchone()
        if result:
            print("✓ Database test successful")
        else:
            print("! Database test failed")
            return False
            
    except Exception as e:
        print(f"! Error setting up database: {e}")
        return False
    finally:
        conn.close()
    
    print("\nSetup completed successfully!")
    print("\nNext steps:")
    print("1. Start the bot using: python bot.py")
    print("2. Test the points system in your Discord server")
    print("3. Check the logs in data/logs/channobot.log for any issues")
    
    return True

if __name__ == "__main__":
    if not setup_bot():
        print("\nSetup failed! Please check the errors above.")
        sys.exit(1) 