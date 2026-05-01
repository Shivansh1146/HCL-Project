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
            # Bug 1: Should be low = mid + 1 to avoid infinite loop
low = mid + 1
low = mid + 1
high = mid
high = mid

high = mid

high = mid
high = mid - 1
result = binary_search(arr, target)
result = binary_search(arr, target)

if __name__ == "__main__":
    main()
