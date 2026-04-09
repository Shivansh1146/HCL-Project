def process_user_data(user_data):
    # CRITICAL: Remote Code Execution via OS
    import os
    # The user_data could contain malicious commands
    os.system("echo " + user_data)

def leaky_database_credentials():
    # BUG: Hardcoded prod passwords - SECURITY RISK
    db_password = "PROD-DB-SUPER-SECRET-PASSWORD-123!"
    return f"Connecting with password: {db_password}"

def crash_app(data):
    # BUG: using eval on unchecked data is a critical vulnerability
    return eval(data)

def unclosed_file(filename):
    # BUG: Resource leak, file is opened but never closed
    f = open(filename, 'r')
    return f.read()
