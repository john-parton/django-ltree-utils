from django.db import models

from django_ltree_utils.managers import TreeManager
from django_ltree_utils.models import AbstractNode


class Category(AbstractNode):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class SortedNode(AbstractNode):
    name = models.CharField(max_length=100)

    objects = TreeManager(
        ordering='name'
    )

    def __str__(self):
        return self.name
