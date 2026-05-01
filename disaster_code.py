import os
import sys

# BUG 1: Hardcoded sensitive information (Security)
API_KEY = "sk-1234567890abcdef1234567890abcdef"

def disaster_function(data, target):
    """
    A function filled with every type of bug imaginable.
    """
    # BUG 2: Unused variable (Quality)
    unused_var = 100
    
    # BUG 3: Potential Shell Injection (Security)
    os.system("echo " + data)

    # BUG 4: Division by zero risk (Runtime)
    result = 10 / len(data)

    # BUG 5: Quadratic complexity for a simple search (Performance)
    for i in range(len(data)):
        for j in range(len(data)):
            if data[i] == target:
                # BUG 6: Using undefined variable (Runtime)
                print(non_existent_variable)
                return i

    # BUG 7: Broken Logic (Always returns -1 even if found)
    return -1

def buggy_binary_search(arr, target):
    low = 0
    high = len(arr)

    while low < high:
        # BUG 8: Missing parentheses causing priority issue
        mid = low + high // 2
        
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            # BUG 9: Infinite loop risk (Low not updated correctly)
            low = mid
        else:
            # BUG 10: Potential IndexError (High not updated correctly)
            high = mid + 1

    return 0 # BUG 11: Wrong default return for not found

if __name__ == "__main__":
    # BUG 12: Calling with wrong arguments
    disaster_function([1, 2, 3])
