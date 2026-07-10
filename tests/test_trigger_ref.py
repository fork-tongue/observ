from unittest.mock import Mock

import pytest

from observ import (
    computed,
    readonly,
    shallow_reactive,
    trigger_ref,
    watch,
    watch_effect,
)


def test_trigger_ref_shallow_key_watcher():
    state = shallow_reactive({"value": {"count": 0}})
    watcher = watch(lambda: state["value"], Mock(), sync=True)

    # Deep mutations bypass a shallow proxy, so no watcher fires
    state["value"]["count"] = 1
    watcher.callback.assert_not_called()

    trigger_ref(state)
    watcher.callback.assert_called_once()


def test_trigger_ref_notifies_dep_and_keydeps():
    state = shallow_reactive({"items": [1]})
    keyed = watch(lambda: state["items"], Mock(), sync=True)
    container = watch(lambda: dict(state.items()), Mock(), sync=True)

    trigger_ref(state)

    keyed.callback.assert_called_once()
    container.callback.assert_called_once()


def test_trigger_ref_watch_effect():
    state = shallow_reactive({"value": [1, 2]})
    lengths = []
    watcher = watch_effect(lambda: lengths.append(len(state["value"])), sync=True)

    assert lengths == [2]

    state["value"].append(3)
    assert lengths == [2]

    trigger_ref(state)
    assert lengths == [2, 3]

    assert watcher.active


def test_trigger_ref_computed():
    state = shallow_reactive({"data": {"count": 1}})

    @computed
    def doubled():
        return state["data"]["count"] * 2

    assert doubled() == 2

    state["data"]["count"] = 3
    # The computed doesn't know its (shallow) dependency changed
    assert doubled() == 2

    trigger_ref(state)
    assert doubled() == 6


def test_trigger_ref_shallow_list():
    items = shallow_reactive([{"a": 0}])
    watcher = watch(lambda: items[0], Mock(), sync=True)

    items[0]["a"] = 1
    watcher.callback.assert_not_called()

    trigger_ref(items)
    watcher.callback.assert_called_once()


def test_trigger_ref_through_readonly_view():
    state = shallow_reactive({"data": {"x": 0}})
    view = readonly(state)
    watcher = watch(lambda: view["data"], Mock(), sync=True)

    state["data"]["x"] = 1
    watcher.callback.assert_not_called()

    # All proxies for the same target share their deps, so triggering
    # any view notifies watchers on all of them
    trigger_ref(view)
    watcher.callback.assert_called_once()


def test_trigger_ref_plain_value_unchanged():
    # Callbacks that watch a plain (non-container) value only fire
    # when that value actually differs from the previous evaluation
    state = shallow_reactive({"value": 0})
    watcher = watch(lambda: state["value"], Mock(), sync=True)

    trigger_ref(state)
    watcher.callback.assert_not_called()

    # But the watched function is re-evaluated, so effects do re-run
    reads = []
    effect = watch_effect(lambda: reads.append(state["value"]), sync=True)
    assert reads == [0]
    trigger_ref(state)
    assert reads == [0, 0]

    assert effect.active


def test_trigger_ref_requires_proxy():
    with pytest.raises(TypeError):
        trigger_ref({"value": 1})

    with pytest.raises(TypeError):
        trigger_ref(None)


def test_trigger_ref_no_watchers():
    # Triggering a proxy nobody watches is a no-op
    state = shallow_reactive({"value": 1})
    trigger_ref(state)
