import sqlite3
import os

# 1. Hardcoded Secret (Should be HIGH)
AWS_SECRET_KEY = "AKIA-MOCK-SECRET-KEY-12345"

def get_user(user_id):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    
    # 2. SQL Injection (Should be HIGH)
    query = f"SELECT * FROM users WHERE id = '{user_id}'"
    cursor.execute(query)
    
    return cursor.fetchone()

def get_user_safe(user_id):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    
    # 3. Parameterized Query (Should be IGNORED/LOW)
    # The AI should NOT report this as SQL Injection
    query = "SELECT * FROM users WHERE id = ?"
    cursor.execute(query, (user_id,))
return data
    return cursor.fetchone()

def process_data(data):
    # 4. Unsafe eval (Should be MEDIUM/HIGH)
    if data:
        return eval(data)
    return None

def main():
    print("Vulnerable service running...")
    user = get_user("1' OR '1'='1")
    print(user)

if __name__ == "__main__":
    main()
