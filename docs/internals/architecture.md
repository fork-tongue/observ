# Architecture

This page describes how observ works under the hood. You don't need any of this to *use* observ — it is aimed at contributors, and at the curious who want to know what actually happens between `state["count"] += 1` and their callback firing.

Observ's reactivity is built from four cooperating pieces:

* **Proxies** (`proxy.py`, `dict_proxy.py`, `list_proxy.py`, `set_proxy.py`, `traps.py`) wrap plain containers and intercept every read and write.
* **Deps** (`dep.py`, `proxy_db.py`) implement the observable pattern: one `Dep` per observable "thing", with watchers as subscribers.
* **Watchers** (`watcher.py`) evaluate a function while recording which deps were read, and re-run when any of them notifies.
* **The scheduler** (`scheduler.py`) batches and deduplicates watcher updates until the event loop flushes the queue.

The flow of a single update looks like this:

```
write through proxy ──> trap detects change ──> dep.notify()
                                                     │
                          for each subscribed watcher▼
             sync watcher: run now / lazy watcher: mark dirty
                    otherwise: scheduler.queue(watcher)
                                                     │
                                event loop goes idle ▼
                scheduler.flush() ──> watcher.run() ──> callback
```

## Proxies and traps

A `Proxy` is a thin wrapper around a target container. It stores the wrapped object in `__target__`, its configuration in `__readonly__` and `__shallow__`, and the reactive state for the target in `__dep__` (see [the proxy registry](#the-proxy-registry) below). The odd dunder-style slot names are deliberate: the proxy has to expose the complete interface of its target, so its own attributes must not collide with anything a wrapped object could plausibly define.

There is no `__getattr__` magic at work. Instead, the concrete proxy classes — `DictProxy`, `ListProxy`, `SetProxy` and their readonly variants — are *generated* at import time. Each container type declares which of its methods belong to which trap category:

| Category | Meaning | Example (`dict`) |
| --- | --- | --- |
| `READERS` | read the container as a whole | `keys`, `__len__`, `__eq__` |
| `KEYREADERS` | read a single key | `get`, `__getitem__`, `__contains__` |
| `ITERATORS` | produce an iterator | `items`, `values`, `__iter__` |
| `WRITERS` | mutate the container | `update`, `__ior__` |
| `KEYWRITERS` | mutate a single key | `__setitem__`, `setdefault` |
| `DELETERS` | remove unspecified keys | `clear`, `popitem` |
| `KEYDELETERS` | remove a single key | `pop`, `__delitem__` |

`construct_methods_traps_dict()` in `traps.py` maps every method through a trap factory that wraps the original (e.g. `dict.__getitem__`) in dependency-tracking and change-notification logic. The result is a plain methods dict from which the proxy class is built with `type()`. Readonly proxies are built from the same tables with a different trap map, in which every write category resolves to a trap that raises `ReadonlyError`.

A read trap does three things: register a dependency (only when a watcher is currently evaluating — see below), call the original method on the raw target, and wrap the returned value in a proxy of the same configuration. That last step is what makes nesting lazy: a child container is proxied at the moment you access it, not when the tree is first made reactive. Shallow proxies skip this wrapping step and return raw values.

### Change detection on writes

Write traps only notify when the container *actually changed*, so that no-op writes (setting a key to its current value, `discard()` of an absent element) don't trigger updates. Because copying a whole container on every write would be wasteful, `write_trap()` picks the cheapest correct strategy per method:

* **Length compare** — most `list` and `set` mutators (`append`, `add`, `remove`, …) can only change the container by changing its length, so comparing `len()` before and after suffices.
* **Affected-slice compare** — `list.__setitem__` compares just the affected index (or slice) instead of the whole list.
* **Incoming-keys diff** — `dict.update` and `__ior__` can only change the keys they receive, so only those keys are compared before and after.
* **Copy and compare** — `sort`, `reverse` and `symmetric_difference_update` can change the container without changing its length, so they fall back to copying; the cost of the copy is proportional to the operation itself.

Key-level traps (`__setitem__`, `pop`, `setdefault`, …) additionally notify the *keydep* for the affected key, so that watchers that only depend on `state["count"]` are not disturbed by writes to other keys.

## Deps and dependency tracking

`Dep` is a minimal observable: it keeps its subscribers in a `WeakSet` and offers `depend()` and `notify()`. The weak references matter — a dep never keeps a watcher alive, which is why you must [hold on to your watchers](../guide/gotchas.md#watchers-must-be-kept-alive).

Dependency tracking works through a class-level stack, `Dep.stack`. When a watcher evaluates its function it pushes itself onto the stack; every read trap that fires during the evaluation calls `dep.depend()`, which registers the dep with the watcher on top of the stack. When no watcher is evaluating, the stack is empty and read traps skip tracking entirely — reads outside of watchers cost almost nothing.

Each evaluation rebuilds the dependency set from scratch: newly-read deps are collected in `Watcher._new_deps`, and afterwards `cleanup_deps()` unsubscribes the watcher from deps it no longer read and swaps the two sets. This is what makes tracking fully dynamic — if a branch of your function stops reading some state, changes to that state stop triggering the watcher.

On `notify()`, subscribers are updated in ascending watcher-id order. Ids are handed out at watcher creation, so updates cascade in creation order — parents before the children they created, in a typical UI tree.

## The proxy registry

`proxy_db.py` keeps a single global registry with one entry per wrapped target object. The entry is a `TargetDep`: the dep for the container as a whole, which also owns

* the **keydeps** — per-key `KeyDep`s for dict targets, created on demand when a key is first read under tracking, and
* the **proxies** — weak references to the (at most four) proxies wrapping the target, keyed on the `(readonly, shallow)` configuration.

This registry is why `reactive(data) is reactive(data)` holds: `proxy()` first checks the registry for an existing proxy with the requested configuration and only creates one if there is none. It is also why watchers and mutations always agree — no matter which proxy a read or write goes through, they meet on the same `TargetDep`.

The registry is keyed on `id(target)`, because plain containers support neither weak references nor (reliable) hashing. This is safe against id reuse: a `TargetDep` holds a strong reference to its target, so an id can only be recycled after the entry for its previous target is already gone.

### Lifetimes

Cleanup relies purely on reference counting; there are no GC hooks and nothing needs the cycle collector:

* Every `Proxy` holds a strong reference to its `TargetDep` (`__dep__`).
* Every watcher holds strong references to the deps it currently depends on; a `KeyDep` in turn holds its owning `TargetDep`.
* The registry itself, and the keydeps/proxies mappings inside `TargetDep`, hold only weak references, with weakref callbacks that remove dead entries.

So a target's reactive state lives exactly as long as someone can still observe it: once the last proxy is destroyed and no watcher depends on the target anymore, the `TargetDep` is destroyed, its registry entry removes itself, and observ's reference to the raw target is released.

## Watchers

A `Watcher` wraps a function and manages its dependencies. Its `get()` method is the heart of tracking: push `self` onto `Dep.stack`, call the function, optionally traverse the result (for deep watching), pop the stack, and clean up stale deps.

Watchers come in two flavors, distinguished by the `lazy` flag:

* **Eager** watchers (created by `watch()` / `watch_effect()`) evaluate immediately on construction and re-evaluate on every change — either synchronously (`sync=True`) or via the scheduler.
* **Lazy** watchers only set a `dirty` flag when notified. `computed()` is a lazy watcher plus a getter: the getter re-evaluates only when the flag is set and otherwise returns the cached `value`.

Computed values chain through `Watcher.depend()`: when a computed getter is called *while another watcher is evaluating*, the computed's watcher re-registers all of its own deps with the outer watcher. The outer watcher thereby depends on the computed's underlying state directly, so invalidation propagates through arbitrarily deep computed chains without any bookkeeping per chain.

The `no_recurse` guard (set for watchers without a callback, i.e. `watch_effect` and `computed`) prevents a watcher from re-triggering itself when its own evaluation writes to state it depends on.

### Deep watching

`deep=True` (the default when watching a proxy directly) means "also fire on changes nested anywhere inside the watched value". After evaluating, the watcher runs `traverse()` over the result, which walks the whole tree and registers a dependency on the dep of every (mutable) container it encounters. For efficiency it walks the *raw* targets rather than iterating through proxies (which would allocate a proxy per visited value); nested containers that don't have a registry entry yet are materialized along the way so future mutations through any proxy will be seen. The traversal keeps a `seen` set of ids, so cyclic data structures are supported.

### Callbacks and bound methods

Watcher callbacks may accept zero, one (`new`) or two (`new, old`) arguments. Rather than inspecting signatures up front (which fails for e.g. `functools.partial` objects), the first invocation discovers the arity by trial: a `TypeError` raised *directly* by the call — recognized by inspecting the traceback — means "wrong number of arguments, try the next arity"; a `TypeError` from inside the callback propagates. The discovered arity is cached for subsequent calls.

Bound methods passed as watched function or callback are stored weakly (a wrapper holding a `weakref` to the instance), so a watcher never keeps your objects alive. Async functions and callbacks are supported as well: coroutines are scheduled as tasks on the running asyncio loop, or run to completion when no loop is running.

## The scheduler

Non-`sync` watchers don't run on `notify()`; they are handed to the global `Scheduler`, which queues them until `flush()` is called. Queueing is deduplicated on watcher id, which is what batches multiple mutations between flushes into a single update per watcher.

The scheduler doesn't know when to flush — that is the job of the event loop integration, registered via `init()` (see [Scheduling](../guide/scheduling.md)). The registered `request_flush` callback is invoked once when the first watcher lands in an empty queue, and should arrange for `flush()` to run soon on the loop's thread.

`flush()` sorts the queue by watcher id and runs the watchers in order. Watchers queued *during* a flush (by callbacks mutating state) are spliced into the not-yet-processed part of the queue by id, so the whole cascade settles in a single flush while preserving creation order — and a watcher whose id was already passed runs next, immediately. If any single watcher is run more than 100 times within one flush, the scheduler raises a `RecursionError` naming the watched expression, cutting off infinite update loops.
