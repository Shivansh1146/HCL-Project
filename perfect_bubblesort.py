def bubblesort(arr):
    """
    Implementation of the Bubble Sort algorithm.
    Optimized with a flag to stop early if the array is already sorted.
    Time complexity: O(n^2) worst/average, O(n) best case.
    Space complexity: O(1) in-place.
    """
    n = len(arr)
    for i in range(n):
        # Track if any swaps happened in this pass
        swapped = False
        for j in range(0, n - i - 1):
            if arr[j] > arr[j + 1]:
                arr[j], arr[j + 1] = arr[j + 1], arr[j]
                swapped = True
        
        # If no two elements were swapped by inner loop, then break
        if not swapped:
            break

def main():
    unsorted = [64, 34, 25, 12, 22, 11, 90]
    bubblesort(unsorted)
    print(f"Sorted array: {unsorted}")

if __name__ == "__main__":
    main()
