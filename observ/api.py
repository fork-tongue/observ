"""
Defines the public API for observ users
"""
from functools import wraps

from .dep import Dep
from .observables import observe
from .scheduler import scheduler
from .watcher import Watcher


__all__ = ("observe", "computed", "watch", "scheduler")


def computed(fn):
    watcher = Watcher(fn)

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
