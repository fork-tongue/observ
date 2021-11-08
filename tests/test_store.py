from unittest.mock import Mock

from observ import watch
from observ.store import computed, mutation, Store


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
        @computed(deep=True)
        def deep_items(self):
            return self.state["items"]

        @computed
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
