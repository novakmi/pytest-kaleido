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


def test_variantpluginbase_from_lists():
    lists = [['router', '1.0'], ['switch', '2.0'], ['foo']]
    objs = VariantPluginBase.from_lists(lists)
    assert len(objs) == 3
    assert objs[0].variant == '1.0'
    assert objs[0].attrs == ['router']
    assert objs[2].variant == 'foo'
    assert objs[2].attrs == []


def test_variantpluginbase_get_products():
    lists = [['router', '1.0'], ['switch', '2.0'], ['foo']]
    objs = VariantPluginBase.from_lists(lists)
    products = VariantPluginBase.get_products(objs)
    assert set(products) == {'router', 'switch'}


def test_variantpluginbase_get_variants():
    lists = [['router', '1.0'], ['router', '1.1'], ['switch', '2.0'], ['foo']]
    objs = VariantPluginBase.from_lists(lists)
    router_variants = VariantPluginBase.get_variants(objs, 'router')
    switch_variants = VariantPluginBase.get_variants(objs, 'switch')
    none_variants = VariantPluginBase.get_variants(objs, None)
    assert set(router_variants) == {'1.0', '1.1'}
    assert set(switch_variants) == {'2.0'}
    assert set(none_variants) == {'foo'}
