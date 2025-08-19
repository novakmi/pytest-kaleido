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


def test_variant_attributes_and_variants_fixtures(pytester):
    pytester.makepyfile(
        """
        def test_attributes_and_variants(all_variant_attributes, variant_filter):
            # Should collect all unique attributes (not just first)
            assert set(all_variant_attributes) == {'router', 'switch', 'special'}
            assert set(obj.variant for obj in variant_filter.by_attribute('router')) == {'1.0', '1.1'}
            assert set(obj.variant for obj in variant_filter.by_attribute('switch')) == {'2.0'}
            assert set(obj.variant for obj in variant_filter.by_attribute('special')) == {'1.0', '1.1', '1,2', '1:0'}
        """
    )
    result = pytester.runpytest(
        r'--variant=router:1.0,router:1.1,switch:2.0,router:special:1.0,' +
        r'router:special:1.1,special:1\,2,special:1\:0',
        '-o', 'log_cli_level=DEBUG', '-vv')
    result.stdout.fnmatch_lines([
        '*::test_attributes_and_variants PASSED*',
    ])
    assert result.ret == 0


def test_variant_variants_none_attributes(pytester):
    pytester.makepyfile(
        """
        def test_variants_none(variant_filter):
            assert set(obj.variant for obj in variant_filter.by_attribute(None)) == {'foo', 'bar'}
        """
    )
    result = pytester.runpytest('--variant=foo,bar', '-v')
    result.stdout.fnmatch_lines([
        '*::test_variants_none PASSED*',
    ])
    assert result.ret == 0


def test_variant_inheritance_across_argument(pytester):
    pytester.makepyfile(
        """
        def test_variant(variant):
            # Should create a:1.0, a:1.1, b:1.0, b:1.1, and merge attributes for same variant
            if variant.variant == '1.0':
                assert set(variant.attributes) == {'a', 'b'}
            if variant.variant == '1.1':
                assert set(variant.attributes) == {'a', 'b'}
        """
    )
    result = pytester.runpytest('--variant=a:1.0,1.1', '--variant=b:1.0,1.1', '-v')
    result.stdout.fnmatch_lines([
        '*::test_variant[a:b:1.0* PASSED*',
        '*::test_variant[a:b:1.1* PASSED*',
    ])
    assert result.ret == 0


def test_variant_escape_characters(pytester):
    pytester.makepyfile(
        """
        def test_variant(variant):
            # router:special:1.0, router:special:1.1, router:special:1,2
            if 'router' in variant.attributes and 'special' in variant.attributes:
                assert variant.variant in ('1.0', '1.1', '1,2', '1:0')
            # '1:0' resets attributes, so should be ['1'] and variant '0'
            if variant.attributes == ['1'] and variant.variant == '0':
                assert True
        """
    )
    result = pytester.runpytest(
        r'--variant=router:special:1.0,1.1,1\,2,1\:0,1:0', '-v')
    result.stdout.fnmatch_lines([
        '*::test_variant[router:special:1.0* PASSED*',
        '*::test_variant[router:special:1.1* PASSED*',
        '*::test_variant[router:special:1,2* PASSED*',
        '*::test_variant[router:special:1:0* PASSED*',
        '*::test_variant[1:0* PASSED*',
    ])
    assert result.ret == 0


def test_variant_mixed_attributes_and_inheritance(pytester):
    pytester.makepyfile(
        """
        def test_variant(variant):
            # router:1.0, 1.1, switch:2.0, 2.1
            if 'router' in variant.attributes:
                assert variant.variant in ('1.0', '1.1')
            if 'switch' in variant.attributes:
                assert variant.variant in ('2.0', '2.1')
        """
    )
    result = pytester.runpytest('--variant=router:1.0,1.1,switch:2.0,2.1', '-v')
    result.stdout.fnmatch_lines([
        '*::test_variant[router:1.0* PASSED*',
        '*::test_variant[router:1.1* PASSED*',
        '*::test_variant[switch:2.0* PASSED*',
        '*::test_variant[switch:2.1* PASSED*',
    ])
    assert result.ret == 0


def test_variant_setup_escape_characters(pytester):
    pytester.makepyfile(
        """
        import pytest
        from pytest_variant.plugin import _parse_variant_args_to_lists

        def test_variant_setup(request):
            setup_str = request.config.getoption('variant_setup')
            variants = _parse_variant_args_to_lists([setup_str])
            # Should parse --variant-setup string (see below)
            assert ['win', 'C:\\Program Files\\App'] in variants
            assert ['linux', '/opt/app'] in variants
            assert ['win', 'C:\\App'] in variants
            assert ['linux', '/opt/app,special'] in variants
            assert len(variants) == 4
        """)  # noqa: E261,W605

    result = pytester.runpytest(
        r'--variant-setup=win:C\:\Program Files\App,linux:/opt/app,' +
        r'win:C\:\App,linux:/opt/app\,special', '-v')
    result.stdout.fnmatch_lines([
        '*::test_variant_setup PASSED*',
    ])
    assert result.ret == 0


def test_variants_with_attributes_fixture(pytester):
    pytester.makepyfile(
        """
        def test_variants_with_attributes(variant_filter):
            # Should return all variants with 'router' or 'special' attributes
            objs = variant_filter.by_attributes(['router', 'special'])
            for obj in objs:
                assert 'router' in obj.attributes or 'special' in obj.attributes
            assert set(obj.variant for obj in objs) == {'1.0', '1.1', '1,2', '1:0'}
            # Should return all variants with 'switch' attribute
            objs2 = variant_filter.by_attributes(['switch'])
            for obj in objs2:
                assert 'switch' in obj.attributes
            assert set(obj.variant for obj in objs2) == {'2.0'}
        """
    )
    result = pytester.runpytest(
        r'--variant=router:1.0,router:1.1,switch:2.0,router:special:1.0,' +
        r'router:special:1.1,special:1\,2,special:1\:0',
        '-vv')
    result.stdout.fnmatch_lines([
        '*::test_variants_with_attributes PASSED*',
    ])
    assert result.ret == 0
