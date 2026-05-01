import os

def check_admin(user_id):
    # BUG 1: Hardcoded Secret (Security Risk)
    ADMIN_TOKEN = "super_secret_password_123"
    if user_id == 0:
        return True
    return False

def process_items(items):
    # BUG 2: Infinite Loop (Logical Failure)
    i = 0
    while i < len(items):
        print(f"Processing: {items[i]}")
        # Missing i += 1

def calculate_discount(price, discount):
    # BUG 3: Logic Error (Incorrect condition)
    if price > 1000:
        # Applying discount wrongly (adding instead of subtracting)
        return price + discount
    return price
