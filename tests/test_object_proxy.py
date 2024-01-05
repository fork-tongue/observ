import pytest

from observ.object_proxy import ObjectProxy, ReadonlyObjectProxy
from observ.object_utils import get_class_slots, get_object_attrs
from observ.proxy import proxy
from observ.traps import ReadonlyError


class A:
    __slots__ = ("bar",)

    def __init__(self, bar=5):
        self.bar = bar


class B(A):
    def __init__(self, baz=10, **kwargs):
        super().__init__(**kwargs)
        self.baz = baz


class C(B):
    __slots__ = ("quux",)

    def __init__(self, quux=15, **kwargs):
        super().__init__(**kwargs)
        self.quux = quux


class D:
    def __init__(self, bar=5):
        self.bar = bar


def test_get_class_slots():
    assert get_class_slots(C) == {'bar', 'quux'}
    assert get_class_slots(D) == set()


def test_get_object_attrs():
    assert set(get_object_attrs(A())) == {'bar'}
    assert set(get_object_attrs(B())) == {'baz', 'bar'}
    assert set(get_object_attrs(C())) == {'baz', 'bar', 'quux'}
    assert set(get_object_attrs(D())) == {'bar'}

    d = D()
    d.quuz = 20
    assert set(get_object_attrs(d)) == {'bar', 'quuz'}


def test_object_proxying():
    obj = B(bar=5)
    proxy = ObjectProxy(obj)
    assert proxy.bar == 5
    proxy.bar = 6
    assert proxy.bar == 6

    proxy.something_else = "toet"
    assert proxy.something_else == "toet"
    assert obj.something_else == "toet"


def test_readonly_proxy():
    proxied = proxy(C(bar=3))
    readonly_proxy = proxy(proxied, readonly=True)
    another_proxied = proxy(readonly_proxy, readonly=False)

    assert isinstance(proxied, ObjectProxy)
    assert isinstance(readonly_proxy, ReadonlyObjectProxy)
    assert proxied is another_proxied

    with pytest.raises(ReadonlyError):
        readonly_proxy.bar = 25
    assert proxied.bar == 3

    another_proxied.bar = 25
    assert proxied.bar == 25

    with pytest.raises(ReadonlyError):
        delattr(readonly_proxy, "baz")
    delattr(another_proxied, "baz")

    assert not hasattr(proxied, "baz")


