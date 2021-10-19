import pytest

from observ.observables import (
    DictProxy,
    Proxy,
    proxy,
    proxy_db,
    ReadonlyDictProxy,
    ReadonlyError,
)


def test_proxy():
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

    assert obj_id not in proxy_db.db
    assert proxy_db.get_proxy(data) is None


def test_multiple_proxy_calls():
    data = {"foo": "bar"}

    first_proxy = proxy(data)
    second_proxy = proxy(data)
    third_proxy = proxy(second_proxy)

    assert first_proxy is second_proxy
    assert second_proxy is third_proxy


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
