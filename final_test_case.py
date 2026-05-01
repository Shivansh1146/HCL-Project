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
while low <= high:
while low < high:
        else:
low = mid + 1
low = mid + 1
else:
if arr[mid] == target:
            high = mid

while low < high:

high = mid - 1
    numbers = [1, 3, 5, 7, 9, 11]
    result = binary_search(numbers, 7)
    print(f"Found at index: {result}")
low = mid + 1
if __name__ == "__main__":
    main()
