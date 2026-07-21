# Scheduling

When reactive state changes, non-`sync` watchers do not run their callbacks immediately. Instead they are queued on a global **scheduler**, which batches them until the queue is *flushed*. This has two important benefits:

* **Deduplication** — if a watcher's dependencies change five times between flushes, its callback runs once, not five times.
* **Consistency** — a burst of related state changes (e.g. everything a single mouse event modifies) results in a single round of updates, run in a predictable order.

The scheduler needs to know *when* to flush, and that depends on your application's event loop. Observ ships with integrations for asyncio, Qt and rendercanvas.

## asyncio

```python
from observ import init

init("asyncio")
```

This registers a flush handler that schedules the flush on the current asyncio event loop (via `call_soon_threadsafe`). Queued watchers are then processed as soon as the loop is idle.

You can also pass a specific loop: `scheduler.register_asyncio(loop)`.

!!! tip "Eager task factory"

    observ's `loop_factory()` helper creates a new event loop with the [eager task factory](https://docs.python.org/3/library/asyncio-task.html#asyncio.eager_task_factory) enabled, which reduces the latency of the async callbacks and watched functions that observ schedules as tasks:

    ```python
    import asyncio
    from observ import init, loop_factory

    async def main():
        init("asyncio")
        ...

    with asyncio.Runner(loop_factory=loop_factory) as runner:
        runner.run(main())
    ```

## Qt

For PySide6 >= 6.7, the preferred integration is asyncio-based, using Qt's own [QtAsyncio](https://doc.qt.io/qtforpython-6/PySide6/QtAsyncio/index.html) module:

```python
from PySide6 import QtAsyncio
from observ import init

app = QApplication([])
# ... build your UI ...

init("asyncio")
QtAsyncio.run(handle_sigint=True)
```

Alternatively, `init("qt")` registers a legacy integration based on a zero-interval single-shot `QTimer`, which works across PySide/PyQt versions without QtAsyncio (note that QtAsyncio is not included in the `pyside6_essentials` package):

```python
init("qt")
app.exec()
```

## Rendercanvas

[Rendercanvas](https://github.com/pygfx/rendercanvas) loop objects can be hooked up directly:

```python
from rendercanvas.auto import RenderCanvas, loop
from observ import init

init("rendercanvas", loop)
```

## Custom event loops

For any other event loop, register a callback that arranges for `scheduler.flush()` to be called when the loop is about to go idle:

```python
from observ import scheduler

scheduler.register_request_flush(lambda: my_loop.call_soon(scheduler.flush))
```

The callback you register is invoked (once) when the first watcher is queued; it should ensure that `flush()` runs soon afterwards on the loop's thread.

## Manual flushing

Without an event loop — in a test suite, for example — you can drive the scheduler by hand:

```python
from observ import scheduler

scheduler.register_request_flush(lambda: None)  # queue silently

state["count"] += 1   # watcher is queued, callback hasn't run yet
scheduler.flush()     # callback runs now
```

Or sidestep the scheduler entirely with `sync=True` watchers, which run their callbacks synchronously on every change — see [Watchers](watchers.md#sync).

!!! warning "No integration registered"

    If reactive state watched by a non-`sync` watcher changes before any flush handler is registered, observ raises `ValueError: No flush request handler registered`. Call `init()` once at application startup.

## Cycle detection

During a flush, a watcher callback may itself change state that queues further watchers; the scheduler processes those in the same flush, ordered by watcher creation order. If watchers keep re-triggering each other, the scheduler raises a `RecursionError` after 100 iterations, pointing at the watched expression that loops:

```
RecursionError: Infinite update loop detected in watched expression my_module.my_fn
```

If you hit this, look for a watcher (or `watch_effect`) that writes to state it also depends on.
