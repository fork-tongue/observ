from observ import reactive
from observ.watcher import watch_effect


def test_watch_effect():
    state = reactive({"count": 0})
    count_mirror = -1

    def bump():
        nonlocal count_mirror
        count_mirror = state["count"]

    watcher = watch_effect(bump, sync=True)
    assert watcher.lazy is False

    assert state["count"] == 0
    assert count_mirror == 0

    state["count"] = 1

    assert state["count"] == 1
    assert count_mirror == 1
