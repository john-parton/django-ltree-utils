from django.contrib import admin

from django_ltree_utils.forms import move_node_form_factory

from .models import Category


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    form = move_node_form_factory(Category.objects)

    list_display = ['_str_with_depth', 'path']

    def _str_with_depth(self, instance):

        depth_indicator = '\u00A0' * 6 * (len(instance.path) - 1)

        if len(instance.path) > 1:
            depth_indicator += '\u21b3'

        return f'{depth_indicator} {instance}'
