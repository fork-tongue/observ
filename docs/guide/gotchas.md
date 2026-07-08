# Gotchas and Best Practices

## Keep no references to raw data

Observ keeps references to the object passed to `reactive()` in order to keep track of dependencies and proxies for that object. When the object that is passed into `reactive()` is not managed by other code, observ cleans up its references automatically when the proxy is destroyed. However, if there is another reference to the original object, observ will only release its own reference when the garbage collector runs and all other references to the object are gone.

For this reason, the **best practice** is to keep **no references** to the raw data, and instead work with the reactive proxies **only**:

```python
# Good: no reference to the raw dict survives
state = reactive({"count": 0})

# Risky: `data` and `state` refer to the same underlying dict,
# but writes to `data` are invisible to observ
data = {"count": 0}
state = reactive(data)
data["count"] = 1  # no watcher will fire!
```

If you need the plain data back — to serialize it, for example — use `to_raw(state)`, which returns a proxy-free copy.

## Only exact plain types are reactive

Only `dict`, `list`, `set` and `tuple` (and their contents) are proxied — deliberately not their subclasses, and not arbitrary objects. Attribute access on a custom object stored inside reactive state is not tracked:

```python
state = reactive({"point": MyPoint(0, 0)})

state["point"] = MyPoint(1, 1)  # tracked: item write on the dict
state["point"].x = 1            # NOT tracked
```

Model your observable state as plain data (as you would for JSON), and keep rich objects at the edges.

## Don't mutate state in computed functions

Computed functions should be pure derivations of state. Mutating reactive state from inside a computed (or inside a watcher's watched function) can lead to infinite update loops, which the scheduler cuts off with a `RecursionError` after 100 iterations. Put side effects in watcher *callbacks* instead.

## Watchers must be kept alive

`watch()` and `watch_effect()` return a `Watcher` object, and observ holds no strong reference to it. If you drop the return value the watcher is garbage collected and the callback silently stops firing:

```python
watch(lambda: state["count"], callback)                # wrong: dies immediately
self.watcher = watch(lambda: state["count"], callback)  # right
```

The flip side: bound methods used as callback are stored weakly, so a watcher never keeps your objects alive. See [Watchers](watchers.md#methods-as-watched-functions-or-callbacks).

## `new` and `old` can be the same object

When a watcher watches a container (or uses `deep=True`), the callback's `new` and `old` arguments refer to the same object: observ does not snapshot the previous state of a container. If you need to diff old against new, watch a *derived* value instead (e.g. a computed that returns a copy or a summary of the container).
