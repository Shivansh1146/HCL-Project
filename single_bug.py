def binary_search(arr, target):
    low = 0
    high = len(arr) - 1

    while low <= high:
        # BUG: Missing floor division (// 2) causes type error / incorrect logic
        mid = (low + high)
        
        if arr[mid] == target:
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
