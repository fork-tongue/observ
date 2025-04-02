from dataclasses import dataclass
from typing import Iterable
from unittest.mock import Mock

import pytest

from observ import computed, reactive, ref, to_raw, watch
from observ.list_proxy import ListProxy
from observ.proxy import Proxy
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


def test_dict_update_same_key():
    state = reactive({"foo": "bar"})
    called = 0

    def _expr():
        nonlocal called
        called += 1

    _ = watch(lambda: state["foo"], _expr, sync=True, immediate=True, deep=True)

    assert called == 1
    assert state["foo"] == "bar"

    state.update({"foo": "baz"})

    assert state["foo"] == "baz"
    assert called == 2


def test_dict_update_new_keys():
    state = reactive({"foo": "bar"})
    called = 0

    def _expr():
        nonlocal called
        called += 1

    _ = watch(lambda: state["foo"], _expr, sync=True, immediate=True, deep=True)

    assert called == 1
    assert state["foo"] == "bar"

    state.update({"foo": "baz", "bar": "foo"})

    assert state["foo"] == "baz"
    assert state["bar"] == "foo"
    assert called == 2

    state.update(foo="bar", baz="fool")

    assert state["foo"] == "bar"
    assert state["baz"] == "fool"
    assert called == 3

    state.update([("foo", "bas"), ("bat", "flat")])

    assert state["foo"] == "bas"
    assert state["bat"] == "flat"
    assert called == 4


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
        # expression should be OK and not cause recursion errors
        # Trigger a key writer
        a["bar"] = a["foo"] * 2
        return a["foo"] * 2

    computed_expr = computed(_expr_with_write)
    _ = computed_expr()


def test_watch_computed():
    a = reactive([0])

    assert isinstance(a, ListProxy)

    @computed
    def _times_ten():
        # This next line modifies state
        # when the watcher is evaluated
        # Trigger a writer trap
        a.append(0)
        return a[0] * 10

    _ = watch(_times_ten, None, sync=True)

    a = reactive({"foo": "bar"})

    @computed
    def _comp_fail():
        # Trigger a key deleter trap
        a.pop("foo")
        return a.get("foo")

    _ = watch(_comp_fail, None, sync=True)

    a = reactive({"foo": "bar"})

    @computed
    def _comp_fail():
        # Trigger a deleter trap
        a.clear()
        return a.get("foo")

    _ = watch(_comp_fail, None, sync=True)


def test_computed_deep():
    a = reactive({"items": []})

    @computed(deep=False)
    def items():
        return a["items"]

    @computed
    def items_deep():
        return a["items"]

    shallow_watcher = watch(items, Mock(), sync=True)
    deep_watcher = watch(items_deep, Mock(), sync=True)
    shallow_watcher.callback.assert_not_called()
    deep_watcher.callback.assert_not_called()

    a["items"].append(3)
    shallow_watcher.callback.assert_not_called()
    deep_watcher.callback.assert_called_once()

    a["items"] = []
    shallow_watcher.callback.assert_called_once()


def test_watch_real_deep():
    a = reactive({"scene": {"objects": {"camera": {"position": [0, 0, 0]}}}})

    watcher = watch(
        lambda: a["scene"],
        Mock(),
        sync=True,
        deep=True,
    )

    watcher.callback.assert_not_called()
    a["scene"]["objects"]["camera"]["position"] = [0, 1, 0]
    watcher.callback.assert_called_once()

    assert isinstance(a["scene"]["objects"]["camera"]["position"], ListProxy)
    assert not a["scene"]["objects"]["camera"]["position"].__shallow__

    watcher.callback = Mock()
    a["scene"]["objects"]["camera"]["position"][1] = 2
    watcher.callback.assert_called_once()


def test_deeply_nested_to_raw():
    """
    In this test a dictionary is created that contains a proxy in one of its values.
    We're writing it to a key on a DictProxy. This means the DictProxy actually
    becomes part of the datastructure.
    """

    def obj_contains_proxy(obj):
        if not isinstance(obj, Iterable):
            return False
        if isinstance(obj, Proxy):
            return True
        for x in obj.values() if hasattr(obj, "values") else obj:
            if obj_contains_proxy(x):
                return True
        return False

    a = reactive({"scene": {"objects": {"camera": {"position": [0, 0, 0]}}}})
    assert obj_contains_proxy(a)
    assert obj_contains_proxy(a["scene"])

    mesh_w_nested_proxy = {
        "position": a["scene"]["objects"]["camera"]["position"],
    }
    assert isinstance(mesh_w_nested_proxy, dict)
    assert obj_contains_proxy(mesh_w_nested_proxy)

    a["scene"]["objects"]["mesh"] = mesh_w_nested_proxy
    assert isinstance(a["scene"]["objects"]["mesh"], Proxy)
    assert isinstance(a["scene"]["objects"]["mesh"]["position"], Proxy)

    # this assertion confirms that the problematic case has been created
    # in other words, that the test was setup properly
    assert obj_contains_proxy(a.__target__)

    # check if we can still get a reference to the raw object using to_raw
    raw_pos = to_raw(a["scene"]["objects"]["mesh"]["position"])
    assert isinstance(raw_pos, list)

    # check what happens when we to_raw the root state
    raw_a = to_raw(a)
    assert not obj_contains_proxy(raw_a)


