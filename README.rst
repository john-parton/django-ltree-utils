=============================
django-ltree-utils
=============================

.. image:: https://badge.fury.io/py/django-ltree-utils.svg
    :target: https://badge.fury.io/py/django-ltree-utils

.. image:: https://travis-ci.org/john-parton/django-ltree-utils.svg?branch=master
    :target: https://travis-ci.org/john-parton/django-ltree-utils

.. image:: https://codecov.io/gh/john-parton/django-ltree-utils/branch/master/graph/badge.svg
    :target: https://codecov.io/gh/john-parton/django-ltree-utils

Your project description goes here

Documentation
-------------

The full documentation is at https://django-ltree-utils.readthedocs.io.

Quickstart
----------

Install django-ltree-utils::

    pip install django-ltree-utils

Add it to your `INSTALLED_APPS`:

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

Features
--------

* TODO

Running Tests
-------------

You need to have a reasonably updated version of PostgreSQL listening on port 5444. You can use
`docker-compose <https://docs.docker.com/compose/>` to start a server

::

    docker-compose up

Does the code actually work?

::

    source <YOURVIRTUALENV>/bin/activate
    (myenv) $ pip install -r requirements.txt -r requirements_test.txt --upgrade
    (myenv) $ ./runtests.py


Development commands
---------------------

::

    pip install -r requirements_dev.txt
    invoke -l


Credits
-------

Tools used in rendering this package:

*  Cookiecutter_
*  `cookiecutter-djangopackage`_

.. _Cookiecutter: https://github.com/audreyr/cookiecutter
.. _`cookiecutter-djangopackage`: https://github.com/pydanny/cookiecutter-djangopackage
