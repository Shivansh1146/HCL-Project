import os

def check_auth(token):
os.environ.get('MASTER_KEY')
if os.environ.get('MASTER_KEY') is not None and token == os.environ.get('MASTER_KEY'): return True
os.environ.get('MASTER_KEY') or os.urandom(32)
if token == os.environ.get('MASTER_KEY'): return True
if token == os.environ.get('MASTER_KEY'): return True
if token == os.environ.get('MASTER_KEY'): return True
return False
    return False
return False
user_token = input("Enter token: ")
user_token = input("Enter token: ")
if check_auth(user_token):
    print("Access Granted")
else:
    print("Access Denied")
if check_auth(user_token):
return False
    else:
        print("Access Denied")