def test_usage_class_instances():
    class Foo:
        def __init__(self):
            self.foo = 5

        def __len__(self):
            return self.foo

    a = reactive([1, 2, Foo()])
    called = 0

    def _callback():
        nonlocal called
        called += 1

    # watch the whole of the state, deep
    watcher = watch(lambda: a, _callback, sync=True, deep=True)
    assert not watcher.dirty
    assert called == 0

    # change the length
    a.append(3)
    assert called == 1

    # write a key
    a[1] = 3
    assert called == 2

    # write to a class attribute
    a[2].foo = 10
    assert called == 3

    # magic methods are supported
    foo_len = computed(lambda: len(a[2]))
    assert foo_len() == 10


def test_usage_dataclass():
    @dataclass
    class Foo:
        bar: int

    a = reactive(Foo(bar=5))
    called = 0

    def _callback():
        nonlocal called
        called += 1

    watcher = watch(lambda: a, _callback, sync=True, deep=True)
    assert not watcher.dirty
    assert called == 0

    # write something
    a.bar = 10
    assert called == 1

    # magic methods are supported
    str_foo = computed(lambda: repr(a))
    assert str_foo() == "test_usage_dataclass.<locals>.Foo(bar=10)"


def test_watch_get_non_existing():
    a = reactive({})

    def result():
        return a.get("foo", False)

    watcher = watch(result, None, sync=True)

    assert watcher.value is False

    a["foo"] = True

    assert watcher.value is True


def test_watch_get_non_existing_dict():
    a = reactive(dict())

    def result():
        return "foo" in a

    watcher = watch(result, None, sync=True)

    assert watcher.value is False

    a["foo"] = "bar"

    assert watcher.value is True


def test_watch_get_non_existing_set():
    a = reactive(set())

    def result():
        return "foo" in a

    watcher = watch(result, None, sync=True)

    assert watcher.value is False

    a.add("foo")

    assert watcher.value is True


def test_watch_get_non_existing_list():
    a = reactive(list())

    def result():
        return "foo" in a

    watcher = watch(result, None, sync=True)

    assert watcher.value is False

    a.append("foo")

    assert watcher.value is True


def test_watch_setdefault_new_key():
    a = reactive(dict())
    cb = Mock()

    watcher = watch(lambda: a, cb, sync=True, deep=True)  # noqa: F841

    some_list = a.setdefault("foo", [])
    assert cb.call_count == 1

    some_list.append("bar")
    assert cb.call_count == 2


def test_watch_setdefault_existing_key():
    a = reactive({"foo": []})
    cb = Mock()

    watcher = watch(lambda: a, cb, sync=True, deep=True)  # noqa: F841

    some_list = a.setdefault("foo", [])
    assert cb.call_count == 0

    some_list.append("bar")
    assert cb.call_count == 1


def test_watch_module_does_not_raise():
    """Check that having modules and classes in the reactive state
    doesn't fail the deep traversal"""
    a = reactive({"foo": pytest, "bar": WrongNumberOfArgumentsError})
    cb = Mock()

    watcher = watch(lambda: a, cb, sync=True, deep=True)  # noqa: F841

    assert cb.call_count == 0

    a["baz"] = "foo"
    assert cb.call_count == 1


def test_use_weird_types_as_value():
    # TypeError: bad argument type for built-in operation
    # Might happen with types that can't be compare to None
    # Problem first encountered with PySide6.QtCore.Qt.ItemFlags object
    class Foo(int):
        """Custom class that can't be compare to None"""

        def __eq__(self, other):
            return not (other < self or other > self)

        def __ne__(self, other):
            return not self.__eq__(other)

    foo = Foo(3)
    comparison = None

    assert foo == 3
    assert foo != 4
    assert foo != 2

    # Check that comparing with a None value raises TypeError
    with pytest.raises(TypeError):
        foo != comparison

    a = reactive(dict())
    a["foo"] = Foo(3)


def test_watch_reactive_object():
    a = reactive({"foo": "foo"})
    cb = Mock()

    watcher = watch(  # noqa: F841
        a,
        cb,
        immediate=False,
        sync=True,
    )

    assert cb.call_count == 0

    a["foo"] = "bar"

    assert cb.call_count == 1


def test_watch_list_of_reactive_objects():
    a = reactive({"foo": "foo"})
    b = reactive(["bar"])
    cb = Mock()

    watcher = watch(  # noqa: F841
        [a, b],
        cb,
        immediate=False,
        sync=True,
    )

    assert cb.call_count == 0

    a["foo"] = "bar"

    assert cb.call_count == 1

    b.append("foo")

    assert cb.call_count == 2


def test_usage_ref():
    counter = ref(0)
    called = 0
    values = ()

    def _callback(new, old):
        nonlocal called
        nonlocal values
        called += 1
        values = (new, old)

    watcher = watch(lambda: counter["value"], _callback, sync=True)

    assert not watcher.dirty
    assert called == 0
    counter["value"] += 1
    assert called == 1
    assert values[0] == 1
    assert values[1] == 0
