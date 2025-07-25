import logging
from typing import List, Optional

import pytest

log = logging.getLogger(__name__)


def pytest_addoption(parser):
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
    Split a string by sep, but allow escaping sep with backslash.
    """
    parts = []
    buf = ''
    escape = False
    for c in s:
        if escape:
            buf += c
            escape = False
        elif c == '\\':
            escape = True
        elif c == sep:
            parts.append(buf)
            buf = ''
        else:
            buf += c
    parts.append(buf)
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
    if not variant_args:
        return []
    result = []
    for arg in variant_args:
        prev_attrs = []
        for vstr in _split_escaped(arg, ','):
            attrs = _split_escaped(vstr, ':')
            attrs = [a for a in attrs if a]
            if len(attrs) == 1 and prev_attrs:
                # Only variant name, inherit previous attributes
                attrs = prev_attrs + [attrs[0]]
            if len(attrs) > 1:
                prev_attrs = attrs[:-1]
            if attrs:
                result.append(attrs)
    return result


# Abstract base for reuse in product-specific plugins
class VariantPluginBase:
    """
    Abstract base class for variant-oriented pytest plugins.
    Each instance represents a single variant, with attributes.
    """

    def __init__(self, attributes: List[str]):
        self.attributes = attributes  # list of attributes, last is variant name

    @property
    def variant(self):
        return self.attributes[-1] if self.attributes else None

    @property
    def attrs(self):
        return self.attributes[:-1] if len(self.attributes) > 1 else []

    @staticmethod
    def parse_variants(variant_args: Optional[List[str]]) -> List[List[str]]:
        return _parse_variants(variant_args)

    @classmethod
    def from_lists(cls, attr_lists: List[List[str]]):
        """
        Create a list of VariantPluginBase objects from a list of attribute lists.
        """
        return [cls(attributes=attrs) for attrs in attr_lists]

    @staticmethod
    def get_products(variant_objs: list) -> list:
        """
        Return a sorted list of unique first attributes (if present) from a list of VariantPluginBase objects.
        """
        return sorted({obj.attrs[0] for obj in variant_objs if obj.attrs})

    @staticmethod
    def get_variants(variant_objs: list, product=None) -> list:
        """
        Return a sorted list of variants for a given product (first attribute), or for None if product is None.
        """
        if product is None:
            return sorted(
                [obj.variant for obj in variant_objs if not obj.attrs])
        else:
            return sorted([obj.variant for obj in variant_objs if
                           obj.attrs and obj.attrs[0] == product])


def get_all_variant_objs(config):
    """
    Helper to read config and parse all variant objects for the current session.
    """
    variant_args = config.getoption('variant')
    if not variant_args:
        ini_variants = config.getini('VARIANTS')
        variant_args = [ini_variants] if ini_variants else []
    attr_lists = _parse_variants(variant_args)
    return VariantPluginBase.from_lists(attr_lists)


def pytest_generate_tests(metafunc):
    variant_objs = get_all_variant_objs(metafunc.config)
    if 'variant' in metafunc.fixturenames:
        metafunc.parametrize('variant', variant_objs,
                             ids=[":".join(obj.attributes) for obj in
                                  variant_objs])


@pytest.fixture
def variant(request):
    return request.param if hasattr(request, 'param') else None


@pytest.fixture
def variant_setup(request):
    config = request.config
    setup_str = config.getoption('variant_setup') or config.getini(
        'VARIANT_SETUP')
    return setup_str


@pytest.fixture
def variant_products(request):
    variant_objs = get_all_variant_objs(request.config)
    return VariantPluginBase.get_products(variant_objs)


@pytest.fixture
def variant_variants(request):
    variant_objs = get_all_variant_objs(request.config)

    def _get(product=None):
        return VariantPluginBase.get_variants(variant_objs, product)

    return _get


def pytest_report_header(config):
    variant_args = config.getoption('variant')
    if not variant_args:
        variant_args = [config.getini('VARIANTS')] if config.getini(
            'VARIANTS') else []
    variant_setup = config.getoption('variant_setup') or config.getini(
        'VARIANT_SETUP')
    return f"Variants: {variant_args} | Variant-setup: {variant_setup}"
