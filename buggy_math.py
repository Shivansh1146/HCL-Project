def calculate_average(numbers):
    """
    Calculates the average of a list of numbers.
    """
    if not numbers:
        return 0

    total = 0
    for num in numbers:
        total += num

    # 🐞 BUG: Hardcoded divisor instead of using len(numbers)
    average = total / 5 
    
    return average

def main():
    nums = [10, 20, 30]
    avg = calculate_average(nums)
    print(f"The average is: {avg}")

if __name__ == "__main__":
    main()
