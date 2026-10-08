"""
Replacing a container with an equal but different container is a change.

Watchers subscribe to the deps of the objects they read. If a write
replaces such an object without notifying (because the new object is
equal to the old one), the watchers are not re-run, so they stay
subscribed to the old, now detached object. Changes to the new object
are then never picked up.
"""

from observ import reactive, scheduler, watch_effect


class Tracker:
    """Records every run of a sync watch_effect on the given function."""

    def __init__(self, fn):
        self.values = []
        self.watcher = watch_effect(lambda: self.values.append(fn()), sync=True)

    @property
    def runs(self):
        return len(self.values)


def test_dict_setitem_equal_dict():
    state = reactive({"item": {"text": "A"}})
    tracker = Tracker(lambda: state["item"]["text"])
    old = state["item"]

    state["item"] = {"text": "A"}
    assert tracker.runs == 2

    state["item"]["text"] = "B"
    assert tracker.values[-1] == "B"

    # The old object is detached and no longer a dependency
    runs = tracker.runs
    old["text"] = "C"
    assert tracker.runs == runs


def test_dict_setitem_equal_list():
    state = reactive({"items": [1, 2]})
    tracker = Tracker(lambda: list(state["items"]))

    state["items"] = [1, 2]
    state["items"].append(3)
    assert tracker.values[-1] == [1, 2, 3]


def test_dict_setitem_equal_set():
    state = reactive({"tags": {"a"}})
    tracker = Tracker(lambda: set(state["tags"]))

    state["tags"] = {"a"}
    state["tags"].add("b")
    assert tracker.values[-1] == {"a", "b"}


def test_dict_setitem_equal_nested_in_tuple():
    state = reactive({"pair": ({"text": "A"}, 1)})
    tracker = Tracker(lambda: state["pair"][0]["text"])

    state["pair"] = ({"text": "A"}, 1)
    state["pair"][0]["text"] = "B"
    assert tracker.values[-1] == "B"


def test_dict_setitem_equal_nested_in_nested_tuple():
    state = reactive({"pair": (({"text": "A"},), 1)})
    tracker = Tracker(lambda: state["pair"][0][0]["text"])

    state["pair"] = (({"text": "A"},), 1)
    state["pair"][0][0]["text"] = "B"
    assert tracker.values[-1] == "B"


def test_dict_update_equal_dict():
    state = reactive({"item": {"text": "A"}})
    tracker = Tracker(lambda: state["item"]["text"])

    state.update({"item": {"text": "A"}})
    state["item"]["text"] = "B"
    assert tracker.values[-1] == "B"


def test_scheduled_watcher_equal_dict(noop_request_flush):
    state = reactive({"item": {"text": "A"}})
    values = []
    watcher = watch_effect(lambda: values.append(state["item"]["text"]))  # noqa: F841
    assert values == ["A"]

    # Both writes happen before the flush, so the watcher runs once
    state["item"] = {"text": "A"}
    state["item"]["text"] = "B"
    scheduler.flush()
    assert values == ["A", "B"]

    # And across separate flushes
    state["item"] = {"text": "B"}
    scheduler.flush()
    state["item"]["text"] = "C"
    scheduler.flush()
    assert values == ["A", "B", "B", "C"]


def test_list_setitem_equal_dict():
    state = reactive([{"text": "A"}])
    tracker = Tracker(lambda: state[0]["text"])

    state[0] = {"text": "A"}
    state[0]["text"] = "B"
    assert tracker.values[-1] == "B"


def test_list_setitem_slice_equal_dicts():
    state = reactive([{"text": "A"}, {"text": "B"}])
    tracker = Tracker(lambda: [item["text"] for item in state])

    state[:] = [{"text": "A"}, {"text": "B"}]
    state[1]["text"] = "C"
    assert tracker.values[-1] == ["A", "C"]


def test_list_reverse_equal_dicts():
    first, second = {"text": "A"}, {"text": "A"}
    state = reactive([first, second])
    tracker = Tracker(lambda: state[0]["text"])

    # The list is equal after reversing, but index 0 is another object
    state.reverse()
    assert state.__target__[0] is second

    state[0]["text"] = "B"
    assert tracker.values[-1] == "B"


def test_list_sort_equal_dicts():
    first, second = {"text": "A"}, {"text": "A"}
    state = reactive([first, second])
    tracker = Tracker(lambda: state[0]["text"])

    state.sort(key=lambda item: 0 if item is second else 1)
    assert state.__target__[0] is second

    state[0]["text"] = "B"
    assert tracker.values[-1] == "B"


# The tests below guard against notifying too eagerly


def test_dict_setitem_equal_plain_values_do_not_notify():
    state = reactive({"number": 1000, "text": "hello"})
    tracker = Tracker(lambda: (state["number"], state["text"]))

    # Equal, but (in CPython) different objects
    state["number"] = int("1000")
    state["text"] = "".join(["hel", "lo"])
    assert tracker.runs == 1


def test_dict_setitem_equal_tuple_notifies():
    # Only plain values are compared by equality, tuples by identity
    state = reactive({"position": (1.0, 2.0)})
    tracker = Tracker(lambda: state["position"])

    state["position"] = (float("1"), float("2"))
    assert tracker.runs == 2


def test_dict_setitem_same_container_does_not_notify():
    state = reactive({"item": {"text": "A"}})
    tracker = Tracker(lambda: state["item"]["text"])

    # Assigning the proxy of the current value is not a change
    state["item"] = state["item"]
    assert tracker.runs == 1

    # And the dependency is still intact
    state["item"]["text"] = "B"
    assert tracker.values[-1] == "B"


def test_list_setitem_same_container_does_not_notify():
    state = reactive([{"text": "A"}])
    tracker = Tracker(lambda: state[0]["text"])

    state[0] = state[0]
    state[:] = list(state)
    state.reverse()
    assert tracker.runs == 1
