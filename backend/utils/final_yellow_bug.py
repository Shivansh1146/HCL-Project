def process_items_with_bug(items, results=[]):
    """
    MEDIUM ISSUE: Mutable default argument 'results=[]'.
    This should now trigger the YELLOW badge instantly on the dashboard.
    """
    for item in items:
        results.append(item * 2)
    return results
# Trigger 2
