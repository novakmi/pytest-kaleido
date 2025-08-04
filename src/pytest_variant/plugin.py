"""
pytest-variant plugin: Provides parametrization and fixtures for testing multiple product variants.

This plugin allows you to specify variants (e.g., product versions, configurations) via
command-line options or ini files.
Variants can have multiple attributes and a variant name. The plugin provides fixtures and helpers to access
variants, their attributes, and to parametrize tests accordingly.

Key features:
- Parse and deduplicate variant attributes from command line or ini
- Parametrize tests for all specified variants
- Provide fixtures for variant attributes and variant-specific test logic
- Support for variant setup/discovery strings
"""

import logging
from typing import List, Optional

import pytest

log = logging.getLogger(__name__)


def pytest_addoption(parser):
    """
    Add command-line options and ini options for variant and variant-setup.
    """
    group = parser.getgroup('variant')
    group.addoption(
        '--variant',
        action='append',  # allow multiple --variant arguments
        dest='variant',
        default=None,
        help='Variant specification(s). Can be repeated.'
             ' Format: <attr1>:<attr2>:...:<variant>[,<...>].'
             ' Colons and commas can be escaped with \\.'
    )
    group.addoption(
        '--variant-setup',
        action='store',
        dest='variant_setup',
        default=None,
        help='General setup string for variant discovery (e.g. directory, '
             'server location). Same syntax as --variant, '
             'but cannot be repeated.'
    )
    parser.addini('VARIANTS',
                  'Default variants (comma-separated, '
                  'same format as --variant)')
    parser.addini('VARIANT_SETUP', 'Default variant-setup string')


def _split_escaped(s, sep):
    """
    Split a string by sep, but allow escaping sep with backslash only if it precedes sep.
    Only split on unescaped sep. Remove escape backslashes from result.
    """
    log.debug("==> _split_escaped s=%s, sep=%s", s, sep)
    parts = []
    buf = ''
    i = 0
    while i < len(s):
        if s[i] == '\\' and i + 1 < len(s) and s[i + 1] == sep:
            buf += sep
            i += 2
        elif s[i] == sep:
            parts.append(buf)
            buf = ''
            i += 1
        else:
            buf += s[i]
            i += 1
    parts.append(buf)
    log.debug("<== _split_escaped ret=%s", parts)
    return parts


def _parse_variants(variant_args: Optional[List[str]]) -> List[List[str]]:
    """
    Parse variants from multiple --variant arguments or ini/config.
    Each variant string can contain multiple attributes separated by colons,
    and multiple variants separated by commas.
    Attributes are optional. If a variant is not preceded by attributes,
    it inherits attributes from the previous variant in the same argument.
    A new --variant argument resets the attribute context.
    Returns: List of attribute lists, where last item is the variant name.
    """
    log.debug("==> _parse_variants variant_args=%s", variant_args)
    ret = []
    if not variant_args:
        log.debug("<== _parse_variants ret=%s", ret)
        return ret
    for arg in variant_args:
        prev_attrs = []
        for vstr in _split_escaped(arg, ','):
            attrs = _split_escaped(vstr, ':')
            attrs = [a for a in attrs if a]
            if len(attrs) == 1 and prev_attrs:
                attrs = prev_attrs + [attrs[0]]
            if len(attrs) > 1:
                prev_attrs = attrs[:-1]
            if attrs:
                ret.append(attrs)
    log.debug("<== _parse_variants ret=%s", ret)
    return ret


class VariantPluginBase:
    """
    Abstract base class for variant-oriented pytest plugins.
    Each instance represents a single variant, with attributes (unique, sorted) and a variant name.
    Provides helpers for parsing, deduplication, and variant/attribute access.
    """

    def __init__(self, attributes: List[str], variant: str):
        """
        Initialize a VariantPluginBase object.
        :param attributes: List of attribute strings (excluding the variant name).
        :param variant: The variant name (string).
        """
        log.debug("==> VariantPluginBase.__init__ attributes=%s, variant=%s",
                  attributes, variant)
        # Store attributes as a sorted set (unique, order not preserved)
        self.attributes = sorted(set(attributes))
        self.variant = variant  # variant name (string)
        log.debug("<== VariantPluginBase.__init__ ret=None")

    @property
    def attrs(self):
        """
        Backward-compatible property for attributes.
        """
        return self.attributes

    @staticmethod
    def parse_variants(variant_args: Optional[List[str]]) -> List[List[str]]:
        """
        Parse variant argument strings into lists of attributes + variant name.
        """
        log.debug("==> VariantPluginBase.parse_variants variant_args=%s",
                  variant_args)
        ret = _parse_variants(variant_args)
        log.debug("<== VariantPluginBase.parse_variants ret=%s", ret)
        return ret

    @classmethod
    def from_lists(cls, attr_lists: List[List[str]]):
        """
        Create a list of VariantPluginBase objects from a list of attribute lists.
        If a variant name appears more than once, merge all attributes for that variant.
        Each list must have at least one item (the variant is the last item).
        """
        log.debug("==> VariantPluginBase.from_lists attr_lists=%s", attr_lists)
        variant_map = {}
        for attrs in attr_lists:
            if not attrs:
                continue
            *attributes, variant = attrs
            if variant in variant_map:
                variant_map[variant].update(attributes)
            else:
                variant_map[variant] = set(attributes)
        ret = [cls(attributes=list(attributes), variant=variant) for variant, attributes in variant_map.items()]
        log.debug("<== VariantPluginBase.from_lists ret=%s", ret)
        return ret

    @staticmethod
    def get_attributes(variant_objs: list) -> list:
        """
        Return a sorted list of all unique attributes from all VariantPluginBase objects.
        """
        log.debug("==> VariantPluginBase.get_attributes variant_objs=%s",
                  variant_objs)
        attributes = set()
        for obj in variant_objs:
            attributes.update(obj.attributes)
        ret = sorted(attributes)
        log.debug("<== VariantPluginBase.get_attributes ret=%s", ret)
        return ret

    @staticmethod
    def get_variants(variant_objs: list, attribute=None) -> list:
        """
        Return a sorted list of variants for a given attribute (any attribute), or for None if no attributes.
        :param variant_objs: List of VariantPluginBase objects.
        :param attribute: Attribute to filter by, or None for variants with no attributes.
        :return: Sorted list of variant names.
        """
        log.debug(
            "==> VariantPluginBase.get_variants variant_objs=%s, attribute=%s",
            variant_objs, attribute)
        variants = []
        for obj in variant_objs:
            if attribute is None:
                if not obj.attributes:
                    variants.append(obj.variant)
            else:
                if attribute in obj.attributes:
                    variants.append(obj.variant)
        ret = sorted(variants)
        log.debug("<== VariantPluginBase.get_variants ret=%s", ret)
        return ret


