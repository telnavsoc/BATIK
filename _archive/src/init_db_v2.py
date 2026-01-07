import sqlite3
import os

DB_FILE = "batik_database.db"

def init_db():
    if os.path.exists(DB_FILE):
        print(f"⚠️  File {DB_FILE} sudah ada. Rename atau hapus jika ingin reset total.")
        return

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # 1. Tabel Sessions (Ditambah kolom EQUIPMENT)
    c.execute('''
        CREATE TABLE sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME,
            equipment TEXT,  -- Contoh: LOC, GP, DVOR, DME
            evidence_path TEXT,
            raw_data TEXT
        )
    ''')

    # 2. Tabel Measurements
    c.execute('''
        CREATE TABLE measurements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER,
            parameter_name TEXT,
            value_mon1 TEXT,
            value_mon2 TEXT,
            FOREIGN KEY(session_id) REFERENCES sessions(id)
        )
    ''')

    conn.commit()
    conn.close()
    print(f"✅ Database V2 siap: {DB_FILE}")

if __name__ == "__main__":
    init_db()