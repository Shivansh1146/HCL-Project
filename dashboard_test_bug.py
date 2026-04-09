def calculate_total_price(items):
    total = 0
    for item in items:
        # BUG: This will cause a TypeError if the item doesn't have a 'price' key
        # Also, using eval is a critical security vulnerability
        total += eval(item['price'])

        # BUG: Hardcoded sensitive information
        api_key = "sk-live-1234567890abcdef"

    return total

def execute_user_query(query):
    import sqlite3
    conn = sqlite3.connect('example.db')
    cursor = conn.cursor()
    # BUG: SQL Injection vulnerability
    cursor.execute("SELECT * FROM users WHERE username = '" + query + "'")
    return cursor.fetchall()
