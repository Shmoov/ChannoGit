import sqlite3
from pathlib import Path

def test_database():
    # Ensure data directory exists
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)
    
    # Set database path
    db_path = data_dir / "channobot.db"
    
    print(f"Testing database at {db_path}")
    
    try:
        # Create new database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create test table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS test (
                id INTEGER PRIMARY KEY,
                name TEXT
            )
        ''')
        
        # Insert test data
        cursor.execute('INSERT INTO test (name) VALUES (?)', ('test_name',))
        conn.commit()
        
        # Verify data
        cursor.execute('SELECT * FROM test')
        result = cursor.fetchone()
        print(f"Test data: {result}")
        
        print("Database test successful!")
        return True
        
    except Exception as e:
        print(f"Database test error: {e}")
        return False
        
    finally:
        conn.close()

if __name__ == "__main__":
    test_database() 