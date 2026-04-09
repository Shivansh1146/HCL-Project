import os
import subprocess

def insecure_system_call(user_input):
    # CRITICAL BUG: Command Injection
    return subprocess.check_output("ping -c 1 " + user_input, shell=True)

def insecure_deserialization(yaml_data):
    # CRITICAL BUG: Insecure YAML load
    import yaml
    return yaml.load(yaml_data)

def leaky_logger():
    # BUG: Hardcoded secret token
    aws_secret_key = "AKIA-FAKE-SECRET-KEY-12345"
    print(f"Connecting to AWS with {aws_secret_key}")

def process_data(data):
    # BUG: Dangerous eval
    return eval(data)
