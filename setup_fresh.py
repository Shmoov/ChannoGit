import sqlite3
import os
from pathlib import Path

def setup_fresh():
    print("Setting up fresh database...")
    
    # Create data directory
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)
    
    # Set database path
    db_path = data_dir / "channobot.db"
    
    # Remove old database if it exists
    if db_path.exists():
        try:
            os.remove(db_path)
            print("✓ Removed old database")
        except Exception as e:
            print(f"! Error removing old database: {e}")
            return False
    
    try:
        # Create new database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create users table
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
        print("✓ Created fresh database with correct schema")
        
        # Test the schema
        try:
            cursor.execute('''
                INSERT INTO users (user_id, guild_id, username, points)
                VALUES (?, ?, ?, ?)
            ''', (123, 456, "test_user", 100))
            
            cursor.execute('SELECT * FROM users WHERE user_id = ? AND guild_id = ?', (123, 456))
            result = cursor.fetchone()
            if result:
                print("✓ Database schema test successful")
            else:
                print("! Database schema test failed")
                return False
        except Exception as e:
            print(f"! Database schema test failed: {e}")
            return False
            
        # Clean up test data
        cursor.execute('DELETE FROM users WHERE user_id = ? AND guild_id = ?', (123, 456))
        conn.commit()
        
        return True
        
    except Exception as e:
        print(f"! Error creating database: {e}")
        return False
        
    finally:
        conn.close()

if __name__ == "__main__":
    if setup_fresh():
        print("\n✓ Setup completed successfully!")
        print("\nNext steps:")
        print("1. Start the bot using: python bot.py")
        print("2. Test the points system in your Discord server")
        print("3. Check the logs in data/logs/channobot.log for any issues")
    else:
        print("\n! Setup failed. Please check the errors above.") 