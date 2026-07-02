"""
Benchmarks for the cost of creating proxies and watchers.

Creating a proxy for a dict registers the target in the proxy_db and
eagerly creates a Dep for every key, so proxy creation cost scales
with the number of keys.
"""

import gc

import pytest

from observ import reactive, watch

SIZES = [10, 1_000, 100_000]
SIZE_IDS = ["10", "1k", "100k"]


def noop():
    pass


@pytest.mark.timeout(timeout=0)
@pytest.mark.benchmark(group="proxy_creation_dict")
@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_proxy_creation_dict(benchmark, size):
    def setup():
        # Collect garbage in between rounds (outside of the measured
        # code) so that proxy_db entries for the previous rounds are
        # cleaned up deterministically instead of adding gc noise to
        # the measurement
        gc.collect()
        return ({f"key_{i}": i for i in range(size)},), {}

    benchmark.pedantic(reactive, setup=setup, warmup_rounds=1, rounds=30)


@pytest.mark.timeout(timeout=0)
@pytest.mark.benchmark(group="watcher_creation")
def test_watcher_creation(benchmark):
    state = reactive({"count": 0})

    def create_watcher():
        return watch(lambda: state["count"], callback=noop, sync=True)

    benchmark(create_watcher)
