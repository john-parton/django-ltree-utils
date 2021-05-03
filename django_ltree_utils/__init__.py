default_app_config = 'django_ltree_utils.apps.DjangoLTreeUtilsConfig'

try:
    from .version import version as __version__
# Should this raise?
except ImportError:
    pass
