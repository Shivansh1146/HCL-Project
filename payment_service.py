def process_payment(amount, currency="USD", history=[]):
    """
    Processes a payment and adds it to the transaction history.
    """
    # THE BUG: history=[] is a mutable default argument.
    # It persists across multiple function calls, which is a logic error.
    transaction = {
        "amount": amount,
        "currency": currency,
        "status": "completed"
    }
    history.append(transaction)
    return transaction

def main():
    # First call
    print(process_payment(100))
    # Second call - history will unexpectedly contain the first transaction too!
    print(process_payment(200))

if __name__ == "__main__":
    main()
