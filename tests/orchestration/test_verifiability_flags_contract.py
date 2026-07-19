from __future__ import annotations

from arnold_pipelines.megaplan.handlers.plan import _build_verifiability_flags
from arnold_pipelines.megaplan.orchestration.critique_custody import prepare_critique_payload


def test_host_verifiability_flags_are_critique_custody_complete() -> None:
    flags = _build_verifiability_flags(
        [
            {
                "criterion": "A maintainer visually approves the rendered layout.",
                "priority": "must",
                "requires": ["human_visual_review"],
            }
        ],
        worker_caps={},
    )

    assert flags
    assert all(flag["evidence"] == flag["concern"] and flag["evidence"] for flag in flags)
    payload = {
        "checks": [],
        "flags": flags,
        "verified_flag_ids": [],
        "disputed_flag_ids": [],
    }
    prepare_critique_payload(payload, expected_check_ids=[])
