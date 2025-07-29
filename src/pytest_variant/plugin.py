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


# Abstract base for reuse in product-specific plugins
class VariantPluginBase:
    """
    Abstract base class for variant-oriented pytest plugins.
    Each instance represents a single variant, with attributes.
    """

    def __init__(self, attributes: List[str], variant: str):
        log.debug("==> VariantPluginBase.__init__ attributes=%s, variant=%s", attributes, variant)
        # Store attributes as a sorted set (unique, order not preserved)
        self.attributes = sorted(set(attributes))
        self.variant = variant        # variant name (string)
        log.debug("<== VariantPluginBase.__init__ ret=None")

    @property
    def attrs(self):
        # For backward compatibility
        return self.attributes

    @staticmethod
    def parse_variants(variant_args: Optional[List[str]]) -> List[List[str]]:
        log.debug("==> VariantPluginBase.parse_variants variant_args=%s", variant_args)
        ret = _parse_variants(variant_args)
        log.debug("<== VariantPluginBase.parse_variants ret=%s", ret)
        return ret

    @classmethod
    def from_lists(cls, attr_lists: List[List[str]]):
        log.debug("==> VariantPluginBase.from_lists attr_lists=%s", attr_lists)
        ret = [cls(attributes=attrs[:-1], variant=attrs[-1]) for attrs in attr_lists if attrs]
        log.debug("<== VariantPluginBase.from_lists ret=%s", ret)
        return ret

    @staticmethod
    def get_attributes(variant_objs: list) -> list:
        log.debug("==> VariantPluginBase.get_attributes variant_objs=%s", variant_objs)
        attributes = set()
        for obj in variant_objs:
            attributes.update(obj.attributes)
        ret = sorted(attributes)
        log.debug("<== VariantPluginBase.get_attributes ret=%s", ret)
        return ret

    @staticmethod
    def get_variants(variant_objs: list, attribute=None) -> list:
        log.debug("==> VariantPluginBase.get_variants variant_objs=%s, attribute=%s", variant_objs, attribute)
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
    log.debug("==> variant request=%s", request)
    ret = request.param if hasattr(request, 'param') else None
    log.debug("<== variant ret=%s", ret)
    return ret


@pytest.fixture
def variant_setup(request):
    log.debug("==> variant_setup request=%s", request)
    config = request.config
    setup_str = config.getoption('variant_setup') or config.getini('VARIANT_SETUP')
    log.debug("<== variant_setup ret=%s", setup_str)
    return setup_str


@pytest.fixture
def variant_attributes(request):
    log.debug("==> variant_attributes request=%s", request)
    variant_objs = get_all_variant_objs(request.config)
    ret = VariantPluginBase.get_attributes(variant_objs)
    log.debug("<== variant_attributes ret=%s", ret)
    return ret


@pytest.fixture
def variant_variants(request):
    log.debug("==> variant_variants request=%s", request)
    variant_objs = get_all_variant_objs(request.config)

    def _get(attribute=None):
        log.debug("==> variant_variants._get attribute=%s", attribute)
        ret = VariantPluginBase.get_variants(variant_objs, attribute)
        log.debug("<== variant_variants._get ret=%s", ret)
        return ret

    log.debug("<== variant_variants ret=_get")
    return _get


def pytest_report_header(config):
    log.debug("==> pytest_report_header config=%s", config)
    variant_args = config.getoption('variant')
    if not variant_args:
        variant_args = [config.getini('VARIANTS')] if config.getini('VARIANTS') else []
    variant_setup = config.getoption('variant_setup') or config.getini('VARIANT_SETUP')
    ret = f"Variants: {variant_args} | Variant-setup: {variant_setup}"
    log.debug("<== pytest_report_header ret=%s", ret)
    return ret
