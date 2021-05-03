default_app_config = 'django_ltree_utils.apps.DjangoLTreeUtilsConfig'

try:
    from .version import version as __version__  # noqa
except ImportError:
    pass
