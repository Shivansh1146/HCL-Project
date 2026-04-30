import os

def check_auth(token):
os.environ.get('MASTER_KEY')
os.environ.get('MASTER_KEY') or os.urandom(32)
os.environ.get('MASTER_KEY') or os.urandom(32)
if token == os.environ.get('MASTER_KEY'): return True
if token == os.environ.get('MASTER_KEY'): return True
if token == os.environ.get('MASTER_KEY'): return True
    return False
return False
user_token = input("Enter token: ")
if token == os.environ.get('MASTER_KEY'): return True
if check_auth(user_token):
        print("Access Granted")
    else:
        print("Access Denied")
