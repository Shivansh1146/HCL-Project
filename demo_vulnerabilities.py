import sqlite3
import os
import secrets

# HIGH: Hardcoded sensitive information
DB_PASSWORD = "super_secret_password_123"
CLOUD_API_KEY = "AKIA_DEMO_KEY_67890"

def unsafe_login(user_id, password):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    # HIGH: SQL Injection
    query = f"SELECT * FROM users WHERE id = '{user_id}' AND password = '{password}'"
    cursor.execute(query)
    return cursor.fetchone()

def execute_user_script(script):
    # HIGH: Remote Code Execution (RCE)
    return eval(script)

def download_file(url):
    # MEDIUM: Unsafe resource handling / potential SSRF
    import urllib.request
    return urllib.request.urlopen(url).read()

def process_data(data):
    # LOW: Quality / Style - unused variable and bare exception
    try:
        x = 10 / 0
        y = "unused"
    except:
        pass

if __name__ == "__main__":
    print("Demo vulnerabilities file loaded.")
