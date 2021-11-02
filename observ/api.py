"""
Defines the public API for observ users
"""
from .observables import (
    reactive,
    readonly,
    shallow_reactive,
    shallow_readonly,
    to_raw,
)
from .scheduler import scheduler
from .watcher import computed, Watcher


__all__ = (
    "reactive",
    "readonly",
    "shallow_reactive",
    "shallow_readonly",
    "computed",
    "watch",
    "scheduler",
    "to_raw",
)


def watch(fn, callback, sync=False, deep=False, immediate=False):
    watcher = Watcher(fn, sync=sync, lazy=False, deep=deep, callback=callback)
    if immediate:
        watcher.dirty = True
        watcher.evaluate()
        if watcher.callback:
            watcher.run_callback(watcher.value, None)
    return watcher
