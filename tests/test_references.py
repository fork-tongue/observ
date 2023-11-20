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
