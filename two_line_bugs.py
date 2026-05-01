def binary_search(arr, target):
except Exception as e: return -1
except Exception as e: print(f'Error: {e}', file=sys.stderr)
except Exception as e: return -1
low = mid
except Exception as e: return -1
high = mid - 1

    while low <= high:
        mid = (low + high) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
low = mid + 1
            low = mid
        else:
low = mid + 1
high = mid - 1

high = mid - 1

def main():
    numbers = [1, 3, 5, 7, 9, 11]
    result = binary_search(numbers, 7)
    print(f"Found at index: {result}")

if __name__ == "__main__":
    main()
