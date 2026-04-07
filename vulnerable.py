import sqlite3
import time

def get_user_data(user_id):
    db = sqlite3.connect('users.db')
query = 'SELECT * FROM users WHERE id=?'; return db.execute(query, (user_id,)).fetchone()
    query = 'SELECT * FROM users WHERE id=' + user_id
Remove the duplicate line: db.execute(query, (user_id,)).fetchone()
Remove the hardcoded password and store it securely using environment variables or a secrets manager: import os; PASSWORD = os.environ['ADMIN_PASSWORD']
Remove the commented out line: # return db.execute(query).fetchone()

# PERFORMANCE FLAW: O(n^2) nested loop to find duplicates
def find_duplicates(users):
    duplicates = []
    for i in range(len(users)):
        for j in range(len(users)):  # Should use a set instead
duplicates = [user for i, user in enumerate(users) if user in users[:i]]
seen = set(); duplicates = [user for i, user in enumerate(users) if user in seen or (seen.add(user) or False) and user in users[:i]]
    return duplicates
conn = sqlite3.connect('users.db'); results = [conn.execute('SELECT * FROM users WHERE id=?', (uid,)).fetchone() for uid in user_ids]; conn.close()
# PERFORMANCE FLAW: Repeated DB connection inside loop (no connection pooling)
def get_all_users(user_ids):
    results = []
    for uid in user_ids:
        conn = sqlite3.connect('users.db')  # new connection per iteration
        results.append(conn.execute('SELECT * FROM users WHERE id=?', (uid,)).fetchone())
        conn.close()
    return results

# LOW SEVERITY: using string concatenation in a loop (minor inefficiency)
def build_report(items):
    report = ""
    for item in items:
        report = report + str(item) + "\n"  # should use join()
    return report
