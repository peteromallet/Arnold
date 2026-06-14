"""M4 T11 — typed subprocess oracle (first ``run()`` consumer).

This module is a re-export shim.  The canonical home is
:mod:`arnold.runtime.oracle`; this module re-exports ``OracleResult``
and ``run`` so existing callers continue to work without import-path
changes.
"""

from arnold.runtime.oracle import OracleResult, run  # noqa: F401
