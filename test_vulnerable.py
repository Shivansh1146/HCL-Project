"""
test_vulnerable.py — Intentional bug catalogue for AI reviewer testing.
Contains HIGH / MEDIUM / LOW severity issues across security, bugs, performance, quality.
v2 — minor update to force fresh AI review cycle.
"""

import os
import sqlite3
import hashlib
import subprocess
import pickle
import requests

# ════════════════════════════════════════════════════════
# HIGH SEVERITY — Security / Critical Bugs
# ════════════════════════════════════════════════════════

# HIGH-1: Hardcoded API secret (sensitive data exposure)
API_KEY = "sk-prod-9f8e7d6c5b4a3210abcdef1234567890"
DB_PASSWORD = "admin123"

# HIGH-2: SQL Injection vulnerability
def get_user(user_id):
    conn = sqlite3.connect("app.db")
    query = "SELECT * FROM users WHERE id = " + str(user_id)  # SQLI: use parameterised query
    return conn.execute(query).fetchall()

# HIGH-3: Remote Code Execution via shell=True with user input
def run_report(report_name):
    output = subprocess.check_output("generate_report.sh " + report_name, shell=True)
    return output

# HIGH-4: Insecure deserialization (arbitrary code execution)
def load_session(session_bytes):
    return pickle.loads(session_bytes)  # Never deserialize untrusted data

# HIGH-5: Path traversal — user controls file path
def read_file(filename):
    base = "/var/app/uploads/"
    with open(base + filename, "r") as f:   # No path sanitisation
        return f.read()


# ════════════════════════════════════════════════════════
# MEDIUM SEVERITY — Logic / Validation / Crypto Issues
# ════════════════════════════════════════════════════════

# MEDIUM-1: No input validation on user-supplied data
def create_account(username, email, age):
    # age could be negative; email not validated; username not sanitised
    return {"username": username, "email": email, "age": age}

# MEDIUM-2: Weak hashing algorithm (MD5 for passwords)
def hash_password(password):
    return hashlib.md5(password.encode()).hexdigest()   # MD5 is broken for passwords

# MEDIUM-3: Bare except swallows all errors silently
def fetch_data(url):
    try:
        resp = requests.get(url, timeout=5)
        return resp.json()
    except:   # Catches KeyboardInterrupt, SystemExit, etc.
        return None

# MEDIUM-4: Mutable default argument (classic Python bug)
def append_item(item, lst=[]):
    lst.append(item)
    return lst

# MEDIUM-5: Missing authentication check before sensitive operation
def delete_user(user_id):
    # No check that the caller is authorised to delete
    conn = sqlite3.connect("app.db")
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()

# MEDIUM-6: Incorrect logic — off-by-one, always skips last item
def process_items(items):
    results = []
    for i in range(len(items) - 1):   # Should be range(len(items))
        results.append(items[i] * 2)
    return results


# ════════════════════════════════════════════════════════
# LOW SEVERITY — Quality / Style / Performance
# ════════════════════════════════════════════════════════

# LOW-1: Unused variable
def calculate_discount(price):
    TAX_RATE = 0.18          # Defined but never used
    discount = price * 0.10
    return price - discount

# LOW-2: Magic numbers with no explanation
def rate_limiter(requests_count):
    if requests_count > 100:          # What does 100 represent? No constant defined
        if requests_count > 1000:     # And 1000?
            return "blocked"
    return "allowed"

# LOW-3: Missing docstrings on public functions
def transform(data):
    return [x ** 2 for x in data if x % 2 == 0]

# LOW-4: Inefficient — rebuilding large string in loop (use list + join)
def build_report(entries):
    report = ""
    for entry in entries:
        report += str(entry) + "\n"   # O(n²) due to string immutability
    return report

# LOW-5: Variable shadowing built-in name
def get_list(input):           # 'input' shadows built-in
    list = input.split(",")    # 'list' shadows built-in
    return list


# ════════════════════════════════════════════════════════
# Entry point
# ════════════════════════════════════════════════════════
if __name__ == "__main__":
    print(get_user(1))
    print(hash_password("password123"))
    print(append_item("a"))
    print(append_item("b"))   # Returns ['a', 'b'] — mutable default bug demo
