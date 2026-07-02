"""
End-to-end benchmarks for the common hot path of a deep watcher:
mutating a single leaf in a large watched tree, which notifies the
watcher, re-evaluates the watched expression and re-traverses the
whole structure to keep tracking all nested dependencies.
"""

import pytest

from observ import reactive, watch


def noop():
    pass


def make_tree(n_branches):
    return {
        f"branch_{i}": {"leaves": list(range(10)), "flag": 0} for i in range(n_branches)
    }


@pytest.mark.timeout(timeout=0)
@pytest.mark.benchmark(group="deep_watch_mutate_leaf")
@pytest.mark.parametrize("n_branches", [10, 100, 1_000], ids=["10", "100", "1k"])
def test_deep_watch_mutate_leaf(benchmark, n_branches):
    state = reactive(make_tree(n_branches))
    watcher = watch(state, callback=noop, deep=True, sync=True)  # noqa: F841

    def mutate():
        state["branch_0"]["flag"] = 1
        state["branch_0"]["flag"] = 0

    benchmark(mutate)
