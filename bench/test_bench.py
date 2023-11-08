from functools import partial

import pytest

from observ import reactive, watch


def noop():
    pass


N = 10000


def bench_dict(plain, add_watcher):
    for _ in range(N):
        obj = {} if plain else reactive({})
        if add_watcher:
            watcher = watch(obj, callback=noop, deep=True, sync=True)  # noqa: F841
        obj["bar"] = "baz"
        obj["quux"] = "quuz"
        obj.update(
            {
                "bar": "foo",
                "quazi": "var",
            }
        )
        del obj["bar"]
        _ = obj["quux"]  # read something
        obj.clear()


@pytest.mark.timeout(timeout=0)
@pytest.mark.benchmark(
    group="dict_plain_vs_reactive",
)
@pytest.mark.parametrize("name", ["plain", "reactive", "reactive+watcher"])
def test_dict_plain_vs_reactive(benchmark, name):
    bench_fn = partial(bench_dict, name == "plain", name.endswith("+watcher"))
    benchmark(bench_fn)


def bench_list(plain, add_watcher):
    for _ in range(N):
        obj = [] if plain else reactive([])
        if add_watcher:
            watcher = watch(obj, callback=noop, deep=True, sync=True)  # noqa: F841
        obj.append("bar")
        obj.extend(["quux", "quuz"])
        obj[1] = "foo"
        obj.pop(0)
        _ = obj[0]  # read something
        obj.clear()


@pytest.mark.timeout(timeout=0)
@pytest.mark.benchmark(
    group="list_plain_vs_reactive",
)
@pytest.mark.parametrize("name", ["plain", "reactive", "reactive+watcher"])
def test_list_plain_vs_reactive(benchmark, name):
    bench_fn = partial(bench_list, name == "plain", name.endswith("+watcher"))
    benchmark(bench_fn)


def bench_set(plain, add_watcher):
    for _ in range(N):
        obj = set() if plain else reactive(set())
        if add_watcher:
            watcher = watch(obj, callback=noop, deep=True, sync=True)  # noqa: F841
        obj.add("bar")
        obj.update({"quux", "quuz"})
        _ = list(iter(obj))  # read something
        obj.clear()


@pytest.mark.timeout(timeout=0)
@pytest.mark.benchmark(
    group="set_plain_vs_reactive",
)
@pytest.mark.parametrize("name", ["plain", "reactive", "reactive+watcher"])
def test_set_plain_vs_reactive(benchmark, name):
    bench_fn = partial(bench_set, name == "plain", name.endswith("+watcher"))
    benchmark(bench_fn)
