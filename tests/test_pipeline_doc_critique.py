"""Sprint 2 acceptance test #4 — 3× critique→revise loop runs to completion."""

from __future__ import annotations

import json
from pathlib import Path


def test_doc_critique_three_iterations(tmp_path: Path) -> None:
    from arnold.pipelines.megaplan._pipeline.demos.doc_critique import run_demo

    fixture = tmp_path / "fixture.md"
    fixture.write_text(
        "The original document. Sentences should be replaced and lengthened "
        "by successive revision passes. Each pass appends a marker that the "
        "next critique pass scores against. The loop runs three times "
        "before halting, per the configured maximum iteration count."
    )

    result = run_demo(fixture, tmp_path)

    # 3 critique passes (v1, v2, v3) + 2 revise passes (v1, v2) — the third
    # critique decides to halt instead of revising again, so only two
    # revisions land.
    critique_paths = sorted((tmp_path / "critique_versions").glob("critique_v*.json"))
    revise_paths = sorted((tmp_path / "doc_versions").glob("doc_v*.md"))
    assert len(critique_paths) == 3, [p.name for p in critique_paths]
    assert len(revise_paths) == 2, [p.name for p in revise_paths]

    state = json.loads((tmp_path / "state.json").read_text())
    assert state["critique_iter"] == 3

    # Each critique json must parse with a float score and an iteration field.
    for path in critique_paths:
        data = json.loads(path.read_text())
        assert isinstance(data, dict)
        assert isinstance(data.get("score"), float)
        assert isinstance(data.get("iteration"), int)

    # Final revised doc must differ from the original fixture.
    final_doc = revise_paths[-1].read_text()
    assert final_doc != fixture.read_text()
    assert "Revision pass" in final_doc

    # Doc continuity: the original fixture content must survive into
    # the final revised doc (revisions are appended, not replacements).
    assert fixture.read_text().strip() in final_doc, (
        "final revised doc lost the original fixture content"
    )
    assert "Revision pass 1" in final_doc
    assert "Revision pass 2" in final_doc

    # Critique chain: critique_v1 reads the fixture; v2 reads doc_v1;
    # v3 reads doc_v2 (proves the latest_doc state-patch threading
    # works between critique and revise).
    v1 = json.loads(critique_paths[0].read_text())
    v2 = json.loads(critique_paths[1].read_text())
    v3 = json.loads(critique_paths[2].read_text())
    assert v1["doc_read"] == str(fixture)
    assert "doc_v1.md" in v2["doc_read"]
    assert "doc_v2.md" in v3["doc_read"]

    assert result.get("final_stage") == "critique"
