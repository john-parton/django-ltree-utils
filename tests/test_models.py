#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
test_django-ltree-utils
------------

Tests for `django-ltree-utils` models module.
"""

from django.test import TestCase

from django_ltree_utils.test_utils.test_app.models import Category
from django_ltree_utils.utils import print_tree


class TestCategoryModel(TestCase):

    def setUp(self):

        Category.objects.bulk_create({
            'name': 'One',
            'children': [{
                'name': 'Graft Here',
                'children': [{
                    'name': 'One'
                }]
            }, {
                'name': 'Two'
            }]
        }, root=True)

        Category.objects.bulk_create({
            'name': 'Grafted',
            'children': [{
                'name': 'One',
                'children': [{
                    'name': 'One'
                }]
            }, {
                'name': 'Two'
            }]
        }, child_of=Category.objects.get(name='Graft Here'))

        foo = Category.objects.create(root=True, name='Foo')

        bar = Category.objects.create(child_of=foo, name='Bar')
        qux = Category.objects.create(right_of=bar, name='Qux')
        Category.objects.create(child_of=qux, name='Quxy')
        Category.objects.create(right_of=qux, name='Qux-2')
        qur = Category.objects.create(left_of=qux, name='Qur')

        print_tree(
            Category.objects.all().roots()
        )
        assert False, 'fail'

        pass

    def test_something(self):
        pass

    def tearDown(self):
        pass
