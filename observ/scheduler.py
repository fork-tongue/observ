"""
The scheduler queues up and deduplicates re-evaluation of lazy Watchers
and should be integrated in the event loop of your choosing.
"""


class Scheduler:
    def __init__(self):
        self._queue = []
        self.flushing = False
        self.has = set()
        self.circular = {}
        self.index = 0
        self.waiting = False

    def register_qt(self):
        """
        Utility function for integration with Qt event loop
        """
        # Currently only supports PySide6
        from PySide6.QtCore import QTimer

        self.timer = QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(scheduler.flush)
        # Set interval to 0 to trigger the timer as soon
        # as possible (when Qt is done processing events)
        self.timer.setInterval(0)
        self.register_flush_request(self.timer.start)

    def register_flush_request(self, request_flush):
        """
        Register callback for registering a call to flush
        """
        self.request_flush = request_flush

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

        while self.index < len(self._queue):
            watcher = self._queue[self.index]
            self.has.remove(watcher.id)
            watcher.run()

            if watcher.id in self.has:
                self.circular[watcher.id] = self.circular.get(watcher.id, 0) + 1
                if self.circular[watcher.id] > 100:
                    # TODO: help user to figure out which watcher
                    # or function this is about
                    raise RecursionError("Infinite update loop detected")

            self.index += 1

        self._queue.clear()
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
            if not self.waiting and self.request_flush:
                self.waiting = True
                self.request_flush()
        else:
            # If already flushing, splice the watcher based on its id
            # If already past its id, it will be run next immediately.
            i = len(self._queue) - 1
            while i > self.index and self._queue[i].id > watcher.id:
                i -= 1
            self._queue.insert(i, watcher)


# Construct global instance
scheduler = Scheduler()
