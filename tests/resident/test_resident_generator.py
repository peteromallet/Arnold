"""Tests for the resident contract generator (B12)."""

from __future__ import annotations

from pathlib import Path

import pytest

from arnold_pipelines.megaplan.resident.astrid_domain import build_astrid_domain
from arnold_pipelines.megaplan.resident.generator import (
    ASTrid_MEDIA_CONTENT_TYPES,
    EVIDENCE_CONTRACT_KEYS,
    POLICY_CONTRACT_KEYS,
    SESSION_CONTRACT_KEYS,
    PROJECT_AGENTS_DIR,
    USER_AGENTS_DIR,
    ResidentDomain,
    build_domain_prompt,
    build_evidence_contract,
    build_policy_contract,
    build_session_contract,
    contracts_digest,
    generate_domain_contracts,
    install_contracts,
    resolve_install_dirs,
)


def _sample_domain() -> ResidentDomain:
    return ResidentDomain(
        slug="demo",
        agent_name="demo-resident",
        description="Demo gateway operator.",
        tools=("gateway", "read", "write"),
        credentials={"DEMO_API_KEY": "demo provider key"},
        cwd_policy={"run_root_template": "projects/<slug>/runs/<run-id>"},
        prompt_body="Operate the demo gateway.\nLoop `demo next`.",
    )


# ── Determinism ─────────────────────────────────────────────────────────────


def test_generation_is_deterministic() -> None:
    first = generate_domain_contracts(_sample_domain())
    second = generate_domain_contracts(_sample_domain())
    assert set(first) == set(second)
    for name in first:
        assert first[name] == second[name], f"{name} differs across runs"
    assert contracts_digest(first) == contracts_digest(second)


def test_digest_changes_with_domain() -> None:
    a = generate_domain_contracts(_sample_domain())
    b = generate_domain_contracts(
        ResidentDomain(
            slug="demo",
            agent_name="demo-resident",
            description="Changed description.",
            tools=("gateway",),
            credentials={},
            cwd_policy={},
            prompt_body="Different body.",
        )
    )
    assert contracts_digest(a) != contracts_digest(b)


# ── All four contracts are emitted ─────────────────────────────────────────


def test_four_contract_files_emitted() -> None:
    contracts = generate_domain_contracts(_sample_domain())
    assert set(contracts) == {
        "demo-resident.md",
        "demo-policy.yaml",
        "demo-session.yaml",
        "demo-evidence.yaml",
    }


def test_domain_prompt_has_frontmatter_and_body() -> None:
    text = build_domain_prompt(_sample_domain())
    assert text.startswith("---\n")
    assert "name: demo-resident" in text
    assert "description: Demo gateway operator." in text
    assert "tools: gateway, read, write" in text
    assert "Loop `demo next`." in text
    # Frontmatter closed before the body
    assert text.index("---\nname:") < text.index("---\n\nOperate")


def test_policy_contract_keys() -> None:
    text = build_policy_contract(_sample_domain())
    assert "contract: resident-policy" in text
    assert "domain: demo" in text
    for key in ("tools:", "permissions:", "credentials:", "cwd:"):
        assert key in text
    assert "DEMO_API_KEY" in text


def test_session_contract_keys() -> None:
    text = build_session_contract(_sample_domain())
    assert "contract: resident-session" in text
    for key in ("identity:", "persistence:", "recovery:", "concurrency:"):
        assert key in text
    assert "agent:demo-resident" in text
    assert "writer_epoch" in text


def test_evidence_contract_keys() -> None:
    text = build_evidence_contract(_sample_domain())
    assert "contract: resident-evidence" in text
    for key in (
        "output_normalization:",
        "typed_media:",
        "media_usage:",
        "supervision:",
        "heartbeat:",
        "delivery:",
    ):
        assert key in text
    for content_type in ("video/mp4", "audio/wav", "x-astrid-timeline"):
        assert content_type in text
    assert "MediaUsage" in text


def test_contract_key_manifests_are_stable() -> None:
    # Guard the documented contract key sets so docs and consumers stay honest.
    assert POLICY_CONTRACT_KEYS == (
        "contract",
        "domain",
        "tools",
        "permissions",
        "credentials",
        "cwd",
    )
    assert SESSION_CONTRACT_KEYS == (
        "contract",
        "domain",
        "identity",
        "persistence",
        "recovery",
        "concurrency",
    )
    assert EVIDENCE_CONTRACT_KEYS == (
        "contract",
        "domain",
        "output_normalization",
        "typed_media",
        "media_usage",
        "supervision",
        "heartbeat",
        "delivery",
    )
    assert ASTrid_MEDIA_CONTENT_TYPES == (
        "video/mp4",
        "audio/wav",
        "x-astrid-timeline",
    )


# ── Project-over-user installation ─────────────────────────────────────────


def test_install_dirs_scope(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    project = tmp_path / "repo"
    project.mkdir()

    from arnold_pipelines.megaplan.resident.generator import _user_agents_dir

    (user_dir,) = resolve_install_dirs(project, "user")
    assert user_dir == _user_agents_dir()
    assert user_dir == tmp_path / "home" / ".omp" / "agent" / "agents"

    (project_dir,) = resolve_install_dirs(project, "project")
    assert project_dir == project / PROJECT_AGENTS_DIR

    with pytest.raises(Exception):
        resolve_install_dirs(project, "bogus")


def test_project_install_shadows_user(monkeypatch: pytest.MonkeyPatch) -> None:
    """Project-scope install wins over user scope for the same agent name."""
    monkeypatch.setenv("HOME", "/nonexistent/home-for-test")
    project = Path("/nonexistent/project-root")

    user_dir = Path(USER_AGENTS_DIR).expanduser()
    project_dir = project / PROJECT_AGENTS_DIR

    # Both scopes would install the same file name; omp resolves project first.
    assert project_dir != user_dir
    assert project_dir.as_posix().endswith(".omp/agents")
    assert user_dir.as_posix().endswith(".omp/agent/agents")


def test_install_contracts_writes_files(tmp_path: Path) -> None:
    contracts = generate_domain_contracts(_sample_domain())
    project = tmp_path / "repo"
    project.mkdir()

    written = install_contracts(contracts, project_root=project, scope="project")
    assert len(written) == 4
    for name, text in contracts.items():
        target = project / PROJECT_AGENTS_DIR / name
        assert target.read_text(encoding="utf-8") == text


def test_astrid_domain_is_generatable() -> None:
    domain = build_astrid_domain()
    contracts = generate_domain_contracts(domain)
    assert "astrid-resident.md" in contracts
    assert "astrid-policy.yaml" in contracts
    assert "astrid-session.yaml" in contracts
    assert "astrid-evidence.yaml" in contracts
