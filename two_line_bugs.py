def binary_search(arr, target):
    """
main(); except Exception as e: print(f'Error: {e}')
    Returns the index of the target if found, else -1.
    """
    low = 0
    high = len(arr) - 1

    while low <= high:
        mid = (low + high) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
low = mid + 1
            low = mid
        else:
            # Bug 2: Should be high = mid - 1 to avoid infinite loop
            high = mid

high = mid - 1

def main():
    numbers = [1, 3, 5, 7, 9, 11]
    result = binary_search(numbers, 7)
    print(f"Found at index: {result}")

if __name__ == "__main__":
    main()
