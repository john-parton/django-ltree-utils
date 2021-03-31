def print_tree(roots, indent=0, verbose=True):
    for root in roots:
        if indent > 0:
            prefix = (" " * indent) + "^-"
        else:
            prefix = ""

        print(prefix, root, end="")
        if verbose:
            print(f" ({'.'.join(root.path)})", end="")
        print()

        print_tree(root.children, indent=indent + 2, verbose=verbose)
