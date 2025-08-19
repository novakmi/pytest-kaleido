import logging
import os
import sys
try:
    from pytest_variant.plugin import _parse_variant_args_to_lists, VariantPluginBase
except ModuleNotFoundError:  # allow running tests without installing the package
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
    from pytest_variant.plugin import _parse_variant_args_to_lists, VariantPluginBase

log = logging.getLogger(__name__)


def test_parse_variant_args_to_lists_no_attributes():
    variants = _parse_variant_args_to_lists(['foo,bar'])
    assert variants == [['foo'], ['bar']]


def test_parse_variant_args_to_lists_with_attributes():
    variants = _parse_variant_args_to_lists(['router:1.0,router:1.1,switch:2.0'])
    assert ['router', '1.0'] in variants
    assert ['router', '1.1'] in variants
    assert ['switch', '2.0'] in variants
    assert len(variants) == 3


def test_parse_variant_args_to_lists_inheritance():
    variants = _parse_variant_args_to_lists(['a:1.0,1.1', 'b:1.0,1.1'])
    assert ['a', '1.0'] in variants
    assert ['a', '1.1'] in variants
    assert ['b', '1.0'] in variants
    assert ['b', '1.1'] in variants
    assert len(variants) == 4


def test_parse_variant_args_to_lists_mixed_attributes():
    variants = _parse_variant_args_to_lists(['router:1.0,1.1,switch:2.0,2.1'])
    assert ['router', '1.0'] in variants
    assert ['router', '1.1'] in variants
    assert ['switch', '2.0'] in variants
    assert ['switch', '2.1'] in variants
    assert len(variants) == 4


def test_parse_variant_args_to_lists_escape_characters():
    variants = _parse_variant_args_to_lists(['router:special:1.0,1.1,1\\,2,1\\:0,1:0'])
    assert ['router', 'special', '1.0'] in variants
    assert ['router', 'special', '1.1'] in variants
    assert ['router', 'special', '1,2'] in variants
    assert ['router', 'special', '1:0'] in variants
    # '1:0' resets attributes, so should be ['1', '0']
    assert ['1', '0'] in variants
    assert len(variants) == 5


def test_parse_variant_args_to_lists_setup_windows_linux_dirs():
    # s = r'win:C\:\ProgramFiles\App,linux:/opt/app,win:C\:\App,linux:/opt/app\,special'
    s = r'win:C\:\App'
    variants = _parse_variant_args_to_lists([s])
    # assert ['win', 'C:\\ProgramFiles\\App'] in variants
    # assert ['linux', '/opt/app'] in variants
    assert ['win', 'C:\\App'] in variants
    # assert ['linux', '/opt/app,special'] in variants
    # assert len(variants) == 4


def test_variantpluginbase_from_lists():
    lists = [['router', '1.0'], ['switch', '2.0'], ['foo']]
    objs = VariantPluginBase.parse_variants_from_list(lists)
    assert len(objs) == 3
    assert objs[0].variant == '1.0'
    assert objs[0].attrs == ['router']
    assert objs[2].variant == 'foo'
    assert objs[2].attrs == []


def test_variantpluginbase_get_attributes():
    lists = [['router', '1.0'], ['switch', '2.0'], ['foo'],
             ['router', 'special', '1.0'], ['router', 'special', '1.1']]
    objs = VariantPluginBase.parse_variants_from_list(lists)
    attributes = VariantPluginBase.get_attributes(objs)
    # Should collect all unique attributes (not just first)
    assert set(attributes) == {'router', 'switch', 'special'}


def test_variantpluginbase_get_variants():
    lists = [['router', '1.0'], ['router', '1.1'], ['router', 'switch', '2.0'],
             ['foo']]
    objs = VariantPluginBase.parse_variants_from_list(lists)
    router_variants = VariantPluginBase.get_variants(objs, 'router')
    switch_variants = VariantPluginBase.get_variants(objs, 'switch')
    none_variants = VariantPluginBase.get_variants(objs, None)
    # get_variants now returns objects, so extract variant names for comparison
    assert set(obj.variant for obj in router_variants) == {'1.0', '1.1', '2.0'}
    assert set(obj.variant for obj in switch_variants) == {'2.0'}
    assert set(obj.variant for obj in none_variants) == {'foo'}


