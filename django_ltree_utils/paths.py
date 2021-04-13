import collections
import itertools as it
import string
import typing

# Type alias
Path = typing.List[str]

# Map strings of FIXED LENGTH N to an integer M such that ordering by
# M preserves lexicographical order
# If alphabet is [0-9A-Za-z] mapping to [0..62] you can treat the entire
# string as a zero-padded base-62 number

# Map strings of MAXIMUM LENGTH N to an integer M such that ordering by
# M preserves lexicographical order
# this is much harder and not obvious how to approach
# Probably a divide-and-conquer method


ALPHANUMERIC_SENSITIVE = string.digits + string.ascii_uppercase + string.ascii_lowercase


class PathFactory:
    """
    Responsible for manipulating and creating "path" lists.
    Each label is treated as a fixed-length, zero-padded base62-encoded integer.
    This ensures that we can create a new path to the left or right of an existing path while maintaining
    lexicographical order.
    """

    def __init__(self, alphabet: str = ALPHANUMERIC_SENSITIVE, max_length: int = 4):
        # Alphabet is in ASCII order
        self.alphabet = alphabet
        self.reverse = {
            char: i for i, char in enumerate(alphabet)
        }
        self.base = len(self.alphabet)
        self.max_length = max_length

    # encode/decode are the heart of this class
    def encode(self, value: int) -> str:
        if value < 0:
            raise ValueError

        d: typing.Deque[str] = collections.deque()

        appendleft = d.appendleft
        alphabet = self.alphabet

        while value:
            value, rem = divmod(value, self.base)
            appendleft(alphabet[rem])

        if len(d) > self.max_length:
            raise ValueError(f"Cannot encode fixed-length base-{self.base}: {value!r}")

        return ''.join(d).zfill(self.max_length)

    def decode(self, chars: str) -> int:
        # An unnecessarily baroque implementation which fits on one line
        # return sum(
        #     map(
        #         op.product,
        #         map(
        #             b62_alphabet_index.__getitem__,
        #             chars[::-1]
        #         )
        #         itertools.accumulate(it.repeat(62), func=op.mul, initial=1)
        #     )
        # )

        total = 0
        radix = 1

        for digit in map(self.reverse.__getitem__, chars[::-1]):
            total += digit * radix
            radix *= self.base

        return total

    def split(self, path: Path) -> typing.Tuple[Path, int]:
        *parent, position = path
        return parent, self.decode(position)

    def nth_child(self, path: Path, n: int) -> Path:
        return path + [self.encode(n)]

    def children(self, path: Path) -> typing.Iterator[Path]:
        for label in map(self.encode, it.count()):
            yield path + [label]

    def next_siblings(self, path: Path) -> typing.Iterator[Path]:
        parent, child_index = self.split(path)

        # Tabulate
        start_index = child_index + 1
        labels = map(self.encode, it.count(start_index))

        for label in labels:
            yield parent + [label]
