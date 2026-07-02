"""
Benchmarks for notifying watchers subscribed to the same piece of
reactive state. Dep.notify sorts its subscribers on every notification,
so these benchmarks guard how notification cost scales with the number
of subscribed watchers.
"""

import pytest

from observ import reactive, watch


def noop():
    pass


@pytest.mark.timeout(timeout=0)
@pytest.mark.benchmark(group="notify_watchers")
@pytest.mark.parametrize("n_watchers", [10, 100, 1_000], ids=["10", "100", "1k"])
def test_notify_watchers(benchmark, n_watchers):
    state = reactive({"count": 0})
    watchers = [  # noqa: F841
        watch(lambda: state["count"], callback=noop, sync=True)
        for _ in range(n_watchers)
    ]

    def mutate():
        state["count"] = 1
        state["count"] = 0

    benchmark(mutate)
