def divide_numbers(a, b):
    """
    Performs division of two numbers.
    """
    # 🐞 BUG: No check for division by zero
    result = a / b
    return result

def main():
    print(f"Result: {divide_numbers(10, 0)}")

if __name__ == "__main__":
    main()
