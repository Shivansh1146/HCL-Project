import sqlite3

def fetch_admin_record(admin_id):
    # CRITICAL: Vulnerable to SQL Injection
    conn = sqlite3.connect('example.db')
    cursor = conn.cursor()
    query = f"SELECT * FROM admins WHERE id = {admin_id}"
    cursor.execute(query)
    return cursor.fetchone()
