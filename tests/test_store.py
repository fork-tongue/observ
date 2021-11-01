from observ import computed, mutation, Store


def test_store_computed_methods():
    class CustomStore(Store):
        @mutation
        def bump_count(self, state):
            state["count"] += 1

        @computed
        def double(self):
            return self.state["count"] * 2

    store = CustomStore(state={"count": 0})

    @computed
    def double():
        return store.state["count"] * 2

    def triple_count():
        return store.state["count"] * 3

    triple = computed(triple_count)

    quadruple = computed(lambda: store.state["count"] * 4)

    assert store.state["count"] == 0
    assert store.double == 0
    assert double() == 0
    assert triple() == 0
    assert quadruple() == 0

    store.bump_count()

    assert store.state["count"] == 1
    assert store.double == 2
    assert double() == 2
    assert triple() == 3
    assert quadruple() == 4
