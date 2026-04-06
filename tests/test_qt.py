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
    # Normally when using observ in a Qt context, there would
    # be a place to call QtAsyncio.run(...) to start the main
    # loop. And if the scheduler is configured to run with
    # asyncio, then it will pick up on Qt's asyncio main loop
    # automatically. However, within pytest context, we can't
    # do that, so instead, we create a new event loop explicitly
    def schedule_qtasyncio_loop():
        loop = QtAsyncio.asyncio.new_event_loop()
        loop.call_soon_threadsafe(scheduler.flush)

    old_callback = scheduler.request_flush
    scheduler.register_request_flush(schedule_qtasyncio_loop)
    try:
        yield
    finally:
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
def test_qt_integration(qapp, qtasyncio):
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

    watcher = watch(lambda: state['count'], lambda x: x)

    state["count"] += 1

    assert label.text() == "1"

    weak_label = ref(label)

    del label

    if weak_label() is not None:
        pytest.xfail("The weak wrapper in watcher doesn't work for QObject methods")
    assert not weak_label()
