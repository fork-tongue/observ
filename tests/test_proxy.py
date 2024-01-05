import gc

import pytest

from observ.dict_proxy import DictProxy, ReadonlyDictProxy
from observ.list_proxy import ListProxy, ReadonlyListProxy
from observ.proxy import Proxy, proxy
from observ.proxy_db import proxy_db
from observ.set_proxy import ReadonlySetProxy, SetProxy
from observ.traps import ReadonlyError


def test_proxy_lifecycle():
    data = {"foo": "bar"}
    obj_id = id(data)

    # Call proxy to wrap the data object
    wrapped_data = proxy(data)

    assert isinstance(wrapped_data, Proxy)
    assert obj_id in proxy_db.db
    assert wrapped_data.__target__ is data

    # Retrieve the proxy from the proxy_db
    referenced_proxy = proxy_db.get_proxy(data)

    assert referenced_proxy is wrapped_data
    assert referenced_proxy.__target__ is wrapped_data.__target__

    # Destroy the second proxy
    del referenced_proxy

    assert obj_id in proxy_db.db
    assert proxy_db.get_proxy(data) is not None

    # Destroy the original proxy
    del wrapped_data

    assert obj_id in proxy_db.db
    assert proxy_db.get_proxy(data) is None

    # Also delete the original data and run garbage collection
    del data
    gc.collect()

    assert obj_id not in proxy_db.db


def test_proxy_lifecycle_auto():
    # Call proxy to wrap the data object
    wrapped_data = proxy({"foo": "bar"})
    obj_id = id(wrapped_data.__target__)

    assert isinstance(wrapped_data, Proxy)
    assert obj_id in proxy_db.db
    # assert wrapped_data.__target__ is data

    # Retrieve the proxy from the proxy_db
    referenced_proxy = proxy_db.get_proxy(wrapped_data.__target__)

    assert referenced_proxy is wrapped_data
    assert referenced_proxy.__target__ is wrapped_data.__target__

    # Destroy the second proxy
    del referenced_proxy

    assert obj_id in proxy_db.db
    assert proxy_db.get_proxy(wrapped_data.__target__) is not None

    # Destroy the original proxy
    del wrapped_data

    assert obj_id not in proxy_db.db


def test_multiple_proxy_calls():
    data = {"foo": "bar"}

    first_proxy = proxy(data)
    second_proxy = proxy(data)
    third_proxy = proxy(second_proxy)

    assert first_proxy is second_proxy
    assert second_proxy is third_proxy


def test_list_proxy():
    data = [1, 2, 3]
    proxied = proxy(data)
    assert isinstance(proxied, ListProxy)
    assert proxied[0] == 1
    assert len(proxied) == 3
    assert 1 in proxied


def test_list_proxy_deep():
    data = [1, {"foo": "bar"}]
    proxied = proxy(data)
    assert isinstance(proxied[1], DictProxy)


def test_set_proxy():
    data = {1, 2, 3}
    proxied = proxy(data)
    assert isinstance(proxied, SetProxy)
    assert len(proxied) == 3
    assert 1 in proxied


def test_dict_proxy():
    data = {"foo": "bar"}

    proxied = proxy(data)
    assert isinstance(proxied, DictProxy)
    assert proxied["foo"] == "bar"

    proxied["foo"] = "baz"

    assert proxied["foo"] == "baz"

    proxied["lorem"] = "ipsum"

    assert proxied["lorem"] == "ipsum"

    del proxied["lorem"]
    assert "lorem" not in proxied
    assert len(proxied) == 1


def test_readonly_dict_proxy():
    data = {"foo": "bar"}
    readonly_proxy = proxy(data, readonly=True)

    assert isinstance(readonly_proxy, ReadonlyDictProxy)

    with pytest.raises(ReadonlyError):
        readonly_proxy["foo"] = "baz"


def test_readonly_nested_dict_proxy():
    proxied = proxy({"foo": "bar"})
    readonly_proxy = proxy(proxied, readonly=True)
    another_proxied = proxy(readonly_proxy, readonly=False)

    assert isinstance(proxied, DictProxy)
    assert isinstance(readonly_proxy, ReadonlyDictProxy)

    with pytest.raises(ReadonlyError):
        readonly_proxy["foo"] = "baz"

    another_proxied["foo"] = "baz"


def test_readonly_list_proxy():
    readonly_proxy = proxy(["foo", "bar"], readonly=True)

    assert isinstance(readonly_proxy, ReadonlyListProxy)

    with pytest.raises(ReadonlyError):
        readonly_proxy[0] = "baz"


def test_readonly_set_proxy():
    readonly_proxy = proxy({"foo", "bar"}, readonly=True)

    assert isinstance(readonly_proxy, ReadonlySetProxy)

    with pytest.raises(ReadonlyError):
        readonly_proxy.add("baz")


def test_nested_dict_proxy():
    data = {"foo": "bar", "baz": {"lorem": "ipsum"}}
    proxied = proxy(data)
    assert isinstance(proxied, DictProxy)
    assert isinstance(proxied["baz"], DictProxy)


def test_tuple():
    data = ({"foo": "bar"},)
    proxied = proxy(data)
    assert isinstance(proxied, tuple)
    assert isinstance(proxied[0], DictProxy)


def test_embedded_tuple():
    data = {"foo": ({"bar"},)}
    proxied = proxy(data)
    assert isinstance(proxied, DictProxy)
    assert isinstance(proxied["foo"][0], SetProxy)


def test_shallow_proxy():
    shallow_proxy = proxy({"foo": "bar", "baz": {"lorem": "ipsum"}}, shallow=True)
    assert isinstance(shallow_proxy, DictProxy)
    assert shallow_proxy.__shallow__

    deep_proxy = proxy(shallow_proxy)
    assert not deep_proxy.__shallow__


def test_non_hashable():
    # Should not be able to create a hash from a proxy
    with pytest.raises(TypeError):
        hash(proxy({}))

    # Should not be able to add a proxy to a set
    with pytest.raises(TypeError):
        _ = proxy({"set", proxy({})})

    # Should not be able to use a proxy as a key
    with pytest.raises(TypeError):
        _ = proxy({proxy({}): "value"})


def test_raise_on_existing_proxy():
    data = {"foo": "bar"}

    _ = Proxy(data)

    with pytest.raises(RuntimeError):
        _ = Proxy(data)


def test_list_equality():
    raw = [1, 2, 3]
    p = proxy(raw)
    assert isinstance(p, Proxy)
    assert isinstance(raw, list)
    assert p is not raw
    assert p == raw


def test_dict_equality():
    raw = {"foo": "bar"}
    p = proxy(raw)
    assert isinstance(p, Proxy)
    assert isinstance(raw, dict)
    assert p is not raw
    assert p == raw


def test_set_equality():
    raw = {"foo"}
    p = proxy(raw)
    assert isinstance(p, Proxy)
    assert isinstance(raw, set)
    assert p is not raw
    assert p == raw


def test_tuple_equality():
    raw = ("foo",)
    p = proxy(raw)
    assert not isinstance(p, Proxy)
    assert isinstance(raw, tuple)
    assert p is not raw
    assert p == raw
