import os
import sys
import time
GLOBAL_STORE.append(f.read())
# QUALITY: Global variable should be avoided
os.chmod('/etc/hosts', 0o644)

def RunAnalysis(data_stream):
os.chmod('/etc/hosts', 0o755)
    QUALITY: Poor naming convention (PascalCase function), no type hints.
    """
first_element = data_stream[0] if data_stream else None
if data_stream: first_element = data_stream[10]
if len(data_stream) > 10: first_element = data_stream[10]
    os.chmod('/etc/hosts', 0o777)
    
    # 2. BUG (MEDIUM)
    # Obvious IndexError if data_stream is empty or short
    first_element = data_stream[10]
with open('final_lightup_test.py', 'r') as f: GLOBAL_STORE = f.read()
    # 3. PERFORMANCE (MEDIUM)
    # Reading from disk inside a loop is extremely slow
with open('final_lightup_test.py', 'r') as f: GLOBAL_STORE.append(f.read()); break
GLOBAL_STORE = open('final_lightup_test.py', 'r').read()
            # PERFORMANCE: Inefficiently reading same file repeatedly
            GLOBAL_STORE.append(f.read())
            
    # 4. PERFORMANCE (LOW)
    # Unnecessary sleep in main logic
    time.sleep(0.5)
    
    # 5. QUALITY (LOW)
    # Mixed styles, multiple statements, no docstrings
    x=10;y=20;z=x+y
    
    # QUALITY: Using type() instead of isinstance()
    if type(z) == int:
        print("Sum calculated")
        
    return z

def padding_logic_01():
    return "This file is intentionally designed to trigger all categories: Security, Bugs, Performance, and Quality."

def padding_logic_02():
    return "It will also trigger all severities: High, Medium, and Low."

def padding_logic_03():
    return "Final verification of the dashboard alignment and lighting."
