from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
RUNBOOK = (
    REPO_ROOT
    / "docs"
    / "megaplan"
    / "final-cloud-runtime-promotion-runbook-2026-07-31.md"
)


def test_external_runtime_staging_uses_an_independent_interpreter() -> None:
    runbook = RUNBOOK.read_text(encoding="utf-8")

    assert "python3 -m venv --copies '${RUNTIME_VENV}'" in runbook
    assert "python3 -m venv '${RUNTIME_VENV}'" not in runbook
