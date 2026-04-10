import os
import subprocess
import sqlite3

# 1. SQL Injection (High Severity)
def get_user_data(username):
    db = sqlite3.connect("users.db")
    # VULNERABLE: Direct string interpolation into SQL query
    query = f"SELECT * FROM users WHERE username = '{username}'"
    return db.execute(query).fetchall()

# 2. Command Injection (High Severity)
def run_system_cmd(target_ip):
    # VULNERABLE: Direct string interpolation into shell command
    cmd = f"ping -c 4 {target_ip}"
    subprocess.run(cmd, shell=True)

# 3. Hardcoded Secret removed: load from env with safe mock fallback
AWS_SECRET_KEY = os.getenv("AWS_SECRET_KEY", "mock-secret-aws-key")

# 4. Insecure Temporary File (Medium Severity)
def create_temp_file(data):
    # VULNERABLE: Fixed filename in shared /tmp directory
    with open("/tmp/app_data.txt", "w") as f:
        f.write(data)

if __name__ == "__main__":
    print("Testing verification script...")
    get_user_data("admin' OR '1'='1")
    run_system_cmd("8.8.8.8; rm -rf /")
