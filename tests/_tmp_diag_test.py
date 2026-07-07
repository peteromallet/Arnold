import pytest
from arnold.workflow import check_workflow_source
from arnold_pipelines.megaplan.workflows import planning
from arnold.workflow.source_compiler import lower_workflow_file
from collections import Counter


def test_diag():
    src = planning.AUTHORING_SOURCE_PATH.read_text(encoding="utf-8")
    res = check_workflow_source(src, source_path=planning.AUTHORING_SOURCE_PATH)
    print("NUM DIAGNOSTICS:", len(res.diagnostics))
    print("BY CODE:", dict(Counter(str(d.code) for d in res.diagnostics)))
    for d in res.diagnostics:
        print("  ", d.code, "|", (getattr(d, "message", "") or "")[:140])
    assert True  # always pass, just for output


def test_lowered():
    lowered = lower_workflow_file(planning.AUTHORING_SOURCE_PATH)
    ids = [s.id for s in lowered.steps]
    from collections import Counter
    dups = {k: v for k, v in Counter(ids).items() if v > 1}
    print("NUM LOWERED STEPS:", len(ids))
    print("ORDER:", ids)
    print("DUP IDS:", dups)
    print("NUM ROUTES:", len(lowered.routes))
    for r in lowered.routes:
        print("  ROUTE", r.id, "|", r.source, "->", r.target, "|", r.label, "|", r.condition_ref)
    assert True
