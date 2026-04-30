import sqlite3
import os

def test_cases(user_id, user_input):
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()

    # ✅ Case 1 — Safe SQL (should NOT flag)
    # The filter should detect the '?' and suppress the SQLi warning.
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))

    # ❌ Case 2 — Broken parameter usage (must flag)
    # The query expects a parameter but none is provided.
    query_broken = "SELECT * FROM users WHERE id = ?"
    cursor.execute(query_broken)

    # ❌ Case 3 — Real SQLi (must flag)
    # Direct f-string interpolation is a classic vulnerability.
    query_sqli = f"SELECT * FROM users WHERE id = {user_id}"
    cursor.execute(query_sqli)

    # ❌ Case 4 — eval (must flag HIGH)
    # Arbitrary code execution vulnerability.
    eval(user_input)