def test_variants_with_attributes_logic():
    # Simulate variant objects
    objs = [
        VariantPluginBase('1.0', ['router', 'special']),
        VariantPluginBase('1.1', ['router', 'special']),
        VariantPluginBase('2.0', ['router']),
        VariantPluginBase('1,2', ['router', 'special']),
        VariantPluginBase('1:0', ['router', 'special']),
        VariantPluginBase('2.0', ['switch']),
        VariantPluginBase('3.0', ['special']),
    ]
    # Filter for both 'router' and 'special'
    filtered = [obj for obj in objs if
                all(attr in obj.attributes for attr in ['router', 'special'])]
    assert set(obj.variant for obj in filtered) == {'1.0', '1.1', '1,2', '1:0'}
    # Filter for 'switch'
    filtered2 = [obj for obj in objs if
                 all(attr in obj.attributes for attr in ['switch'])]
    assert set(obj.variant for obj in filtered2) == {'2.0'}


def test_variantpluginbase_from_lists_merges_attributes():
    # If a variant is specified multiple times, attributes should be merged
    lists = [
        ['router', '1.0'],
        ['special', '1.0'],
        ['router', 'special', '1.1'],
        ['router', '1.1'],
        ['switch', '2.0'],
        ['router', 'switch', '2.0'],
        ['foo'],
        ['router', 'foo'],
    ]
    objs = VariantPluginBase.parse_variants_from_list(lists)
    # Find merged variant '1.0'
    v10 = next(obj for obj in objs if obj.variant == '1.0')
    assert set(v10.attributes) == {'router', 'special'}
    # Find merged variant '1.1'
    v11 = next(obj for obj in objs if obj.variant == '1.1')
    assert set(v11.attributes) == {'router', 'special'}
    # Find merged variant '2.0'
    v20 = next(obj for obj in objs if obj.variant == '2.0')
    assert set(v20.attributes) == {'router', 'switch'}
    # Find merged variant 'foo'
    vfoo = next(obj for obj in objs if obj.variant == 'foo')
    assert set(vfoo.attributes) == {'router'}


def test_variants_with_attributes_any_logic():
    # Simulate merged variant objects
    objs = [
        VariantPluginBase('1.0', ['router', 'special']),
        VariantPluginBase('1.1', ['router', 'special']),
        VariantPluginBase('2.0', ['router', 'switch']),
        VariantPluginBase('foo', ['router']),
    ]
    # Should return all variants with 'router' or 'switch'
    filtered = [obj for obj in objs if
                any(attr in obj.attributes for attr in ['router', 'switch'])]
    assert set(obj.variant for obj in filtered) == {'1.0', '1.1', '2.0', 'foo'}
    # Should return only those with 'special'
    filtered2 = [obj for obj in objs if
                 any(attr in obj.attributes for attr in ['special'])]
    assert set(obj.variant for obj in filtered2) == {'1.0', '1.1'}
    # Should return only those with 'switch'
    filtered3 = [obj for obj in objs if
                 any(attr in obj.attributes for attr in ['switch'])]
    assert set(obj.variant for obj in filtered3) == {'2.0'}


def test_variant_setup_parsing():
    # Simulate a variant-setup string with multiple setups
    setup_str = r'win:C\:App,linux:/opt/app,special:setup1'
    objs = VariantPluginBase.parse_variants([setup_str])
    # Should return a list of VariantPluginBase objects
    assert isinstance(objs, list)
    assert all(isinstance(obj, VariantPluginBase) for obj in objs)
    # Check that the parsed objects have expected attributes and variants
    found = {(tuple(obj.attrs), obj.variant) for obj in objs}
    expected = {
        (('win',), 'C:App'),
        (('linux',), '/opt/app'),
        (('special',), 'setup1'),
    }
    assert found == expected


