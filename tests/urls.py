# -*- coding: utf-8 -*-
from django.contrib import admin
from django.urls import path

urlpatterns = [
    path('admin/', admin.site.urls),
    # path('', include('django_ltree_utils.urls', namespace='django_ltree_utils')),
]
