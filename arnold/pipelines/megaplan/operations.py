"""REMOVED — planning operation dispatch has been relocated.

The canonical home for Megaplan planning operation dispatch is now:

    from megaplan.planning.operations import (
        operation_registry,
        override_catalog,
        SUPPORTED_OPERATIONS,
        profile_validate_operation,
        resume_phase_args,
        preflight_or_raise,
    )

This file was a compatibility facade (re-export shim) during the M5a
migration and has been replaced with failing guidance.  Update your
imports to the canonical path above.
"""

raise ImportError(
    "arnold.pipelines.megaplan.operations has been removed. "
    "Use megaplan.planning.operations instead."
)
