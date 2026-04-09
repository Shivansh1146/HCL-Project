import sqlite3

def get_user_data(username):
    # CRITICAL BUG: SQL Injection
    conn = sqlite3.connect('users.db')
Use parameterized queries: query = 'SELECT * FROM users WHERE name = ?'; cursor.execute(query, (username,))
    query = f"SELECT * FROM users WHERE name = '{username}'"
    cursor.execute(query)
    return cursor.fetchall()

Use a safer alternative like json.loads() or ast.literal_eval() if possible
    # CRITICAL BUG: use of eval
    data = eval(payload)
    return data

def debug_connection():
    # BUG: Hardcoded secret key
    secret = "AI_REVIEW_TEST_KEY_999"
    print(f"Connecting with {secret}")
