"""
Defines the public API for observ users
"""
from functools import wraps

from .dep import Dep
from .observables import reactive, to_raw
from .scheduler import scheduler
from .watcher import Watcher


__all__ = ("reactive", "computed", "watch", "scheduler", "to_raw")


def computed(fn):
    watcher = Watcher(fn, readonly=True)

    @wraps(fn)
    def getter():
        if watcher.dirty:
            watcher.evaluate()
        if Dep.stack:
            watcher.depend()
        return watcher.value

    getter.__watcher__ = watcher
    return getter


def watch(fn, callback, sync=False, deep=False, immediate=False):
    watcher = Watcher(fn, sync=sync, lazy=False, deep=deep, callback=callback)
    if immediate:
        watcher.dirty = True
        watcher.evaluate()
        if watcher.callback:
            watcher.run_callback(watcher.value, None)
    return watcher
