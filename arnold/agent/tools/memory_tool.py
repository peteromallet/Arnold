"""Compatibility shim for the legacy local memory tool.

The full local MEMORY.md tool was removed in the M6 clean break, but older
agent paths still instantiate ``MemoryStore`` when memory is enabled in config.
Keep that path inert instead of letting optional memory crash agent startup.
"""
from __future__ import annotations

class MemoryStore:
    """No-op legacy memory store used by older agent code paths."""

    def __init__(self, *args, **kwargs):
        pass

    def load_from_disk(self):
        return None

    def format_for_system_prompt(self, target: str = "memory") -> str:
        return ""

def memory_tool(*args, **kwargs):
    """Legacy memory tool stub (M6)."""
    return '{"success": false, "error": "memory_tool was removed in M6"}'

__all__ = ['MemoryStore', 'memory_tool']
