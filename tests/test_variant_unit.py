import pytest
import logging
log = logging.getLogger(__name__)

from pytest_variant.plugin import _parse_variants, VariantPluginBase

def test_parse_variants_no_product():
    variants = _parse_variants('foo,bar')
    assert variants == [('foo', None), ('bar', None)]

def test_parse_variants_with_product():
    variants = _parse_variants('router:1.0,1.1;switch:2.0')
    assert ('1.0', 'router') in variants
    assert ('1.1', 'router') in variants
    assert ('2.0', 'switch') in variants
    assert len(variants) == 3

def test_variantpluginbase_from_tuples():
    tuples = [('1.0', 'router'), ('2.0', 'switch'), ('foo', None)]
    objs = VariantPluginBase.from_tuples(tuples)
    assert len(objs) == 3
    assert objs[0].variant == '1.0'
    assert objs[0].product == 'router'
    assert objs[2].variant == 'foo'
    assert objs[2].product is None

def test_variantpluginbase_get_products():
    tuples = [('1.0', 'router'), ('2.0', 'switch'), ('foo', None)]
    objs = VariantPluginBase.from_tuples(tuples)
    products = VariantPluginBase.get_products(objs)
    assert set(products) == {'router', 'switch'}

def test_variantpluginbase_get_variants():
    tuples = [('1.0', 'router'), ('1.1', 'router'), ('2.0', 'switch'), ('foo', None)]
    objs = VariantPluginBase.from_tuples(tuples)
    router_variants = VariantPluginBase.get_variants(objs, 'router')
    switch_variants = VariantPluginBase.get_variants(objs, 'switch')
    none_variants = VariantPluginBase.get_variants(objs, None)
    assert set(router_variants) == {'1.0', '1.1'}
    assert set(switch_variants) == {'2.0'}
    assert set(none_variants) == {'foo'}
