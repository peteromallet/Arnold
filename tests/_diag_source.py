"""Diagnostic helper run via pytest to inspect workflow source state."""
import sys
from pathlib import Path

from arnold.workflow import check_workflow_source
from arnold.workflow.compiler import compile_pipeline
from arnold.workflow.source_compiler import lower_workflow_file

from arnold_pipelines.megaplan.workflows import planning


def main():
    source_path = planning.PYPELINE_AUTHORING_SOURCE_PATH
    result = check_workflow_source(
        source_path.read_text(encoding="utf-8"),
        source_path=source_path,
    )
    print("=== check_workflow_source ===")
    print("ok:", result.ok)
    print("diagnostics count:", len(result.diagnostics))
    for d in result.diagnostics:
        print("  DIAG:", repr(d))
    print()

    print("=== lowered workflow ===")
    lowered = lower_workflow_file(source_path)
    print("id:", lowered.id, "version:", lowered.version)
    print("step count:", len(lowered.steps))
    print("steps:", [s.id for s in lowered.steps])
    print()

    # Check for duplicate step ids in lowered
    ids = [s.id for s in lowered.steps]
    seen = set()
    dups = []
    for i in ids:
        if i in seen:
            dups.append(i)
        seen.add(i)
    print("duplicate lowered step ids:", dups)
    print()

    print("=== compile_pipeline ===")
    try:
        manifest = compile_pipeline(lowered)
        print("compiled OK, manifest id:", manifest.id)
        m_ids = [s.id for s in manifest.steps]
        print("manifest step count:", len(m_ids))
        print("manifest steps:", m_ids)
        seen2 = set()
        mdups = []
        for i in m_ids:
            if i in seen2:
                mdups.append(i)
            seen2.add(i)
        print("duplicate manifest step ids:", mdups)
    except Exception as e:
        print("COMPILE ERROR:", type(e).__name__, e)


def test_diag():
    main()


if __name__ == "__main__":
    main()
