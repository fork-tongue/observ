"""
The scheduler queues up and deduplicates re-evaluation of lazy Watchers
and should be integrated in the event loop of your choosing.
"""

from __future__ import annotations

import asyncio
import importlib
import warnings
from bisect import bisect
from collections import defaultdict
from operator import attrgetter
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from collections.abc import Callable

    from .watcher import Watcher

watcher_id = attrgetter("id")


class SupportsCallSoon(Protocol):
    """
    The part of the (asyncio or rendercanvas) event loop interface
    that the scheduler needs to schedule flushes.
    """

    def call_soon(self, callback: Callable[[], Any]) -> object: ...

    def call_soon_threadsafe(self, callback: Callable[[], Any]) -> object: ...


class Scheduler:
    __slots__ = (
        "__weakref__",
        "_queue",
        "_queue_indices",
        "circular",
        "detect_cycles",
        "flushing",
        "has",
        "index",
        "request_flush",
        "timer",
        "waiting",
    )

    _queue: list[Watcher[Any]]
    _queue_indices: list[int]
    circular: defaultdict[int, int]
    detect_cycles: bool
    flushing: bool
    has: set[int]
    index: int
    request_flush: Callable[[], Any]
    timer: Any
    waiting: bool

    def __init__(self) -> None:
        self._queue = []
        self._queue_indices = []
        self.flushing = False
        self.has = set()
        self.circular = defaultdict(int)
        self.index = 0
        self.waiting = False
        self.request_flush = self.request_flush_raise
        self.detect_cycles = True

    def request_flush_raise(self) -> None:
        """
        Error raising default request flusher.
        """
        raise ValueError("No flush request handler registered")

    def register_request_flush(self, callback: Callable[[], Any]) -> None:
        """
        Register callback for registering a call to flush
        """
        self.request_flush = callback

    def request_flush_asyncio(self) -> None:
        loop = asyncio.get_event_loop()
        loop.call_soon_threadsafe(self.flush)

    def register_asyncio(self, loop: SupportsCallSoon | None = None) -> None:
        """
        Utility function for integration with asyncio.

        If no loop object is given, ``get_event_loop()`` is used on each flush
        to determine the current loop.
        """
        if loop is not None:
            self.register_request_flush(lambda: loop.call_soon(self.flush))
        else:
            self.register_request_flush(self.request_flush_asyncio)

    def register_qt(self) -> None:
        """
        Legacy utility function for integration with Qt event loop. Note that using
        the `register_asyncio` method is preferred over this, together with
        running `QtAsyncio.run(...)` instead of app.exec().
        This is supported from Pyside 6.7. Note that the QtAsyncio submodule
        is not included in the `pyside6_essentials` package.
        """
        for qt in ("PySide6", "PyQt6", "PySide2", "PyQt5", "PySide", "PyQt4"):
            try:
                QtCore = importlib.import_module(f"{qt}.QtCore")  # noqa: N806
                break
            except ImportError:
                continue
        else:
            raise ImportError("Could not import QtCore")

        try:
            importlib.import_module(f"{qt}.QtAsyncio")

            warnings.warn(
                "QtAsyncio module available: please consider using `register_asyncio` "
                "and call the following code:\n"
                f"    from {qt} import QtAsyncio\n"
                "    QtAsyncio.run(handle_sigint=True)"
                ""
            )
        except ImportError:
            pass

        self.timer = QtCore.QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(scheduler.flush)
        # Set interval to 0 to trigger the timer as soon
        # as possible (when Qt is done processing events)
        self.timer.setInterval(0)
        self.register_request_flush(self.timer.start)

    def register_rendercanvas(self, loop: SupportsCallSoon) -> None:
        """
        Utility function for integration with rendercanvas loop objects
        """
        need = {"call_soon", "call_soon_threadsafe"}
        if not all(hasattr(loop, m) for m in need):
            raise TypeError(
                f"Given loop object does not have all needed methods: {need!r}"
            )
        # Since rc loop objects look similar to asyncio, we can reuse the method
        self.register_asyncio(loop)

    def flush(self) -> None:
        """
        Flush the queue to evaluate all queued watchers.
        You can call this manually, or register a callback
        to request to perform the flush.
        """
        if not self._queue:
            return

        self.flushing = True
        self.waiting = False
        self._queue.sort(key=watcher_id)
        self._queue_indices.sort()

        while self.index < len(self._queue):
            watcher = self._queue[self.index]
            self.has.discard(watcher.id)
            watcher.run()

            if self.detect_cycles:
                self.circular[watcher.id] += 1
                if self.circular[watcher.id] > 100:
                    raise RecursionError(
                        "Infinite update loop detected in watched"
                        f" expression {watcher.fn_fqn}"
                    )

            self.index += 1

        self.clear()

    def clear(self) -> None:
        self._queue.clear()
        self._queue_indices.clear()
        self.flushing = False
        self.has.clear()
        self.waiting = False
        self.circular.clear()
        self.index = 0

    def queue(self, watcher: Watcher[Any]) -> None:
        if watcher.id in self.has:
            return

        self.has.add(watcher.id)
        if not self.flushing:
            self._queue.append(watcher)
            self._queue_indices.append(watcher.id)
            if not self.waiting:
                self.waiting = True
                self.request_flush()
        else:
            # If already flushing, splice the watcher based on its id
            # If already past its id, it will be run next immediately.
            # Last part of the queue should stay ordered, in order to
            # properly make use of bisect and avoid deadlocks
            i = bisect(self._queue_indices[self.index + 1 :], watcher.id)
            i += self.index + 1
            self._queue.insert(i, watcher)
            self._queue_indices.insert(i, watcher.id)


# Construct global instance
scheduler = Scheduler()
