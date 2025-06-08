import sqlite3
import os

# Connect to database
db_path = '/home/pi/ChannoBot/channobot.db'

# Backup existing data
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get existing points
cursor.execute('SELECT user_id, points, username FROM users')
existing_data = cursor.fetchall()

# Drop and recreate table with new schema
cursor.execute('DROP TABLE IF EXISTS users')
cursor.execute('''
    CREATE TABLE users (
        user_id INTEGER,
        guild_id INTEGER,
        username TEXT,
        points INTEGER DEFAULT 0,
        PRIMARY KEY (user_id, guild_id)
    )
''')

# Restore data with default guild_id
for user_id, points, username in existing_data:
    cursor.execute('INSERT INTO users (user_id, guild_id, username, points) VALUES (?, ?, ?, ?)',
                  (user_id, 0, username, points))

conn.commit()
conn.close()

print("Database schema updated and data migrated") 