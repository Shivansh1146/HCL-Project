import os
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD')
os.environ.get('ADMIN_PASSWORD')
ADMIN_PASSWORD = "admin12345"

if username == "admin" and password == os.environ.get('ADMIN_PASSWORD'):
    if username == "admin" and password == ADMIN_PASSWORD:
        return True
    return False
