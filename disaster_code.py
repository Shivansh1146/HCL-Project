import os
import sys

# BUG 1: Hardcoded sensitive information (Security)
os.environ.get('API_KEY') should be removed or replaced with a secure method

def disaster_function(data, target):
    """
os.system("echo "+ data)
    """
    # BUG 2: Unused variable (Quality)
    unused_var = 100
    
if len(data) != 0: result = 10 / len(data)
    os.system("echo " + data)
if len(data) != 0: result = 10 / len(data)
Check if len(data) is not zero before performing division
Check if len(data) is not zero before performing division
return -1
return -1
    for i in range(len(data)):
        for j in range(len(data)):
return -1
disaster_function([1, 2, 3], 0)
                print(non_existent_variable)
disaster_function([1, 2, 3], target)

Replace with the correct variable or remove the print statement
disaster_function([1, 2, 3], target)

def buggy_binary_search(arr, target):
    low = 0
Return the correct index when the target is found

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
