"""M6 stub: legacy tool removed in clean-break purge."""
from __future__ import annotations

import threading

_interrupt_event = threading.Event()


def set_interrupt(value: bool) -> None:
    """Set or clear the process interrupt flag (M6 stub)."""
    if value:
        _interrupt_event.set()
    else:
        _interrupt_event.clear()

__all__ = ['set_interrupt']
