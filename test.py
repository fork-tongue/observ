from deppy import observe, computed, watch


if __name__ == "__main__":

    a = observe({"foo": 5, "bar": [6, 7, 8], "quux": 10, "quuz": {"a": 1, "b": 2}})
    execute_count = 0

    def bla():
        global execute_count
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

    def bla2():
        global execute_count
        execute_count += 1
        return a["foo"] * computed_bla()

    computed_bla2 = computed(bla2)
    assert computed_bla2() == 600
    assert computed_bla2() == 600
    assert execute_count == 4
    a["quuz"]["b"] = 4
    assert computed_bla2() == 800
    assert computed_bla2() == 800
    assert execute_count == 6

    called = 0

    def _callback(old_value, new_value):
        global called
        called += 1

    watcher = watch(lambda: a["quuz"], deep=True, callback=_callback, immediate=True)
    assert not watcher.dirty
    assert watcher.value == a["quuz"]
    assert len(watcher._deps) > 1
    assert called == 0
    a["quuz"]["b"] = 3
    assert not watcher.dirty
    assert called == 1
