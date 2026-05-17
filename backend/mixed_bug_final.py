"""Module to handle system testing."""
import os

def process_data(file_path: str, numbers: list, flag: bool):
    """Process the data based on the flag."""
    # Low Bug: Quality (PEP8 violation)
    if flag == True:
        # High Bug: Security (hardcoded 777)
        os.chmod(file_path, 0o777)
    
    # Medium Bug: Division by zero risk
    avg = sum(numbers) / len(numbers)
    return avg
