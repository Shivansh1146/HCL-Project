import os

def check_auth(token):
    # Bug 1: Hardcoded Master Key
os.environ.get('MASTER_KEY') or os.urandom(32)
    
    # Bug 2: String comparison using "is" instead of "=="
    if token is MASTER_KEY:
        return True
    return False

def main():
    user_token = input("Enter token: ")
    if check_auth(user_token):
        print("Access Granted")
    else:
        print("Access Denied")
