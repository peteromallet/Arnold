from __future__ import annotations

import ast
import re
import warnings
from pathlib import Path
from typing import Any

import pytest

from scripts.runpod_corpus_matrix import _remote_script
from vibecomfy.registry import models_loader
from vibecomfy.registry.models_loader import (
    ModelEntry,
    ModelSource,
    ModelTarget,
    canonical_filename,
    load_registry,
    normalize_alias,
    stage_entry,
)


def _write_registry(path: Path, body: str) -> Path:
    path.write_text(body, encoding="utf-8")
    models_loader._clear_cache()
    return path


def _sample_registry(path: Path) -> Path:
    return _write_registry(
        path,
        """
models:
  - id: sample
    source:
      kind: huggingface
      repo: example/repo
      filename: nested/model.bin
    min_size: 3
    targets:
      - node_pack: pack
        path: checkpoints/model.bin
      - node_pack: alt
        path: diffusion_models/model.bin
    aliases:
      - alias.bin
    tags:
      - phase:core
    notes: sample model
""",
    )


def test_load_registry_roundtrip_sample(tmp_path: Path) -> None:
    entries = load_registry(_sample_registry(tmp_path / "models.yaml"))

    assert len(entries) == 1
    entry = entries[0]
    assert entry == ModelEntry(
        id="sample",
        source=ModelSource(kind="huggingface", repo="example/repo", filename="nested/model.bin"),
        min_size=3,
        targets=(
            ModelTarget(node_pack="pack", path="checkpoints/model.bin"),
            ModelTarget(node_pack="alt", path="diffusion_models/model.bin"),
        ),
        aliases=("alias.bin",),
        tags=("phase:core",),
        notes="sample model",
    )
    assert canonical_filename("sample", registry=entries) == "model.bin"


