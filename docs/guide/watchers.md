# Watchers

Where [computed state](computed.md) *derives* values, watchers let you *react* to changes — updating a UI widget, writing to disk, sending a network request.

```python
from observ import reactive, watch

state = reactive({"count": 0})

watcher = watch(
    lambda: state["count"],
    lambda new, old: print(f"count changed from {old} to {new}"),
)
```

`watch(fn, callback)` evaluates `fn` once immediately to collect its dependencies, then calls `callback` whenever the result of `fn` changes.

!!! note "Keep the watcher alive"

    `watch()` returns a `Watcher` object. Hold on to it: when the watcher is garbage collected the callback stops firing. Storing it in a dict or on the object that owns the reaction (`self.watchers["count"] = watch(...)`) is a common pattern.

## Callback signatures

The callback may accept zero, one, or two arguments — observ automatically detects which:

```python
watch(fn, lambda: print("changed!"))
watch(fn, lambda new: print(f"now: {new}"))
watch(fn, lambda new, old: print(f"was: {old}, now: {new}"))
```

## What can be watched

The first argument to `watch()` is typically a function, but it can also be a proxy (or even a list of proxies) to watch directly, which implies `deep=True`:

```python
state = reactive({"count": 0})

watcher = watch(state, lambda: print("something in state changed"))
```

Async functions are supported as well, both as the watched expression and as the callback; coroutines are scheduled on the running asyncio event loop.

## Options

### `immediate`

By default the callback only fires on the first *change*. Pass `immediate=True` to also call it right away with the initial value (with `None` for the old value):

```python
watcher = watch(lambda: state["count"], update_label, immediate=True)
```

This is handy for UI code: the same callback initializes the widget and keeps it up to date.

### `deep`

When watching a function, only the state that is actually read is tracked, and the callback fires when the *result* changes. With `deep=True`, the result is also traversed completely, so the callback fires on changes nested anywhere inside a returned container:

```python
state = reactive({"items": [{"done": False}]})

watch(lambda: state["items"], callback)             # fires when the list itself changes
watch(lambda: state["items"], callback, deep=True)  # also fires when an item's "done" flips
```

!!! note

    With `deep=True` (and also when the watched value is a container), the callback's `new` and `old` arguments will be the same object, since the watcher can't keep a snapshot of the old state.

### `sync`

By default, callbacks are not run at the moment the state changes: the watcher is queued on the [scheduler](scheduling.md), which batches and deduplicates updates and runs them on your event loop. Pass `sync=True` to skip the scheduler and run the callback synchronously on every change. Use this sparingly — for tests, scripts without an event loop, or when you really need the callback to have run before the next line of code.

## `watch_effect`

If there is no meaningful "result" to watch and you just want to run a piece of code whenever any state it touches changes, use `watch_effect()`:

```python
from observ import reactive, watch_effect

state = reactive({"count": 0})

def persist():
    save_to_disk(state["count"])

watcher = watch_effect(persist)
```

The function runs once immediately to collect dependencies, and re-runs (via the scheduler) whenever they change. It is equivalent to `watch(fn, deep=True)` without a callback.

## Watcher lifecycle

The returned `Watcher` object gives you full control over the reaction:

```python
watcher = watch(lambda: state["count"], callback)

watcher.pause()   # dependency changes no longer trigger the callback
watcher.resume()  # if anything changed while paused, triggers once now

watcher.stop()    # permanently stop and release resources
```

* `pause()` / `resume()` — temporarily suspend the watcher. If a dependency changed while paused, the watcher triggers once upon resume. Check the state with the `paused` property.
* `stop()` — permanently deactivate the watcher and release its resources. Calling the watcher object itself (`watcher()`) is equivalent, which is convenient when a framework expects a teardown callable. Check the state with the `active` property.
* Deleting the last reference to a watcher deactivates it as well.

## Methods as watched functions or callbacks

When you pass a *bound method* as the watched function or as the callback, observ stores it with a weak reference to the instance. The watcher will then not keep your object alive:

```python
class Display:
    def __init__(self, state):
        self.watcher = watch(lambda: state["count"], self.update)

    def update(self, new):
        ...
```

Here the `Display` instance can be garbage collected normally, even though its watcher references `self.update`.
