import collections
import enum
from functools import reduce
import itertools as it
import operator as op
import string
import typing

from django.contrib.postgres.indexes import GistIndex
from django.db import models
from django.db.models import Case, When, Value, Q
from django.utils.functional import cached_property
from django_ltree_field.fields import LTreeField
from django_ltree_field.functions import Concat, Subpath

from .paths import Path, PathFactory



# Make this a method on querysets
def tree_iterator(queryset, path_field='path'):

    iterator = iter(queryset)

    path_getter = op.attrgetter(path_field)

    while True:
        try:
            root = next(iterator)
        except StopIteration:
            break

        # TODO make attribute configurable here
        path = path_getter(root)

        # Set properties so that the rest of the API can work
        root.depth = len(path)
        root.descendants = []

        # We should probably assert that the prefixes match up to this point
        for node in iterator:

            path = path_getter(node)

            node.depth = len(path)

            # Does not set descendants
            # That will get set by root.children property

            if node.depth > root.depth:
                root.descendants.append(node)
            else:
                # Shift the element back on to the front
                iterator = it.chain([node], iterator)
                break

        yield root



# Create your models here.

# # Can write a trigger to delete children
# r"""
# CREATE OR REPLACE FUNCTION delete_descendants() RETURNS trigger AS
# $$BEGIN
#    DELETE FROM "SOME_TABLE"
#    WHERE
#        path <@ OLD.path;
# END;$$ LANGUAGE plpgsql;
#
# CREATE TRIGGER delete_descendants
#    AFTER DELETE ON  FOR EACH ROW
#    EXECUTE PROCEDURE add_money();
# """

