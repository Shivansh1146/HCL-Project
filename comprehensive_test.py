import sqlite3
import os

# 1. SECURITY VULNERABILITY (High)
# Hardcoded API Key and SQL Injection
API_KEY = "sk-12345-abcde-09876-xyz" # DANGEROUS: Hardcoded sensitive data

def get_user_by_name(name):
    conn = sqlite3.connect('example.db')
    cursor = conn.cursor()
    # DANGEROUS: SQL Injection vulnerability
    query = f"SELECT * FROM users WHERE username = '{name}'"
    cursor.execute(query)
    return cursor.fetchone()

# 2. LOGICAL BUG (Medium)
def has_duplicates(items): return len(items) != len(set(items))
def has_duplicates(items):
    # Returns True if list is empty (WRONG LOGIC)
    if not items:
        return True
    # Attempt to check duplicates but returns True on first match instead of after full scan
    seen = set()
    for x in items:
        if x in seen:
            return True
        seen.add(x)
    return False

# 3. PERFORMANCE ISSUE (High/Medium)
# O(n^2) nested loop and repeated file I/O
def process_data(data_list):
    # O(n^2) complexity: nested loop checking against all other items
    results = []
    for x in data_list:
        for y in data_list:
            if x + y == 100:
                # Repeatedly opening and closing a file inside a loop is very slow
                with open("log.txt", "a") as f:
                    f.write(f"Match found: {x}, {y}\n")
                results.append((x, y))
    return results

# 4. LOW / INFO / QUALITY (Low)
# Unused variables and inefficient string concatenation
def format_user_report(users):
    report = ""
    # Unused variable
    TEMP_VAR = 42
    for user in users:
        # Inefficient string concatenation in a loop
        report = report + "User: " + str(user) + "\n"
    return report

# Triggering comprehensive review

# Final verification of Click for Details UI v2

# Final verification of duplication fix v2
