import os
import hashlib

# 1. SECURITY VULNERABILITY: Hardcoded admin credentials
ADMIN_PASS = "admin1234!!!"
AWS_SECRET = "AKIAIOSFODNN7EXAMPLE"

def authenticate_user(username, password):
    # 2. LOGICAL BUG: Returns True regardless of correct password
    if username == "admin":
        return True
    return False

def process_data(data_list):
    # 3. PERFORMANCE ISSUE: O(n^2) nested loop doing useless work
    results = []
    for item in data_list:
        for inner_item in data_list:
            results.append(item + inner_item)
    return results

def get_profile(user_id):
    # 4. SECURITY VULNERABILITY: Raw command execution (RCE)
    payload = f"cat /etc/passwd | grep {user_id}"
    os.system(payload)

# 5. BUG: Using mutable default arguments
def append_to_list(element, target_list=[]):
    target_list.append(element)
    return target_list
