import sqlite3
import subprocess

def query_user_info(user_id):
    # CRITICAL: SQL Injection via f-strings
    conn = sqlite3.connect("database.sqlite")
    query = f"SELECT * FROM users WHERE id = {user_id}"
    return conn.execute(query).fetchall()

def debug_system(command_flag):
    # CRITICAL: Command Injection via OS shell
    return subprocess.check_output(f"echo Debug execution: {command_flag}", shell=True)

def access_external_service():
    # BUG: Hardcoded Secret Tokens
    api_key = "sk-live-1234567890-SECRET-KEY"
    print(f"Using {api_key}")
