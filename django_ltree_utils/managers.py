import collections
import enum
from functools import reduce
from functools import partial
import itertools as it
import operator as op
import string
import typing
import warnings

from django.contrib.postgres.indexes import GistIndex
from django.db import models
from django.db.models import Case, When, Value, Q
from django.utils.functional import cached_property
from django_ltree_field.fields import LTreeField
from django_ltree_field.functions import Concat, Subpath

from .paths import Path, PathFactory
from .position import RelativePosition, SortedPosition
from .sorting import sort_func



def tree_iterator(queryset, path_field='path'):
    # This will very much break if the tree is not in a good state

    iterator = iter(queryset)

    if isinstance(path_field, str):
        path_getter = op.attrgetter(path_field)
    # Avoid calling attrgetter repeatedly
    # Could check if it's calalble
    else:
        path_getter = path_field

    while True:
        try:
            root = next(iterator)
        except StopIteration:
            break

        # Need the path field bound?
        root._tree_iterator = partial(tree_iterator, path_field=path_getter)

        # TODO make attribute configurable here
        parent_path = path_getter(root)

        # Set properties so that the rest of the API can work
        root.depth = len(parent_path)
        root.descendants = []

        # We should probably assert that the prefixes match up to this point
        for node in iterator:

            path = path_getter(node)

            node.depth = len(path)

            # Does not set descendants
            # That will get set by root.children property

            if node.depth > root.depth:
                root.descendants.append(node)

                # Issue warning
                # if path[:len(parent_path)] != parent_path:
                #     pass

            else:
                # Shift the element back on to the front
                iterator = it.chain([node], iterator)
                break

        yield root


class TreeQuerySet(models.QuerySet):
    def __init__(self, *args, path_field: str = 'path', **kwargs):
        super().__init__(*args, **kwargs)
        self.path_field = path_field

    def roots(self):
        return tree_iterator(
            self, path_field=self.path_field
        )


class TreeManager(models.Manager):
    _queryset_class = TreeQuerySet

    def __init__(self, *args, path_field: str = 'path', path_factory: typing.Optional[PathFactory] = None, ordering = (), **kwargs):
        # Default label_length of 4 allows each node to have 14,776,336 children
        # You can (but shouldn't) change this after adding rows to the database, but you must
        # run a migration to zero-pad or truncate labels as appropriate
        # Exercise is left to the reader
        self.path_factory = PathFactory() if path_factory is None else path_factory
        self.path_field = path_field
        self.ordering = ordering

        # To convert an object to a dictionary for sorting
        self._ordering_columns = [
            col[1:] if col[0] == '-' else col for col in ordering
        ]

        if ordering:
            self._sort_func = sort_func(ordering)
            self.Position = SortedPosition
        else:
            self._sort_func = None
            self.Position= RelativePosition

        super().__init__(*args, **kwargs)

    def _resolve_position(self, kwargs, reference=None):
        """
        Takes the kwargs and resolves it to an absolute path
        Returns a tuple
        typing.Tuple[Path, typing.List[typing.Tuple[Path, Path]]
        first element is the parent path we're going to act on
        second element is a list of (old_path, new_path) tuples that must first be
        moved
        """

        parent, child_index = self.Position.resolve(
            kwargs, path_field=self.path_field, path_factory=self.path_factory
        )

        children = list(
            self.filter(
                **{f"{self.path_field}__child_of": parent}
            ).values(
                self.path_field, *self.ordering
            ).order_by(self.path_field)  # Explicit ordering
        )

        if reference is None:
            reference = kwargs

        if self.path_field in reference:
            raise ValueError(f"Do not manually specify {self.path_field!r} when creating {self.model} instances")

        # Insert object to actually be created
        if child_index is None:
            children.append(reference)
        else:
            children.insert(child_index, reference)

        # Sort again if ordering is desired
        if self._sort_func:
            self._sort_func(children)

        moves = []
        final_path = None

        for i, child in enumerate(children):
            current_path = child.get(self.path_field, None)

            if self.path_field in child:
                # Already has a path, let's check to see if needs to move
                # We could/should assert that the parent is the same?
                current_index = self.path_factory.split(current_path)[1]

                # Node isn't in the right position, schedule it for bulk moving
                if current_index != i:
                    moves.append(
                        (
                            current_path, self.path_factory.nth_child(parent, i)
                        )
                    )
            else:
                # This is the position we want to insert at, save the index for later
                assert final_path is None
                final_path = self.path_factory.nth_child(parent, i)
        # Returns the final freed ABSOLUTE path, and a list of tuples of nodes
        # which must moves to make that happen each tuple (src, dest)
        return final_path, moves

    def bulk_create(self, branch, **kwargs):
        # Just does one branch
        # I was going to have a bulkier api where you could create multiple branches at the same
        # time, but it tended to make things more complicated because the entire tree mutates every
        # time you graft a branch

        # kwargs is mutated
        path, moves = self._resolve_position(kwargs, reference=branch)

        if kwargs:
            raise ValueError(f"Got un-handled kwargs: {kwargs}")

        # Issue the actual move command
        self._bulk_move(moves)

        # Recursively walk through branch structure and generate instances with calculated paths
        def walk(node, path):
            children = node.pop('children', [])

            # Sort the children if we have ordering!
            if self._sort_func:
                self._sort_func(children)

            node[self.path_field] = path
            yield self.model(**node)

            for child, path in zip(children, self.path_factory.children(path)):
                yield from walk(child, path)

        return super().bulk_create(walk(branch, path), **kwargs)

    def _bulk_move(self, path_tuples: typing.Iterable[typing.Tuple[Path, Path]]) -> int:
        # We should probably check that all of the old/new paths
        # Are the same depth
        # If you pass multiple path tuples and it happens that one is a subpath
        # of another, very bad things will happen

        q: typing.List[Q] = []
        cases: typing.List[When] = []

        # This would almost certainly be simplified by a VALUES() join
        for old_path, new_path in path_tuples:
            # Sometimes happens if there are holes left in a tree
            if old_path == new_path:
                continue

            # Match ltree normal formatting instead of arrays
            new_path = '.'.join(new_path)

            q.append(
                Q(**{f'{self.path_field}__descendant_of': old_path})
            )
            cases.extend([
                # Order matters
                When(**{self.path_field: old_path}, then=Value(new_path)),
                When(
                    **{f'{self.path_field}__descendant_of': old_path},
                    then=Concat(
                        Value(new_path),
                        Subpath(
                            self.path_field,
                            # Avoid an nlevel function call here?
                            # NLevel(Value(old_path))
                            Value(len(old_path))
                        )
                    )
                )
            ])

        if q or cases:
            return self.filter(
                reduce(op.or_, q)
            ).update(**{
                self.path_field: Case(*cases)
            })
        else:
            return 0

    def move(self, instance, **kwargs):
        assert False, 'fail -- needs re-implentation due to ordering property'
        path, occupied = self._resolve_position(kwargs)

        if kwargs:
            raise ValueError(f"Got unexpected kwargs to move(): {kwargs!r}")

        if occupied:
            self._move_right(path)

        # TODO Refresh model instance or at least clear caches on it?

        self._bulk_move([
            (instance.path, path),
        ])

    def create(self, **kwargs):
        # kwargs is mutated
        path, moves = self._resolve_position(kwargs)

        self._bulk_move(moves)

        return super().create(
            path=path,
            **kwargs
        )
