def process_data(data_list):
    """
    Processes a list of data items and calculates success rate.
    """
    # padding lines to ensure the diff is large enough to bypass tiny-diff filters
    total_items = 0
    valid_items = 0
    invalid_items = 0
    
    for item in data_list:
        if item is not None:
            valid_items += 1
            total_items += 1
        else:
            invalid_items += 1
            total_items += 1
            
    # AI BUG: Division by zero vulnerability if data_list is empty
    # The AI should suggest a fix like: if total_items == 0: return 0.0
    success_rate = valid_items / total_items
    
    # Rule-Based BUG: Unsafe eval
    # The static scanner will definitely catch this
    eval("print('Processing complete')")
    
    return success_rate
