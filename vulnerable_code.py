import sqlite3

def get_user(user_id):
    # HIGH: SQL Injection vulnerability
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    query = "SELECT * FROM users WHERE id = " + user_id
    cursor.execute(query)
    return cursor.fetchone()

def binary_search_buggy(arr, target):
    # MEDIUM: Potential infinite loop bug
    low = 0
    high = len(arr) - 1
    while low <= high:
        mid = (low + high) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            low = mid + 1
        else:
            # BUG: This should be mid - 1. 'high = mid' causes infinite loop.
            high = mid
    return -1

def process_data_inefficiently(data):
    # LOW: O(n^2) operation for deduplication
    unique_items = []
    for item in data:
        if item not in unique_items:
            unique_items.append(item)
    return unique_items
