"""`tasks/` — *which worker* runs a cell (§4). Deliberately separate from `dag/`.

`dag/` answers "is this cell ready"; this package answers "who runs it and
where". Keeping them apart is what stops the readiness rules from quietly
growing queue semantics — and the queue from growing a second opinion about
readiness.
"""

from app.tasks.app import build_app, procrastinate_app, queue_dsn
from app.tasks.cells import TASK_NAME, enqueue_cell, execute_cell

__all__ = [
    "TASK_NAME",
    "build_app",
    "enqueue_cell",
    "execute_cell",
    "procrastinate_app",
    "queue_dsn",
]
