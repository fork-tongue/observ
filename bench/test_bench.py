from functools import partial

import pytest

from observ import reactive


def bench_dict(plain, n=1000):
    for _ in range(n):
        obj = {} if plain else reactive({})
        obj["bar"] = "baz"
        obj["quux"] = "quuz"
        obj.update(
            {
                "bar": "foo",
                "quazi": "var",
            }
        )
        del obj["bar"]
        assert obj["quux"]  # read something
        obj.clear()


@pytest.mark.benchmark(
    group="dict_plain_vs_reactive",
)
@pytest.mark.parametrize("name", ["plain", "reactive"])
def test_dict_plain_vs_reactive(benchmark, name):
    bench_fn = partial(bench_dict, name == "plain")
    benchmark(bench_fn)


def bench_list(plain, n=1000):
    for _ in range(n):
        obj = [] if plain else reactive([])
        obj.append("bar")
        obj.extend(["quux", "quuz"])
        obj[1] = "foo"
        obj.pop(0)
        assert obj[0]  # read something
        obj.clear()


@pytest.mark.benchmark(
    group="list_plain_vs_reactive",
)
@pytest.mark.parametrize("name", ["plain", "reactive"])
def test_list_plain_vs_reactive(benchmark, name):
    bench_fn = partial(bench_list, name == "plain")
    benchmark(bench_fn)


def bench_set(plain, n=1000):
    for _ in range(n):
        obj = set() if plain else reactive(set())
        obj.add("bar")
        obj.update({"quux", "quuz"})
        assert list(iter(obj))  # read something
        obj.clear()


@pytest.mark.benchmark(
    group="set_plain_vs_reactive",
)
@pytest.mark.parametrize("name", ["plain", "reactive"])
def test_set_plain_vs_reactive(benchmark, name):
    bench_fn = partial(bench_set, name == "plain")
    benchmark(bench_fn)
