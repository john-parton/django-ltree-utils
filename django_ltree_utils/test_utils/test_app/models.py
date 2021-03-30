from django.db import models

from django_ltree_utils.models import AbstractNode


class Category(AbstractNode):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name
