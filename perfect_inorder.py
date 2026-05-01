class Node:
    def __init__(self, key):
        self.left = None
        self.right = None
        self.val = key

def print_inorder(root):
    """
    Performs an inorder traversal of a binary tree.
    """
    if root:
        # First recur on left child
        print_inorder(root.left)
        
        # Then print the data of node
        print(root.val, end=" "),
        
        # Now recur on right child
        print_inorder(root.right)

def main():
    # Construct a simple tree
    root = Node(1)
    root.left = Node(2)
    root.right = Node(3)
    root.left.left = Node(4)
    root.left.right = Node(5)

    print("Inorder traversal of binary tree is:")
    print_inorder(root)
    print() # New line

if __name__ == "__main__":
    main()
