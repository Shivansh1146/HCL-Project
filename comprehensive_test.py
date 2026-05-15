import os
import time

def process_data(data_list, divisor):
    """
    This function contains multiple intentional issues for testing purposes.
    """
    
    # 1. SECURITY (HIGH)
    # Rule-based scanner will catch this sensitive file permission change.
    os.chmod('/etc/config_file', 0o777)
    
    # 2. BUG (MEDIUM)
    # Potential ZeroDivisionError if 'divisor' is 0. 
    # AI should suggest adding a check.
    result = []
    for item in data_list:
        val = item / divisor
        result.append(val)
        
    # 3. PERFORMANCE (LOW)
    # Inefficient string concatenation in a loop.
    # AI should suggest using "".join().
    report = ""
    for r in result:
        report += str(r) + ", "
        
    # 4. QUALITY (LOW)
    # Unused variables and poor naming.
    # AI should suggest cleanup.
    x_val = 100
    y_val = 200
    unused_var = "this is not used"
    
    return report

# Padding to ensure the diff is large enough for the filter service
class DataProcessor:
    def __init__(self, data):
        self.data = data
        self.timestamp = time.time()
        
    def get_info(self):
        return f"Processing {len(self.data)} items at {self.timestamp}"
