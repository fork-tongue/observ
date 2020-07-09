from observ import computed, observe


def test_deps_copy():
    state = observe({"foo": 5, "bar": 6})

    @computed
    def prop():
        return state.copy()

    assert prop() == {"foo": 5, "bar": 6}
    # reproduce issue #16
    assert len(prop.__watcher__._deps) == 3
