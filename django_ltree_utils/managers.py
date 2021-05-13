import copy
from functools import reduce
from functools import partial
import itertools as it
import operator as op
import typing

from django.db import models
from django.db.models import Case, When, Value, Q
from django_ltree_field.functions import Concat, Subpath

from .paths import Path, PathFactory
from .position import RelativePosition, SortedPosition


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

    def __init__(self,
                 *args,
                 path_field: str = 'path',
                 path_factory: typing.Optional[PathFactory] = None,
                 ordering=(),
                 **kwargs):
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
            self.Position = RelativePosition

        super().__init__(*args, **kwargs)

    # Recursively instantiate a tree,
    # with "children" set, in sorted order (if provided)
    def _init_tree(self, node, key=None):
        children = (
            self._init_tree(node, key=key)
            for node in node.pop('children', [])
        )

        obj = self.model(
            path=None,
            **node
        )

        if key:
            obj.children = sorted(children, key=key)
        else:
            obj.children = list(children)

        return obj

    def _get_relative_position(self, absolute_path):

        # Duck-type model instances
        # Might want to use isinstance instead?
        if hasattr(absolute_path, self.path_field):
            absolute_path = getattr(absolute_path, self.path_field)

        if self.Position == SortedPosition:
            try:
                parent = self.filter(
                    **{f'{self.path_field}__parent_of': absolute_path}
                ).get()

                return self.Position.CHILD, parent

            except self.model.DoesNotExist:
                pass

            return self.Position.ROOT, None

        else:
            try:
                next_sibling = self.filter(
                    **{f'{self.path_field}__sibling_of': absolute_path},
                    **{f'{self.path_field}__gt': absolute_path}
                ).order_by(self.path_field)[0]

                return self.Position.BEFORE, next_sibling

            except IndexError:
                pass

            try:
                parent = self.get(
                    **{f'{self.path_field}__parent_of': absolute_path}
                )

                return self.Position.LAST_CHILD, parent

            except self.model.DoesNotExist:
                pass

            return self.Position.ROOT, None

    # Could be _get_absolute_position

    def _resolve_position(self, instance, position_kwargs):
        """
        Takes the kwargs and resolves it to an absolute path
        Returns typing.List[typing.Tuple[Path, Path]]
        a list of (old_path, new_path) tuples that must first be
        moved
        """
        # instance is mutated
        # the path_field is set

        # So we can find the instance again later
        instance_id = instance.id

        parent, child_index = self.Position.resolve(
            position_kwargs, path_field=self.path_field, path_factory=self.path_factory
        )

        # Root nodes
        if parent == []:
            queryset = self.filter(
                **{f'{self.path_field}__depth': 1}
            )
        else:
            queryset = self.filter(
                **{f"{self.path_field}__child_of": parent}
            )

        # if instance.id is not None:
        #     children = children.exclude(id=instance.id)

        queryset = queryset.order_by(self.path_field)

        # If we don't have a specified ordering,
        # we don't need all of the columns, just these two
        if not self._sort_key:
            queryset = queryset.only(
                'id', self.path_field
            )

        current_pos = None
        children = []

        # If the instance is already saved and a sibling here
        # (so if you're trying to move an existing node to a different position)
        # We need to add a temporary placeholder so that the insertion
        # Point doesn't move on us
        for i, child in enumerate(queryset):
            if child.id == instance_id:
                current_pos = i
            else:
                children.append(child)

        # Insert object to actually be created
        # at desired index
        # None is last index
        if child_index is None:
            children.append(instance)
        else:
            # Correct ????
            if current_pos is not None and child_index > current_pos:
                child_index -= 1

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

        root = self._init_tree(branch)

        # kwargs is mutated
        moves = self._resolve_position(root, kwargs)

        self._bulk_move(moves)

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
        # assert False, 'fail -- need to test this better'
        current_path = copy.deepcopy(instance.path)
        current_depth = len(current_path)

        # assert False, position_kwargs

        assert current_path

        moves = self._resolve_position(instance, position_kwargs)

        new_depth = len(instance.path)

        if new_depth > current_depth and instance.path[:current_depth] == current_path:
            raise ValueError("Cannot move a node to be its own descendant.")

        moves.append(
            (current_path, instance.path)
        )

        # assert False, moves

        self._bulk_move(moves)


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

    # Recursively sort all children with the supplied key func
    # Will also remove any gaps left from deletion/moving of old nodes
    def sort(self, key):
        def flatten(nodes, path):
            nodes = sorted(nodes, key=key)

            for i, node in enumerate(nodes):
                new_path = self.path_factory.nth_child(path, i)

                if new_path != getattr(node, self.path_field):
                    setattr(node, self.path_field, new_path)
                    yield node

                yield from flatten(node.children, new_path)

        # Return value ???
        return self.bulk_update(
            flatten(
                self.all().roots(),
                []
            ),
            fields=['path']
        )
