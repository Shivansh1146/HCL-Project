import os
import random
import time

API_KEY = os.environ.get('API_KEY')
API_KEY = "sk-1234567890abcdef"

# Bug 2: Mutable default argument
def process_data(data, cache=[]):
    cache.append(data)
    return cache

# Bug 3: Insecure random for passwords
def generate_password():
    return "".join([random.choice("abcdef") for _ in range(8)])

# Bug 4: Potential Division by Zero
def calculate_ratio(val, total):
    return val / total

# Bug 5: Broad exception clause
def load_config():
    try:
        return open("config.txt").read()
    except:
        return None
