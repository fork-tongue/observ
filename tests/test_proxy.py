import pytest

from observ import watch
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

    # Destroy the original proxy: without any proxy (or subscribed
    # watcher) left, the registry entry is removed right away, even
    # though `data` itself is still alive
    del wrapped_data

    assert obj_id not in proxy_db.db
    assert proxy_db.get_proxy(data) is None


def test_proxy_db_entry_kept_alive_by_watcher():
    state = proxy({"inner": {"count": 0}})
    inner_id = id(state.__target__["inner"])

    calls = []
    watcher = watch(
        lambda: state["inner"]["count"],
        lambda: calls.append(1),
        sync=True,
    )

    # No proxy for the inner dict is alive anymore (the one created
    # during evaluation was transient), but the watcher keeps the
    # registry entry alive through the deps it subscribed to, so a
    # mutation through a fresh proxy notifies the watcher
    assert inner_id in proxy_db.db

    state["inner"]["count"] += 1

    assert calls == [1]

    # Once the watcher is gone as well, the entry is released
    del watcher

    assert inner_id not in proxy_db.db


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


def test_dict_subclass_not_wrapped():
    class Custom(dict):
        pass

    raw = Custom(foo="bar")
    p = proxy(raw)
    assert not isinstance(p, Proxy)
    assert isinstance(raw, dict)
    assert p is raw


def test_list_subclass_not_wrapped():
    class Custom(list):
        pass

    raw = Custom([0, 1, 2])
    p = proxy(raw)
    assert not isinstance(p, Proxy)
    assert isinstance(raw, list)
    assert p is raw


def test_set_subclass_not_wrapped():
    class Custom(set):
        pass

    raw = Custom([1, 2, 3])
    p = proxy(raw)
    assert not isinstance(p, Proxy)
    assert isinstance(raw, set)
    assert p is raw


def test_proxy_is_slotted():
    some_dict = proxy({1: 1, 2: 2, 3: 3})
    assert isinstance(some_dict, DictProxy)
    some_list = proxy([1, 2, 3])
    assert isinstance(some_list, ListProxy)
    some_set = proxy({1, 2, 3})
    assert isinstance(some_set, SetProxy)

    with pytest.raises(
        AttributeError, match="'DictProxy' object has no attribute 'foo'"
    ):
        some_dict.foo = "foo"

    with pytest.raises(
        AttributeError, match="'ListProxy' object has no attribute 'foo'"
    ):
        some_list.foo = "foo"

    with pytest.raises(
        AttributeError, match="'SetProxy' object has no attribute 'foo'"
    ):
        some_set.foo = "foo"


def test_proxy_types_registered_without_extra_imports():
    """
    Importing just the top-level package must be enough to register
    the proxy types in TYPE_LOOKUP. Run in a fresh interpreter, since
    within the test suite the proxy modules are already imported
    directly by (other) test modules, which would mask a missing
    registration.
    """
    import subprocess
    import sys

    subprocess.run(
        [
            sys.executable,
            "-c",
            "from observ import reactive; assert type(reactive({})) is not dict",
        ],
        check=True,
    )


def test_proxy_flag_call_conventions():
    """
    The readonly and shallow flags resolve identically whether they
    are passed positionally or as keywords: every combination maps to
    the same (cached) proxy for the same target.
    """
    data = {"foo": "bar"}
    writable = proxy(data, readonly=False, shallow=False)
    readonly_proxy = proxy(data, readonly=True)
    shallow = proxy(data, shallow=True)
    readonly_shallow = proxy(data, readonly=True, shallow=True)

    # All four configurations are distinct proxies
    configs = (writable, readonly_proxy, shallow, readonly_shallow)
    assert len({id(p) for p in configs}) == 4

    # Positional calls resolve to the same proxies as keyword calls
    assert proxy(data, False, False) is writable
    assert proxy(data, True) is readonly_proxy
    assert proxy(data, False, True) is shallow
    assert proxy(data, True, True) is readonly_shallow

    assert writable.__readonly__ is False and writable.__shallow__ is False
    assert readonly_proxy.__readonly__ is True
    assert readonly_proxy.__shallow__ is False
    assert shallow.__readonly__ is False and shallow.__shallow__ is True
    assert readonly_shallow.__readonly__ is True
    assert readonly_shallow.__shallow__ is True


def test_readonly_proxy_construction_forces_readonly():
    """
    Constructing a Readonly* proxy class directly always yields a
    readonly proxy, whatever flags are passed, and the shallow flag
    still comes through.
    """
    for proxy_type, target in (
        (ReadonlyDictProxy, {"foo": "bar"}),
        (ReadonlyListProxy, ["foo"]),
        (ReadonlySetProxy, {"foo"}),
    ):
        readonly_proxy = proxy_type(target)
        assert readonly_proxy.__readonly__ is True
        assert readonly_proxy.__shallow__ is False

        # A passed readonly flag is ignored
        del readonly_proxy
        overridden = proxy_type(target, readonly=False)
        assert overridden.__readonly__ is True

        del overridden
        shallow = proxy_type(target, shallow=True)
        assert shallow.__readonly__ is True
        assert shallow.__shallow__ is True
