import pytest

from observ import reactive, scheduler, watch


def test_no_flush_handler():
    """
    Test if we get a ValueError when no flush request handler is registered
    """
    state = reactive({"foo": 5, "bar": 6})
    calls = 0

    def cb(new, old):
        nonlocal calls
        calls += 1

    watcher = watch(lambda: state["foo"], cb)  # noqa: F841

    with pytest.raises(ValueError, match="No flush request handler registered"):
        state["foo"] += 1


def test_flush(noop_request_flush):
    """
    Test if flush works
    """
    state = reactive({"foo": 5, "bar": 6})
    calls = 0

    def cb(new, old):
        nonlocal calls
        calls += 1

    watcher = watch(lambda: state["foo"], cb)  # noqa: F841

    state["foo"] += 1

    assert len(scheduler._queue) == 1
    assert len(scheduler._queue_indices) == 1
    assert calls == 0

    scheduler.flush()

    assert len(scheduler._queue) == 0
    assert len(scheduler._queue_indices) == 0
    assert calls == 1


def test_cycle_expression(noop_request_flush):
    """
    Test if we can detect an infinite update cycle caused by
    the watch expression
    """
    state = reactive({"foo": 5, "bar": 6})
    calls = 0

    def exp():
        return state["foo"]

    def cb(new, old):
        state["foo"] += 1
        nonlocal calls
        calls += 1

    watcher = watch(exp, cb)  # noqa: F841

    state["foo"] += 1

    assert len(scheduler._queue) == 1
    assert len(scheduler._queue_indices) == 1
    assert calls == 0

    with pytest.raises(RecursionError):
        scheduler.flush()


def test_cycle_callback(noop_request_flush):
    """
    Test if we can detect an infinite update cycle caused
    by a callback
    """
    state = reactive({"foo": 5, "bar": 6})
    calls = 0

    def exp():
        return state["foo"]

    def cb(new, old):
        nonlocal calls
        calls += 1
        state["foo"] += 1

    watcher = watch(exp, cb)  # noqa: F841

    state["foo"] += 1

    assert len(scheduler._queue) == 1
    assert len(scheduler._queue_indices) == 1
    assert calls == 0

    with pytest.raises(RecursionError):
        scheduler.flush()


def test_queue_growth(noop_request_flush):
    """
    Test if a flush also handles watchers that are triggered
    during the flush
    """
    state = reactive({"foo": 5, "bar": 6})
    calls_1 = 0
    calls_2 = 0

    def cb_1(new, old):
        nonlocal calls_1
        calls_1 += 1
        state["bar"] += 1

    def cb_2(new, old):
        nonlocal calls_2
        calls_2 += 1

    watcher_1 = watch(lambda: state["foo"], cb_1)  # noqa: F841
    watcher_2 = watch(lambda: state["bar"], cb_2)  # noqa: F841

    state["foo"] += 1

    assert len(scheduler._queue) == 1
    assert len(scheduler._queue_indices) == 1
    assert calls_1 == 0
    assert calls_2 == 0

    scheduler.flush()

    assert len(scheduler._queue) == 0
    assert len(scheduler._queue_indices) == 0
    assert calls_1 == 1
    assert calls_2 == 1


def test_queue_cycle_indirect(noop_request_flush):
    """
    Test if we can detect an infinite update cycle between
    _multiple_ watchers' callbacks
    """
    state = reactive({"foo": 5, "bar": 6})
    calls_1 = 0
    calls_2 = 0

    def cb_1(new, old):
        nonlocal calls_1
        calls_1 += 1
        state["bar"] += 1

    def cb_2(new, old):
        nonlocal calls_2
        state["foo"] += 1
        calls_2 += 1

    watcher_1 = watch(lambda: state["foo"], cb_1)  # noqa: F841
    watcher_2 = watch(lambda: state["bar"], cb_2)  # noqa: F841

    state["bar"] += 1

    assert len(scheduler._queue) == 1
    assert len(scheduler._queue_indices) == 1
    assert calls_1 == 0
    assert calls_2 == 0

    with pytest.raises(RecursionError):
        scheduler.flush()


def test_lots_of_watchers(noop_request_flush):
    """
    Test with a lot of watchers
    """
    state = reactive({"items": [[["Item", "Value"], False], [["Foo", "Bar"], False]]})

    calls = 0

    def cb():
        nonlocal calls
        calls += 1

    nr_of_watchers = 100
    watchers = []
    for _ in range(nr_of_watchers):
        watchers.append(watch(lambda: state, cb, deep=True))

    state["items"][1][1] = True

    assert calls == 0

    scheduler.flush()

    assert calls == nr_of_watchers
