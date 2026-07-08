# Examples

Complete, runnable examples live in the [`examples/`](https://github.com/fork-tongue/observ/tree/master/examples) directory of the repository. This page walks through what they demonstrate.

## Qt (`observe_qt.py`)

[`examples/observe_qt.py`](https://github.com/fork-tongue/observ/blob/master/examples/observe_qt.py) shows the unidirectional data flow that observ enables in a classic widget UI:

* A single `state = reactive({"clicked": 0, "progress": 0})` is shared between two independent widgets.
* The `Display` widget declares *watchers* that keep a label and a progress bar in sync with the state — note the `immediate=True` so the widgets are also initialized from the watchers:

    ```python
    self.watchers["label"] = watch(label_text, self.label.setText, immediate=True)
    self.watchers["progress_visible"] = watch(
        lambda: state["progress"] > 0, self.progress.setVisible, immediate=True
    )
    ```

* The `Controls` widget never talks to `Display` directly — it only *mutates the state* (from a worker thread's signals), and the watchers take care of the rest.
* The scheduler is hooked up with `init("asyncio")` and the app runs under `QtAsyncio.run()`, so watcher callbacks are batched per event loop iteration.

Run it with:

```bash
uv run --group qt examples/observe_qt.py
```

## Rendercanvas (`observe_rc.py`)

[`examples/observe_rc.py`](https://github.com/fork-tongue/observ/blob/master/examples/observe_rc.py) demonstrates observ driving an interactive canvas application:

* The positions of three draggable blocks live in reactive state.
* Two `@watch`-decorated effects keep the blocks at a consistent distance from each other: dragging one block updates the state, which triggers the effects, which update the other blocks' positions in turn.
* The scheduler is integrated with the rendercanvas loop via `scheduler.register_rendercanvas(loop)`.

This example also shows the scheduler's cycle handling at work: the two effects write to state the other one depends on, and the scheduler's deduplication is what lets them settle instead of ping-ponging forever.

Run it with:

```bash
uv run --group pygfx --group numpy examples/observe_rc.py
```
