__version__ = "0.13.0"


from .proxy import (
    reactive,
    readonly,
    ref,
    shallow_reactive,
    shallow_readonly,
    to_raw,
)
from .scheduler import scheduler
from .watcher import computed, watch, watch_effect
