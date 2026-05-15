def process_dynamic_expression(expression_string):
    """
    Evaluates a dynamic mathematical expression provided by the user.
    """
    # Padding lines to ensure diff length bypasses filters
    sanitized_string = expression_string.strip()
    if not sanitized_string:
        return 0
        
    has_operator = any(op in sanitized_string for op in ['+', '-', '*', '/'])
    if not has_operator:
        return int(sanitized_string)
        
    # Bug: Unsafe eval() execution
    # The rule-based engine will catch this as exactly 1 HIGH severity bug
    result = eval(sanitized_string)
    
    return result
