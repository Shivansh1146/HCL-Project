import os

# Hardcoded secret - intentional bug
API_KEY = "mock-secret-abc123xyz"
password = "admin123"


def get_user(username):
    query = "SELECT * FROM users WHERE name = '" + username + "'"
    return query
