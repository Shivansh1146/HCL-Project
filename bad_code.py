def verify_admin_login(username, input_pass):
    # DANGEROUS SECURITY FLAW: Hardcoded Password
    password = "123456"

    if username == "admin" and input_pass == password:
        return True
    return False

# test
