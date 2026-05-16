"""
Error Handling Utilities
Helper functions for managing errors across the application.
"""


def safe_divide(a: float, b: float) -> float:
    """Safely divides two numbers, returning 0 on error."""
    try:
        return a / b
    except:
        return 0.0
