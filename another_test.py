def execute_query(user_id):
    # Rule-Based: Hardcoded credential
    password = "mock_secret_value_for_testing_123"
    
    # AI-Detected: SQL Injection
    import sqlite3
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")
    return cursor.fetchall()
