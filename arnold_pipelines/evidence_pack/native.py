"""Compatibility shim — re-exports from ``arnold.pipelines.evidence_pack.native``.

Do NOT add graph-era imports or behavior forks to this module.
"""

from arnold.pipelines.evidence_pack.native import (  # noqa: F401
    build_native_program,
    evidence_pack_native,
)

__all__ = [
    "build_native_program",
    "evidence_pack_native",
]
