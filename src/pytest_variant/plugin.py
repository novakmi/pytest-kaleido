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
    Split a string by sep, but allow escaping sep with backslash only if it precedes sep.
    Only split on unescaped sep. Remove escape backslashes from result.
    """
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
    log.debug("_split_escaped: input='%s', sep='%s' -> parts=%s", s, sep, parts)
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

    def __init__(self, attributes: List[str], variant: str):
        # Store attributes as a sorted set (unique, order not preserved)
        self.attributes = sorted(set(attributes))
        self.variant = variant        # variant name (string)

    @property
    def attrs(self):
        # For backward compatibility
        return self.attributes

    @staticmethod
    def parse_variants(variant_args: Optional[List[str]]) -> List[List[str]]:
        return _parse_variants(variant_args)

    @classmethod
    def from_lists(cls, attr_lists: List[List[str]]):
        """
        Create a list of VariantPluginBase objects from a list of attribute lists.
        Each list must have at least one item (the variant is the last item).
        """
        return [cls(attributes=attrs[:-1], variant=attrs[-1]) for attrs in attr_lists if attrs]

    @staticmethod
    def get_attributes(variant_objs: list) -> list:
        """
        Return a sorted list of all unique attributes from all VariantPluginBase objects.
        """
        attributes = set()
        for obj in variant_objs:
            attributes.update(obj.attributes)
        return sorted(attributes)

    @staticmethod
    def get_variants(variant_objs: list, attribute=None) -> list:
        """
        Return a sorted list of variants for a given attribute (any attribute), or for None if no attributes.
        """
        log.debug("==> get_variants attribute=%s", attribute)
        variants = []
        for obj in variant_objs:
            if attribute is None:
                if not obj.attributes:
                    variants.append(obj.variant)
            else:
                if attribute in obj.attributes:
                    variants.append(obj.variant)
        log.debug("<== variants=%s", variants)
        return sorted(variants)


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
        metafunc.parametrize(
            'variant',
            variant_objs,
            ids=[":".join(obj.attributes + [obj.variant]) for obj in variant_objs]
        )


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
def variant_attributes(request):
    variant_objs = get_all_variant_objs(request.config)
    return VariantPluginBase.get_attributes(variant_objs)


@pytest.fixture
def variant_variants(request):
    variant_objs = get_all_variant_objs(request.config)

    def _get(attribute=None):
        return VariantPluginBase.get_variants(variant_objs, attribute)

    return _get


def pytest_report_header(config):
    variant_args = config.getoption('variant')
    if not variant_args:
        variant_args = [config.getini('VARIANTS')] if config.getini(
            'VARIANTS') else []
    variant_setup = config.getoption('variant_setup') or config.getini(
        'VARIANT_SETUP')
    return f"Variants: {variant_args} | Variant-setup: {variant_setup}"
