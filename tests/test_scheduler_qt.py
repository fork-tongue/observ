import asyncio

from PySide6 import QtAsyncio
import pytest

from observ import reactive, scheduler, watch


@pytest.fixture
def qtasyncio():
    old_policy = asyncio.get_event_loop_policy()
    qt_policy = QtAsyncio.QAsyncioEventLoopPolicy()
    asyncio.set_event_loop_policy(qt_policy)
    old_callback = scheduler.request_flush
    scheduler.register_asyncio()
    try:
        yield
    finally:
        asyncio.set_event_loop_policy(old_policy)
        scheduler.register_request_flush(old_callback)


def test_scheduler_pyside_asyncio(qtasyncio, qapp):
    """
    Test integration between PySide6 and asyncio
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
