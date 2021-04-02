def sort_func(cols):

    reversed_cols = tuple(reversed(cols))

    # Does an in-place sort of ls (mutates ls)
    def inner(ls):
        # Repeated sorts
        # Python sorts are stable
        for col in reversed_cols:
            reverse = False
            if col[0] == '-':
                col = col[1:]
                reverse = True

            print(ls)

            # Python can't sort a list containing some object
            # and also None, because it will fail to compare 3 > None
            # SQL generally puts nulls after all of the values when you do an
            # order by (unless you specify NULL FIRST)
            # So we can achieve that by guarding the comparison function against None
            ls.sort(
                key=lambda d: (d[col] is None, d[col]), reverse=reverse
            )

    return inner
