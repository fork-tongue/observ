from observ import reactive, scheduler
from observ.watcher import watch_effect


def test_watch_effect():
    state = reactive({"count": 0})
    count_mirror = -1

    def bump():
        nonlocal count_mirror
        count_mirror = state["count"]
        state["other"] = state["count"]

    watcher = watch_effect(bump, sync=True)
    assert watcher.lazy is False

    assert state["count"] == 0
    assert count_mirror == 0

    state["count"] = 1

    assert state["count"] == 1
    assert count_mirror == 1


def test_watch_effect_scheduled(noop_request_flush):
    state = reactive({"count": 0})
    count_mirror = -1

    def bump():
        nonlocal count_mirror
        count_mirror = state["count"]

    _ = watch_effect(bump)

    assert state["count"] == 0
    assert count_mirror == 0

    state["count"] = 1
    assert state["count"] == 1
    assert count_mirror == 0

    scheduler.flush()

    assert state["count"] == 1
    assert count_mirror == 1


def test_watch_effect_recursion():
    state = reactive({"count": 0})
    count_mirror = -1

    def bump():
        nonlocal count_mirror
        count_mirror = state["count"]
        # Adjust the same value that triggerred the bump
        state["count"] += 1

    _ = watch_effect(bump, sync=True)
    assert state["count"] == 1
    assert count_mirror == 0


def test_watch_effect_scheduled_recursion(noop_request_flush):
    state = reactive({"count": 0})
    count_mirror = -1

    def bump():
        nonlocal count_mirror
        count_mirror = state["count"]
        # Adjust the same value that triggerred the bump
        state["count"] += 1

    _ = watch_effect(bump)

    # Bump should have bumped the version
    assert state["count"] == 1
    assert count_mirror == 0

    # Doesn't do anything
    scheduler.flush()

    assert state["count"] == 1
    assert count_mirror == 0

    # Still does not trigger the effect
    state["count"] += 1

    assert state["count"] == 2
    assert count_mirror == 0

    # But this should trigger it!
    scheduler.flush()

    assert state["count"] == 3
    assert count_mirror == 2
