from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.validate_post_m11_release_evidence import validate


REPO = Path(__file__).resolve().parents[1]
RECORD = REPO / "docs/megaplan/post-m11-release-evidence-20260731.json"


def test_release_evidence_record_is_structurally_valid() -> None:
    validate(RECORD)


def test_release_evidence_cannot_claim_done_with_pending_gates(
    tmp_path: Path,
) -> None:
    data = json.loads(RECORD.read_text(encoding="utf-8"))
    data["record_status"] = "complete"
    candidate = tmp_path / "release-evidence.json"
    candidate.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(ValueError, match="residuals are pending"):
        validate(candidate)
