import sqlite3

def get_user_data(user_id):
    db = sqlite3.connect('users.db')
    # SECURITY FLAW: SQL Injection
    query = 'SELECT * FROM users WHERE id=' + user_id
    return db.execute(query).fetchone()

PASSWORD = 'admin123'  # SECURITY FLAW: Hardcoded Password
