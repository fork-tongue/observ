from observ import computed, reactive
from observ.proxy import proxy_db


def test_deps_copy():
    # this test proves that even though we have
    # redundant deps we don't redundantly recompute
    # FIXME: I don't think this test works as intended anymore
    state = reactive({"foo": 5, "bar": 6})
    call_count = 0

    @computed(deep=False)
    def prop():
        nonlocal call_count
        call_count += 1
        return state.copy()

    assert prop() == {"foo": 5, "bar": 6}
    assert prop() is not state
    # FIXME: the _deps length was 3
    assert len(prop.__watcher__._deps) == 1
    assert call_count == 1

    state["foo"] = 3
    assert prop() == {"foo": 3, "bar": 6}
    assert prop() is not state
    # FIXME: the _deps length was 3
    assert len(prop.__watcher__._deps) == 1
    assert call_count == 2


def test_deps_delete():
    # test that dep objects are _not_ removed on delete
    state = reactive({"foo": 5, "bar": 6})

    # keydeps are created lazily: writes don't create them...
    state["baz"] = 5
    assert len(proxy_db.attrs(state)["keydep"]) == 0

    # ...but reads with dependency tracking active do
    @computed
    def prop():
        return state["foo"] + state["bar"] + state["baz"]

    assert prop() == 16
    assert len(proxy_db.attrs(state)["keydep"]) == 3

    del state["baz"]
    assert len(proxy_db.attrs(state)["keydep"]) == 3

    state.popitem()
    assert len(proxy_db.attrs(state)["keydep"]) == 3

    state.clear()
    assert len(proxy_db.attrs(state)["keydep"]) == 3
