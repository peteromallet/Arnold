"""Arnold agent tools package.

M6 note: legacy compatibility shims that re-exported vendored Hermes tools
from the deleted ``arnold.pipelines`` package were removed.  The remaining
modules in this package are native Arnold implementations.
"""

from __future__ import annotations

def check_file_requirements():
    """File tools only require the terminal backend to be available."""
    from arnold.agent.tools.terminal_tool import check_terminal_requirements

    return check_terminal_requirements()


__all__ = ["check_file_requirements"]
