from observ import computed, observe


def test_deps_copy():
    # this test proves that even tho we have redundant deps
    # we don't redundantly recompute
    state = observe({"foo": 5, "bar": 6})
    call_count = 0

    @computed
    def prop():
        nonlocal call_count
        call_count += 1
        return state.copy()

    assert prop() == {"foo": 5, "bar": 6}
    assert prop() is not state
    assert len(prop.__watcher__._deps) == 3
    assert call_count == 1

    state["foo"] = 3
    assert prop() == {"foo": 3, "bar": 6}
    assert prop() is not state
    assert len(prop.__watcher__._deps) == 3
    assert call_count == 2


def test_deps_delete():
    # test that dep objects are removed on delete
    state = observe({"foo": 5, "bar": 6})

    state["baz"] = 5
    assert len(state.__keydeps__) == 3

    del state["baz"]
    assert len(state.__keydeps__) == 2

    state.popitem()
    assert len(state.__keydeps__) == 1

    state.clear()
    assert len(state.__keydeps__) == 0
