import pytest

from observ import computed, observe, watch
from observ.watcher import WrongNumberOfArgumentsError


def test_usage_dict():
    a = observe({"foo": "bar"})
    called = 0
    values = ()

    def _callback(new, old):
        nonlocal called
        nonlocal values
        called += 1
        values = (new, old)

    watcher = watch(lambda: a["foo"], _callback, sync=True)

    assert not watcher.dirty
    assert called == 0
    a["foo"] = "baz"
    assert called == 1
    assert values[0] == "baz"
    assert values[1] == "bar"


def test_usage_dict_new_key():
    a = observe({"foo": "bar"})
    called = 0

    def _callback(new, old):
        nonlocal called
        called += 1

    watcher = watch(lambda: len(a), _callback, sync=True)

    assert not watcher.dirty
    assert called == 0
    a["quuz"] = "quur"
    assert called == 1
    assert len(a) == 2
    assert a["quuz"] == "quur"


def test_usage_list():
    a = observe([1, 2])
    called = 0

    def _callback():
        nonlocal called
        called += 1

    watcher = watch(lambda: len(a), _callback, sync=True)
    assert not watcher.dirty
    assert called == 0
    a.append(3)
    assert called == 1
    assert len(a) == 3


def test_usage_set():
    a = observe({1, 2})
    called = 0

    def _callback():
        nonlocal called
        called += 1

    watcher = watch(lambda: len(a), _callback, sync=True)
    assert not watcher.dirty
    assert called == 0
    a.add(3)
    assert called == 1
    assert len(a) == 3


def test_usage():
    a = observe({"foo": 5, "bar": [6, 7, 8], "quux": 10, "quuz": {"a": 1, "b": 2}})
    execute_count = 0

    def bla():
        nonlocal execute_count
        execute_count += 1
        multi = 0
        if a["quux"] == 10:
            multi = a["foo"] * 5
        else:
            multi = a["bar"][-1] * 5
        return multi * a["quuz"]["b"]

    computed_bla = computed(bla)
    assert computed_bla() == 50
    assert computed_bla() == 50
    assert execute_count == 1
    a["quux"] = 25
    assert computed_bla() == 80
    assert computed_bla() == 80
    assert execute_count == 2
    a["quuz"]["b"] = 3
    assert computed_bla() == 120
    assert computed_bla() == 120
    assert execute_count == 3

    @computed
    def bla2():
        nonlocal execute_count
        execute_count += 1
        return a["foo"] * computed_bla()

    assert bla2() == 600
    assert bla2() == 600
    assert execute_count == 4
    a["quuz"]["b"] = 4
    assert bla2() == 800
    assert bla2() == 800
    assert execute_count == 6

    called = 0

    def _callback():
        nonlocal called
        called += 1

    watcher = watch(lambda: a["quuz"], _callback, sync=True, deep=True, immediate=False)
    assert not watcher.dirty
    assert watcher.value == a["quuz"]
    assert len(watcher._deps) > 1
    assert called == 0
    a["quuz"]["b"] = 3
    assert not watcher.dirty
    assert called == 1

    assert computed_bla() == 120
    assert execute_count == 7
    assert not computed_bla.__watcher__.dirty
    a["bar"].extend([9, 10])
    assert computed_bla.__watcher__.dirty
    assert computed_bla() == 150
    assert execute_count == 8


def test_watch_immediate():
    a = observe({"foo": 5, "bar": [6, 7, 8], "quux": 10, "quuz": {"a": 1, "b": 2}})

    called = 0

    def _callback(old_value, new_value):
        nonlocal called
        called += 1

    watcher = watch(lambda: a["quuz"], _callback, sync=True, deep=True, immediate=True)
    assert not watcher.dirty
    assert watcher.value == a["quuz"]
    assert len(watcher._deps) > 1
    assert called == 1
    a["quuz"]["b"] = 3
    assert not watcher.dirty
    assert called == 2


def test_usage_deep_vs_non_deep():
    a = observe({"foo": [0, 1]})

    non_deep_called = 0

    def _non_deep_callback(new):
        nonlocal non_deep_called
        non_deep_called += 1

    deep_called = 0

    def _deep_callback():
        nonlocal deep_called
        deep_called += 1

    watcher = watch(lambda: a["foo"], _non_deep_callback, sync=True)
    deep_watcher = watch(lambda: a["foo"], _deep_callback, sync=True, deep=True)
    assert not watcher.dirty
    assert not deep_watcher.dirty
    assert non_deep_called == 0
    a["foo"].append(1)
    assert non_deep_called == 0
    assert deep_called == 1


def test_callback_signatures():
    a = observe({"foo": 0})
    called = 0

    def empty_callback():
        nonlocal called
        called += 1

    watcher = watch(lambda: a["foo"], empty_callback, sync=True, immediate=True)
    assert called == 1

    def simple_callback(value):
        nonlocal called
        called += 1

    watcher = watch(lambda: a["foo"], simple_callback, sync=True, immediate=True)
    assert called == 2

    def full_callback(new, old):
        nonlocal called
        called += 1

    watcher = watch(lambda: a["foo"], full_callback, sync=True, immediate=True)
    assert called == 3

    def too_complex_callback(new, old, other):
        nonlocal called
        called += 1

    # Test specifically for WrongNumberOfArgumentsError
    with pytest.raises(WrongNumberOfArgumentsError):
        watcher = watch(
            lambda: a["foo"], too_complex_callback, sync=True, immediate=True
        )
    assert called == 3

    # This method accepts all kinds of signatures
    # but raises a TypeError within the callback
    def method_raises_type_error(*args):
        nonlocal called
        called += 1
        empty_callback(0)

    watcher = None
    # This should raise a TypeError specifically
    with pytest.raises(TypeError) as e:
        watcher = watch(  # noqa: F841
            lambda: a["foo"], method_raises_type_error, sync=True, immediate=True
        )
    assert called == 4
    assert not isinstance(e, WrongNumberOfArgumentsError)
