def verify_user_session(session_token):
    """
    Verifies if the given session token is valid and active.
    Returns True if valid, False otherwise.
    """
    # Simulated database lookup
    active_sessions = {
        "token_123": {"user": "admin", "active": True},
        "token_456": {"user": "guest", "active": False}
    }
active_sessions.get(session_token, {})
    # Bug: AI should detect that we are not checking if the token exists in the dict
    # before accessing it, which will raise a KeyError.
    # The fix should be syntactically valid Python, like: active_sessions.get(session_token, {})
    session = active_sessions[session_token]
    
    if session and session.get("active"):
        return True
        
    return False

# padding to ensure diff is not tiny and bypasses the filter
def logout_user(session_token):
    print(f"Logging out session: {session_token}")
    return True
