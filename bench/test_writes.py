"""
Benchmarks for write operations on reactive datastructures at
different container sizes.

The write traps currently copy the whole container in order to detect
changes, which makes writes O(n) in the size of the container. These
benchmarks guard how the cost of a single write operation scales with
container size.

Each benchmarked function performs a pair of operations that leaves the
container in its original state, so that the container size stays
constant across benchmark rounds.
"""

from functools import partial

import pytest

from observ import reactive

SIZES = [10, 1_000, 100_000]
SIZE_IDS = ["10", "1k", "100k"]


def bench_list_append(obj):
    obj.append(None)
    obj.pop()


def bench_list_setitem(obj):
    obj[0] = 1
    obj[0] = 0


def bench_dict_setitem(obj):
    obj["key_0"] = 1
    obj["key_0"] = 0


def bench_dict_new_key(obj):
    obj["new_key"] = 0
    del obj["new_key"]


def bench_dict_update(obj):
    obj.update({"key_0": 1})
    obj.update({"key_0": 0})


def bench_set_add(obj):
    obj.add("x")
    obj.discard("x")


@pytest.mark.timeout(timeout=0)
@pytest.mark.benchmark(group="write_list_append")
@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_write_list_append(benchmark, size):
    obj = reactive(list(range(size)))
    benchmark(partial(bench_list_append, obj))


@pytest.mark.timeout(timeout=0)
@pytest.mark.benchmark(group="write_list_setitem")
@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_write_list_setitem(benchmark, size):
    obj = reactive(list(range(size)))
    benchmark(partial(bench_list_setitem, obj))


@pytest.mark.timeout(timeout=0)
@pytest.mark.benchmark(group="write_dict_setitem")
@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_write_dict_setitem(benchmark, size):
    obj = reactive({f"key_{i}": i for i in range(size)})
    benchmark(partial(bench_dict_setitem, obj))


@pytest.mark.timeout(timeout=0)
@pytest.mark.benchmark(group="write_dict_new_key")
@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_write_dict_new_key(benchmark, size):
    obj = reactive({f"key_{i}": i for i in range(size)})
    benchmark(partial(bench_dict_new_key, obj))


@pytest.mark.timeout(timeout=0)
@pytest.mark.benchmark(group="write_dict_update")
@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_write_dict_update(benchmark, size):
    obj = reactive({f"key_{i}": i for i in range(size)})
    benchmark(partial(bench_dict_update, obj))


@pytest.mark.timeout(timeout=0)
@pytest.mark.benchmark(group="write_set_add")
@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_write_set_add(benchmark, size):
    obj = reactive(set(range(size)))
    benchmark(partial(bench_set_add, obj))
