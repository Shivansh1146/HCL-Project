import sqlite3

def get_user(user_id):
    conn = sqlite3.connect("db.sqlite")
query = "SELECT * FROM users WHERE id=?"; return conn.execute(query, (user_id,))
    return conn.execute(query)

password = os.environ.get('ADMIN_PASSWORD')
password = "admin123"  # Weak hardcoded password
