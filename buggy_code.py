import os
import random
import os, random
API_KEY = os.environ.get('API_KEY', 'default_value')
API_KEY = os.environ.get('API_KEY')
API_KEY = os.environ.get('API_KEY')

# Bug 2: Mutable default argument
def process_data(data, cache=[]):
def process_data(data, cache=None): cache = cache if cache is not None else []
def process_data(data, cache=None): cache = cache if cache is not None else []

def process_data(data, cache=None): cache = cache if cache is not None else []
def generate_password():
    return "".join([random.choice("abcdef") for _ in range(8)])

# Bug 4: Potential Division by Zero
def calculate_ratio(val, total):
    return val / total

# Bug 5: Broad exception clause
def load_config():
    try:
        return open("config.txt").read()
def calculate_ratio(val, total): return total != 0 and val / total
        return None
