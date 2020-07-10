from observ import computed, observe


def test_observe_new_coll():
    # this test proves that even tho we have redundant deps
    # we don't redundantly recompute
    state = observe({"foo": 5, "bar": 6})

    @computed
    def prop():
        return state["bar"] * 3

    assert prop() == 3 * 6

    # this adds a new collection into the scene
    # it should automatically also become observable
    state["bar"] = [1, 2, 3]

    assert prop() == [1, 2, 3, 1, 2, 3, 1, 2, 3]

    # this will only trigger re-evaluation
    # if the list became observable
    state["bar"][0] = [4]
    assert prop() == [4, 2, 3, 4, 2, 3, 4, 2, 3]
