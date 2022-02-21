from patchdiff import iapply

from observ import reactive, watch
from observ.dep import Path


def test_shallow_list_ops():
    a = reactive([])
    b = []

    last_ops = None

    def callback(new, old, ops):
        nonlocal last_ops
        last_ops = ops

    _ = watch(lambda: a, callback, sync=True, deep=True)

    a.append(1)
    assert len(last_ops) == 1
    assert last_ops[0]["op"] == "add"
    assert last_ops[0]["value"] == 1
    assert last_ops[0]["path"].tokens == ["-"]
    iapply(b, last_ops)
    assert a == b

    a.remove(1)
    assert len(last_ops) == 1
    assert last_ops[0]["op"] == "remove"
    assert last_ops[0]["path"].tokens == [0]
    iapply(b, last_ops)
    assert a == b


def test_shallow_dict_ops():
    a = reactive({})
    b = {}

    last_ops = None

    def callback(new, old, ops):
        nonlocal last_ops
        last_ops = ops

    _ = watch(lambda: a, callback, sync=True, deep=True)

    a[0] = 0
    assert len(last_ops) == 1
    assert last_ops[0]["op"] == "add"
    assert last_ops[0]["value"] == 0
    assert last_ops[0]["path"].tokens == [0]
    iapply(b, last_ops)
    assert a == b

    a[0] = 1
    assert len(last_ops) == 1
    assert last_ops[0]["op"] == "replace"
    assert last_ops[0]["value"] == 1
    assert last_ops[0]["path"].tokens == [0]
    iapply(b, last_ops)
    assert a == b

    del a[0]
    assert len(last_ops) == 1
    assert last_ops[0]["op"] == "remove"
    assert last_ops[0]["path"].tokens == [0]
    iapply(b, last_ops)
    assert a == b

    a.update(a=0)
    assert len(last_ops) == 1
    assert last_ops[0]["op"] == "add"
    assert last_ops[0]["value"] == 0
    assert last_ops[0]["path"].tokens == ["a"]
    iapply(b, last_ops)
    assert a == b


def test_deep_dict_ops():
    a = reactive({"a": {}})
    c = reactive({"b": [1]})
    b = {"a": {"b": 0}}

    last_ops = None

    def callback(new, old, ops):
        nonlocal last_ops
        last_ops = ops

    _ = watch(lambda: a, callback, sync=True, deep=True)

    a["a"]["b"] = 0
    assert len(last_ops) == 1
    assert last_ops[0]["op"] == "add"
    assert last_ops[0]["value"] == 0
    assert last_ops[0]["path"].tokens == ["a", "b"]
    iapply(b, last_ops)
    assert a == b

    # TODO: how to figure out which scope we are???
    assert a["a"]
    assert c["b"] == [1]

    a["a"]["b"] = 1
    assert len(last_ops) == 1
    assert last_ops[0]["op"] == "replace"
    assert last_ops[0]["value"] == 1
    assert last_ops[0]["path"].tokens == ["a", "b"]
    iapply(b, last_ops)
    assert a == b


def test_deep_dict_combined_ops():
    a = reactive({"a": {"b": {"c": {"d": [{"a": 0}]}}}})
    b = {"a": {"b": {"c": {"d": [{"a": 0}]}}}}

    last_ops = None
    path = None

    def callback(new, old, ops):
        nonlocal last_ops
        nonlocal path
        last_ops = ops
        path = [p for _, p in Path.stack.copy()]

    _ = watch(lambda: a, callback, sync=True, deep=True)

    a["a"]["b"]["c"]["d"][0]["a"] = 1
    assert path == ["a", "b", "c", "d", 0]
    assert len(last_ops) == 1
    assert last_ops[0]["op"] == "replace"
    assert last_ops[0]["value"] == 1
    assert last_ops[0]["path"].tokens == ["a", "b", "c", "d", 0, "a"]
    iapply(b, last_ops)
    assert a == b


# TODO: add test for watchers that watch a specific path within the reactive data


def test_shallow_set_ops():
    a = reactive(set())
    b = set()

    last_ops = None

    def callback(new, old, ops):
        nonlocal last_ops
        last_ops = ops

    _ = watch(lambda: a, callback, sync=True, deep=True)

    a.add("a")
    assert len(last_ops) == 1
    assert last_ops[0]["op"] == "add"
    assert last_ops[0]["path"].tokens == ["-"]
    assert last_ops[0]["value"] == "a"
    iapply(b, last_ops)
    assert a == b

    a.remove("a")
    assert len(last_ops) == 1
    assert last_ops[0]["op"] == "remove"
    assert last_ops[0]["path"].tokens == ["a"]
    iapply(b, last_ops)
    assert a == b
