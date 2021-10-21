import gc

import pytest

from observ.observables import (
    DictProxy,
    ListProxy,
    Proxy,
    proxy,
    proxy_db,
    ReadonlyDictProxy,
    ReadonlyError,
    SetProxy,
)


def test_proxy_lifecycle():
    data = {"foo": "bar"}
    obj_id = id(data)

    # Call proxy to wrap the data object
    wrapped_data = proxy(data)

    assert isinstance(wrapped_data, Proxy)
    assert obj_id in proxy_db.db
    assert wrapped_data.target is data

    # Retrieve the proxy from the proxy_db
    referenced_proxy = proxy_db.get_proxy(data)

    assert referenced_proxy is wrapped_data
    assert referenced_proxy.target is wrapped_data.target

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
    obj_id = id(wrapped_data.target)

    assert isinstance(wrapped_data, Proxy)
    assert obj_id in proxy_db.db
    # assert wrapped_data.target is data

    # Retrieve the proxy from the proxy_db
    referenced_proxy = proxy_db.get_proxy(wrapped_data.target)

    assert referenced_proxy is wrapped_data
    assert referenced_proxy.target is wrapped_data.target

    # Destroy the second proxy
    del referenced_proxy

    assert obj_id in proxy_db.db
    assert proxy_db.get_proxy(wrapped_data.target) is not None

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
