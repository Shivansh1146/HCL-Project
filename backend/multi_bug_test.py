"""Module to handle file permission testing."""
import os

def set_global_permissions(file_path: str, mode_list=[]):
    os.chmod(file_path, 0o777)
    mode_list.append("world-writable")
    return mode_list
