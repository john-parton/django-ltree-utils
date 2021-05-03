#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
test_django-ltree-utils
------------

Tests for `django-ltree-utils` models module.
"""

from django.test import TestCase

# from django_ltree_utils.test_utils.test_app.models import Category, SortedNode
# from django_ltree_utils.utils import print_tree


class TestCategoryModel(TestCase):

    def setUp(self):
        pass

        # Category.objects.bulk_create({
        #     'name': 'One',
        #     'children': [{
        #         'name': 'Graft Here',
        #         'children': [{
        #             'name': 'One'
        #         }]
        #     }, {
        #         'name': 'Two'
        #     }]
        # }, root=True)
        #
        # Category.objects.bulk_create({
        #     'name': 'Grafted',
        #     'children': [{
        #         'name': 'One',
        #         'children': [{
        #             'name': 'One'
        #         }]
        #     }, {
        #         'name': 'Two'
        #     }]
        # }, child_of=Category.objects.get(name='Graft Here'))
        #
        #
        # foo = Category.objects.create(root=True, name='Foo')
        #
        # bar = Category.objects.create(child_of=foo, name='Bar')
        # qux = Category.objects.create(after=bar, name='Qux')
        # Category.objects.create(child_of=qux, name='Quxy')
        # Category.objects.create(after=qux, name='Qux-2')
        # qur = Category.objects.create(before=qux, name='Qur')
        #
        # roots = Category.objects.all().roots()
        #
        # print("TEST #1")
        # print_tree(roots)
        #
        #
        # Category.objects.sort(key=lambda node: node.name)
        #
        # roots = Category.objects.all().roots()
        #
        # print("TEST #2")
        # print_tree(roots)
        # print("Subtree of 'Foo'")
        # print_tree(
        #     Category.objects.filter(
        #         path__descendant_of=Subquery(
        #             Category.objects.filter(
        #                 path__depth=1,
        #                 name="Foo"
        #             ).order_by().values('path')[:1]
        #         )
        #     ).roots()
        # )
        #
        # print("Subtree of 'One > Graft Here'")
        # print_tree(
        #     Category.objects.filter(
        #         Q(
        #             path__descendant_of=Subquery(
        #                 Category.objects.filter(
        #                     name="One",
        #                     path__depth=1
        #                 ).order_by().values('path')[:1]
        #             )
        #         ) &
        #         Q(
        #             path__descendant_of=Subquery(
        #                 Category.objects.filter(
        #                     name="Graft Here",
        #                     path__depth=2
        #                 ).order_by().values('path')[:1]
        #             )
        #         )
        #     ).roots()
        # )
        #
        # print("TEST #2")
        # print_tree(roots)
        pass

    def tearDown(self):
        pass