def test_stage_entry_hardlinks_or_symlinks_all_targets(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    source = tmp_path / "hf" / "model.bin"
    source.parent.mkdir()
    source.write_bytes(b"model-bytes")
    monkeypatch.setattr("huggingface_hub.hf_hub_download", lambda repo_id, filename: str(source))
    entry = load_registry(_sample_registry(tmp_path / "models.yaml"))[0]
    models_root = tmp_path / "models-root"

    staged_paths = stage_entry(entry, models_root=models_root)

    assert staged_paths == [
        models_root / "checkpoints/model.bin",
        models_root / "diffusion_models/model.bin",
    ]
    for staged in staged_paths:
        assert staged.read_bytes() == b"model-bytes"
        assert staged.exists()


def test_stage_entry_rejects_small_staged_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    source = tmp_path / "source.bin"
    source.write_bytes(b"tiny")
    monkeypatch.setattr("huggingface_hub.hf_hub_download", lambda repo_id, filename: str(source))
    entry = ModelEntry(
        id="small",
        source=ModelSource(kind="huggingface", repo="example/repo", filename="model.bin"),
        min_size=100,
        targets=(ModelTarget(node_pack="pack", path="checkpoints/model.bin"),),
    )

    with pytest.raises(RuntimeError, match="small.*too small"):
        stage_entry(entry, models_root=tmp_path / "models")


def test_stage_entry_rejects_unrelated_existing_target(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    source = tmp_path / "source.bin"
    source.write_bytes(b"large-enough")
    target = tmp_path / "models" / "checkpoints" / "model.bin"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"unrelated")
    monkeypatch.setattr("huggingface_hub.hf_hub_download", lambda repo_id, filename: str(source))
    entry = ModelEntry(
        id="collision",
        source=ModelSource(kind="huggingface", repo="example/repo", filename="model.bin"),
        min_size=3,
        targets=(ModelTarget(node_pack="pack", path="checkpoints/model.bin"),),
    )

    with pytest.raises(RuntimeError, match="refusing to overwrite unrelated existing file"):
        stage_entry(entry, models_root=tmp_path / "models")


def test_normalize_alias_hits_and_misses(tmp_path: Path) -> None:
    entries = load_registry(_sample_registry(tmp_path / "models.yaml"))

    assert normalize_alias("alias.bin", registry=entries) == "model.bin"
    assert normalize_alias("alias.bin", registry=entries, node_pack="pack") == "model.bin"
    assert normalize_alias("alias.bin", registry=entries, node_pack="missing") is None
    assert normalize_alias("unknown.bin", registry=entries) is None


def test_load_registry_rejects_duplicate_ids(tmp_path: Path) -> None:
    text = _sample_registry(tmp_path / "models.yaml").read_text(encoding="utf-8")
    duplicate = text + "\n" + text.split("models:\n", 1)[1]
    _write_registry(tmp_path / "models.yaml", duplicate)

    with pytest.raises(ValueError, match="duplicate model id"):
        load_registry(tmp_path / "models.yaml")


def test_load_registry_rejects_duplicate_aliases(tmp_path: Path) -> None:
    text = _sample_registry(tmp_path / "models.yaml").read_text(encoding="utf-8")
    second = text.split("models:\n", 1)[1].replace("id: sample", "id: second")
    _write_registry(tmp_path / "models.yaml", text + "\n" + second)

    with pytest.raises(ValueError, match="duplicate alias"):
        load_registry(tmp_path / "models.yaml")


@pytest.mark.parametrize("bad_path", ["/abs/model.bin", "../model.bin", "foo/../model.bin", "models/checkpoints/model.bin", "models\\checkpoints\\model.bin"])
def test_load_registry_rejects_bad_target_paths(tmp_path: Path, bad_path: str) -> None:
    registry = _write_registry(
        tmp_path / "models.yaml",
        f"""
models:
  - id: bad_path
    source:
      kind: huggingface
      repo: example/repo
      filename: model.bin
    min_size: 0
    targets:
      - node_pack: pack
        path: '{bad_path}'
""",
    )

    with pytest.raises(ValueError, match="bad_path.*target.path"):
        load_registry(registry)


def test_load_registry_rejects_unknown_tags(tmp_path: Path) -> None:
    text = _sample_registry(tmp_path / "models.yaml").read_text(encoding="utf-8").replace("phase:core", "phase:typo")
    _write_registry(tmp_path / "models.yaml", text)

    with pytest.raises(ValueError, match="unknown tag"):
        load_registry(tmp_path / "models.yaml")


def test_filter_entries_selects_phase_and_env_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    entries = (
        ModelEntry("core", ModelSource("huggingface", repo="r", filename="a.bin"), 0, (ModelTarget("pack", "a.bin"),), tags=("phase:core",)),
        ModelEntry("gguf", ModelSource("huggingface", repo="r", filename="b.bin"), 0, (ModelTarget("pack", "b.bin"),), tags=("phase:gguf",)),
        ModelEntry(
            "lean",
            ModelSource("huggingface", repo="r", filename="c.bin"),
            0,
            (ModelTarget("pack", "c.bin"),),
            tags=("phase:core", "ltx_lean_excluded"),
        ),
        ModelEntry(
            "token",
            ModelSource("huggingface", repo="r", filename="d.bin"),
            0,
            (ModelTarget("pack", "d.bin"),),
            tags=("phase:core", "requires_hf_token"),
        ),
    )
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.setenv("VIBECOMFY_MATRIX_SCOPE", "ltx_official")

    selected = models_loader._filter_entries(entries, ids=None, select_phase="core")

    assert [entry.id for entry in selected] == ["core"]


def test_load_registry_caches_until_clear_cache(tmp_path: Path) -> None:
    registry = _sample_registry(tmp_path / "models.yaml")
    first = load_registry(registry)
    registry.write_text(registry.read_text(encoding="utf-8").replace("id: sample", "id: changed"), encoding="utf-8")

    assert load_registry(registry) is first
    models_loader._clear_cache()
    assert load_registry(registry)[0].id == "changed"


# TODO: remove this test once the heredocs are deleted post-soak.
def test_legacy_heredoc_downloads_match_registry_entries() -> None:
    registry = load_registry()
    by_source = {(entry.source.repo, entry.source.filename, entry.min_size): entry for entry in registry}

    for phase, repo, filename, targets, min_size in _legacy_download_tuples():
        entry = by_source[(repo, filename, min_size)]
        assert f"phase:{phase}" in entry.tags
        registry_targets = {target.path for target in entry.targets}
        for target in targets:
            assert target.startswith("models/")
            assert target.removeprefix("models/") in registry_targets


def _legacy_download_tuples() -> list[tuple[str, str, str, list[str], int]]:
    blocks = [block for block in re.findall(r"\"\$PY\" - <<'PY'\n(.*?)\nPY", _remote_script(), flags=re.S) if "def materialize_model" in block]
    phases = ["core", "gguf", "ltx", "wan_wrapper"]
    assert len(blocks) == len(phases)
    rows: list[tuple[str, str, str, list[str], int]] = []
    for phase, block in zip(phases, blocks):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            parsed = ast.parse(block)
        for repo, filename, targets, min_size in _extract_downloads_from_ast(parsed):
            rows.append((phase, repo, filename, targets, min_size))
    return rows


def _extract_downloads_from_ast(module: ast.Module) -> list[tuple[str, str, list[str], int]]:
    rows: list[tuple[str, str, list[str], int]] = []

    def visit(statements: list[ast.stmt]) -> None:
        for statement in statements:
            if isinstance(statement, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "downloads" for target in statement.targets):
                rows.extend(_tuples_from_list(statement.value))
            elif isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call):
                call = statement.value
                if isinstance(call.func, ast.Attribute) and isinstance(call.func.value, ast.Name) and call.func.value.id == "downloads":
                    if call.func.attr == "extend":
                        rows.extend(_tuples_from_list(call.args[0]))
                    elif call.func.attr == "append":
                        rows.append(_download_tuple(call.args[0]))
            elif isinstance(statement, ast.If):
                visit(statement.body)
                visit(statement.orelse)

    visit(module.body)
    return rows


def _tuples_from_list(node: ast.AST) -> list[tuple[str, str, list[str], int]]:
    assert isinstance(node, ast.List)
    return [_download_tuple(item) for item in node.elts]


def _download_tuple(node: ast.AST) -> tuple[str, str, list[str], int]:
    assert isinstance(node, ast.Tuple)
    repo = ast.literal_eval(node.elts[0])
    filename = ast.literal_eval(node.elts[1])
    targets = [_path_arg(target) for target in node.elts[2].elts]  # type: ignore[attr-defined]
    min_size = ast.literal_eval(node.elts[3])
    return repo, filename, targets, min_size


def _path_arg(node: ast.AST) -> str:
    assert isinstance(node, ast.Call)
    assert isinstance(node.func, ast.Name) and node.func.id == "Path"
    return ast.literal_eval(node.args[0])
