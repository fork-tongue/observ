from PySide6 import QtWidgets

from observ import reactive, watch


def test_no_strong_reference_to_callback():
    class Counter:
        count_a = 0
        count_b = 0
        count_c = 0

        def count(self):
            type(self).count_a += 1

        def count_new(self, new):
            type(self).count_b = new

        def count_new_old(self, new, old):
            type(self).count_c += new - (old or 0)

    state = reactive({"count": 0})

    counter = Counter()

    counter.watcher_a = watch(
        lambda: state["count"],
        counter.count,
        deep=True,
        sync=True,
    )
    counter.watcher_b = watch(
        lambda: state["count"],
        counter.count_new,
        deep=True,
        sync=True,
    )
    counter.watcher_c = watch(
        lambda: state["count"],
        counter.count_new_old,
        deep=True,
        sync=True,
    )

    state["count"] += 1

    assert Counter.count_a == 1
    assert Counter.count_b == 1
    assert Counter.count_c == 1

    del counter

    state["count"] += 1

    assert Counter.count_a == 1
    assert Counter.count_b == 1
    assert Counter.count_c == 1


def test_no_strong_reference_to_fn():
    count = 0

    def cb():
        nonlocal count
        count += 1

    state = reactive({"count": 0})

    class Counter:
        def __init__(self, state):
            self.state = state

        def count(self):
            return self.state["count"]

    counter = Counter(state)

    counter.watcher = watch(
        counter.count,
        cb,
        deep=True,
        sync=True,
    )

    state["count"] += 1

    assert count == 1

    del counter

    state["count"] += 1

    assert count == 1


def test_qt_integration(qapp):
    class Widget(QtWidgets.QWidget):
        count = 0

        def __init__(self, state):
            super().__init__()
            self.state = state
            self.label = QtWidgets.QLabel()

            self.watcher = watch(
                self.count_display,
                self.label.setText,
                deep=True,
                sync=True,
            )

        def count_display(self):
            return str(self.state["count"])

        def __del__(self):
            Widget.count += 1

    state = reactive({"count": 0})
    widget = Widget(state)

    state["count"] += 1

    assert widget.label.text() == "1"

    del widget

    assert Widget.count == 1
