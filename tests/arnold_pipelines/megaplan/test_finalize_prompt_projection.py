from __future__ import annotations

from arnold_pipelines.megaplan.prompts.finalize import (
    _FINALIZE_SELECTOR_HINT_LIMIT,
    _finalize_clearance_prompt_projection,
    _finalize_metadata_prompt_projection,
)


def test_finalize_metadata_projection_bounds_high_cardinality_selectors() -> None:
    selectors = [
        {"kind": "path", "value": f"tests/test_{index}.py", "reason": "dependent"}
        for index in range(_FINALIZE_SELECTOR_HINT_LIMIT + 17)
    ]
    metadata = {
        "version": 8,
        "test_blast_radius": {
            "strategy": "scoped",
            "changed_surfaces": ["src/runtime.py"],
            "selectors": selectors,
        },
    }

    projected = _finalize_metadata_prompt_projection(metadata)

    blast_radius = projected["test_blast_radius"]
    assert blast_radius["selectors"] == selectors[:_FINALIZE_SELECTOR_HINT_LIMIT]
    assert blast_radius["changed_surfaces"] == ["src/runtime.py"]
    assert blast_radius["selector_projection"] == {
        "authoritative_count": len(selectors),
        "included_count": _FINALIZE_SELECTOR_HINT_LIMIT,
        "omitted_count": 17,
        "purpose": (
            "Prompt-only bounded hints. The handler compiles validation from the "
            "complete plan metadata artifact."
        ),
    }
    assert metadata["test_blast_radius"]["selectors"] == selectors


def test_finalize_clearance_projection_preserves_every_finding_without_hash_repetition() -> None:
    clearance = {
        "admitted": True,
        "plan_sha256": "sha256:plan",
        "source_receipts": [{"sha256": "sha256:receipt"}],
        "resolutions": [
            {
                "finding_id": "CF-1",
                "flag_id": "CF-1",
                "disposition": "verified_plan_mutation",
                "plan_artifact": "plan_v8.md",
                "plan_sha256": "sha256:plan",
                "evidence": "Step 1 preserves the repair.",
            },
            {
                "finding_id": "CF-2",
                "flag_id": "CF-2",
                "disposition": "verified_plan_mutation",
                "plan_artifact": "plan_v8.md",
                "plan_sha256": "sha256:plan",
                "evidence": "Step 2 preserves the repair.",
            },
        ],
    }

    projected = _finalize_clearance_prompt_projection(clearance)

    assert projected["resolutions"] == [
        {
            "finding_id": "CF-1",
            "disposition": "verified_plan_mutation",
            "evidence": "Step 1 preserves the repair.",
        },
        {
            "finding_id": "CF-2",
            "disposition": "verified_plan_mutation",
            "evidence": "Step 2 preserves the repair.",
        },
    ]
    assert projected["source_receipt_count"] == 1
    assert "source_receipts" not in projected
    assert all("plan_sha256" not in row for row in projected["resolutions"])
    assert clearance["resolutions"][0]["plan_sha256"] == "sha256:plan"
