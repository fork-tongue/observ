"""
Benchmarks for read operations on reactive datastructures.

Every read through a proxy runs the returned value through the full
`proxy()` machinery, even when the value is a plain (unproxyable)
value like an int or str. These benchmarks measure that read overhead,
compared against plain datastructures, both outside of a watcher
(untracked) and during a watcher evaluation (tracked).

Each benchmarked function performs a batch of 100 reads (or a full
iteration) so that the measured times are well above timer resolution.
"""

from functools import partial

import pytest

from observ import reactive
from observ.watcher import Watcher

SIZE = 1_000
KEYS = [f"key_{i}" for i in range(0, SIZE, 10)]
INDICES = list(range(0, SIZE, 10))


def make_dict():
    return {f"key_{i}": i for i in range(SIZE)}


def read_dict_keys(obj):
    for key in KEYS:
        _ = obj[key]


def read_list_items(obj):
    for index in INDICES:
        _ = obj[index]


def iterate_dict_values(obj):
    for _value in obj.values():
        pass


def iterate_list(obj):
    for _item in obj:
        pass


@pytest.mark.timeout(timeout=0)
@pytest.mark.benchmark(group="read_dict_getitem")
@pytest.mark.parametrize("kind", ["plain", "reactive"])
def test_read_dict_getitem(benchmark, kind):
    obj = make_dict()
    if kind == "reactive":
        obj = reactive(obj)
    benchmark(partial(read_dict_keys, obj))


@pytest.mark.timeout(timeout=0)
@pytest.mark.benchmark(group="read_list_getitem")
@pytest.mark.parametrize("kind", ["plain", "reactive"])
def test_read_list_getitem(benchmark, kind):
    obj = list(range(SIZE))
    if kind == "reactive":
        obj = reactive(obj)
    benchmark(partial(read_list_items, obj))


@pytest.mark.timeout(timeout=0)
@pytest.mark.benchmark(group="read_dict_iterate_values")
@pytest.mark.parametrize("kind", ["plain", "reactive"])
def test_read_dict_iterate_values(benchmark, kind):
    obj = make_dict()
    if kind == "reactive":
        obj = reactive(obj)
    benchmark(partial(iterate_dict_values, obj))


@pytest.mark.timeout(timeout=0)
@pytest.mark.benchmark(group="read_list_iterate")
@pytest.mark.parametrize("kind", ["plain", "reactive"])
def test_read_list_iterate(benchmark, kind):
    obj = list(range(SIZE))
    if kind == "reactive":
        obj = reactive(obj)
    benchmark(partial(iterate_list, obj))


@pytest.mark.timeout(timeout=0)
@pytest.mark.benchmark(group="read_tracked")
def test_read_dict_getitem_tracked(benchmark):
    """
    Benchmark reads during a watcher evaluation, so with dependency
    tracking active. This includes the cost of registering the deps
    on the watcher and the dep cleanup afterwards.
    """
    obj = reactive(make_dict())
    watcher = Watcher(partial(read_dict_keys, obj), deep=False)
    benchmark(watcher.get)
