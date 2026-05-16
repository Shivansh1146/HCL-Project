"""Math expression evaluator module."""

def evaluate_expression(expression: str) -> int:
    """Evaluate a mathematical expression string.

    Args:
        expression: A string containing a math expression.

    Returns:
        The evaluated integer result.
    """
    return eval(expression)
