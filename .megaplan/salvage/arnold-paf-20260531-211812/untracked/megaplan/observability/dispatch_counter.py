"""Thread-local dispatch counter for hermes judge invocations (M5-eval).

Tracks invocations of :func:`megaplan.workers.hermes.dispatch_judge` for
assertions like ``assert_zero_dispatch`` used by ``re_judge(live=False)`` to
prove zero model I/O.

Counter is **thread-local and in-process only** — worker subprocesses bypass
it. M5-eval unit tests run in-process; production multi-process invocation is
out of scope (filed as M5-cal debt).
"""

from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import Iterator

_HERMES_DISPATCH_CALLS = threading.local()


def _current_count() -> int:
    return int(getattr(_HERMES_DISPATCH_CALLS, "count", 0))


@contextmanager
def assert_zero_dispatch() -> Iterator[None]:
    """Raise on exit if the dispatch counter advanced inside the block."""
    before = _current_count()
    yield
    after = _current_count()
    if after > before:
        raise AssertionError(
            f"dispatch_judge invoked {after - before} time(s) inside assert_zero_dispatch"
        )
