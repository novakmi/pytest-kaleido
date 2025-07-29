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
