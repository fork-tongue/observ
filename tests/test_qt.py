import asyncio
from weakref import ref

import pytest

from observ import reactive, scheduler, watch

try:
    from PySide6 import QtAsyncio, QtWidgets

    has_qt = True
except ImportError:
    has_qt = False
qt_missing_reason = "Qt is not installed"


@pytest.fixture
def qtasyncio():
    old_policy = asyncio.get_event_loop_policy()
    qt_policy = QtAsyncio.QAsyncioEventLoopPolicy(quit_qapp=False)
    asyncio.set_event_loop_policy(qt_policy)
    old_callback = scheduler.request_flush
    scheduler.register_asyncio()
    try:
        yield
    finally:
        asyncio.set_event_loop_policy(old_policy)
        scheduler.register_request_flush(old_callback)


@pytest.mark.skipif(not has_qt, reason=qt_missing_reason)
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


@pytest.mark.skipif(not has_qt, reason=qt_missing_reason)
def test_qt_integration(qapp):
    class Label(QtWidgets.QLabel):
        count = 0

        def __init__(self, state):
            super().__init__()
            self.state = state

            self.watcher = watch(
                self.count_display,
                # Use a method from QLabel directly as callback. These methods don't
                # have a __func__ attribute, so currently this won't be wrapped by
                # the 'weak' wrapper in the watcher, so it will create a strong
                # reference instead to self.
                # Ideally we would be able to detect this and wrap it, but then
                # there is the problem that these kinds of methods don't have a
                # signature, so we can't detect the number of arguments to supply.
                # I guess we can assume that we should supply only two arguments
                # in those cases: 'self' and 'new'?
                # We'll solve this if this becomes an actual problem :)
                self.setText,
                deep=True,
                sync=True,
            )

        def count_display(self):
            return str(self.state["count"])

    state = reactive({"count": 0})
    label = Label(state)

    state["count"] += 1

    assert label.text() == "1"

    weak_label = ref(label)

    del label

    if weak_label() is not None:
        pytest.xfail("The weak wrapper in watcher doesn't work for QObject methods")
    assert not weak_label()
