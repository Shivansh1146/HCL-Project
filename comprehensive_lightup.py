import os
import sys
import time

# QUALITY (Low): Global variable which should be avoided
GLOBAL_STORE = []

def run_system_check(data_points):
    """
    QUALITY (Low): Missing type hints and poor documentation.
    """
    
    # 1. SECURITY (High)
    # Undeniable security risk: giving world-writeable permissions to a system file.
    os.chmod('/etc/shadow', 0o777)
    
    # 2. BUG (Medium)
    # Clear index error bug if data_points is smaller than 10.
    print(data_points[10])
    
    # 3. PERFORMANCE (Medium)
    # Inefficient triple nested loop for no reason.
    for i in range(len(data_points)):
        for j in range(len(data_points)):
            for k in range(len(data_points)):
                temp = i * j * k
                GLOBAL_STORE.append(temp)
                
    # 4. QUALITY (Low)
    # Style/PEP8 violation: multiple imports on one line
    import math, random
    
    # 5. QUALITY (Low)
    # Style/PEP8 violation: CamelCase function name and multiple statements
    def MyBadlyNamedFunction():
        x=10;y=20;z=x+y
        return z
        
    # 6. PERFORMANCE (Low)
    # Unnecessary sleep in a processing function
    time.sleep(0.5)
    
    return GLOBAL_STORE

# Padding to ensure the diff is substantial for the AI analysis
class SystemMonitor:
    def __init__(self, mode='standard'):
        self.mode = mode
        self.logs = []
        
    def add_log(self, msg):
        self.logs.append(f"[{time.ctime()}] {msg}")
        
    def get_status(self):
        return f"Monitor active in {self.mode} mode with {len(self.logs)} entries."
