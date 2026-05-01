def binary_search(arr, target):
    """
    Performs a binary search on a sorted list.
    Contains ONE intentional logical bug.
    """
    low = 0
    high = len(arr) - 1

    while low <= high:
        mid = (low + high) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            low = mid + 1
        else:
            # BUG: This should be high = mid - 1
            # This will cause an infinite loop or incorrect search
            high = mid + 1

    return -1

def main():
    numbers = [1, 3, 5, 7, 9, 11]
    # Searching for 2 (which is smaller than some elements)
    # should trigger the buggy else block
    result = binary_search(numbers, 2)
    print(f"Found at index: {result}")

if __name__ == "__main__":
    main()
