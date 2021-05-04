from functools import partial
import itertools as it
import operator as op

from django.contrib.postgres.indexes import GistIndex
from django.db import models
from django.utils.functional import cached_property
from django_ltree_field.fields import LTreeField

from .managers import TreeManager


# Make this a method on querysets
def tree_iterator(queryset, path_field='path'):

    iterator = iter(queryset)

    path_getter = op.attrgetter(path_field)

    while True:
        try:
            root = next(iterator)
        except StopIteration:
            break

        root._tree_iterator = partial(tree_iterator, path_field=path_field)

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


class AbstractNode(models.Model):
    path = LTreeField(db_index=True, null=False)

    objects = TreeManager()

    def move(self, **kwargs):
        return self.objects.move(self, **kwargs)

    # def add_child(self, **kwargs):
    #     return self.objects.create(
    #         child_of=self, **kwargs
    #     )

    # This might be better served as a descriptor
    @cached_property
    def children(self):
        if not hasattr(self, 'descendants'):
            raise TypeError("Node was not annotated with descendants.")

        return self._tree_iterator(self.descendants)

        # return list(
        #     tree_iterator(
        #         self.descendants
        #     )
        # )

    def __str__(self):
        return '.'.join(self.path)

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
