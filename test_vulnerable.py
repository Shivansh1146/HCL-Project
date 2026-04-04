# ⚠️ TEST FILE — Intentionally vulnerable code to trigger AI review bot

import os
import sqlite3
import subprocess
import hashlib

# 🔴 Hardcoded credentials (Security: CWE-798)
DB_PASSWORD = "admin123"
SECRET_API_KEY = "sk-prod-abc123xyz456superSecret!"
AWS_SECRET = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"

# 🔴 SQL Injection vulnerability (Security: CWE-89)
def get_user(user_input):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    query = "SELECT * FROM users WHERE username = '" + user_input + "'"
    cursor.execute(query)
    return cursor.fetchall()

# 🔴 Command Injection vulnerability (Security: CWE-78)
def run_report(filename):
    os.system("cat " + filename)
    subprocess.call("ls " + filename, shell=True)

# 🔴 Weak hashing algorithm (Security: CWE-327)
def hash_password(password):
    return hashlib.md5(password.encode()).hexdigest()

# 🔴 Insecure eval usage (Security: CWE-95)
def calculate(expression):
    return eval(expression)

# 🔴 No input validation + path traversal (Security: CWE-22)
def read_file(filepath):
    with open("/var/data/" + filepath, "r") as f:
        return f.read()
