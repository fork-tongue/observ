__version__ = "0.13.1"


from .init import init, loop_factory
from .proxy import (
    reactive,
    readonly,
    ref,
    shallow_reactive,
    shallow_readonly,
    to_raw,
)
from .scheduler import scheduler
from .watcher import computed, watch, watch_effect, Watcher
