from weakref import ref

from PySide6 import QtWidgets
import pytest

from observ import reactive, watch
from observ.watcher import WrongNumberOfArgumentsError


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
    class Counter:
        def __init__(self, state):
            self.state = state

        def count(self):
            return self.state["count"]

    count = 0

    def cb():
        nonlocal count
        count += 1

    state = reactive({"count": 0})
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


def test_check_nr_arguments_of_weak_callback():
    class Counter:
        def cb(self, new, old, too_much):
            pass

    counter = Counter()
    state = reactive({})

    with pytest.raises(WrongNumberOfArgumentsError):
        watch(
            state,
            counter.cb,
            sync=True,
            deep=True,
        )


@pytest.mark.xfail
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

    assert not weak_label()
