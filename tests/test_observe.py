from observ import computed, reactive


def test_reactivity_new_coll():
    # this test proves that inserting a plain collection
    # type into an already reactive object will make it
    # reactive.
    state = reactive({"foo": 5, "bar": 6})
    call_count = 0

    @computed
    def prop():
        nonlocal call_count
        call_count += 1
        return state["bar"] * 3

    for _ in range(2):
        assert prop() == 3 * 6
    assert call_count == 1

    # this adds a new collection into the scene
    # it should automatically also become observable
    state["bar"] = [1, 2, 3]

    for _ in range(2):
        assert prop() == [1, 2, 3, 1, 2, 3, 1, 2, 3]
    assert call_count == 2

    # this will only trigger re-evaluation
    # if the list became observable
    state["bar"][0] = 4
    for _ in range(2):
        assert prop() == [4, 2, 3, 4, 2, 3, 4, 2, 3]
    assert call_count == 3


def test_observe_dict_value_not_changed():
    # this test proves that we don't fire if a value
    # has not actually changed
    state = reactive({"foo": 5, "bar": 6})
    call_count = 0

    @computed
    def prop():
        nonlocal call_count
        call_count += 1
        return state["bar"] * 3

    for _ in range(2):
        assert prop() == 3 * 6
    assert call_count == 1

    # no change
    state["bar"] = state["bar"]

    for _ in range(2):
        assert prop() == 3 * 6
    assert call_count == 1

    state.update({"bar": 6})

    for _ in range(2):
        assert prop() == 3 * 6
    assert call_count == 1


def test_observe_list_item_not_changed():
    # this test proves that we don't fire if a value
    # has not actually changed
    state = reactive([5, 6])
    call_count = 0

    @computed
    def prop():
        nonlocal call_count
        call_count += 1
        return state[0] * 3

    for _ in range(2):
        assert prop() == 3 * 5
    assert call_count == 1

    # no change
    state[0] = 5

    for _ in range(2):
        assert prop() == 3 * 5
    assert call_count == 1


def test_observe_set_not_changed():
    # this test proves that we don't fire if a value
    # has not actually changed
    state = reactive({5, 6})
    call_count = 0

    @computed
    def prop():
        nonlocal call_count
        call_count += 1
        return sum(state)

    for _ in range(2):
        assert prop() == 5 + 6
    assert call_count == 1

    # no change
    state.add(5)

    for _ in range(2):
        assert prop() == 5 + 6
    assert call_count == 1