def test_variants_with_attributes_none_or_empty_fixture():
    # This test uses the fixture-like logic directly, but in a real pytest session you would use the fixture
    class DummyConfig:
        pass

    # Simulate variants: some with attributes, one with none
    objs = [
        VariantPluginBase('1.0', ['router', 'special']),
        VariantPluginBase('1.1', ['router', 'special']),
        VariantPluginBase('2.0', ['router', 'switch']),
        VariantPluginBase('foo', ['router']),
        VariantPluginBase('bare', []),
    ]

    def variants_with_attributes(attributes=None):
        if not attributes:
            return [obj for obj in objs if not obj.attributes]
        else:
            return [obj for obj in objs if
                    any(attr in obj.attributes for attr in attributes)]

    # Test with None
    filtered_none = variants_with_attributes(None)
    assert set(obj.variant for obj in filtered_none) == {'bare'}
    # Test with empty list
    filtered_empty = variants_with_attributes([])
    assert set(obj.variant for obj in filtered_empty) == {'bare'}
    # Test with attribute
    filtered_router = variants_with_attributes(['router'])
    assert set(obj.variant for obj in filtered_router) == {'1.0', '1.1', '2.0',
                                                           'foo'}


def test_get_variants_with_attributes_no_attributes():
    objs = [
        VariantPluginBase('1.0', ['router', 'special']),
        VariantPluginBase('1.1', ['router', 'special']),
        VariantPluginBase('2.0', ['router', 'switch']),
        VariantPluginBase('foo', ['router']),
        VariantPluginBase('bare', []),
    ]
    filtered = VariantPluginBase.get_variants(objs)
    assert len(filtered) == 1
    assert filtered[0].variant == 'bare'


def test_get_variants_with_attributes_single():
    objs = [
        VariantPluginBase('1.0', ['router', 'special']),
        VariantPluginBase('1.1', ['router', 'special']),
        VariantPluginBase('2.0', ['router', 'switch']),
        VariantPluginBase('foo', ['router']),
        VariantPluginBase('bare', []),
    ]
    filtered = VariantPluginBase.get_variants(objs, attributes=['switch'])
    assert set(obj.variant for obj in filtered) == {'2.0'}


def test_get_variants_with_attributes_multiple():
    objs = [
        VariantPluginBase('1.0', ['router', 'special']),
        VariantPluginBase('1.1', ['router', 'special']),
        VariantPluginBase('2.0', ['router', 'switch']),
        VariantPluginBase('foo', ['router']),
        VariantPluginBase('bare', []),
    ]
    filtered = VariantPluginBase.get_variants(objs,attributes=['router', 'switch'])
    assert set(obj.variant for obj in filtered) == {'1.0', '1.1', '2.0', 'foo'}


def test_get_variants_with_attributes_nonexistent():
    objs = [
        VariantPluginBase('1.0', ['router', 'special']),
        VariantPluginBase('1.1', ['router', 'special']),
        VariantPluginBase('2.0', ['router', 'switch']),
        VariantPluginBase('foo', ['router']),
        VariantPluginBase('bare', []),
    ]
    filtered = VariantPluginBase.get_variants(objs, attributes=['notfound'])
    assert filtered == []


def test_get_variants_with_attributes_empty_list():
    objs = [
        VariantPluginBase('1.0', ['router', 'special']),
        VariantPluginBase('1.1', ['router', 'special']),
        VariantPluginBase('2.0', ['router', 'switch']),
        VariantPluginBase('foo', ['router']),
        VariantPluginBase('bare', []),
    ]
    filtered = VariantPluginBase.get_variants(objs, [])
    assert len(filtered) == 1
    assert filtered[0].variant == 'bare'


def test_parse_variant_args_no_attributes():
    objs = VariantPluginBase.parse_variants(['foo,bar'])
    by_variant = {o.variant: o.attributes for o in objs}
    assert by_variant == {'foo': [], 'bar': []}


def test_parse_variant_args_merge_attributes():
    objs = VariantPluginBase.parse_variants([
        'router:1.0,router:1.1,switch:2.0',
        'router:special:1.0',
        'special:1.1',
    ])
    by_variant = {o.variant: set(o.attributes) for o in objs}
    assert by_variant == {
        '1.0': {'router', 'special'},
        '1.1': {'router', 'special'},
        '2.0': {'switch'},
    }


def test_parse_variant_args_escape_and_inheritance():
    s = r'router:special:1.0,1.1,1\,2,1\:0,1:0'
    objs = VariantPluginBase.parse_variants([s])
    found = {(tuple(sorted(obj.attributes)), obj.variant) for obj in objs}
    expected = {
        (('router', 'special'), '1.0'),
        (('router', 'special'), '1.1'),
        (('router', 'special'), '1,2'),
        (('router', 'special'), '1:0'),
        (('1',), '0'),
    }
    assert found == expected
