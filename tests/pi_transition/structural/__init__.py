"""L3 — Pi-backed fake dispatcher for the structural harness.

Integrates Pi into the existing Sisypy structural harness (``tests/structural_harness/``)
by providing a ``DISPATCHER_FAKE_PI`` dispatcher that uses Pi's faux provider
instead of Arnold's AIAgent.

This allows all existing structural scenarios (M2, M3, M4, M5, M6) to run
with Pi as the agent engine while keeping compile-only deterministic outputs.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tests.harness_common import (
    DISPATCHER_FAKE,
    DISPATCHER_FAKING,
    FAKE_DISPATCHERS,
    FLOW_KIND_STRUCTURAL_CONTRACT,
    MODEL_BEHAVIOR_SCRIPTED,
    STATUS_SUCCESS,
    build_flow_metadata,
)

# Extended dispatcher constant for Pi-backed fake mode
DISPATCHER_FAKE_PI = "fake_pi"


def build_pi_structural_chain(frozen_root: Path) -> dict[str, Any]:
    """Build a structural evidence chain using Pi's faux provider.

    This mirrors the pattern in ``actors.py:build_faking_structural_chain``
    but tags the evidence as originating from Pi.

    During transition, this function will invoke the Pi worker via
    ``harness.run_pi_turn_fixture()``.  Until that integration is complete,
    it produces compile-only evidence identical to the existing faking chain.
    """
    frozen_root.mkdir(parents=True, exist_ok=True)

    flow_metadata = build_flow_metadata(
        flow_kind=FLOW_KIND_STRUCTURAL_CONTRACT,
        dispatcher=DISPATCHER_FAKE_PI,
        model_behavior=MODEL_BEHAVIOR_SCRIPTED,
        entrypoint="structural_harness",
        status=STATUS_SUCCESS,
    )

    (frozen_root / "flow_metadata.json").write_text(
        json.dumps(flow_metadata, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    manifest: dict[str, Any] = {
        "dispatcher": DISPATCHER_FAKE_PI,
        "flow_metadata_path": str(frozen_root / "flow_metadata.json"),
        "written": [str(frozen_root / "flow_metadata.json")],
    }

    # When Pi worker is integrated, extend manifest with turn results:
    # from tests.pi_transition.harness import run_pi_turn_fixture
    # result = run_pi_turn_fixture(user_message=..., response_contract=...)
    # ... write result to frozen evidence ...

    (frozen_root / "freeze_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    return manifest


# ── Adapter registration ─────────────────────────────────────────────────────
#
# When Pi worker is ready, register this adapter in
# ``tests/structural_harness/adapter.py``:
#
#   from tests.pi_transition.structural import DISPATCHER_FAKE_PI
#
#   # In VibeComfyProjectAdapter._capture_structural_evidence():
#   if run.dispatcher == DISPATCHER_FAKE_PI:
#       from tests.pi_transition.structural import build_pi_structural_chain
#       return build_pi_structural_chain(frozen_root)
#
# This allows scenarios to specify ``dispatcher: fake_pi`` and route through Pi.
