import logging

log = logging.getLogger(__name__)


def test_variant_parametrize_basic(pytester):
    pytester.makepyfile(
        """
        def test_variant(variant):
            assert hasattr(variant, 'variant')
            assert variant.variant in ('foo', 'bar')
        """
    )
    result = pytester.runpytest('--variant=foo,bar', '-v')
    result.stdout.fnmatch_lines([
        "*::test_variant[foo* PASSED*",
        '*::test_variant[bar* PASSED*',
    ])
    assert result.ret == 0


def test_variant_parametrize_with_attributes(pytester):
    pytester.makepyfile(
        """
        def test_variant(variant):
            assert hasattr(variant, 'variant')
            assert isinstance(variant.attributes, list)
            # router:1.0,router:1.1,switch:2.0
            if 'router' in variant.attributes:
                assert variant.variant in ('1.0', '1.1')
            if 'switch' in variant.attributes:
                assert variant.variant == '2.0'
        """
    )
    result = pytester.runpytest('--variant=router:1.0,router:1.1,switch:2.0',
                                '-v')
    result.stdout.fnmatch_lines([
        '*::test_variant[router:1.0* PASSED*',
        '*::test_variant[router:1.1* PASSED*',
        '*::test_variant[switch:2.0* PASSED*',
    ])
    assert result.ret == 0


def test_variant_products_and_variants_fixtures(pytester):
    pytester.makepyfile(
        """
        def test_products_and_variants(variant_products, variant_variants):
            assert set(variant_products) == {'router', 'switch'}
            assert set(variant_variants('router')) == {'1.0', '1.1'}
            assert set(variant_variants('switch')) == {'2.0'}
        """
    )
    result = pytester.runpytest('--variant=router:1.0,router:1.1,switch:2.0',
                                '-o', 'log_cli_level=DEBUG', '-vv')
    result.stdout.fnmatch_lines([
        '*::test_products_and_variants PASSED*',
    ])
    assert result.ret == 0


def test_variant_variants_none_attributes(pytester):
    pytester.makepyfile(
        """
        def test_variants_none(variant_variants):
            assert set(variant_variants(None)) == {'foo', 'bar'}
        """
    )
    result = pytester.runpytest('--variant=foo,bar', '-v')
    result.stdout.fnmatch_lines([
        '*::test_variants_none PASSED*',
    ])
    assert result.ret == 0
