import sqlite3
from pathlib import Path

# Ensure database is created in the backend folder
db_path = Path(__file__).resolve().parent / "database.db"
conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()

cursor.executescript("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    password BLOB NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
""")

conn.commit()
conn.close()
print("Database tables created successfully.")