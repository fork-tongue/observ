from unittest.mock import Mock

import pytest

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


@pytest.mark.xfail(reason="deepcopy is used to restore state")
def test_store_undo_redo_unchanged_watcher():
    store = CustomStore(state={"count": 0, "foo": {}})
    mock = Mock()
    _ = watch(lambda: store.state["foo"], mock, sync=True)

    store.bump_count()
    assert store.state["count"] == 1
    mock.assert_not_called()

    store.undo()
    assert store.state["count"] == 0
    mock.assert_not_called()
