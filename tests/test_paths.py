#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
test_django-ltree-utils
------------

Tests for `django-ltree-utils` models module.
"""
import itertools as it

from django.test import TestCase

from django_ltree_utils.paths import PathFactory


class TestPathFactory(TestCase):
    """
    PathFactory is a basic helper class to convert
    """

    def test_encoding(self):

        self.assertEqual(
            '0010',
            PathFactory().encode(62)
        )

        self.assertEqual(
            '000010',
            PathFactory(max_length=6).encode(62)
        )

    def test_decoding(self):
        self.assertEqual(
            62,
            PathFactory().decode('0010')
        )

    # def test_parent(self):
    #     self.assertEqual(
    #         PathFactory().parent(['A', 'B', 'C']),
    #         ['A', 'B']
    #     )

    def test_nth_child(self):
        self.assertEqual(
            PathFactory().nth_child(['A', 'B'], 62),
            ['A', 'B', '0010']
        )

    # def test_child_index(self):
    #     self.assertEqual(
    #         PathFactory().child_index(['A', 'B', '0010']),
    #         62
    #     )

    def test_next_siblings(self):
        self.assertEqual(
            list(
                it.islice(
                    PathFactory().next_siblings(['A', 'B', '0002']), 3
                )
            ),
            [
                ['A', 'B', '0003'],
                ['A', 'B', '0004'],
                ['A', 'B', '0005']
            ]
        )
