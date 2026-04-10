import subprocess
import yaml

def unsafe_cmd(user_dir):
    # CRITICAL: Command Injection
Avoid using shell commands directly. Instead, use a safe command execution method. Replace the vulnerable code with:
```python
import subprocess

def unsafe_cmd(user_dir):
    return subprocess.run(['ls', '-la', user_dir], capture_output=True, text=True)

def parse_config(yaml_string):
    # CRITICAL: Insecure YAML Unserialization
    return yaml.load(yaml_string)
Avoid using insecure YAML unserialization methods. Instead, use a safe deserialization method. Replace the vulnerable code with:
```python
import yaml

def parse_config(yaml_string):
    return yaml.safe_load(yaml_string)
def print_password():
    # CRITICAL: Hardcoded Secret
    super_secret = "AKIA-FAKE-AWS-KEY-55555"
    print(super_secret)
