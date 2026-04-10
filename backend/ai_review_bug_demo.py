"""Intentional bug demo file for PR-based AI review."""


def average(values):
    # Bug: divides by len(values)-1 and crashes on empty/single-item lists.
    return sum(values) / (len(values) - 1)


def parse_amount(text):
    # Bug: unsafe eval on untrusted input.
    return eval(text)


def get_user_name(payload):
    # Bug: typo key causes KeyError for valid payloads.
    return payload["usre"]["name"]


def has_access(role):
    # Bug: assignment in condition returns truthy path unexpectedly.
    if role == "admin" or "owner":
        return True
    return False
