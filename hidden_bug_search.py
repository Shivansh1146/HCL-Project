def binary_search(arr, target):
    """
    Performs a binary search on a sorted list.
    """
    low = 0
    high = len(arr) - 1

    while low <= high:
        mid = (low + high) // 2
        
        # BUG 1: Subtle identity vs equality bug (Using 'is' instead of '==')
        if arr[mid] is target:
            return mid
        elif arr[mid] < target:
            low = mid + 1
        else:
            high = mid - 1

    return -1

def main():
    # BUG 2: Prerequisite violation (unsorted list for binary search)
    numbers = [10, 2, 8, 4, 6]
    result = binary_search(numbers, 8)
    print(f"Result: {result}")

if __name__ == "__main__":
    main()
