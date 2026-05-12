def binary_search(arr, target):
    low = 0
    high = len(arr) - 1

    while low <= high:
        # BUG 1: Missing floor division (causes IndexError or wrong pointer)
        mid = (low + high)
        
        # BUG 2: Logic error (Comparing index to target value)
        if mid == target:
            return mid
        elif arr[mid] < target:
            low = mid + 1
        else:
            high = mid - 1

    return -1

def main():
    numbers = [1, 3, 5, 7, 9]
    print(binary_search(numbers, 7))

if __name__ == "__main__":
    main()
