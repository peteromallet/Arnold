from __future__ import annotations

import json

from arnold_pipelines.megaplan.prompts.review import (
    REVIEW_EVIDENCE_PROMPT_MAX_CHARS,
    _review_evidence_block,
)


def test_review_evidence_block_projects_large_evidence_without_raw_dump(tmp_path):
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    payload = {
        "schema": "megaplan.review_evidence",
        "schema_version": 1,
        "accepted": True,
        "would_block": False,
        "providers_used": ["GreenSuiteProvider"],
        "evidence": [
            {
                "kind": "green_suite",
                "status": "satisfied",
                "summary": "verification suite passed",
                "details": {
                    "stdout": "x" * 300_000,
                    "changed_files": [f"file_{idx}.py" for idx in range(1_000)],
                },
                "provider": "GreenSuiteProvider",
                "source": "verification:abc",
                "artifact": {
                    "path": "verification/raw_abc.log",
                    "sha256": "sha256:abc",
                    "artifact_type": "text/plain",
                },
                "artifacts": [
                    {
                        "path": f"verification/raw_{idx}.log",
                        "sha256": f"sha256:{idx}",
                        "artifact_type": "text/plain",
                    }
                    for idx in range(20)
                ],
            }
        ],
        "green_suite": {
            "delta": {
                "computable": True,
                "newly_failing": [],
                "still_green": [f"test_{idx}" for idx in range(5_000)],
            }
        },
    }
    (plan_dir / "review_evidence.json").write_text(json.dumps(payload), encoding="utf-8")

    block = _review_evidence_block(plan_dir)

    assert len(block) < REVIEW_EVIDENCE_PROMPT_MAX_CHARS
    assert "verification suite passed" in block
    assert "verification/raw_abc.log" in block
    assert "full data remains in `review_evidence.json`" in block
    assert "x" * 10_000 not in block
    assert '"still_green": 5000' in block
    assert '"artifacts_omitted": 12' in block
