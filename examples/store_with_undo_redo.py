"""
Example that shows how to use the store module
for undo/redo functionality
"""
from observ import watch
from observ.store import computed, mutation, Store


class CounterStore(Store):
    @mutation
    def bump_count(self, state):
        """
        Bump counter by one.

        Note: don't pass in the state argument: that is taken
        care of by the store. By decorating it with `mutation`
        the store wraps this method and passes in a writable
        version of the state.
        """
        state["count"] += 1

    @mutation
    def adjust_count(self, state, amount):
        state["count"] = amount

    @computed
    def count(self):
        """
        Decorating a method with `computed` will create a property
        on the store instance for easy access.
        """
        return self.state["count"]


if __name__ == "__main__":
    store = CounterStore({"count": 0})

    _ = watch(
        lambda: store.state["count"],
        lambda val: print(f"Count is now: {val}"),  # noqa: T001
        sync=True,
        immediate=True,
    )

    # Bump the count by one
    # Note that no state argument is provided here!
    store.bump_count()
    # Current state of the store can be accessed through
    # the `state` property on store
    assert store.state["count"] == 1
    # The count is now also accessible as a property because
    # of the computed `count` method defined on CounterStore
    assert store.count == 1

    # Set the count to 5
    # Again, no state argument, just the amount
    store.adjust_count(5)
    assert store.count == 5

    # Undo last change
    store.undo()
    assert store.count == 1

    # Redo undone change
    store.redo()
    assert store.count == 5
