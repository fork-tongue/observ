import pytest

from observ import reactive, to_raw, watch
from observ.object_proxy import ObjectProxy, ReadonlyObjectProxy
from observ.object_utils import get_class_slots, get_object_attrs
from observ.proxy import proxy
from observ.traps import ReadonlyError

try:
    import numpy as np

    has_numpy = True
except ImportError:
    has_numpy = False
numpy_missing_reason = "Numpy is not installed"


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

    i_am_none = None


def test_get_class_slots():
    assert get_class_slots(C) == {"bar", "quux"}
    assert get_class_slots(D) == set()


def test_get_object_attrs():
    assert set(get_object_attrs(A())) == {"bar"}
    assert set(get_object_attrs(B())) == {"baz", "bar"}
    assert set(get_object_attrs(C())) == {"baz", "bar", "quux"}
    assert set(get_object_attrs(D())) == {"bar"}

    d = D()
    d.quuz = 20
    assert set(get_object_attrs(d)) == {"bar", "quuz"}


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


@pytest.mark.skipif(not has_numpy, reason=numpy_missing_reason)
def test_usage_numpy():
    arr = np.eye(4)
    proxy = reactive(arr)
    # not supported
    assert not isinstance(proxy, ObjectProxy)


@pytest.mark.skipif(not has_numpy, reason=numpy_missing_reason)
def test_usage_watcher_with_numpy_values():
    proxy = reactive({"key": np.eye(4)})

    _ = watch(lambda: proxy, lambda: (), deep=True)


def test_toraw():
    """Demonstrate the supported and unsupported to_raw code paths"""
    obj = B(bar=5)
    proxy = ObjectProxy(obj)
    also_obj = to_raw(proxy)
    assert obj is also_obj and obj is not proxy

    tree = B(bar=obj)
    tree_proxy = ObjectProxy(tree)
    also_tree = to_raw(tree_proxy)
    assert tree is also_tree and tree is not tree_proxy
    assert also_tree.bar is obj

    tree = B(bar=proxy)
    tree_proxy = ObjectProxy(tree)
    also_tree = to_raw(tree_proxy)
    assert tree is also_tree and tree is not tree_proxy

    # since to_raw cannot copy/instantiate custom objects
    # any proxies assigned to object attributes will
    # not be processed recursively by to_raw
    assert also_tree.bar is not obj


def test_typeerror():
    obj = D()
    proxy = reactive(obj)
    assert isinstance(proxy, ObjectProxy)

    assert obj.i_am_none is None
    assert proxy.i_am_none is None

    with pytest.raises(AttributeError):
        obj.doesnt_exist()

    with pytest.raises(AttributeError):
        proxy.doesnt_exist()

    with pytest.raises(TypeError):
        iter(obj)

    with pytest.raises(TypeError):
        iter(proxy)
