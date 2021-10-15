from observ.observables import Proxy, proxy, proxy_db


def test_proxy():
    data = {"foo": "bar"}
    obj_id = id(data)

    # Call proxy to wrap the data object
    wrapped_data = proxy(data)

    assert isinstance(wrapped_data, Proxy)
    assert obj_id in proxy_db.db
    assert wrapped_data.obj is data

    # Retrieve the proxy from the proxy_db
    referenced_proxy = proxy_db.get_proxy(data)

    assert referenced_proxy is wrapped_data
    assert referenced_proxy.obj is wrapped_data.obj

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
