import sqlite3

conn = sqlite3.connect("database.db")

try:
    conn.execute("ALTER TABLE applications ADD COLUMN interview_date TEXT")
except:
    print("interview_date already exists")

try:
    conn.execute("ALTER TABLE applications ADD COLUMN interview_time TEXT")
except:
    print("interview_time already exists")

conn.commit()
conn.close()

print("Database updated ✅")