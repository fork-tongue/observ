class Scheduler:
    def __init__(self):
        self._queue = []
        self.flushing = False
        self.has = set()
        self.circular = {}
        self.index = 0

    def flush(self):
        """Call this as many times as you want"""
        if not self._queue:
            return

        self.flushing = True
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
        else:
            # If already flushing, splice the watcher based on its id
            # If already past its id, it will be run next immediately.
            i = len(self._queue) - 1
            while i > self.index and self._queue[i].id > watcher.id:
                i -= 1
            self._queue.insert(i, watcher)


# Construct global instance
scheduler = Scheduler()
