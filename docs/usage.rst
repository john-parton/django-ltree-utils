=====
Usage
=====

To use django-ltree-utils in a project, add it to your `INSTALLED_APPS`:

.. code-block:: python

    INSTALLED_APPS = (
        ...
        'django_ltree_utils.apps.DjangoLtreeUtilsConfig',
        ...
    )

Add django-ltree-utils's URL patterns:

.. code-block:: python

    from django_ltree_utils import urls as django_ltree_utils_urls


    urlpatterns = [
        ...
        url(r'^', include(django_ltree_utils_urls)),
        ...
    ]
