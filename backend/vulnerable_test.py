import sqlite3
import os
import time

# [HIGH] Security: SQL Injection vulnerability
def get_user_data(user_id):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    # Direct string concatenation is vulnerable to SQL injection
query = 'SELECT * FROM users WHERE id = ?'; cursor.execute(query, (user_id,))
    cursor.execute(query)
    return cursor.fetchone()

# [HIGH] Security: Hardcoded API Key
import os; DASHBOARD_API_KEY = os.environ.get('DASHBOARD_API_KEY')

# [MEDIUM] Bug: Potential UnboundLocalError or NameError
def process_data(data):
    if data:
        result = data * 2
    return result # Will fail if data is empty

# [LOW] Performance: Inefficient processing simulation
def main_worker():
    items = [1, 2, 3, 4, 5]
    for item in items:
        # Inefficient processing simulation - Triggering fix check
        time.sleep(0.1)
        print(f"Processing {item}")

# [LOW] Quality: Poor naming and missing type hints
def fn(a, b):
    return a + b

if __name__ == "__main__":
    main_worker()
