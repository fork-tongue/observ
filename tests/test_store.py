from unittest.mock import Mock

import pytest

from observ import watch
from observ.store import Store, computed, mutation


class CustomStore(Store):
    @mutation
    def bump_count(self):
        self.state["count"] += 1

    @computed
    def double(self):
        return self.state["count"] * 2


def test_store_undo_redo():
    store = CustomStore(state={"count": 0})
    assert store.state["count"] == 0
    assert not store.can_undo
    assert not store.can_redo

    store.bump_count()
    assert store.state["count"] == 1
    assert not store.can_redo

    store.undo()
    assert store.state["count"] == 0
    assert not store.can_undo
    assert store.can_redo

    store.redo()
    assert store.state["count"] == 1
    assert store.can_undo
    assert not store.can_redo

    store.bump_count()
    assert store.state["count"] == 2
    assert store.can_undo
    assert not store.can_redo

    store.undo()
    store.undo()
    assert store.state["count"] == 0
    assert not store.can_undo
    assert store.can_redo

    store.bump_count()
    assert store.can_undo
    assert not store.can_redo


def test_store_computed_methods():
    store = CustomStore(state={"count": 0})

    assert store.state["count"] == 0
    assert store.double == 0

    store.bump_count()

    assert store.state["count"] == 1
    assert store.double == 2


def test_store_undo_redo_unchanged_watcher():
    store = CustomStore(state={"count": 0, "foo": {}})
    watcher = watch(lambda: store.state["foo"], Mock(), sync=True)

    store.bump_count()
    assert store.state["count"] == 1
    watcher.callback.assert_not_called()

    store.undo()
    assert store.state["count"] == 0
    watcher.callback.assert_not_called()


def test_store_computed_deep():
    class DeepStore(Store):
        @computed
        def deep_items(self):
            return self.state["items"]

        @computed(deep=False)
        def shallow_items(self):
            return self.state["items"]

        @mutation
        def add_item(self, item):
            self.state["items"].append(item)

    store = DeepStore({"items": []})
    deep_watcher = watch(lambda: store.deep_items, Mock(), sync=True, deep=True)
    shallow_watcher = watch(lambda: store.shallow_items, Mock(), sync=True)

    store.add_item(3)
    shallow_watcher.callback.assert_not_called()
    deep_watcher.callback.assert_called_once()


def test_store_undo_redo_all_types():
    class SetStore(Store):
        @mutation
        def add(self, item):
            self.state["set"].add(item)

        @mutation
        def append(self, item):
            self.state["list"].append(item)

        @mutation
        def set(self, key, value):
            self.state["dict"][key] = value

    store = SetStore(
        {
            "set": {"a"},
            "list": ["a"],
            "dict": {"a": "b"},
        }
    )
    assert store.state["set"] == {"a"}
    assert store.state["list"] == ["a"]
    assert store.state["dict"] == {"a": "b"}

    store.add("b")
    assert store.state["set"] == {"a", "b"}
    store.undo()
    assert store.state["set"] == {"a"}

    store.append("b")
    assert store.state["list"] == ["a", "b"]
    store.undo()
    assert store.state["list"] == ["a"]

    store.set("b", "c")
    assert store.state["dict"] == {"a": "b", "b": "c"}
    store.undo()
    assert store.state["dict"] == {"a": "b"}


def test_store_empty_mutation_non_strict_store():
    class SimpleStore(Store):
        @mutation
        def update_count(self, count):
            self.state["count"] = count

    # Create a store with strict set to False
    store = SimpleStore({"count": 1}, strict=False)
    assert store.state["count"] == 1
    assert not store.can_undo

    # Update with the same number. This should
    # result in no change being recorded
    store.update_count(1)
    assert not store.can_undo

    # Check that if we do supply another number
    # that a change will actually be recorded
    store.update_count(2)
    assert store.can_undo


def test_store_empty_mutation_strict_store():
    class SimpleStore(Store):
        @mutation
        def update_count(self, count):
            self.state["count"] = count

    # Create a store with strict set to True
    # (is the default value for `strict` argument)
    store = SimpleStore({"count": 1})
    assert store.state["count"] == 1
    assert not store.can_undo

    # Update with the same number. This should
    # trigger a RuntimeError
    with pytest.raises(RuntimeError):
        store.update_count(1)
