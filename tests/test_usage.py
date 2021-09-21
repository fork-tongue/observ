from observ import computed, observe, watch


def test_usage():
    a = observe({"foo": 5, "bar": [6, 7, 8], "quux": 10, "quuz": {"a": 1, "b": 2}})
    execute_count = 0

    def bla():
        nonlocal execute_count
        execute_count += 1
        multi = 0
        if a["quux"] == 10:
            multi = a["foo"] * 5
        else:
            multi = a["bar"][-1] * 5
        return multi * a["quuz"]["b"]

    computed_bla = computed(bla)
    assert computed_bla() == 50
    assert computed_bla() == 50
    assert execute_count == 1
    a["quux"] = 25
    assert computed_bla() == 80
    assert computed_bla() == 80
    assert execute_count == 2
    a["quuz"]["b"] = 3
    assert computed_bla() == 120
    assert computed_bla() == 120
    assert execute_count == 3

    @computed
    def bla2():
        nonlocal execute_count
        execute_count += 1
        return a["foo"] * computed_bla()

    assert bla2() == 600
    assert bla2() == 600
    assert execute_count == 4
    a["quuz"]["b"] = 4
    assert bla2() == 800
    assert bla2() == 800
    assert execute_count == 6

    called = 0

    def _callback(old_value, new_value):
        nonlocal called
        called += 1

    watcher = watch(lambda: a["quuz"], _callback, sync=True, deep=True, immediate=False)
    assert not watcher.dirty
    assert watcher.value == a["quuz"]
    assert len(watcher._deps) > 1
    assert called == 0
    a["quuz"]["b"] = 3
    assert not watcher.dirty
    assert called == 1

    assert computed_bla() == 120
    assert execute_count == 7
    assert not computed_bla.__watcher__.dirty
    a["bar"].extend([9, 10])
    assert computed_bla.__watcher__.dirty
    assert computed_bla() == 150
    assert execute_count == 8


def test_watch_immediate():
    a = observe({"foo": 5, "bar": [6, 7, 8], "quux": 10, "quuz": {"a": 1, "b": 2}})

    called = 0

    def _callback(old_value, new_value):
        nonlocal called
        called += 1

    watcher = watch(lambda: a["quuz"], _callback, sync=True, deep=True, immediate=True)
    assert not watcher.dirty
    assert watcher.value == a["quuz"]
    assert len(watcher._deps) > 1
    assert called == 1
    a["quuz"]["b"] = 3
    assert not watcher.dirty
    assert called == 2


def test_usage_deep_vs_non_deep():
    a = observe({"foo": [0, 1]})

    non_deep_called = 0

    def _non_deep_callback(old_value, new_value):
        nonlocal non_deep_called
        non_deep_called += 1

    deep_called = 0

    def _deep_callback(old_value, new_value):
        nonlocal deep_called
        deep_called += 1

    watcher = watch(lambda: a["foo"], _non_deep_callback, sync=True)
    deep_watcher = watch(lambda: a["foo"], _deep_callback, sync=True, deep=True)
    assert not watcher.dirty
    assert not deep_watcher.dirty
    assert non_deep_called == 0
    a["foo"].append(1)
    assert non_deep_called == 0
    assert deep_called == 1
