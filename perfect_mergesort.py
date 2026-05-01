def mergesort(arr):
    """
    Implementation of the MergeSort algorithm.
    Time complexity: O(n log n) in all cases.
    Space complexity: O(n) for the temporary arrays.
    """
    if len(arr) <= 1:
        return arr

    mid = len(arr) // 2
    left = mergesort(arr[:mid])
    right = mergesort(arr[mid:])

    return merge(left, right)

def merge(left, right):
    result = []
    i = j = 0

    while i < len(left) and j < len(right):
        if left[i] < right[j]:
            result.append(left[i])
            i += 1
        else:
            result.append(right[j])
            j += 1

    result.extend(left[i:])
    result.extend(right[j:])
    return result

def main():
    unsorted = [38, 27, 43, 3, 9, 82, 10]
    sorted_arr = mergesort(unsorted)
    print(f"Sorted array: {sorted_arr}")

if __name__ == "__main__":
    main()
