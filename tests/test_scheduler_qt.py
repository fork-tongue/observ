import asyncio

from PySide6 import QtAsyncio

from observ import reactive, scheduler, watch


def test_scheduler_pyside(qapp):
    scheduler.register_qt()

    assert not hasattr(scheduler, "timer")
    assert isinstance(
        asyncio.get_event_loop_policy(), QtAsyncio.events.QAsyncioEventLoopPolicy
    )

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
