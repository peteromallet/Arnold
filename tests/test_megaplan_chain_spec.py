from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
CHAIN = ROOT / "docs" / "megaplan_chains" / "readable_ready_templates" / "chain.yaml"
README = ROOT / "docs" / "megaplan_chains" / "readable_ready_templates" / "README.md"


def test_readable_ready_template_chain_stays_on_codex_route() -> None:
    spec = yaml.safe_load(CHAIN.read_text(encoding="utf-8"))
    milestones = spec["milestones"]

    assert milestones
    assert {milestone["profile"] for milestone in milestones} == {"all-codex"}
    assert {milestone["vendor"] for milestone in milestones} == {"codex"}
    assert "all-claude" not in CHAIN.read_text(encoding="utf-8")


def test_readable_ready_template_chain_docs_match_route() -> None:
    readme = README.read_text(encoding="utf-8")

    assert "profile: all-codex" in readme
    assert "vendor: codex" in readme
    assert "does not reliably submit the initial prompt" in readme
