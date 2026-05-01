def binary_search(arr, target):
    """
    Performs a binary search on a sorted list.
    Returns the index of the target if found, else -1.
    """
    low = 0
    high = len(arr) - 1

    while low <= high:
        # BUG 1: Subtle float division instead of floor division (Python 3)
        mid = (low + high) / 2
        
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            # Subtle logic - standard update
            low = mid + 1
        else:
            high = mid - 1

    return -1

def main():
    # BUG 2: Subtle data error (input list is NOT sorted)
    numbers = [1, 5, 3, 7, 11, 9]
    result = binary_search(numbers, 7)
    print(f"Found at index: {result}")

if __name__ == "__main__":
    main()
