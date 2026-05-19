"""Guard rail: prevent skill-doc duplication from creeping back in.

The setup code in `megaplan/cli.py` writes user-level skill files at
`~/.claude/skills/...` and `~/.codex/skills/...`. There are two install modes:

* `copy`   — for composite skills built from multiple sources (header +
             canonical + appendix). The installed file is a regenerated copy.
* `symlink` — for single-source skills where the installed content is
              identical to a bundled canonical file. These MUST be symlinks
              so they cannot drift from the canonical, and so the canonical
              has exactly one on-disk representation.

This module enforces three invariants:

1. Every target marked `install: "symlink"` actually installs as a symlink
   pointing at the canonical bundle.
2. Every single-source skill (where `bundled_global_file(name)` equals the
   raw canonical file) is marked `install: "symlink"`. Reverting one to
   `copy` (or omitting the field) is the regression we're guarding against.
3. `handle_setup_global` is idempotent — running it twice against the same
   home leaves symlinks unchanged.

If you add a new skill and tests fail here, either:
  * make the skill content equal to its canonical file and set
    `install: "symlink"`, OR
  * document why the skill needs `install: "copy"` (composite content) and
    add the bundle name to `KNOWN_COMPOSITE_BUNDLES` below.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from megaplan import cli


# Bundles that legitimately need `install: "copy"` because their installed
# content is composed from multiple source files (header + body + appendix).
# Adding to this list requires a one-line justification.
KNOWN_COMPOSITE_BUNDLES = {
    "claude_skill.md",   # header + instructions + claude_subagent_appendix
    "codex_skill.md",    # header + instructions + codex_subagent_appendix
    "cursor_rule.mdc",   # header + instructions, agent-specific framing
}


def _read_canonical(data_name: str) -> str:
    return cli._resolve_bundle_path(data_name).read_text(encoding="utf-8")


def test_every_target_declares_install_mode():
    for target in cli._GLOBAL_TARGETS:
        assert "install" in target, (
            f"_GLOBAL_TARGETS entry for {target['path']!r} is missing the "
            f"`install` key. Every target must declare 'symlink' or 'copy' "
            f"explicitly — implicit defaults are how shadow docs creep in."
        )
        assert target["install"] in {"symlink", "copy"}, (
            f"_GLOBAL_TARGETS entry for {target['path']!r} has unknown install "
            f"mode {target['install']!r}; expected 'symlink' or 'copy'."
        )


def test_single_source_bundles_must_be_symlinked():
    """If a bundle's `bundled_global_file` output equals its canonical file
    byte-for-byte, every target referencing it MUST install as a symlink."""
    bundle_names = {t["data"] for t in cli._GLOBAL_TARGETS}
    for name in bundle_names:
        if name in KNOWN_COMPOSITE_BUNDLES:
            continue
        bundled = cli.bundled_global_file(name)
        try:
            canonical = _read_canonical(name)
        except (FileNotFoundError, OSError):
            pytest.skip(f"canonical bundle file {name!r} not available in this install")
        assert bundled == canonical, (
            f"Bundle {name!r} composes content (bundled output != canonical "
            f"file). Add it to KNOWN_COMPOSITE_BUNDLES with a justification."
        )
        targets_for_bundle = [t for t in cli._GLOBAL_TARGETS if t["data"] == name]
        for target in targets_for_bundle:
            assert target["install"] == "symlink", (
                f"Bundle {name!r} is single-source (installed content equals "
                f"canonical) but target {target['path']!r} is install: "
                f"{target['install']!r}. Single-source bundles must be "
                f"symlinked or they will drift — that's how the megaplan-decision "
                f"shadow-doc regression happened in May 2026."
            )


def _make_fake_home(tmp_path: Path) -> Path:
    home = tmp_path / "home"
    (home / ".claude" / "skills").mkdir(parents=True)
    (home / ".codex" / "skills").mkdir(parents=True)
    (home / ".cursor" / "rules").mkdir(parents=True)
    return home


def test_handle_setup_global_creates_symlinks_for_symlink_targets(tmp_path: Path):
    home = _make_fake_home(tmp_path)
    cli.handle_setup_global(force=True, home=home)

    for target in cli._GLOBAL_TARGETS:
        if target["install"] != "symlink":
            continue
        installed_path = home / target["path"]
        assert installed_path.is_symlink(), (
            f"{installed_path} is install: symlink but was created as "
            f"a regular file. Setup must use _install_owned_symlink for "
            f"symlink-mode targets."
        )
        canonical = cli._resolve_bundle_path(target["data"]).resolve()
        assert installed_path.resolve() == canonical, (
            f"{installed_path} symlink resolves to {installed_path.resolve()}, "
            f"expected {canonical}."
        )


def test_handle_setup_global_is_idempotent_for_symlinks(tmp_path: Path):
    home = _make_fake_home(tmp_path)
    cli.handle_setup_global(force=True, home=home)

    sample = next(t for t in cli._GLOBAL_TARGETS if t["install"] == "symlink")
    sample_path = home / sample["path"]
    assert sample_path.is_symlink()
    first_target = sample_path.readlink()

    cli.handle_setup_global(force=False, home=home)
    assert sample_path.is_symlink(), "second setup turned the symlink into a regular file"
    assert sample_path.readlink() == first_target, "second setup changed the symlink target"


def test_setup_replaces_stale_regular_file_with_symlink(tmp_path: Path):
    """The original bug: an old `megaplan setup` wrote a regular-file copy
    of the decision skill. The new install code must replace that regular
    file with a symlink, not leave the shadow copy in place."""
    home = _make_fake_home(tmp_path)
    target = next(t for t in cli._GLOBAL_TARGETS if t["install"] == "symlink" and t["agent"] == "claude")
    stale_path = home / target["path"]
    stale_path.parent.mkdir(parents=True, exist_ok=True)
    stale_path.write_text("# stale shadow copy from a previous install\n", encoding="utf-8")
    assert not stale_path.is_symlink()

    cli.handle_setup_global(force=True, home=home)
    assert stale_path.is_symlink(), "setup left a stale shadow file in place"
    canonical = cli._resolve_bundle_path(target["data"]).resolve()
    assert stale_path.resolve() == canonical


def test_canonical_decision_skill_carries_its_own_frontmatter():
    """If the canonical doc loses its frontmatter, bundled_global_file would
    silently install a frontmatter-less skill, and Claude would stop finding
    it. Guard against accidentally stripping it."""
    canonical = _read_canonical("decision_skill.md")
    first_lines = canonical.splitlines()[:4]
    assert first_lines[0] == "---", "canonical decision skill must start with YAML frontmatter"
    assert any(line.startswith("name: megaplan-decision") for line in first_lines), (
        "canonical decision skill frontmatter must declare `name: megaplan-decision`"
    )
