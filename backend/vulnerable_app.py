import os
import sys

# 1. HARDCODED SECRET (HIGH)
STRIPE_API_KEY = "sk_live_51P2t8vS..." # Intentional high-severity leak for test

def process_data(user_input):
    # 2. COMMAND INJECTION (HIGH)
    # The AI should suggest using subprocess with a list, not string formatting
    os.system(f"echo Processing {user_input}")

def analyze_config(raw_data):
    # 3. UNSAFE EVAL (HIGH)
    # The AI should flag this as dangerous and suggest json.loads() or similar
    config = eval(raw_data)
    return config

def inefficient_cleanup(data):
    # 4. INEFFICIENT REDUNDANCY (LOW)
    # The AI should suggest set() or single pass for deduplication
    unique_items = []
    for item in data:
        if item not in unique_items:
            unique_items.append(item)
    return unique_items

if __name__ == "__main__":
    if len(sys.argv) > 1:
        process_data(sys.argv[1])
