import pytest

from observ import observe, scheduler, watch


def test_no_flush_handler():
    """
    Test if we get a ValueError when no flush request handler is registered
    """
    state = observe({"foo": 5, "bar": 6})
    calls = 0

    def cb(old, new):
        nonlocal calls
        calls += 1

    watcher = watch(lambda: state["foo"], cb)  # noqa: F841

    with pytest.raises(ValueError, match="No flush request handler registered"):
        state["foo"] += 1


def test_flush(noop_request_flush):
    """
    Test if flush works
    """
    state = observe({"foo": 5, "bar": 6})
    calls = 0

    def cb(old, new):
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
    state = observe({"foo": 5, "bar": 6})
    calls = 0

    def exp():
        state["foo"] += 1
        return state["foo"]

    def cb(old, new):
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
    state = observe({"foo": 5, "bar": 6})
    calls = 0

    def exp():
        return state["foo"]

    def cb(old, new):
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
    state = observe({"foo": 5, "bar": 6})
    calls_1 = 0
    calls_2 = 0

    def cb_1(old, new):
        nonlocal calls_1
        calls_1 += 1
        state["bar"] += 1

    def cb_2(old, new):
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
    state = observe({"foo": 5, "bar": 6})
    calls_1 = 0
    calls_2 = 0

    def exp_1():
        if state["foo"] == 5:
            return state["foo"]
        else:
            return state["bar"]

    def cb_1(old, new):
        nonlocal calls_1
        calls_1 += 1
        state["bar"] += 1

    def cb_2(old, new):
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
