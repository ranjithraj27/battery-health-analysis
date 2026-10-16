import sqlite3
from pathlib import Path

p = Path(__file__).resolve().parent / 'database.db'
print('DB path:', p)
con = sqlite3.connect(str(p))
cur = con.cursor()
try:
    tables = [row[0] for row in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    print('Tables:', tables)
    if 'users' in tables:
        print('users schema:')
        for row in cur.execute("PRAGMA table_info(users)"):
            print(' ', row)
        rows = list(cur.execute("SELECT id, email, typeof(password), length(password) FROM users"))
        print('user rows count:', len(rows))
        for r in rows[:10]:
            print(' ', r)
    else:
        print('No users table found')
except Exception as e:
    import traceback
    traceback.print_exc()
finally:
    con.close()
