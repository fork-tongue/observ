import pytest

from observ import computed, reactive, to_raw, watch
from observ.observables import Proxy, ReadonlyError, StateModifiedError
from observ.watcher import WrongNumberOfArgumentsError


def test_usage_dict():
    a = reactive({"foo": "bar"})
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
    a = reactive({"foo": "bar"})
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
    a = reactive([1, 2])
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
    a = reactive({1, 2})
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


def test_usage_computed():
    a = reactive({"foo": 5, "bar": [6, 7, 8], "quux": 10, "quuz": {"a": 1, "b": 2}})
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
    a = reactive({"foo": 5, "bar": [6, 7, 8], "quux": 10, "quuz": {"a": 1, "b": 2}})

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
    a = reactive({"foo": [0, 1]})

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
    a = reactive({"foo": 0})
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


def test_dict_keys():
    state = reactive({"foo": {"bar": 5}})

    calls = []

    def _called(new):
        nonlocal calls
        calls.append(new)

    def _expr():
        i = 0
        for key in state:
            i += 1
        return i

    _ = watch(_expr, _called, sync=True, immediate=True, deep=True)

    assert len(calls) == 1

    state["baz"] = 1
    assert len(calls) == 2


def test_dict_values():
    state = reactive({"foo": {"bar": 5}})

    calls = []

    def _called(new):
        nonlocal calls
        calls.append(new)

    def _expr():
        for value in state.values():
            if value:
                return value

    _ = watch(_expr, _called, sync=True, immediate=True, deep=True)

    assert len(calls) == 1

    state["foo"]["bar"] += 1
    assert len(calls) == 2


def test_dict_items():
    state = reactive({"foo": {"bar": 5}})

    calls = []

    def _called(new):
        nonlocal calls
        calls.append(new)

    def _expr():
        for key, value in state.items():
            if key == "foo":
                return value

    _ = watch(_expr, _called, sync=True, immediate=True, deep=True)

    assert len(calls) == 1

    state["foo"]["bar"] += 1
    assert len(calls) == 2


def test_list_iter():
    state = reactive([{"b": 5}])

    calls = []

    def _called(new):
        nonlocal calls
        calls.append(new)

    def _expr():
        for x in state:
            return x["b"]

    _ = watch(_expr, _called, sync=True, immediate=True, deep=True)

    assert len(calls) == 1

    state[0]["b"] = 6
    assert len(calls) == 2


def test_list_reversed():
    state = reactive([{"b": 5}])

    calls = []

    def _called(new):
        nonlocal calls
        calls.append(new)

    def _expr():
        for x in reversed(state):
            return x["b"]

    _ = watch(_expr, _called, sync=True, immediate=True, deep=True)

    assert len(calls) == 1

    state[0]["b"] = 6
    assert len(calls) == 2


def test_isinstance():
    state = reactive(["a", {"b": 5}])

    calls = []

    def _called(new):
        nonlocal calls
        calls.append(new)

    def _expr():
        if isinstance(state[1], Proxy):
            return state[1]

    watcher = watch(_expr, _called, sync=True, immediate=True)

    assert len(calls) == 1
    assert isinstance(watcher.value, Proxy), type(watcher.value)


def test_reactive_in_reactive():
    state = reactive({"foo": 5})
    state["bar"] = reactive(["something", "else"])

    assert state["bar"][0] == "something"


def test_to_raw():
    state = reactive({"dict": {"key": 5}})
    state["list"] = reactive(["list", "item"])
    state["list"].append(reactive({"set"}))
    state["tuple"] = (reactive({"set", "bloeb"}), reactive({"dict": "value"}))

    raw = to_raw(state)

    assert isinstance(raw, dict)
    assert isinstance(raw["dict"], dict)
    assert isinstance(raw["dict"]["key"], int), type(raw["dict"]["key"])
    assert isinstance(raw["list"], list), type(raw["list"])
    assert isinstance(raw["list"][-1], set), type(raw["list"][-1])
    assert isinstance(raw["tuple"], tuple), type(raw["tuple"])
    assert isinstance(raw["tuple"][0], set), type(raw["tuple"][0])
    assert isinstance(raw["tuple"][1], dict), type(raw["tuple"][1])


def test_computed():
    a = reactive({"foo": 5})

    def _readonly_expr():
        return a["foo"] * 2

    computed_expr = computed(_readonly_expr)
    assert computed_expr() == 10

    def _expr_with_write():
        # Writing to the state during a computed
        # expression should raise a StateModifiedError
        # Trigger a key writer
        a["bar"] = a["foo"] * 2
        return a["foo"] * 2

    computed_expr = computed(_expr_with_write)
    with pytest.raises(StateModifiedError):
        _ = computed_expr()


def test_watch_computed():
    a = reactive([0])
    from observ.observables import ListProxy

    assert isinstance(a, ListProxy)

    @computed
    def _times_ten():
        # This next line should trigger the StateModifiedError
        # when the watcher is evaluated
        # Trigger a writer trap
        a.append(0)
        return a[0] * 10

    with pytest.raises(StateModifiedError):
        _ = watch(_times_ten, None, sync=True)

    a = reactive({"foo": "bar"})

    @computed
    def _comp_fail():
        # Trigger a key deleter trap
        a.pop()
        return a[0]

    with pytest.raises(StateModifiedError):
        _ = watch(_comp_fail, None, sync=True)

    @computed
    def _comp_fail():
        # Trigger a deleter trap
        a.clear()
        return a[0]

    with pytest.raises(StateModifiedError):
        _ = watch(_comp_fail, None, sync=True)
