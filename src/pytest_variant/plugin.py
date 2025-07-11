import pytest
from typing import List, Dict, Optional
import logging

log = logging.getLogger(__name__)

def pytest_addoption(parser):
    group = parser.getgroup('variant')
    group.addoption(
        '--variant',
        action='store',
        dest='variant',
        default=None,
        help='Comma- or semicolon-separated list of variants, or product:variant,... pairs.'
    )
    group.addoption(
        '--variant-setup',
        action='store',
        dest='variant_setup',
        default=None,
        help='Path to product installation directory for variant discovery.'
    )
    parser.addini('VARIANTS', 'Default variants (comma-separated)')
    parser.addini('VARIANT_SETUP', 'Default variant-setup path')


def _parse_variants(variant_str: Optional[str]) -> List[tuple]:
    """
    Parse variants and products from command-line or ini/config.
    Supports:
      --variant=pro,enterprise
      --variant=router:1.0,1.1;switch:2.0,2.1,3.0
    Returns: List of (variant, product) tuples. If no product, product is None.
    """

    if not variant_str:
        return []
    result = []
    if ':' in variant_str or ';' in variant_str:
        # Format: router:1.0,1.1;switch:2.0,2.1,3.0
        for proddef in variant_str.split(';'):
            if not proddef.strip():
                continue
            if ':' in proddef:
                prod, vers = proddef.split(':', 1)
                for v in vers.split(','):
                    v = v.strip()
                    if v:
                        result.append((v, prod.strip()))
    else:
        # Format: pro,enterprise (no product)
        vlist = [v.strip() for v in variant_str.split(',') if v.strip()]
        for v in vlist:
            result.append((v, None))
    return result


# Abstract base for reuse in product-specific plugins
class VariantPluginBase:
    """
    Abstract base class for variant-oriented pytest plugins.
    Provides helpers for variant/product discovery and parametrization.
    Each instance represents a single variant string.
    """
    def __init__(self, variant: str, product: str = None):
        self.variant = variant
        self.product = product

    @staticmethod
    def parse_variants(variant_str: Optional[str]) -> List[tuple]:
        return _parse_variants(variant_str)

    @classmethod
    def from_tuples(cls, variant_tuples: List[tuple]):
        """
        Create a list of VariantPluginBase objects from a list of (variant, product) tuples.
        """
        return [cls(variant=v, product=p) for v, p in variant_tuples]

    @staticmethod
    def get_products(variant_objs: list) -> list:
        """
        Return a sorted list of unique products (excluding None) from a list of VariantPluginBase objects.
        """
        # log.debug(f"get_products: variant_objs={variant_objs}")
        return sorted({obj.product for obj in variant_objs if obj.product is not None})

    @staticmethod
    def get_variants(variant_objs: list, product=None) -> list:
        """
        Return a sorted list of variants for a given product (or for None if product is None).
        """
        return sorted([obj.variant for obj in variant_objs if obj.product == product])

def get_all_variant_objs(config):
    """
    Helper to read config and parse all variant objects for the current session.
    """
    variant_str = config.getoption('variant') or config.getini('VARIANTS')
    variant_tuples = _parse_variants(variant_str)
    return VariantPluginBase.from_tuples(variant_tuples)

def pytest_generate_tests(metafunc):
    # log.debug(f"==> pytest_generate_tests metafunc={dir(metafunc)}")
    # config = metafunc.config
    variant_objs = get_all_variant_objs(metafunc.config)
    # variant_str = config.getoption('variant') or config.getini('VARIANTS')
    # variant_tuples = _parse_variants(variant_str)
    # log.debug(f"Parsed variant tuples: {variant_tuples}")
    # variant_objs = VariantPluginBase.from_tuples(variant_tuples)
    # log.debug("Variant objects created: %s %i", variant_objs, len(variant_objs))
    if 'variant' in metafunc.fixturenames:
        metafunc.parametrize('variant', variant_objs, ids=[f"{obj.product}:{obj.variant}" if obj.product else obj.variant for obj in variant_objs])


@pytest.fixture
def variant(request):
    # log.debug("==> variant fixture: request=%s", dir(request))
    return request.param if hasattr(request, 'param') else None


@pytest.fixture
def variant_setup(request):
    """
    Fixture providing the variant-setup path (product installation directory) as specified by CLI or ini.
    """
    config = request.config
    return config.getoption('variant_setup') or config.getini('VARIANT_SETUP')


@pytest.fixture
def variant_products(request):
    """
    Fixture returning all products (excluding None) from the parametrized variants.
    Always returns the full set of products for the current test session.
    """
    variant_objs = get_all_variant_objs(request.config)
    # log.debug("variant_products: variant_objs=%s", variant_objs)
    return VariantPluginBase.get_products(variant_objs)


@pytest.fixture
def variant_variants(request):
    """
    Fixture returning a function to get variants for a given product (or None).
    Always returns the full set of variants for the current test session.
    Usage: variant_variants(product=None)
    """
    variant_objs = get_all_variant_objs(request.config)
    # log.debug("variant_variants: variant_objs=%s", variant_objs)
    def _get(product=None):
        return VariantPluginBase.get_variants(variant_objs, product)
    return _get


def pytest_report_header(config):
    variant = config.getoption('variant') or config.getini('VARIANTS')
    variant_setup = config.getoption('variant_setup') or config.getini('VARIANT_SETUP')
    return f"Variants: {variant} | Variant-setup: {variant_setup}"
