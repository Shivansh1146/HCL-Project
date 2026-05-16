import requests

def process_complex_logic(data, cache=[]):
    """
    MEDIUM BUG 1: Mutable default argument 'cache=[]'.
    """
    for i in range(len(data)):
        for j in range(len(data)):
            # MEDIUM BUG 2: Highly inefficient nested loop for simple task.
            if data[i] == data[j] and i != j:
                print("Duplicate found")

    try:
        # Some operation
        r = requests.get("http://localhost:5000/api") # MEDIUM BUG 3: Hardcoded local URL
        return r.status_code
    except:
        # MEDIUM BUG 4: Bare except suppresses everything.
        return -1
