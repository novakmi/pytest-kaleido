import logging
from pytest_variant.plugin import _parse_variants, VariantPluginBase

log = logging.getLogger(__name__)


def test_parse_variants_no_attributes():
    variants = _parse_variants(['foo,bar'])
    assert variants == [['foo'], ['bar']]


def test_parse_variants_with_attributes():
    variants = _parse_variants(['router:1.0,router:1.1,switch:2.0'])
    assert ['router', '1.0'] in variants
    assert ['router', '1.1'] in variants
    assert ['switch', '2.0'] in variants
    assert len(variants) == 3


def test_parse_variants_inheritance():
    variants = _parse_variants(['a:1.0,1.1', 'b:1.0,1.1'])
    assert ['a', '1.0'] in variants
    assert ['a', '1.1'] in variants
    assert ['b', '1.0'] in variants
    assert ['b', '1.1'] in variants
    assert len(variants) == 4


def test_parse_variants_mixed_attributes():
    variants = _parse_variants(['router:1.0,1.1,switch:2.0,2.1'])
    assert ['router', '1.0'] in variants
    assert ['router', '1.1'] in variants
    assert ['switch', '2.0'] in variants
    assert ['switch', '2.1'] in variants
    assert len(variants) == 4


def test_parse_variants_escape_characters():
    variants = _parse_variants(['router:special:1.0,1.1,1\\,2,1\\:0,1:0'])
    assert ['router', 'special', '1.0'] in variants
    assert ['router', 'special', '1.1'] in variants
    assert ['router', 'special', '1,2'] in variants
    assert ['router', 'special', '1:0'] in variants
    # '1:0' resets attributes, so should be ['1', '0']
    assert ['1', '0'] in variants
    assert len(variants) == 5


def test_parse_variant_setup_windows_linux_dirs():
    # s = r'win:C\:\ProgramFiles\App,linux:/opt/app,win:C\:\App,linux:/opt/app\,special'
    s = r'win:C\:\App'
    variants = _parse_variants([s])
    # assert ['win', 'C:\\ProgramFiles\\App'] in variants
    # assert ['linux', '/opt/app'] in variants
    assert ['win', 'C:\\App'] in variants
    # assert ['linux', '/opt/app,special'] in variants
    # assert len(variants) == 4


def test_variantpluginbase_from_lists():
    lists = [['router', '1.0'], ['switch', '2.0'], ['foo']]
    objs = VariantPluginBase.from_lists(lists)
    assert len(objs) == 3
    assert objs[0].variant == '1.0'
    assert objs[0].attrs == ['router']
    assert objs[2].variant == 'foo'
    assert objs[2].attrs == []


def test_variantpluginbase_get_attributes():
    lists = [['router', '1.0'], ['switch', '2.0'], ['foo'], ['router', 'special', '1.0'], ['router', 'special', '1.1']]
    objs = VariantPluginBase.from_lists(lists)
    attributes = VariantPluginBase.get_attributes(objs)
    # Should collect all unique attributes (not just first)
    assert set(attributes) == {'router', 'switch', 'special'}


def test_variantpluginbase_get_variants():
    lists = [['router', '1.0'], ['router', '1.1'], ['router', 'switch', '2.0'], ['foo']]
    objs = VariantPluginBase.from_lists(lists)
    router_variants = VariantPluginBase.get_variants(objs, 'router')
    switch_variants = VariantPluginBase.get_variants(objs, 'switch')
    none_variants = VariantPluginBase.get_variants(objs, None)
    assert set(router_variants) == {'1.0', '1.1', '2.0'}
    assert set(switch_variants) == {'2.0'}
    assert set(none_variants) == {'foo'}


def test_variants_with_attributes_logic():
    # Simulate variant objects
    objs = [
        VariantPluginBase(['router', 'special'], '1.0'),
        VariantPluginBase(['router', 'special'], '1.1'),
        VariantPluginBase(['router'], '2.0'),
        VariantPluginBase(['router', 'special'], '1,2'),
        VariantPluginBase(['router', 'special'], '1:0'),
        VariantPluginBase(['switch'], '2.0'),
        VariantPluginBase(['special'], '3.0'),
    ]
    # Filter for both 'router' and 'special'
    filtered = [obj for obj in objs if all(attr in obj.attributes for attr in ['router', 'special'])]
    assert set(obj.variant for obj in filtered) == {'1.0', '1.1', '1,2', '1:0'}
    # Filter for 'switch'
    filtered2 = [obj for obj in objs if all(attr in obj.attributes for attr in ['switch'])]
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
    objs = VariantPluginBase.from_lists(lists)
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
        VariantPluginBase(['router', 'special'], '1.0'),
        VariantPluginBase(['router', 'special'], '1.1'),
        VariantPluginBase(['router', 'switch'], '2.0'),
        VariantPluginBase(['router'], 'foo'),
    ]
    # Should return all variants with 'router' or 'switch'
    filtered = [obj for obj in objs if any(attr in obj.attributes for attr in ['router', 'switch'])]
    assert set(obj.variant for obj in filtered) == {'1.0', '1.1', '2.0', 'foo'}
    # Should return only those with 'special'
    filtered2 = [obj for obj in objs if any(attr in obj.attributes for attr in ['special'])]
    assert set(obj.variant for obj in filtered2) == {'1.0', '1.1'}
    # Should return only those with 'switch'
    filtered3 = [obj for obj in objs if any(attr in obj.attributes for attr in ['switch'])]
    assert set(obj.variant for obj in filtered3) == {'2.0'}
