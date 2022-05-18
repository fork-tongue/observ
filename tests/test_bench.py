from functools import partial

import pytest

from observ import reactive


def bench_dict(obj):
    for i in range(10000):
        obj[str(i)] = "foo"


@pytest.mark.parametrize("name", ["plain", "reactive"])
def test_bench_dict(benchmark, name):
    obj = {}
    if name == "reactive":
        obj = reactive(obj)
    bench_fn = partial(bench_dict, obj)

    benchmark(bench_fn)
