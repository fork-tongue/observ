"""
The scheduler queues up and deduplicates re-evaluation of lazy Watchers
and should be integrated in the event loop of your choosing.
"""

import asyncio
import importlib
import warnings
from bisect import bisect
from collections import defaultdict


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

    def __init__(self):
        self._queue = []
        self._queue_indices = []
        self.flushing = False
        self.has = set()
        self.circular = defaultdict(int)
        self.index = 0
        self.waiting = False
        self.request_flush = self.request_flush_raise
        self.detect_cycles = True

    def request_flush_raise(self):
        """
        Error raising default request flusher.
        """
        raise ValueError("No flush request handler registered")

    def register_request_flush(self, callback):
        """
        Register callback for registering a call to flush
        """
        self.request_flush = callback

    def request_flush_asyncio(self):
        loop = asyncio.get_event_loop_policy().get_event_loop()
        loop.call_soon(self.flush)

    def register_asyncio(self):
        """
        Utility function for integration with asyncio
        """
        self.register_request_flush(self.request_flush_asyncio)

    def register_qt(self):
        """
        Legacy utility function for integration with Qt event loop. Note that using
        the `register_asyncio` method is preferred over this, together with
        setting the asyncio event loop policy to `QtAsyncio.QAsyncioEventLoopPolicy`.
        This is supported from Pyside 6.6.0. Note that the QtAsyncio submodule
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
                "    asyncio.set_event_loop_policy(QtAsyncio.QAsyncioEventLoopPolicy())"
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

    def flush(self):
        """
        Flush the queue to evaluate all queued watchers.
        You can call this manually, or register a callback
        to request to perform the flush.
        """
        if not self._queue:
            return

        self.flushing = True
        self.waiting = False
        self._queue.sort(key=lambda s: s.id)
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

    def clear(self):
        self._queue.clear()
        self._queue_indices.clear()
        self.flushing = False
        self.has.clear()
        self.circular.clear()
        self.index = 0

    def queue(self, watcher: "Watcher"):  # noqa: F821
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
