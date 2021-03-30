def print_tree(roots, indent=0):
    for root in roots:
        if indent > 0:
            prefix = (" " * indent) + "^-"
        else:
            prefix = ""

        print(prefix, root)
        print_tree(root.children, indent=indent + 2)
