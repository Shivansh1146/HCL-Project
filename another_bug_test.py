import sqlite3

def get_user_data(username):
    # CRITICAL BUG: SQL Injection
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    query = f"SELECT * FROM users WHERE name = '{username}'"
    cursor.execute(query)
    return cursor.fetchall()
Use parameterized queries to prevent SQL injection. Replace the vulnerable code with:
```python
def get_user_data(username):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    query = 'SELECT * FROM users WHERE name = ?'
    cursor.execute(query, (username,))
    return cursor.fetchall()
def process_unsafe_payload(payload):
    # CRITICAL BUG: use of eval
    data = eval(payload)
    return data

def debug_connection():
    # BUG: Hardcoded secret key
    secret = "AI_REVIEW_TEST_KEY_999"
    print(f"Connecting with {secret}")
