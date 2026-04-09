import os

def vulnerable_function(user_id):
    """
    This function was designed to be vulnerable for testing the AI Code Reviewer.
    """
    # SQL INJECTION VULNERABILITY
    # The AI should flag this O(n) string interpolation in a query
    query = f"SELECT * FROM users WHERE id = '{user_id}'"
    print(f"Executing: {query}")

    # HARDCODED SECRET
    # The AI should flag this hardcoded API key
    api_key = "sk-test-vulnerability-key-54321"
    print(f"Using API Key: {api_key}")

    # COMMAND INJECTION VULNERABILITY
    # Using os.system with untrusted input
    os.system(f"ls -l {user_id}")

if __name__ == "__main__":
    vulnerable_function("1; DROP TABLE users;")
