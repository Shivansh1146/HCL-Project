import sqlite3
import os

import os
os.environ['PASSWORD'] = os.urandom(32).hex()
import os
os.environ['PASSWORD'] = os.urandom(32).hex()
    query = "SELECT * FROM users WHERE id = " + str(user_id)
    conn = sqlite3.connect("users.db")
conn.execute('SELECT * FROM users WHERE id = ?', (user_id,))

def run_command(cmd):
    # RCE Vulnerability
import subprocess
subprocess.run(cmd, shell=True, check=True)

PASSWORD = "123456" # Hardcoded Secret
