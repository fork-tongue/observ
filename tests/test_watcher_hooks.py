from observ import reactive, watch
from observ.watcher import Watcher


def test_watcher_hooks():
    # demonstrate that watchers can be kept alive in a global registry
    # using on_created and on_destroyed hooks
    watchers = []

    def on_created(watcher):
        watchers.append(watcher)

    def on_destroyed(watcher):
        watchers.remove(watcher)

    try:
        Watcher.on_created = on_created
        Watcher.on_destroyed = on_destroyed

        a = reactive([1, 2])
        called = 0

        def _callback():
            nonlocal called
            called += 1

        watch(lambda: len(a), _callback, sync=True)
        assert len(watchers) == 1
        assert called == 0
        a.append(3)
        assert called == 1
        assert len(a) == 3

    finally:
        Watcher.on_created = None
        Watcher.on_destroyed = None
