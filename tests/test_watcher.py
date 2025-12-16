from unittest.mock import Mock

from observ import reactive, scheduler, watch


def test_watcher_active(noop_request_flush):
    a = reactive({"foo": "bar"})
    callback = Mock()

    unwatch = watch(lambda: a["foo"], callback, immediate=False)

    assert callable(unwatch)

    callback.assert_not_called()

    a["foo"] = "baz"
    scheduler.flush()

    callback.assert_called_once()

    callback.reset_mock()

    a["foo"] = "qux"
    # Call the watcher to stop the watcher
    unwatch()

    scheduler.flush()
    callback.assert_not_called()


def test_watcher_removed_icw_active(noop_request_flush):
    """
    This example is a basic reconstruction of what happens inside collagraph
    when a list of elements is rendered and watchers are created for items
    within a reactive list.
    """
    a = reactive({"foo": ["bar", "baz"]})

    callback_args = []

    def callback(arg):
        callback_args.append(arg)

    watchers = []

    def create_watchers(new):
        for i in range(len(watchers), new):
            watchers.append(
                watch(
                    lambda i=i: a["foo"][i],
                    lambda new, old, /, i=i: callback(i),
                    deep=True,
                    immediate=True,
                )
            )

        while len(watchers) > new:
            unwatch = watchers.pop()
            # Here the watcher is stopped to make sure it won't
            # trigger and tries to get a non-existing value from the
            # watched array
            unwatch()

    _length_watcher = watch(
        lambda: len(a["foo"]),
        create_watchers,
        deep=False,
        immediate=True,
    )

    scheduler.flush()

    assert callback_args == [0, 1]
    callback_args.clear()

    a["foo"].pop()

    # Popping the last item of the array will trigger the removal of the
    # last watcher. However, the watcher needs to be deactivated to make
    # sure it won't try to get a value from a["foo"] that doesn't exist
    # anymore, resulting in an IndexError
    scheduler.flush()
    # Note: before the active property was there, the work-around was the following:
    #     watcher.fn = lambda: ()
    #     watcher.callback = None

    assert callback_args == [0]
