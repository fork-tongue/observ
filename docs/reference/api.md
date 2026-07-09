# API Reference

Everything documented on this page is available from the top-level `observ` package:

```python
from observ import (
    reactive, readonly, shallow_reactive, shallow_readonly, ref, to_raw,
    computed, watch, watch_effect, Watcher,
    init, loop_factory, scheduler,
)
```

## Reactive state

### `reactive`

```python
reactive(target: T) -> T
```

Returns a reactive proxy for the given target, which behaves like the target itself but tracks reads and writes for dependency tracking. Supports (arbitrarily nested) dicts, lists, sets and tuples; plain values are returned as-is. Calling `reactive` multiple times on the same target returns the same proxy. See [Reactivity](../guide/reactivity.md).

### `readonly`

```python
readonly(target: T) -> T
```

Same as `reactive`, but the returned proxy can only be read from: reads are tracked, and any write raises `ReadonlyError`. See [Readonly and Shallow Proxies](../guide/readonly-shallow.md).

### `shallow_reactive`

```python
shallow_reactive(target: T) -> T
```

Same as `reactive`, but only the first level of the target is made reactive: nested values are returned raw. See [Readonly and Shallow Proxies](../guide/readonly-shallow.md).

### `shallow_readonly`

```python
shallow_readonly(target: T) -> T
```

Combination of `shallow_reactive` and `readonly`.

::: observ.proxy.ref

::: observ.proxy.to_raw

## Watching state

::: observ.watcher.watch

::: observ.watcher.watch_effect

::: observ.watcher.computed

::: observ.watcher.Watcher
    options:
      members:
        - stop
        - pause
        - resume
        - active
        - paused

## Scheduling

::: observ.init.init

::: observ.init.loop_factory

### `scheduler`

The global `Scheduler` instance on which watchers are queued. Use the `register_*` methods (or the `init()` shorthand) to integrate it with an event loop, or call `flush()` manually. See [Scheduling](../guide/scheduling.md).

::: observ.scheduler.Scheduler
    options:
      members:
        - register_asyncio
        - register_qt
        - register_rendercanvas
        - register_request_flush
        - flush
