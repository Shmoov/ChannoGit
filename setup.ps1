# Create data directory if it doesn't exist
New-Item -ItemType Directory -Force -Path "data"

# Remove old database if it exists
$dbPath = "data/channobot.db"
if (Test-Path $dbPath) {
    Remove-Item $dbPath -Force
    Write-Host "Old database removed"
}

# Create Python script to set up database
$setupScript = @"
import sqlite3
import sys

try:
    conn = sqlite3.connect('data/channobot.db')
    cursor = conn.cursor()
    
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
    print('Database created successfully')
    sys.exit(0)
except Exception as e:
    print(f'Error: {e}')
    sys.exit(1)
finally:
    conn.close()
"@

# Save the Python script
$setupScript | Out-File -Encoding UTF8 "setup_db.py"

# Run the Python script
Write-Host "Setting up database..."
python setup_db.py

# Clean up
Remove-Item "setup_db.py"

Write-Host "`nSetup completed!"
Write-Host "Next steps:"
Write-Host "1. Start the bot using: python bot.py"
Write-Host "2. Test the points system in your Discord server"
Write-Host "3. Check the logs in data/logs/channobot.log for any issues" 