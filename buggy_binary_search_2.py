def binary_search(arr, target):
    """
    Performs a binary search on a sorted list.
    Returns the index of the target if found, else -1.
    """
    low = 0
    high = len(arr) - 1

    while low <= high:
        mid = (low + high) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            # INTENTIONAL BUG: Should be low = mid + 1
            low = mid 
        else:
            # Correct logic:
            high = mid - 1

    return -1

if __name__ == "__main__":
    numbers = [1, 3, 5, 7, 9, 11]
    print(f"Found at index: {binary_search(numbers, 7)}")
