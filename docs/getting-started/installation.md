# Installation

Observ is published on [PyPI](https://pypi.org/project/observ/) and has **no dependencies**. It supports Python 3.13 and up.

=== "uv"

    ```bash
    uv add observ
    ```

=== "pip"

    ```bash
    pip install observ
    ```

=== "poetry"

    ```bash
    poetry add observ
    ```

That's it! Continue with the [Quick Start](quick-start.md) to learn the core concepts.

!!! note "Optional integrations"

    Observ itself is framework agnostic. If you want to integrate with a UI event loop, you'll need the corresponding framework installed as well, for example [PySide6](https://pypi.org/project/PySide6/) or [rendercanvas](https://pypi.org/project/rendercanvas/). See [Scheduling](../guide/scheduling.md) for details.
