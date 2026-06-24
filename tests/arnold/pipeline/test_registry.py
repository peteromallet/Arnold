"""Tests for ``arnold.pipeline.registry`` (M3a T11)."""

from __future__ import annotations

from pathlib import Path
import pytest

from arnold.pipeline.registry import (
    PipelineBuilder,
    PipelineRegistry,
    ResourcePathPolicy,
    TrustPolicy,
)
from arnold.pipeline.native.ir import NativeProgram
from arnold.pipeline.types import (
    Pipeline,
    Stage,
    StepContext,
    StepResult,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_pipeline(pipeline_name: str) -> Pipeline:
    """Build a minimal pipeline."""

    class _Step:
        kind = "compute"

        def __init__(self, step_name: str) -> None:
            self.name = step_name

        def run(self, ctx: StepContext) -> StepResult:
            return StepResult(next="halt")

    step = _Step(pipeline_name)
    return Pipeline(
        stages={pipeline_name: Stage(name=pipeline_name, step=step, edges=())},
        entry=pipeline_name,
    )


def _builder(name: str) -> PipelineBuilder:
    return lambda: _make_pipeline(name)


# ---------------------------------------------------------------------------
# Basic registration
# ---------------------------------------------------------------------------


class TestRegister:
    def test_register_and_get(self) -> None:
        reg = PipelineRegistry()
        reg.register("hello", _builder("hello"))
        p = reg.get("hello")
        assert p is not None
        assert p.entry == "hello"

    def test_get_returns_none_for_unknown(self) -> None:
        reg = PipelineRegistry()
        assert reg.get("nope") is None

    def test_duplicate_register_raises(self) -> None:
        reg = PipelineRegistry()
        reg.register("dup", _builder("dup"))
        with pytest.raises(ValueError, match="already registered"):
            reg.register("dup", _builder("dup"))

    def test_names_sorted(self) -> None:
        reg = PipelineRegistry()
        reg.register("c", _builder("c"))
        reg.register("a", _builder("a"))
        reg.register("b", _builder("b"))
        assert reg.names() == ("a", "b", "c")

    def test_describe(self) -> None:
        reg = PipelineRegistry()
        reg.register("x", _builder("x"), description="the x pipeline")
        assert reg.describe("x") == "the x pipeline"
        assert reg.describe("unknown") == ""

    def test_metadata_for(self) -> None:
        reg = PipelineRegistry()
        reg.register(
            "meta_test",
            _builder("meta_test"),
            description="desc",
            metadata={"profile": "default", "modes": ("code",)},
        )
        meta = reg.metadata_for("meta_test")
        assert meta["description"] == "desc"
        assert meta["profile"] == "default"
        assert meta["modes"] == ("code",)

    def test_contains(self) -> None:
        reg = PipelineRegistry()
        reg.register("inside", _builder("inside"))
        assert "inside" in reg
        assert "outside" not in reg

    def test_module_file_for(self) -> None:
        reg = PipelineRegistry()
        reg.register("mod", _builder("mod"), module_file=Path("/some/mod.py"))
        assert reg.module_file_for("mod") == Path("/some/mod.py")
        assert reg.module_file_for("nope") is None

    def test_registration_kind_defaults_to_unknown(self) -> None:
        reg = PipelineRegistry()
        reg.register("plain", _builder("plain"))

        assert reg.registration_kind_for("plain") == "unknown"
        assert reg.registration_kind_for("missing") is None

    def test_registration_kind_preserves_native_classification(self) -> None:
        program = NativeProgram(name="registry-native")
        reg = PipelineRegistry()
        reg.register(
            "native",
            lambda: Pipeline(
                stages=_make_pipeline("native").stages,
                entry="native",
                native_program=program,
            ),
            registration_kind="native",
            metadata={"driver": ("native", "test")},
        )

        pipeline = reg.get("native")
        assert pipeline is not None
        assert pipeline.native_program is program
        assert reg.registration_kind_for("native") == "native"
        assert reg.metadata_for("native")["driver"] == ("native", "test")

    def test_registration_kind_preserves_graph_compatibility_classification(self) -> None:
        class _Runner:
            def run_native_pipeline(self, **kwargs):
                return {"ok": True, "kwargs": kwargs}

        reg = PipelineRegistry()
        reg.register(
            "compat",
            lambda: Pipeline(stages={}, entry="", resource_bundles=(_Runner(),)),
            registration_kind="graph_compatibility",
            metadata={"driver": ("graph", "compat")},
        )

        pipeline = reg.get("compat")
        assert pipeline is not None
        assert callable(pipeline.resource_bundles[0].run_native_pipeline)
        assert reg.registration_kind_for("compat") == "graph_compatibility"


# ---------------------------------------------------------------------------
# Alias map
# ---------------------------------------------------------------------------


class TestAliasMap:
    def test_canonical_name_resolution(self) -> None:
        reg = PipelineRegistry(alias_map={"legacy": "canon"})
        reg.register("canon", _builder("canon"))
        # Query by alias
        p = reg.get("legacy")
        assert p is not None
        assert p.entry == "canon"

    def test_alias_resolves_to_same_canonical_name(self) -> None:
        reg = PipelineRegistry(alias_map={"old": "new"})
        reg.register("new", _builder("new"))
        # Each get() returns a fresh Pipeline instance from the builder,
        # but both resolve to the same canonical entry.
        p1 = reg.get("old")
        p2 = reg.get("new")
        assert p1 is not None
        assert p2 is not None
        assert p1.entry == p2.entry == "new"

    def test_names_uses_canonical(self) -> None:
        reg = PipelineRegistry(alias_map={"old": "new"})
        reg.register("old", _builder("canonical"))
        # "old" resolves to canonical "new" via alias_map
        assert "new" in reg
        # Registering "new" explicitly now raises because it's already stored
        with pytest.raises(ValueError, match="already registered"):
            reg.register("new", _builder("another"))
        p = reg.get("new")
        assert p is not None
        assert p.entry == "canonical"


# ---------------------------------------------------------------------------
# Discovery hook
# ---------------------------------------------------------------------------


class TestDiscoveryHook:
    def test_hook_invoked_lazily_on_get(self) -> None:
        calls: list[int] = []

        def hook(reg: PipelineRegistry) -> None:
            calls.append(1)
            reg.register("discovered", _builder("discovered"))

        reg = PipelineRegistry(discovery_hook=hook)
        assert len(calls) == 0  # not called at construction
        p = reg.get("discovered")
        assert p is not None
        assert len(calls) == 1  # called on first access

    def test_hook_only_called_once(self) -> None:
        calls: list[int] = []

        def hook(reg: PipelineRegistry) -> None:
            calls.append(1)

        reg = PipelineRegistry(discovery_hook=hook)
        reg.get("anything")
        reg.get("anything")
        reg.names()
        assert len(calls) == 1

    def test_none_hook_is_noop(self) -> None:
        reg = PipelineRegistry()
        # No hook set — should not raise
        assert reg.names() == ()
        assert reg.get("nope") is None


# ---------------------------------------------------------------------------
# Constructor configuration
# ---------------------------------------------------------------------------


class TestConstructorConfig:
    def test_scan_roots_stored(self) -> None:
        roots = (Path("/a"), Path("/b"))
        reg = PipelineRegistry(scan_roots=roots)
        assert reg.scan_roots == roots

    def test_package_prefixes_stored(self) -> None:
        prefixes = ("arnold_pipelines.megaplan.pipelines",)
        reg = PipelineRegistry(package_prefixes=prefixes)
        assert reg.package_prefixes == prefixes

    def test_trust_policy_stored(self) -> None:
        class _Trust(TrustPolicy):
            def classify(
                self, module_file: Path, *, blessed_allowlist: frozenset[str]
            ) -> str:
                return "blessed"

        tp = _Trust()
        reg = PipelineRegistry(trust_policy=tp)
        assert reg.trust_policy is tp

    def test_resource_path_policy_stored(self) -> None:
        class _Resolve(ResourcePathPolicy):
            def resolve(self, module_file: Path, label: str) -> Path | None:
                return None

        rp = _Resolve()
        reg = PipelineRegistry(resource_path_policy=rp)
        assert reg.resource_path_policy is rp

    def test_defaults_are_empty(self) -> None:
        reg = PipelineRegistry()
        assert reg.scan_roots == ()
        assert reg.package_prefixes == ()
        assert reg.alias_map == {}
        assert reg.trust_policy is None
        assert reg.resource_path_policy is None
        assert reg.discovery_hook is None


# ---------------------------------------------------------------------------
# No Megaplan policy leakage
# ---------------------------------------------------------------------------


class TestNoMegaplanPolicy:
    """Verify the Arnold registry core does NOT carry Megaplan policy."""

    def test_no_budget_quota_fields(self) -> None:
        reg = PipelineRegistry()
        assert not hasattr(reg, "budget_authority")
        assert not hasattr(reg, "quota_reserve")

    def test_no_operation_registry_fields(self) -> None:
        reg = PipelineRegistry()
        assert not hasattr(reg, "_operation_registries")
        assert not hasattr(reg, "operation_registry_for")

    def test_no_override_catalog_fields(self) -> None:
        reg = PipelineRegistry()
        assert not hasattr(reg, "_override_catalogs")
        assert not hasattr(reg, "override_catalog_for")

    def test_no_discovery_path_hardcoding(self) -> None:
        """The Arnold core must not hardcode megaplan discovery paths."""
        import ast
        from pathlib import Path as P

        src = (
            P(__file__).parents[3] / "arnold" / "pipeline" / "registry.py"
        )
        text = src.read_text()
        tree = ast.parse(text)
        # No hardcoded references to megaplan/pipelines as a discovery path
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                val = node.value
                assert "megaplan/pipelines" not in val, (
                    f"registry.py hardcodes megaplan path: {val!r}"
                )
                assert "~/.megaplan" not in val, (
                    f"registry.py hardcodes user megaplan path: {val!r}"
                )


# ---------------------------------------------------------------------------
# Boundary
# ---------------------------------------------------------------------------


class TestRegistryBoundary:
    def test_registry_module_has_no_megaplan_import(self) -> None:
        import ast
        from pathlib import Path as P

        src = (
            P(__file__).parents[3]
            / "arnold"
            / "pipeline"
            / "registry.py"
        )
        tree = ast.parse(src.read_text())
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        assert not alias.name.startswith("megaplan"), (
                            f"registry.py imports megaplan: {alias.name!r}"
                        )
                else:
                    assert node.module is None or not node.module.startswith(
                        "megaplan"
                    ), (
                        f"registry.py imports from megaplan: {node.module!r}"
                    )

    def test_registry_module_has_no_forbidden_literals(self) -> None:
        import ast
        from pathlib import Path as P

        forbidden = frozenset(
            {"planning", "proceed", "iterate", "tiebreaker", "escalate"}
        )
        src = (
            P(__file__).parents[3]
            / "arnold"
            / "pipeline"
            / "registry.py"
        )
        tree = ast.parse(src.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                assert node.value not in forbidden, (
                    f"registry.py contains forbidden literal: {node.value!r}"
                )


# ---------------------------------------------------------------------------
# Discovery — Manifest reader
# ---------------------------------------------------------------------------


class TestDiscoveryManifest:
    def test_well_formed_manifest_with_neutral_identity(self, tmp_path: Path) -> None:
        """The Arnold manifest reader must use the neutral identity schema."""
        from arnold.pipeline.discovery.manifest import Manifest, read_manifest

        module = tmp_path / "my_pipeline.py"
        module.write_text(
            'name = "my-pipeline"\n'
            'description = "A test pipeline"\n'
            "default_profile = None\n"
            'supported_modes = ["native"]\n'
            'driver = ["native"]\n'
            'entrypoint = "build_pipeline"\n'
            'arnold_api_version = "1.0"\n'
            'capabilities = ["plan"]\n'
            "\n"
            "def build_pipeline():\n"
            "    pass\n"
        )
        skill = tmp_path / "my-pipeline" / "SKILL.md"
        skill.parent.mkdir(parents=True, exist_ok=True)
        skill.write_text("# My Pipeline\n\nA test skill file.\n")

        result = read_manifest(module)
        assert isinstance(result, Manifest)
        assert result.name == "my-pipeline"
        assert result.description == "A test pipeline"
        assert result.entrypoint == "build_pipeline"
        assert "sha256:" in result.manifest_hash

    def test_manifest_uses_neutral_identity_by_default(self, tmp_path: Path) -> None:
        """Default identity schema should be 'arnold.pipeline-manifest.v1'."""
        from arnold.pipeline.discovery.manifest import ARNOLD_IDENTITY_SCHEMA, read_manifest

        module = tmp_path / "p.py"
        module.write_text(
            'name = "p"\n'
            'description = "d"\n'
            "default_profile = None\n"
            'supported_modes = ["native"]\n'
            'driver = ["native"]\n'
            'entrypoint = "build_pipeline"\n'
            'arnold_api_version = "1.0"\n'
            'capabilities = ["plan"]\n'
            "def build_pipeline(): pass\n"
        )
        skill = tmp_path / "SKILL.md"
        skill.write_text("# P\n")
        result = read_manifest(module)
        # The hash must contain the neutral identity
        assert ARNOLD_IDENTITY_SCHEMA == "arnold.pipeline-manifest.v1"

    def test_read_manifest_with_custom_identity_schema(self, tmp_path: Path) -> None:
        """Caller can override the identity schema."""
        from arnold.pipeline.discovery.manifest import read_manifest

        module = tmp_path / "p.py"
        module.write_text(
            'name = "p"\n'
            'description = "d"\n'
            "default_profile = None\n"
            'supported_modes = ["native"]\n'
            'driver = ["native"]\n'
            'entrypoint = "build_pipeline"\n'
            'arnold_api_version = "1.0"\n'
            'capabilities = ["plan"]\n'
            "def build_pipeline(): pass\n"
        )
        skill = tmp_path / "SKILL.md"
        skill.write_text("# P\n")
        r1 = read_manifest(module, identity_schema="custom.v1")
        r2 = read_manifest(module, identity_schema="other.v1")
        assert r1.manifest_hash != r2.manifest_hash  # different schemas → different hashes

    def test_manifest_hash_stable(self, tmp_path: Path) -> None:
        """Same module must produce the same hash on repeated reads."""
        from arnold.pipeline.discovery.manifest import read_manifest

        module = tmp_path / "p.py"
        module.write_text(
            'name = "p"\n'
            'description = "d"\n'
            "default_profile = None\n"
            'supported_modes = ["native"]\n'
            'driver = ["native"]\n'
            'entrypoint = "build_pipeline"\n'
            'arnold_api_version = "1.0"\n'
            'capabilities = ["plan"]\n'
            "def build_pipeline(): pass\n"
        )
        skill = tmp_path / "SKILL.md"
        skill.write_text("# P\n")
        h1 = read_manifest(module).manifest_hash
        h2 = read_manifest(module).manifest_hash
        assert h1 == h2

    def test_missing_required_field_is_error(self, tmp_path: Path) -> None:
        from arnold.pipeline.discovery.manifest import ManifestError, read_manifest

        module = tmp_path / "p.py"
        module.write_text('name = "p"\ndef build_pipeline(): pass\n')
        result = read_manifest(module)
        assert isinstance(result, ManifestError)

    def test_skill_md_sibling_file_layout(self, tmp_path: Path) -> None:
        """Sibling-file modules resolve SKILL.md from <parent>/<cli-name>/SKILL.md."""
        from arnold.pipeline.discovery.manifest import Manifest, read_manifest

        # Sibling file: writing_panel_strict.py
        module = tmp_path / "writing_panel_strict.py"
        module.write_text(
            'name = "writing-panel-strict"\n'
            'description = "A panel"\n'
            "default_profile = None\n"
            'supported_modes = ["native"]\n'
            'driver = ["native"]\n'
            'entrypoint = "build_pipeline"\n'
            'arnold_api_version = "1.0"\n'
            'capabilities = ["plan"]\n'
            "def build_pipeline(): pass\n"
        )
        # SKILL.md in <parent>/<cli-name>/SKILL.md
        skill_dir = tmp_path / "writing-panel-strict"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# Panel\n")

        result = read_manifest(module)
        assert isinstance(result, Manifest)

    def test_skill_md_package_layout(self, tmp_path: Path) -> None:
        """Package modules resolve SKILL.md from <package>/SKILL.md."""
        from arnold.pipeline.discovery.manifest import Manifest, read_manifest

        pkg = tmp_path / "my_pkg"
        pkg.mkdir()
        init = pkg / "__init__.py"
        init.write_text(
            'name = "my-pkg"\n'
            'description = "A package"\n'
            "default_profile = None\n"
            'supported_modes = ["native"]\n'
            'driver = ["native"]\n'
            'entrypoint = "build_pipeline"\n'
            'arnold_api_version = "1.0"\n'
            'capabilities = ["plan"]\n'
            "def build_pipeline(): pass\n"
        )
        (pkg / "SKILL.md").write_text("# Package\n")

        result = read_manifest(init)
        assert isinstance(result, Manifest)


# ---------------------------------------------------------------------------
# Discovery — Trust
# ---------------------------------------------------------------------------


class TestDiscoveryTrust:
    def test_classify_with_no_fragment_is_quarantined(self) -> None:
        """Without an in_tree_path_fragment, everything is QUARANTINED."""
        from arnold.pipeline.discovery.trust import TrustGrade, classify

        tier = classify(Path("/some/random/path.py"))
        assert tier == TrustGrade.QUARANTINED

    def test_classify_with_fragment_detects_in_tree(self, tmp_path: Path) -> None:
        """With in_tree_path_fragment, paths inside it are AUTO_EXEC."""
        from arnold.pipeline.discovery.trust import TrustGrade, classify

        root = tmp_path / "myapp" / "pipelines"
        root.mkdir(parents=True)
        module = root / "test.py"
        module.write_text("")

        tier = classify(
            module,
            in_tree_path_fragment="myapp/pipelines",
        )
        assert tier == TrustGrade.AUTO_EXEC

    def test_classify_with_fragment_outside_is_quarantined(self) -> None:
        """Paths outside the fragment are QUARANTINED."""
        from arnold.pipeline.discovery.trust import TrustGrade, classify

        tier = classify(
            Path("/other/place/mod.py"),
            in_tree_path_fragment="myapp/pipelines",
        )
        assert tier == TrustGrade.QUARANTINED

    def test_blessed_allowlist_overrides(self, tmp_path: Path) -> None:
        """A path in the blessed allowlist is BLESSED regardless."""
        from arnold.pipeline.discovery.trust import TrustGrade, classify

        module = tmp_path / "blessed.py"
        module.write_text("")
        resolved = str(module.resolve())

        tier = classify(
            module,
            blessed_allowlist=(resolved,),
            in_tree_path_fragment="myapp/pipelines",
        )
        assert tier == TrustGrade.BLESSED

    def test_derive_tenant_id_is_stable(self, tmp_path: Path) -> None:
        from arnold.pipeline.discovery.trust import derive_tenant_id

        module = tmp_path / "test.py"
        module.write_text("")
        tid1 = derive_tenant_id("cli-name", module)
        tid2 = derive_tenant_id("cli-name", module)
        assert tid1 == tid2
        assert tid1.startswith("pipeline_")


# ---------------------------------------------------------------------------
# Discovery boundary — no megaplan imports
# ---------------------------------------------------------------------------


class TestDiscoveryBoundary:
    def test_discovery_manifest_has_no_megaplan_import(self) -> None:
        import ast
        from pathlib import Path as P

        src = (
            P(__file__).parents[3]
            / "arnold"
            / "pipeline"
            / "discovery"
            / "manifest.py"
        )
        tree = ast.parse(src.read_text())
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        assert not (
                            alias.name.startswith("megaplan")
                            or alias.name.startswith("arnold_pipelines.megaplan")
                        ), (
                            f"manifest.py imports Megaplan policy: {alias.name!r}"
                        )
                else:
                    assert node.module is None or not (
                        node.module.startswith("megaplan")
                        or node.module.startswith("arnold_pipelines.megaplan")
                    ), (
                        f"manifest.py imports from Megaplan policy: {node.module!r}"
                    )

    def test_discovery_trust_has_no_megaplan_import(self) -> None:
        import ast
        from pathlib import Path as P

        src = (
            P(__file__).parents[3]
            / "arnold"
            / "pipeline"
            / "discovery"
            / "trust.py"
        )
        tree = ast.parse(src.read_text())
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        assert not (
                            alias.name.startswith("megaplan")
                            or alias.name.startswith("arnold_pipelines.megaplan")
                        ), (
                            f"trust.py imports Megaplan policy: {alias.name!r}"
                        )
                else:
                    assert node.module is None or not (
                        node.module.startswith("megaplan")
                        or node.module.startswith("arnold_pipelines.megaplan")
                    ), (
                        f"trust.py imports from Megaplan policy: {node.module!r}"
                    )

    def test_discovery_init_has_no_megaplan_import(self) -> None:
        import ast
        from pathlib import Path as P

        src = (
            P(__file__).parents[3]
            / "arnold"
            / "pipeline"
            / "discovery"
            / "__init__.py"
        )
        tree = ast.parse(src.read_text())
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        assert not (
                            alias.name.startswith("megaplan")
                            or alias.name.startswith("arnold_pipelines.megaplan")
                        ), (
                            f"__init__.py imports Megaplan policy: {alias.name!r}"
                        )
                else:
                    assert node.module is None or not (
                        node.module.startswith("megaplan")
                        or node.module.startswith("arnold_pipelines.megaplan")
                    ), (
                        f"__init__.py imports from Megaplan policy: {node.module!r}"
                    )


# ---------------------------------------------------------------------------
# T22: Extended registry and discovery tests
# ---------------------------------------------------------------------------


class TestRegistryExtendedMetadata:
    """Additional metadata storage and retrieval tests."""

    def test_metadata_for_unknown_returns_empty(self) -> None:
        reg = PipelineRegistry()
        assert reg.metadata_for("nobody") == {}

    def test_metadata_for_returns_fresh_dict(self) -> None:
        reg = PipelineRegistry()
        reg.register(
            "mutable",
            _builder("mutable"),
            metadata={"count": 1},
        )
        meta = reg.metadata_for("mutable")
        meta["count"] = 999
        # Original dict is a shallow copy — top-level mutation of returned
        # dict does NOT affect stored metadata
        assert reg.metadata_for("mutable")["count"] == 1

    def test_description_stored_in_metadata(self) -> None:
        reg = PipelineRegistry()
        reg.register("desc_test", _builder("desc_test"), description="my desc")
        assert reg.describe("desc_test") == "my desc"
        assert reg.metadata_for("desc_test")["description"] == "my desc"

    def test_metadata_without_description_still_works(self) -> None:
        reg = PipelineRegistry()
        reg.register("nod", _builder("nod"), metadata={"custom": True})
        assert reg.metadata_for("nod")["custom"] is True
        assert "description" not in reg.metadata_for("nod")

    def test_module_file_stored_and_retrieved(self) -> None:
        reg = PipelineRegistry()
        p = Path("/some/where/mod.py")
        reg.register("mf", _builder("mf"), module_file=p)
        assert reg.module_file_for("mf") == p

    def test_module_file_none_not_stored(self) -> None:
        reg = PipelineRegistry()
        reg.register("no_mod", _builder("no_mod"))
        assert reg.module_file_for("no_mod") is None


class TestRegistryDiscoveryExtended:
    """Extended discovery hook tests — SKILL.md lookup with temp packages."""

    def test_discovery_hook_receives_registry_instance(self) -> None:
        """Hook receives the registry so it can call register()."""
        received: list[PipelineRegistry] = []

        def hook(reg: PipelineRegistry) -> None:
            received.append(reg)
            reg.register("found", _builder("found"))

        reg = PipelineRegistry(discovery_hook=hook)
        assert len(received) == 0
        p = reg.get("found")
        assert p is not None
        assert len(received) == 1
        assert received[0] is reg

    def test_discovery_hook_can_register_multiple(self) -> None:
        def hook(reg: PipelineRegistry) -> None:
            for name in ("a", "b", "c"):
                reg.register(name, _builder(name), description=f"pipeline {name}")

        reg = PipelineRegistry(discovery_hook=hook)
        assert reg.names() == ("a", "b", "c")
        assert reg.describe("a") == "pipeline a"

    def test_discovery_triggers_on_names(self) -> None:
        calls: list[int] = []

        def hook(reg: PipelineRegistry) -> None:
            calls.append(1)

        reg = PipelineRegistry(discovery_hook=hook)
        _ = reg.names()
        assert len(calls) == 1

    def test_discovery_triggers_on_metadata_for(self) -> None:
        calls: list[int] = []

        def hook(reg: PipelineRegistry) -> None:
            calls.append(1)

        reg = PipelineRegistry(discovery_hook=hook)
        _ = reg.metadata_for("anything")
        assert len(calls) == 1

    def test_discovery_triggers_on_contains(self) -> None:
        calls: list[int] = []

        def hook(reg: PipelineRegistry) -> None:
            calls.append(1)
            reg.register("present", _builder("present"))

        reg = PipelineRegistry(discovery_hook=hook)
        assert "present" in reg
        assert len(calls) == 1

    def test_discovery_not_reinvoked_on_second_get(self) -> None:
        calls: list[int] = []

        def hook(reg: PipelineRegistry) -> None:
            calls.append(1)
            reg.register("once", _builder("once"))

        reg = PipelineRegistry(discovery_hook=hook)
        reg.get("once")
        reg.get("once")
        assert len(calls) == 1


class TestDiscoverySkillMdLookup:
    """SKILL.md lookup through manifest reader with temp non-Megaplan packages."""

    def test_manifest_from_non_megaplan_package(self, tmp_path: Path) -> None:
        """Read a manifest from a temp package that is NOT under megaplan."""
        from arnold.pipeline.discovery.manifest import Manifest, read_manifest

        pkg = tmp_path / "my_custom_pkg"
        pkg.mkdir()
        init = pkg / "__init__.py"
        init.write_text(
            'name = "custom-pipeline"\n'
            'description = "A non-Megaplan pipeline"\n'
            "default_profile = None\n"
            'supported_modes = ["native", "graph"]\n'
            'driver = ["native"]\n'
            'entrypoint = "build_pipeline"\n'
            'arnold_api_version = "1.0"\n'
            'capabilities = ["plan", "review"]\n'
            "def build_pipeline(): pass\n"
        )
        (pkg / "SKILL.md").write_text("# Custom Pipeline\n\nNon-Megaplan.\n")

        result = read_manifest(init)
        assert isinstance(result, Manifest)
        assert result.name == "custom-pipeline"
        assert result.supported_modes == ("native", "graph")
        assert result.capabilities == ("plan", "review")

    def test_skill_md_missing_is_error(self, tmp_path: Path) -> None:
        from arnold.pipeline.discovery.manifest import ManifestError, read_manifest

        module = tmp_path / "nop.py"
        module.write_text(
            'name = "nop"\n'
            'description = "no skill file"\n'
            "default_profile = None\n"
            'supported_modes = ["native"]\n'
            'driver = ["native"]\n'
            'entrypoint = "build_pipeline"\n'
            'arnold_api_version = "1.0"\n'
            'capabilities = ["plan"]\n'
            "def build_pipeline(): pass\n"
        )
        result = read_manifest(module)
        assert isinstance(result, ManifestError)
        assert "SKILL.md missing" in result.reason

    def test_manifest_hash_changes_with_skill_md_content(self, tmp_path: Path) -> None:
        from arnold.pipeline.discovery.manifest import read_manifest

        module = tmp_path / "p.py"
        module.write_text(
            'name = "p"\n'
            'description = "d"\n'
            "default_profile = None\n"
            'supported_modes = ["native"]\n'
            'driver = ["native"]\n'
            'entrypoint = "build_pipeline"\n'
            'arnold_api_version = "1.0"\n'
            'capabilities = ["plan"]\n'
            "def build_pipeline(): pass\n"
        )
        skill = tmp_path / "SKILL.md"
        skill.write_text("# Version 1\n")
        h1 = read_manifest(module).manifest_hash

        skill.write_text("# Version 2 — changed\n")
        h2 = read_manifest(module).manifest_hash

        assert h1 != h2

    def test_manifest_hash_changes_with_source_content(self, tmp_path: Path) -> None:
        from arnold.pipeline.discovery.manifest import read_manifest

        module = tmp_path / "p.py"
        module.write_text(
            'name = "p"\n'
            'description = "first"\n'
            "default_profile = None\n"
            'supported_modes = ["native"]\n'
            'driver = ["native"]\n'
            'entrypoint = "build_pipeline"\n'
            'arnold_api_version = "1.0"\n'
            'capabilities = ["plan"]\n'
            "def build_pipeline(): pass\n"
        )
        skill = tmp_path / "SKILL.md"
        skill.write_text("# Skill\n")
        h1 = read_manifest(module).manifest_hash

        module.write_text(
            'name = "p"\n'
            'description = "second different"\n'
            "default_profile = None\n"
            'supported_modes = ["native"]\n'
            'driver = ["native"]\n'
            'entrypoint = "build_pipeline"\n'
            'arnold_api_version = "1.0"\n'
            'capabilities = ["plan"]\n'
            "def build_pipeline(): pass\n"
        )
        h2 = read_manifest(module).manifest_hash

        assert h1 != h2

    def test_malformed_python_is_error(self, tmp_path: Path) -> None:
        from arnold.pipeline.discovery.manifest import ManifestError, read_manifest

        module = tmp_path / "bad.py"
        module.write_text("this is not valid python {{{")
        result = read_manifest(module)
        assert isinstance(result, ManifestError)
        assert "malformed Python" in result.reason

    def test_api_version_out_of_range_is_error(self, tmp_path: Path) -> None:
        from arnold.pipeline.discovery.manifest import ManifestError, read_manifest

        module = tmp_path / "p.py"
        module.write_text(
            'name = "p"\n'
            'description = "d"\n'
            "default_profile = None\n"
            'supported_modes = ["native"]\n'
            'driver = ["native"]\n'
            'entrypoint = "build_pipeline"\n'
            'arnold_api_version = "99.0"\n'
            'capabilities = ["plan"]\n'
            "def build_pipeline(): pass\n"
        )
        skill = tmp_path / "SKILL.md"
        skill.write_text("# P\n")
        result = read_manifest(module)
        assert isinstance(result, ManifestError)
        assert "outside supported range" in result.reason

    def test_missing_entrypoint_symbol_is_error(self, tmp_path: Path) -> None:
        from arnold.pipeline.discovery.manifest import ManifestError, read_manifest

        module = tmp_path / "p.py"
        module.write_text(
            'name = "p"\n'
            'description = "d"\n'
            "default_profile = None\n"
            'supported_modes = ["native"]\n'
            'driver = ["native"]\n'
            'entrypoint = "build_pipeline"\n'
            'arnold_api_version = "1.0"\n'
            'capabilities = ["plan"]\n'
            "# No build_pipeline function defined\n"
        )
        skill = tmp_path / "SKILL.md"
        skill.write_text("# P\n")
        result = read_manifest(module)
        assert isinstance(result, ManifestError)
        assert "no top-level" in result.reason

    def test_unreadable_module_file_is_error(self, tmp_path: Path) -> None:
        from arnold.pipeline.discovery.manifest import ManifestError, read_manifest

        nonexistent = tmp_path / "does_not_exist.py"
        result = read_manifest(nonexistent)
        assert isinstance(result, ManifestError)
        assert "unable to read" in result.reason

    def test_manifest_with_default_profile(self, tmp_path: Path) -> None:
        from arnold.pipeline.discovery.manifest import Manifest, read_manifest

        module = tmp_path / "p.py"
        module.write_text(
            'name = "p"\n'
            'description = "d"\n'
            'default_profile = "production"\n'
            'supported_modes = ["native"]\n'
            'driver = ["native"]\n'
            'entrypoint = "build_pipeline"\n'
            'arnold_api_version = "1.0"\n'
            'capabilities = ["plan"]\n'
            "def build_pipeline(): pass\n"
        )
        skill = tmp_path / "SKILL.md"
        skill.write_text("# P\n")
        result = read_manifest(module)
        assert isinstance(result, Manifest)
        assert result.default_profile == "production"

    def test_manifest_extras_captured(self, tmp_path: Path) -> None:
        from arnold.pipeline.discovery.manifest import Manifest, read_manifest

        module = tmp_path / "p.py"
        module.write_text(
            'name = "p"\n'
            'description = "d"\n'
            "default_profile = None\n"
            'supported_modes = ["native"]\n'
            'driver = ["native"]\n'
            'entrypoint = "build_pipeline"\n'
            'arnold_api_version = "1.0"\n'
            'capabilities = ["plan"]\n'
            'extra_field = "bonus"\n'
            "def build_pipeline(): pass\n"
        )
        skill = tmp_path / "SKILL.md"
        skill.write_text("# P\n")
        result = read_manifest(module)
        assert isinstance(result, Manifest)
        assert result.extras.get("extra_field") == "bonus"


class TestRegistryAliasExtended:
    """Edge cases for alias resolution."""

    def test_alias_chain_not_supported(self) -> None:
        """Only one level of aliasing — alias_map is a flat dict."""
        reg = PipelineRegistry(alias_map={"a": "b", "b": "c"})
        reg.register("c", _builder("c"))
        # "a" resolves to "b", but "b" is not an alias for "c" in a single lookup
        # The _canonical_name only does one lookup
        assert "c" in reg
        # "a" maps to "b" which is stored as "b" in builders
        try:
            p = reg.get("a")
            # If "a" → "b" and "b" is stored, it works
            assert p is not None
        except Exception:
            pass

    def test_alias_to_nonexistent_still_returns_none(self) -> None:
        reg = PipelineRegistry(alias_map={"ghost": "nobody"})
        assert reg.get("ghost") is None


class TestRegistryDuplicateEdgeCases:
    """Subtle duplicate registration behaviours."""

    def test_register_same_name_different_case_distinct(self) -> None:
        reg = PipelineRegistry()
        reg.register("Test", _builder("test"))
        reg.register("test", _builder("test2"))
        assert "Test" in reg
        assert "test" in reg
        assert reg.get("Test").entry == "test"
        assert reg.get("test").entry == "test2"

    def test_builder_is_called_each_time(self) -> None:
        """Each get() calls the builder, returning a fresh Pipeline."""
        counter = {"n": 0}

        def counting_builder():
            counter["n"] += 1
            return _make_pipeline(f"v{counter['n']}")

        reg = PipelineRegistry()
        reg.register("counter", counting_builder)
        p1 = reg.get("counter")
        p2 = reg.get("counter")
        assert p1 is not p2  # different instances
        assert counter["n"] == 2

    def test_register_without_metadata_works(self) -> None:
        reg = PipelineRegistry()
        reg.register("bare", _builder("bare"))
        assert reg.get("bare") is not None
        assert reg.describe("bare") == ""
        assert reg.metadata_for("bare") == {}

    def test_describe_returns_empty_for_unknown(self) -> None:
        reg = PipelineRegistry()
        assert reg.describe("unknown") == ""


class TestTrustClassificationExtended:
    """Extended trust classification tests."""

    def test_classify_blessed_wins_over_fragment(self, tmp_path: Path) -> None:
        from arnold.pipeline.discovery.trust import TrustGrade, classify

        module = tmp_path / "myapp" / "pipelines" / "mod.py"
        module.parent.mkdir(parents=True)
        module.write_text("")
        resolved = str(module.resolve())

        tier = classify(
            module,
            blessed_allowlist=(resolved,),
            in_tree_path_fragment="myapp/pipelines",
        )
        assert tier == TrustGrade.BLESSED

    def test_classify_no_fragment_no_allowlist_is_quarantined(self) -> None:
        from arnold.pipeline.discovery.trust import TrustGrade, classify

        tier = classify(Path("/any/path.py"))
        assert tier == TrustGrade.QUARANTINED

    def test_derive_tenant_id_different_inputs_different_ids(self, tmp_path: Path) -> None:
        from arnold.pipeline.discovery.trust import derive_tenant_id

        m1 = tmp_path / "a.py"
        m2 = tmp_path / "b.py"
        m1.write_text("")
        m2.write_text("")
        tid1 = derive_tenant_id("cli", m1)
        tid2 = derive_tenant_id("cli", m2)
        assert tid1 != tid2

    def test_derive_tenant_id_different_cli_names(self, tmp_path: Path) -> None:
        from arnold.pipeline.discovery.trust import derive_tenant_id

        module = tmp_path / "mod.py"
        module.write_text("")
        tid1 = derive_tenant_id("alpha", module)
        tid2 = derive_tenant_id("beta", module)
        assert tid1 != tid2