class NodePosition(enum.Enum):
    CHILD = 'child_of'
    FIRST_CHILD = 'first_child_of'
    # Same functionality as child_of
    LAST_CHILD = 'last_child_of'
    # These could be "before" and "after"
    LEFT = 'left_of'
    RIGHT = 'right_of'

    # Rightmost root element
    ROOT = 'root'

    # Consider just making its own functions
    # Or put back on manager or something

    @classmethod
    def _valid_kwargs(cls) -> str:
        return ', '.join(repr(position.value) for position in cls)

    @classmethod
    def _parse_kwargs(cls, kwargs, path_field, path_factory) -> typing.Tuple[Path, typing.Optional[int]]:
        positions: typing.Dict['NodePosition', typing.Any] = {}

        for position in NodePosition:
            try:
                positions[position] = kwargs.pop(position.value)
            except KeyError:
                continue

        if len(positions) != 1:
            raise TypeError(f"Pass exactly one of the following kwargs to TreeManager.create: {cls._valid_kwargs()}")

        position, relative_to = positions.popitem()

        if position == cls.ROOT:
            if relative_to is not True:
                raise ValueError(f"Expected kwarg root=True, got root={relative_to!r}")
            return [], None

        # Duck-type model instances
        # Might want to use isinstance instead?
        if hasattr(relative_to, path_field):
            relative_to = getattr(relative_to, path_field)

        # TODO Better error handling here?
        # Convert strings to lists?
        if not isinstance(relative_to, list):
            relative_to = relative_to.split('.')

        # last_child_of is a more verbose alias for child_of
        if position in {cls.CHILD, cls.LAST_CHILD}:
            return relative_to, None
        elif position == cls.FIRST_CHILD:
            return relative_to, 0
        elif position in {cls.LEFT, cls.RIGHT}:
            parent, child_index = path_factory.split(relative_to)

            if position == cls.RIGHT:
                child_index += 1

            return parent, child_index
        else:
            # Should never get here
            raise Exception


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

    def __init__(self, *args, path_field: str = 'path', path_factory: typing.Optional[PathFactory] = None, **kwargs):
        # Default label_length of 4 allows each node to have 14,776,336 children
        # You can (but shouldn't) change this after adding rows to the database, but you must
        # run a migration to zero-pad or truncate labels as appropriate
        # Exercise is left to the reader
        self.path_factory = PathFactory() if path_factory is None else path_factory
        self.path_field = path_field
        super().__init__(*args, **kwargs)

    # Private API, don't call this directly, call .create(child_of=parent)
    # args have underscore to avoid colliding with model fields
    def _create_child(self, parent: Path, child_index: typing.Optional[int], attributes):
        insertion_path = self._get_insertion_path(parent, child_index)

        return super().create(
            **{self.path_field: insertion_path},
            **attributes
        )

    def _get_insertion_path(self, parent: Path, child_index: typing.Optional[int]) -> Path:
        """
        Modifies the tree so that we can insert a node as the nth child of parent.
        Returns the resolved Path.
        """
        # Insert at the end, figure out what the actual index needs to be
        if child_index is None:
            try:
                last_child = self.filter(
                    **{f"{self.path_field}__child_of": parent}
                ).order_by(
                    f"-{self.path_field}"
                ).values_list(
                    # We could get the last part of the path by slicing with a negative index
                    self.path_field, flat=True
                )[0]

                insertion_path = next(
                    self.path_factory.next_siblings(last_child)
                )

            except IndexError:
                insertion_path = self.path_factory.nth_child(parent, 0)
        else:
            insertion_path = self.path_factory.nth_child(parent, child_index)

            # Potentially need to move nodes if index was specified
            # Move nodes to make room for new node
            self._move_right(
                insertion_path
            )

        return insertion_path

    def _move_right(self, gap_path: Path):
        """Move every node to the right (inclusive) of ltree right one
        position.

        Does 2 queries where N is the number of nodes to the right of path
        """

        to_move: typing.Iterable[Path] = self.filter(
            **{
                f"{self.path_field}__sibling_of": gap_path,
                # Any nodes to the right of or exactly at index
                f"{self.path_field}__gte": gap_path
            }
        ).order_by(
            # Should already be there
            f"{self.path_field}"
        ).values_list(
            self.path_field, flat=True
        )

        to_move = list(to_move)

        if not to_move:
            return 0


        return self._bulk_move(
            zip(to_move, self.path_factory.next_siblings(gap_path))
        )

    def bulk_create(self, branch, **kwargs):
        # Just does one branch
        # I was going to have a bulkier api where you could create multiple branches at the same
        # time, but it tended to make things more complicated because the entire tree mutates every
        # time you graft a branch

        # kwargs is mutated
        parent, index = NodePosition._parse_kwargs(
            kwargs, path_field=self.path_field, path_factory=self.path_factory
        )

        insertion_path = self._get_insertion_path(parent, index)

        # Recursively walk through branch structure and generate instances with calculated paths
        def walk(node, path):
            children = node.pop('children', [])
            node[self.path_field] = path
            yield self.model(**node)

            for child, path in zip(children, self.path_factory.children(path)):
                yield from walk(child, path)

        return super().bulk_create(walk(branch, insertion_path), **kwargs)


    def _bulk_move(self, path_tuples: typing.Iterable[typing.Tuple[Path, Path]]) -> int:
        # We should probably check that all of the old/new paths
        # Are the same depth
        # If you pass multiple path tuples and it happens that one is a subpath
        # of another, very bad things will happen


        q: typing.List[Q] = []
        cases: typing.List[When] = []

        # This would almost certainly be simplified by a VALUES() join
        for old_path, new_path in path_tuples:
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

        return self.filter(
            reduce(op.or_, q)
        ).update(**{
            self.path_field: Case(*cases)
        })

    def create(self, *args, **kwargs):
        # kwargs is mutated
        parent, index = NodePosition._parse_kwargs(
            kwargs, path_field=self.path_field, path_factory=self.path_factory
        )

        return self._create_child(parent, index, kwargs)


class AbstractNode(models.Model):
    path = LTreeField(db_index=True, null=False)

    objects = TreeManager()

    def move(self, **kwargs):

        position, relative_to, kwargs = NodePosition._parse_kwargs(kwargs)

        if kwargs:
            # TODO Better error
            raise TypeError("Got invalid kwargs to Node.move()")

        self.objects._move()

    @cached_property
    def children(self):
        if not hasattr(self, 'descendants'):
            raise TypeError("Node was not annotated with descendants.")

        return list(
            tree_iterator(
                self.descendants
            )
        )

    def __str__(self):
        return self.path


    # def move(self, **kwargs):
    #
    #
    # def delete(self):
    #     # TODO Delete children
    #     # Better as a trigger
    #     pass

    class Meta:
        abstract = True
        ordering = ['path']
        constraints = [
            # We want this deferred, because sometimes we move more than one node at once
            # and there might be an intermediate step where nodes conflict
            models.UniqueConstraint(
                name='%(app_label)s_%(class)s_unique_path_deferred',
                fields=['path'],
                deferrable=models.Deferrable.DEFERRED,
            )
        ]
        indexes = [
            # This would probably be better served as
            # the default if Ltree(index=True) is specified
            GistIndex(
                fields=['path']
            ),
        ]
