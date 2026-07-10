"""
Traps mirror the call conventions of the plain container methods they
wrap: positional arguments are forwarded as-is, and keyword arguments
are only accepted where the plain method accepts them (list.sort;
dict.update takes arbitrary **kwargs). These tests pin down argument
positioning and resolution through the traps, and check that calls a
plain container rejects with a TypeError are also rejected on a proxy.
"""

from unittest.mock import Mock

import pytest

from observ import reactive, readonly, to_raw
from observ.traps import ReadonlyError


def test_dict_get_argument_positioning():
    obj = reactive({"a": 1})

    assert obj.get("a") == 1
    assert obj.get("missing") is None
    # The default is a positional argument, just like on a plain dict
    assert obj.get("missing", "default") == "default"

    # A nested default is run through proxy() like any other read
    nested = obj.get("missing", {"deep": True})
    assert nested["deep"] is True

    # Plain dict.get accepts no keyword arguments; neither does the trap
    with pytest.raises(TypeError):
        {}.get("a", default=1)
    with pytest.raises(TypeError):
        obj.get("a", default=1)
    # Calling get without arguments fails on both as well
    with pytest.raises(TypeError):
        {}.get()
    with pytest.raises(TypeError):
        obj.get()


def test_dict_update_argument_resolution():
    obj = reactive({"a": 1})
    mock = Mock()
    obj.__dep__.add_sub(mock)

    # A mapping argument
    obj.update({"b": 2})
    assert obj["b"] == 2
    mock.update.assert_called_once()

    # An iterable of key/value pairs
    mock.reset_mock()
    obj.update([("c", 3)])
    assert obj["c"] == 3
    mock.update.assert_called_once()

    # Keyword arguments only
    mock.reset_mock()
    obj.update(d=4)
    assert obj["d"] == 4
    mock.update.assert_called_once()

    # A mapping combined with keyword arguments; the keyword argument
    # wins for a duplicated key, just like on a plain dict
    mock.reset_mock()
    obj.update({"e": "positional", "f": 6}, e="keyword")
    assert obj["e"] == "keyword"
    assert obj["f"] == 6
    mock.update.assert_called_once()

    # More than one positional argument fails on both
    with pytest.raises(TypeError):
        {}.update({}, {})
    with pytest.raises(TypeError):
        obj.update({}, {})


def test_list_sort_keyword_arguments():
    obj = reactive([3, 1, 2])
    mock = Mock()
    obj.__dep__.add_sub(mock)

    # list.sort is the one wrapped method that takes keyword arguments
    obj.sort(key=lambda item: -item, reverse=True)
    assert to_raw(obj) == [1, 2, 3]
    mock.update.assert_called_once()

    # sort accepts no positional arguments, on either side
    with pytest.raises(TypeError):
        [].sort(lambda item: item)
    with pytest.raises(TypeError):
        obj.sort(lambda item: item)


def test_dict_setdefault_argument_positioning():
    obj = reactive({"a": 1})
    assert obj.setdefault("a", 99) == 1
    assert obj.setdefault("b", 2) == 2
    assert obj["b"] == 2

    # The default for a missing key comes back proxied
    nested = obj.setdefault("c", {"deep": True})
    assert nested["deep"] is True
    assert type(nested) is not dict

    # setdefault without a default, like on a plain dict
    assert obj.setdefault("d") is None

    # Plain dict.setdefault accepts no keyword arguments
    with pytest.raises(TypeError):
        {}.setdefault("a", default=1)
    with pytest.raises(TypeError):
        obj.setdefault("a", default=1)


def test_dict_pop_argument_positioning():
    obj = reactive({"a": 1})
    assert obj.pop("missing", "default") == "default"
    assert obj.pop("a") == 1
    with pytest.raises(KeyError):
        obj.pop("a")

    # Plain dict.pop accepts no keyword arguments
    with pytest.raises(TypeError):
        {}.pop("a", default=1)
    with pytest.raises(TypeError):
        obj.pop("a", default=1)


def test_list_multi_positional_arguments():
    obj = reactive([1, 2, 3, 2])

    # index takes optional start/stop positionally
    assert obj.index(2) == 1
    assert obj.index(2, 2) == 3
    assert obj.index(2, 2, 4) == 3

    # pop with and without an index
    assert obj.pop() == 2
    assert obj.pop(0) == 1
    assert to_raw(obj) == [2, 3]

    # insert requires both arguments
    with pytest.raises(TypeError):
        [].insert(0)
    with pytest.raises(TypeError):
        obj.insert(0)


def test_set_multi_positional_arguments():
    obj = reactive({1, 2})

    # These accept any number of positional arguments
    assert obj.union({3}, [4]) == {1, 2, 3, 4}
    assert obj.difference({1}, {2}) == set()
    assert obj.issubset({1, 2, 3})

    obj.update({3}, [4])
    assert to_raw(obj) == {1, 2, 3, 4}


def test_iterators_take_no_arguments():
    obj = reactive({"a": 1})
    # Plain dict iterator methods take no arguments; neither do the traps
    with pytest.raises(TypeError):
        {}.values("bogus")
    with pytest.raises(TypeError):
        obj.values("bogus")
    with pytest.raises(TypeError):
        {}.items("bogus")
    with pytest.raises(TypeError):
        obj.items("bogus")


def test_unexpected_keyword_arguments_raise_typeerror():
    """
    Calls that a plain container rejects with a TypeError are also
    rejected on a proxy.
    """
    plain_and_proxied = [
        ({"a": 1}, lambda d: d.keys(x=1)),
        ({"a": 1}, lambda d: d.popitem(x=1)),
        ({"a": 1}, lambda d: d.__getitem__("a", x=1)),
        ([1], lambda ls: ls.append(1, x=1)),
        ([1], lambda ls: ls.count(1, x=1)),
        ({1}, lambda s: s.add(1, x=1)),
    ]
    for target, call in plain_and_proxied:
        with pytest.raises(TypeError):
            call(target)
        with pytest.raises(TypeError):
            call(reactive(target))


def test_readonly_writes_raise_regardless_of_arguments():
    obj = readonly({"a": [1, 2]})
    with pytest.raises(ReadonlyError):
        obj.update({"b": 2})
    with pytest.raises(ReadonlyError):
        obj.update(b=2)
    with pytest.raises(ReadonlyError):
        obj.pop("a")
    with pytest.raises(ReadonlyError):
        obj["a"].sort(reverse=True)
