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
        # self.ordering = ordering

        if ordering:
            if callable(ordering):
                self._sort_key = ordering
            elif isinstance(ordering, str):
                self._sort_key = op.attrgetter(ordering)
            else:
                self._sort_key = op.attrgetter(*ordering)
            self.Position = SortedPosition
        else:
            self._sort_key = None
            self.Position= RelativePosition

        super().__init__(*args, **kwargs)

    def _resolve_position(self, instance, position_kwargs):
        """
        Takes the kwargs and resolves it to an absolute path
        Returns a tuple
        typing.Tuple[Path, typing.List[typing.Tuple[Path, Path]]
        first element is the parent path we're going to act on
        second element is a list of (old_path, new_path) tuples that must first be
        moved
        """
        # instance is mutated
        # the path_field is set

        # So we can find the instance again later
        instance_id = instance.id

        parent, child_index = self.Position.resolve(
            position_kwargs, path_field=self.path_field, path_factory=self.path_factory
        )

        children = self.filter(
            **{f"{self.path_field}__child_of": parent}
        ).order_by(self.path_field)

        # If we don't have a specified ordering,
        # we don't need all of the columns, just these two
        if not self._sort_key:
            children = children.only(
                'id', self.path_field
            )

        # Pull entire queryset into memory so we can manually sort/inspect
        children = list(children)

        # Insert object to actually be created
        # at desired index
        # None is last index
        if child_index is None:
            children.append(instance)
        else:
            children.insert(child_index, instance)

        # Sort again if ordering is desired
        if self._sort_key:
            children.sort(key=self._sort_key)
            # self._sort_func(children)

        # Move tuples
        # (old_path, new_path)
        moves = []

        for i, child in enumerate(children):
            correct_path = self.path_factory.nth_child(parent, i)

            if child.id == instance_id:
                # Mutate passed instance
                setattr(child, self.path_field, correct_path)
                continue

            current_path = getattr(child, self.path_field)

            # Need to move this one
            if current_path != correct_path:
                moves.append(
                    (current_path, correct_path)
                )

        # Return any children which must be moved
        return moves

    def bulk_create(self, branch, **kwargs):
        # Just does one branch
        # I was going to have a bulkier api where you could create multiple branches at the same
        # time, but it tended to make things more complicated because the entire tree mutates every
        # time you graft a branch

        # Recursively instantiate the tree, with "children" set, optionally in sorted order
        def init_tree(node):
            children = map(init_tree, node.pop('children', []))

            obj = self.model(**node)

            if self._sort_key:
                obj.children = sorted(children, key=self._sort_key)
            else:
                obj.children = list(children)

            return obj

        root = init_tree(branch)

        # kwargs is mutated
        moves = self._resolve_position(root, kwargs)

        # Recursively update the path attribute of all descendants and yield out flattened
        # nodes
        def flatten(node):
            yield node
            for i, child in enumerate(node.children):
                child.path = self.path_factory.nth_child(node.path, i)
                yield from flatten(child)

        super().bulk_create(
            flatten(root), **kwargs
        )

        return root

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

    def move(self, instance, **position_kwargs):
        assert False, 'fail -- need to test this better'
        current_path = instance.path

        assert current_path

        moves = self._resolve_position(obj, position_kwargs)

        self._bulk_move(moves)

        # Get the current node's position.
        # It might have changed because it could have been a child of
        # moves
        current_path = self.filter(id=instance.id).values_list('path', flat=True)[0]




        self._bulk_move([
            (current_path, instance.path)
        ])

    def create(self, **kwargs):

        position_kwargs = {}

        for position in self.Position:
            try:
                position_kwargs[position.value] = kwargs.pop(position.value)
            except KeyError:
                continue

        obj = self.model(
            path=None,
            **kwargs
        )

        self._for_write = True

        moves = self._resolve_position(obj, position_kwargs)

        self._bulk_move(moves)

        obj.save(force_insert=True, using=self.db)

        return obj

    def sort(self, key):
        roots = self.all().roots()

        def step(node):
            node.children.sort(key=key)

            for i, child in enumerate(node.children):
                new_path = self.path_factory.nth_child(path, i)

                if new_path != getattr(child, self.path_field):
                    setattr(child, self.path_field, new_path)
                    yield child

                yield from step(child, new_path)