def get_all_variant_objs(config):
    """
    Read config and parse all variant objects for the current session.
    Returns a list of VariantPluginBase objects.
    """
    log.debug("==> get_all_variant_objs config=%s", config)
    variant_args = config.getoption('variant')
    if not variant_args:
        ini_variants = config.getini('VARIANTS')
        variant_args = [ini_variants] if ini_variants else []
    attr_lists = _parse_variants(variant_args)
    ret = VariantPluginBase.from_lists(attr_lists)
    log.debug("<== get_all_variant_objs ret=%s", ret)
    return ret


def pytest_generate_tests(metafunc):
    """
    Parametrize tests with all variants if the 'variant' fixture is used.
    """
    log.debug("==> pytest_generate_tests metafunc=%s", metafunc)
    variant_objs = get_all_variant_objs(metafunc.config)
    if 'variant' in metafunc.fixturenames:
        ids = [":".join(obj.attributes + [obj.variant]) for obj in variant_objs]
        metafunc.parametrize('variant', variant_objs, ids=ids)
        log.debug("<== pytest_generate_tests ret=None (parametrized)")
    else:
        log.debug("<== pytest_generate_tests ret=None (not parametrized)")


@pytest.fixture
def variant(request):
    """
    Fixture providing the current variant object to tests.
    """
    log.debug("==> variant request=%s", request)
    ret = request.param if hasattr(request, 'param') else None
    log.debug("<== variant ret=%s", ret)
    return ret


@pytest.fixture
def variant_setup(request):
    """
    Fixture providing the variant-setup string (for setup/discovery).
    """
    log.debug("==> variant_setup request=%s", request)
    config = request.config
    setup_str = config.getoption('variant_setup') or config.getini(
        'VARIANT_SETUP')
    log.debug("<== variant_setup ret=%s", setup_str)
    return setup_str


@pytest.fixture
def variant_attributes(request):
    """
    Fixture returning all unique attributes from all variants.
    """
    log.debug("==> variant_attributes request=%s", request)
    variant_objs = get_all_variant_objs(request.config)
    ret = VariantPluginBase.get_attributes(variant_objs)
    log.debug("<== variant_attributes ret=%s", ret)
    return ret


@pytest.fixture
def variant_variants(request):
    """
    Fixture returning a function to get all variants for a given attribute.
    """
    log.debug("==> variant_variants request=%s", request)
    variant_objs = get_all_variant_objs(request.config)

    def _get(attribute=None):
        log.debug("==> variant_variants._get attribute=%s", attribute)
        ret = VariantPluginBase.get_variants(variant_objs, attribute)
        log.debug("<== variant_variants._get ret=%s", ret)
        return ret

    log.debug("<== variant_variants ret=_get")
    return _get


@pytest.fixture
def variants_with_attributes(request):
    """
    Fixture returning a function to get all variants that have any of the specified attributes.
    Usage: variants_with_attributes([attr1, attr2, ...])
    Returns a list of VariantPluginBase objects matching any attribute.
    """
    log.debug("==> variants_with_attributes request=%s", request)
    variant_objs = get_all_variant_objs(request.config)

    def _get(attributes: list):
        log.debug("==> variants_with_attributes._get attributes=%s", attributes)
        # Return variants that have ANY of the specified attributes
        ret = [obj for obj in variant_objs if any(attr in obj.attributes for attr in attributes)]
        log.debug("<== variants_with_attributes._get ret=%s", [(obj.attributes, obj.variant) for obj in ret])
        return ret

    log.debug("<== variants_with_attributes ret=_get")
    return _get


def pytest_report_header(config):
    """
    Add a header to the pytest report showing the variants and setup string.
    """
    log.debug("==> pytest_report_header config=%s", config)
    variant_args = config.getoption('variant')
    if not variant_args:
        variant_args = [config.getini('VARIANTS')] if config.getini(
            'VARIANTS') else []
    variant_setup = config.getoption('variant_setup') or config.getini(
        'VARIANT_SETUP')
    ret = f"Variants: {variant_args} | Variant-setup: {variant_setup}"
    log.debug("<== pytest_report_header ret=%s", ret)
    return ret
