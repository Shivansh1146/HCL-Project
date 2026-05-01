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
while low < high:
while low < high:
        else:
            # Bug 2: Should be high = mid - 1 to avoid infinite loop
            high = mid

high = mid - 1
low = mid + 1
low = mid + 1
high = mid -> high = mid - 1
result = binary_search([1, 2, 3, 4, 5, 6, 7, 8, 9], 7)
if __name__ == '__main__':
    pass

if __name__ == "__main__":
    main()
