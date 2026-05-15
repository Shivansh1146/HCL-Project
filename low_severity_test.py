import sys,os

# LOW: PascalCase function name and missing docstring
def TrivialFunction(x,y):
    # LOW: Multiple statements on one line
    a=x+1;b=y+1
    
    # LOW: No space after comma
    c = [a,b]
    
    # LOW: PEP8 naming
    Variable_With_Mixed_Style = "sloppy"
    
    # LOW: Trivial comment
    # this is a comment with no capital letter or period
    
    return c

# LOW: Missing docstring and PEP8 violation
def my_bad_style_func():
    pass

# PADDING
def pad():
    print("padding line 1")
    print("padding line 2")
    print("padding line 3")
    print("padding line 4")
    print("padding line 5")
    print("padding line 6")
    print("padding line 7")
    print("padding line 8")
    print("padding line 9")
    print("padding line 10")
    print("padding line 11")
    print("padding line 12")
