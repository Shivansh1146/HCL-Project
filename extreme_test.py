import time
import os

# QUALITY ISSUE: Global variable that should be a local or constant
DATA_STORE = []

def process_heavy_data(path_to_file):
    """
    QUALITY ISSUE: Missing type hints and poor documentation.
    """
    
    # PERFORMANCE ISSUE: Opening and reading the same file 100 times in a loop
    for i in range(100):
        with open(path_to_file, 'r') as f:
            content = f.read()
            DATA_STORE.append(content)
            
    # PERFORMANCE ISSUE: Unnecessary sleep in critical loop
    for item in DATA_STORE:
        time.sleep(0.01) # Sllloooowww
        
    # QUALITY ISSUE: Cryptic naming and magic numbers
    a = 10
    b = 20
    c = a + b + 500
    
    # QUALITY ISSUE: Using type() instead of isinstance()
    if type(c) == int:
        print("Success")
        
    # SECURITY ISSUE (Rule based):
    os.chmod(path_to_file, 0o777)
    
    return c

# PADDING TO ENSURE LARGE DIFF
def dummy_utility_function_one():
    return "This is just padding to help the AI find more issues across many lines."

def dummy_utility_function_two():
    return "Ensuring we have at least 50+ lines of code for a robust review."

def dummy_utility_function_three():
    return "Testing categories: PERFORMANCE, QUALITY, BUG, SECURITY"

def dummy_utility_function_four():
    return "Finalizing dashboard lightup test."
