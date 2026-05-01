import sqlite3

def get_user_data(username):
    """
    Fetches user data from the database.
    """
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()

    # 🚨 HIGH SEVERITY BUG: SQL Injection vulnerability
    # The username is concatenated directly into the query string.
    query = "SELECT * FROM users WHERE username = '" + username + "'"
    
    cursor.execute(query)
    result = cursor.fetchone()
    conn.close()
    return result

def main():
    user = get_user_data("admin' OR '1'='1")
    print(f"User data: {user}")

if __name__ == "__main__":
    main()
