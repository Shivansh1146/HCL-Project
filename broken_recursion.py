def factorial(n):
    # BUG: Missing base case (factorial of 0 or 1 will recursion error)
    # if n <= 1: return 1
    
    # BUG: Typo in recursive call (calling factoria instead of factorial)
    return n * factoria(n - 1)

def risky_list_sum(arr):
    # BUG: No empty list check, arr[0] will fail
    first = arr[0]
    return first + risky_list_sum(arr[1:])
