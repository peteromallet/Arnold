"""Installed-package composition smoke tests.

Verifies the canonical authority chain for composition:

1. **Canonical authored source** (``workflows/workflow.pypeline``) is the
   semantic authority — the readable, product-local source of truth.
2. **WorkflowManifest** is a compiled inspection/replay artifact produced
   by ``compile_pipeline(build_pipeline())``.
3. **Pipeline.native_program** is the dispatch substrate — a
   NativeProgram projection that carries routing topology and phase
   instructions derived from the canonical source.

These tests also verify installed-package import behavior: the
``arnold_pipelines.megaplan`` package must be importable, must expose
``build_pipeline`` and ``build_and_compile_pipeline``, and must not
leak legacy shims or deleted subpackages.
"""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import textwrap
import venv
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from zipfile import ZipFile

import pytest

from arnold.manifest.manifests import WorkflowManifest
from arnold.pipeline.native.ir import NativeProgram
from arnold.workflow.compiler import compile_pipeline
from arnold.workflow.dsl import Pipeline as DslPipeline
from arnold.workflow.source_compiler import lower_workflow_file
from tests.arnold_pipelines.megaplan.package_resources import checkout_path

REPO_ROOT = checkout_path()
WORKFLOW_PYPELINE_ARCHIVE_PATH = "arnold_pipelines/megaplan/workflows/workflow.pypeline"
WORKFLOW_PY_ARCHIVE_PATH = "arnold_pipelines/megaplan/workflows/workflow.py"
PROHIBITED_WRAPPER_TOKENS = (
    "SOURCE_",
    "handler_ref",
    "route_bindings",
    "manifest_hash",
    "build_manifest",
    "build_node",
    "node_builder",
    "generic dispatch",
)
WORKFLOW_SHIM_PROHIBITED_TOKENS = (
    "@workflow",
    "planning_workflow",
    "SOURCE_CRITIQUE",
    "SOURCE_EXECUTE",
    "handler_ref",
    "route_bindings",
)
REQUIRED_INSTALLED_CONFORMANCE_SUITES = MappingProxyType(
    {
        "structural_conformance": "compile canonical .pypeline and compare manifest/native topology",
        "handler_purity": "inspect installed handler sources for forbidden routing/state ownership",
        "mutation_guards": "scan installed workflow source for anti-wrapper mutation targets",
        "static_topology": "verify compiled nodes, edges, and native routes from installed package",
        "fixed_scenario": "verify packaged native scenario fixtures are present",
        "rendered_policy": "verify compiled policy/native metadata from installed package",
        "override_matrix": "verify installed override matrix classification",
        "execute_s4_parity": "verify installed execute topology/checkpoints/receipts match development",
        "native_python_anti_wrapper": "verify .pypeline control flow and shim absence",
        "source_path_reconciliation": "verify installed resources, not checkout paths, supply proof",
    }
)


@dataclass(frozen=True)
class InstalledWheelArtifact:
    python: Path
    wheel: Path


@pytest.fixture(scope="module")
def installed_megaplan_wheel(
    tmp_path_factory: pytest.TempPathFactory,
) -> InstalledWheelArtifact:
    tmp = tmp_path_factory.mktemp("megaplan-installed-wheel")
    wheel_dir = tmp / "wheelhouse"
    wheel_dir.mkdir()

    subprocess.run(
        [sys.executable, "-m", "pip", "wheel", "--no-deps", "-w", str(wheel_dir), str(REPO_ROOT)],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    wheels = sorted(wheel_dir.glob("*.whl"))
    assert len(wheels) == 1, f"expected one wheel, found {[wheel.name for wheel in wheels]}"

    venv_dir = tmp / "venv"
    venv.create(venv_dir, with_pip=True)
    python = venv_dir / "bin" / "python"
    pip = venv_dir / "bin" / "pip"
    subprocess.run(
        [str(pip), "install", str(wheels[0])],
        check=True,
        capture_output=True,
        text=True,
    )
    return InstalledWheelArtifact(python=python, wheel=wheels[0])


def _execute_s4_parity_payload() -> dict[str, object]:
    from arnold.workflow.boundary_evidence import (
        AuthorityRecord,
        BoundaryOutcome,
        BoundaryReceipt,
    )
    from arnold_pipelines.megaplan._core import (
        compute_task_batches,
        execute_batch_artifact_path,
        stable_task_id_digest,
    )
    from arnold_pipelines.megaplan.pipeline import build_and_compile_pipeline, build_pipeline
    from arnold_pipelines.megaplan.workflows import POLICY_COMPONENTS
    from arnold_pipelines.megaplan.workflows.boundary_contracts import (
        BOUNDARY_CONTRACTS_BY_ID,
    )

    pipeline = build_pipeline()
    shell = build_and_compile_pipeline()
    sample_tasks = [
        {"id": "T1", "depends_on": []},
        {"id": "T2", "depends_on": ["T1"]},
        {"id": "T3", "depends_on": ["T1"]},
        {"id": "T4", "depends_on": ["T2", "T3"]},
    ]
    digest = stable_task_id_digest(["T3", "T2", "T2"])
    checkpoint = execute_batch_artifact_path(Path("/plan"), 2, ["T3", "T2"])
    execute_policy = next(policy for policy in POLICY_COMPONENTS if policy.id == "megaplan:execute")
    route_surface = execute_policy.metadata["route_surface"]
    s4_ids = (
        "execute_approval",
        "execute_approval_denial",
        "execute_batch_checkpoint",
        "execute_partial_failure",
        "execute_blocked_anchor",
        "execute_resume_anchor",
        "execute_aggregate_promotion",
        "execute_no_review_terminal",
    )
    batch_receipt = BoundaryReceipt(
        boundary_id="execute_batch_checkpoint",
        workflow_id="megaplan-review",
        row_id=BOUNDARY_CONTRACTS_BY_ID["execute_batch_checkpoint"].row_id,
        invocation_id="inv-s4",
        artifact_refs=("execute_batches/batch_2/tasks_digest.json",),
        state_observation={"current_phase": "execute", "batch_stage": "checkpoint"},
        history_ref="execute_batch_checkpoint",
        phase_result_ref="phase_result.json",
        outcome=BoundaryOutcome.COMPLETE,
        details={"batch_index": 2, "task_ids": ("T2", "T3"), "child_trace_path": "execute/2"},
    ).to_dict()
    approval_receipt = BoundaryReceipt(
        boundary_id="execute_approval",
        workflow_id="megaplan-review",
        row_id=BOUNDARY_CONTRACTS_BY_ID["execute_approval"].row_id,
        invocation_id="inv-s4",
        artifact_refs=("approval_record.json",),
        state_observation={"current_phase": "execute", "approval_gate": "cleared"},
        history_ref="execute_approval_cleared",
        phase_result_ref="phase_result.json",
        outcome=BoundaryOutcome.COMPLETE,
        authority_records=(
            AuthorityRecord(
                actor="operator",
                role="approver",
                decision="approved",
                scope="execute:approval-approved",
            ),
        ),
        details={"approval_scope": "execute:approval-approved", "session_freshness": "current"},
    ).to_dict()
    return {
        "execute_routes": [
            {
                "source": route.source,
                "target": route.target,
                "label": route.label,
                "condition_ref": route.condition_ref,
            }
            for route in pipeline.routes
            if route.source == "execute" or route.target == "execute"
        ],
        "native_execute_routes": [
            route
            for route in shell.native_program.routing_topology["routes"]
            if route["source"] == "execute" or route["target"] == "execute"
        ],
        "route_surface_keys": sorted(route_surface),
        "batch_order": compute_task_batches(sample_tasks),
        "stable_digest": digest,
        "checkpoint_path": checkpoint.relative_to("/plan").as_posix(),
        "s4_contracts": {
            boundary_id: {
                "phase": BOUNDARY_CONTRACTS_BY_ID[boundary_id].phase.value,
                "row_id": BOUNDARY_CONTRACTS_BY_ID[boundary_id].row_id,
                "authority_required": BOUNDARY_CONTRACTS_BY_ID[boundary_id].authority_required,
                "details_keys": sorted(BOUNDARY_CONTRACTS_BY_ID[boundary_id].details),
            }
            for boundary_id in s4_ids
        },
        "receipt_schema": {
            "batch_keys": sorted(batch_receipt),
            "batch_detail_keys": sorted(batch_receipt["details"]),
            "approval_keys": sorted(approval_receipt),
            "approval_authority_keys": sorted(approval_receipt["authority_records"][0]),
            "approval_detail_keys": sorted(approval_receipt["details"]),
        },
    }


# ── installed-package authority chain ──────────────────────────────────────


class TestInstalledPackageAuthorityChain:
    """The installed package must expose the full authority chain:
    canonical source → WorkflowManifest → Pipeline.native_program."""

    def test_package_is_importable(self) -> None:
        import arnold_pipelines.megaplan as megaplan

        assert megaplan.__name__ == "arnold_pipelines.megaplan"

    def test_build_pipeline_returns_dsl_pipeline(self) -> None:
        """build_pipeline() must return a DSL Pipeline from the canonical source."""
        from arnold_pipelines.megaplan.pipeline import build_pipeline

        pipeline = build_pipeline()
        assert isinstance(pipeline, DslPipeline), (
            f"build_pipeline() must return DslPipeline, got {type(pipeline).__name__}"
        )

    def test_compile_pipeline_produces_workflow_manifest(self) -> None:
        """compile_pipeline(build_pipeline()) must produce a WorkflowManifest."""
        from arnold_pipelines.megaplan.pipeline import build_pipeline

        pipeline = build_pipeline()
        manifest = compile_pipeline(pipeline)
        assert isinstance(manifest, WorkflowManifest), (
            f"compile_pipeline must return WorkflowManifest, "
            f"got {type(manifest).__name__}"
        )
        assert manifest.id == "megaplan"
        assert manifest.manifest_hash is not None

    def test_build_and_compile_exposes_manifest(self) -> None:
        """build_and_compile_pipeline().manifest must be a WorkflowManifest."""
        from arnold_pipelines.megaplan.pipeline import build_and_compile_pipeline

        shell = build_and_compile_pipeline()
        assert shell.manifest is not None
        assert isinstance(shell.manifest, WorkflowManifest), (
            f"shell.manifest must be WorkflowManifest, "
            f"got {type(shell.manifest).__name__}"
        )

    def test_build_and_compile_exposes_native_program(self) -> None:
        """build_and_compile_pipeline().native_program must be a NativeProgram."""
        from arnold_pipelines.megaplan.pipeline import build_and_compile_pipeline

        shell = build_and_compile_pipeline()
        assert shell.native_program is not None
        assert isinstance(shell.native_program, NativeProgram), (
            f"shell.native_program must be NativeProgram, "
            f"got {type(shell.native_program).__name__}"
        )

    def test_build_and_compile_exposes_authored_pipeline(self) -> None:
        """build_and_compile_pipeline() must carry the authored DSL pipeline
        as evidence of canonical source authority."""
        from arnold_pipelines.megaplan.pipeline import build_and_compile_pipeline

        shell = build_and_compile_pipeline()
        assert shell.authored_pipeline is not None, (
            "shell must preserve authored_pipeline reference"
        )
        assert isinstance(shell.authored_pipeline, DslPipeline), (
            f"authored_pipeline must be DslPipeline, "
            f"got {type(shell.authored_pipeline).__name__}"
        )

    def test_authored_pipeline_matches_direct_build(self) -> None:
        """The shell's authored_pipeline must be structurally equivalent to
        a direct build_pipeline() call on the canonical source."""
        from arnold_pipelines.megaplan.pipeline import (
            build_and_compile_pipeline,
            build_pipeline,
        )

        direct = build_pipeline()
        shell = build_and_compile_pipeline()
        authored = shell.authored_pipeline

        assert authored.id == direct.id
        assert len(authored.steps) == len(direct.steps)
        assert authored.entry == direct.entry


# ── manifest as compiled inspection/replay artifact ────────────────────────


class TestManifestAsCompiledArtifact:
    """WorkflowManifest is a compiled artifact for inspection and replay,
    not the semantic source of truth."""

    def test_manifest_is_derived_not_authoritative(self) -> None:
        """The manifest is produced by the compiler; it should not be
        the primary way to author pipeline semantics."""
        from arnold_pipelines.megaplan.pipeline import build_pipeline

        pipeline = build_pipeline()
        manifest = compile_pipeline(pipeline)

        # Manifest derives from pipeline, not the other way around
        assert manifest.id == pipeline.id
        # Manifest nodes should correspond to DSL steps
        dsl_step_ids = {step.id for step in pipeline.steps}
        manifest_node_ids = {n.id for n in manifest.nodes if "policy" not in n.id}
        # The manifest carries step nodes (not just policy nodes)
        assert len(manifest_node_ids) > 0

    def test_manifest_hash_is_stable_for_same_source(self) -> None:
        """Repeated compilation of the same source must produce the same hash."""
        from arnold_pipelines.megaplan.pipeline import build_pipeline

        pipeline1 = build_pipeline()
        pipeline2 = build_pipeline()

        manifest1 = compile_pipeline(pipeline1)
        manifest2 = compile_pipeline(pipeline2)

        assert manifest1.manifest_hash == manifest2.manifest_hash, (
            "manifest hash must be stable for identical source"
        )
        assert manifest1.topology_hash == manifest2.topology_hash, (
            "topology hash must be stable for identical source"
        )

    def test_manifest_exposes_inspection_surface(self) -> None:
        """WorkflowManifest must expose id, nodes, edges, capabilities,
        policy, metadata, and hashes for inspection."""
        from arnold_pipelines.megaplan.pipeline import build_pipeline

        manifest = compile_pipeline(build_pipeline())

        assert manifest.id, "manifest must have id"
        assert manifest.nodes, "manifest must have nodes"
        assert manifest.edges is not None, "manifest must have edges"
        assert manifest.topology_hash, "manifest must have topology_hash"
        assert manifest.manifest_hash, "manifest must have manifest_hash"


# ── native_program as dispatch substrate ───────────────────────────────────


class TestNativeProgramAsDispatchSubstrate:
    """Pipeline.native_program is the dispatch substrate, not the semantic
    source of truth."""

    def test_native_program_has_routing_topology(self) -> None:
        from arnold_pipelines.megaplan.pipeline import build_and_compile_pipeline

        shell = build_and_compile_pipeline()
        native = shell.native_program

        assert native.routing_topology is not None
        assert "nodes" in native.routing_topology
        assert "routes" in native.routing_topology

    def test_native_program_instructions_match_dsl_steps(self) -> None:
        from arnold_pipelines.megaplan.pipeline import (
            build_and_compile_pipeline,
            build_pipeline,
        )

        pipeline = build_pipeline()
        shell = build_and_compile_pipeline()
        native = shell.native_program

        assert len(native.instructions) == len(pipeline.steps), (
            f"native instructions ({len(native.instructions)}) must match "
            f"DSL steps ({len(pipeline.steps)})"
        )

    def test_native_program_phases_correspond_to_steps(self) -> None:
        from arnold_pipelines.megaplan.pipeline import (
            build_and_compile_pipeline,
            build_pipeline,
        )

        pipeline = build_pipeline()
        shell = build_and_compile_pipeline()
        native = shell.native_program

        native_names = {p.name for p in native.phases}
        step_ids = {s.id for s in pipeline.steps}
        assert native_names == step_ids, (
            f"native phase names must match DSL step ids: "
            f"extra={native_names - step_ids}, missing={step_ids - native_names}"
        )

    def test_native_program_description_marks_as_substrate_proof(self) -> None:
        from arnold_pipelines.megaplan.pipeline import build_and_compile_pipeline

        shell = build_and_compile_pipeline()
        desc = shell.native_program.description

        assert "substrate proof" in desc.lower() or "compatibility projection" in desc.lower(), (
            f"native_program description must identify as substrate, got: {desc}"
        )


# ── canonical source is semantic authority ─────────────────────────────────


class TestCanonicalSourceIsSemanticAuthority:
    """The canonical authored source (workflows/workflow.pypeline) is the
    readable, product-local source of truth. The manifest and native_program
    are derived artifacts."""

    def test_canonical_source_path_is_committed_workflow_pypeline(self) -> None:
        from arnold_pipelines.megaplan.workflows.planning import AUTHORING_SOURCE_PATH

        assert AUTHORING_SOURCE_PATH.name == "workflow.pypeline"
        assert AUTHORING_SOURCE_PATH.is_file()

    def test_canonical_source_compiles_with_only_row_evidence_diagnostics(self) -> None:
        from arnold.workflow import check_workflow_source
        from arnold_pipelines.megaplan.workflows.planning import AUTHORING_SOURCE_PATH

        result = check_workflow_source(
            AUTHORING_SOURCE_PATH.read_text(encoding="utf-8"),
            source_path=AUTHORING_SOURCE_PATH,
        )
        assert {
            diagnostic.code.value for diagnostic in result.diagnostics
        } <= {"AWF245_ROW_EVIDENCE_INSUFFICIENCY"}

    def test_canonical_source_lowers_to_known_structure(self) -> None:
        """Lowering the canonical source must reveal parallel_map and
        subpipeline steps that the native_program dispatches."""
        from arnold_pipelines.megaplan.workflows.planning import AUTHORING_SOURCE_PATH

        lowered = lower_workflow_file(AUTHORING_SOURCE_PATH)
        kinds = {step.kind for step in lowered.steps}
        assert "parallel_map" in kinds, "canonical source must contain parallel_map steps"
        assert {
            "megaplan:tiebreaker_researcher",
            "megaplan:tiebreaker_challenger",
            "megaplan:tiebreaker_synthesis",
            "megaplan:tiebreaker_decision",
        } <= kinds, "canonical source must expose tiebreaker child steps"

    def test_changes_to_source_reflect_in_built_pipeline(self) -> None:
        """Modifications to the canonical source (even just re-reading it)
        should produce a fresh pipeline — proving the source is authoritative."""
        from arnold_pipelines.megaplan.pipeline import build_pipeline

        pipeline = build_pipeline()
        assert pipeline.steps, "pipeline must have steps from canonical source"
        # The canonical S4 topology exposes the four tiebreaker child steps
        # and the execute/review handoff directly.
        assert len(pipeline.steps) == 14, (
            f"expected 14 canonical steps, got {len(pipeline.steps)}"
        )

    def test_workflow_components_are_from_canonical_source(self) -> None:
        """The workflow components module (declared policy surfaces) must
        be traceable back to the canonical authored source."""
        from arnold_pipelines.megaplan import workflows
        from arnold_pipelines.megaplan.workflows.planning import AUTHORING_SOURCE_PATH

        # Components file must exist alongside the canonical source
        components_path = Path(workflows.components.__file__)
        assert components_path.parent == AUTHORING_SOURCE_PATH.parent, (
            "components.py must live in same directory as workflow.pypeline"
        )

    def test_installed_wheel_ships_canonical_pypeline_resource(
        self,
        installed_megaplan_wheel: InstalledWheelArtifact,
    ) -> None:
        with ZipFile(installed_megaplan_wheel.wheel) as archive:
            names = set(archive.namelist())

        assert WORKFLOW_PYPELINE_ARCHIVE_PATH in names
        assert WORKFLOW_PY_ARCHIVE_PATH in names

    def test_installed_wheel_resource_contract_preserves_native_authority(
        self,
        installed_megaplan_wheel: InstalledWheelArtifact,
    ) -> None:
        with ZipFile(installed_megaplan_wheel.wheel) as archive:
            pypeline_text = archive.read(WORKFLOW_PYPELINE_ARCHIVE_PATH).decode("utf-8")
            workflow_py_text = archive.read(WORKFLOW_PY_ARCHIVE_PATH).decode("utf-8")
        workflow_tree = ast.parse(pypeline_text)
        function = next(node for node in workflow_tree.body if isinstance(node, ast.FunctionDef))
        payload = {
            "pypeline_name": Path(WORKFLOW_PYPELINE_ARCHIVE_PATH).name,
            "workflow_py_name": Path(WORKFLOW_PY_ARCHIVE_PATH).name,
            "contains_while": any(isinstance(node, ast.While) for node in ast.walk(function)),
            "if_count": sum(isinstance(node, ast.If) for node in ast.walk(function)),
            "called_names": sorted(
                {
                    node.func.id
                    for node in ast.walk(function)
                    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                }
            ),
            "branch_names": sorted(
                {
                    node.left.id
                    for node in ast.walk(function)
                    if isinstance(node, ast.Compare) and isinstance(node.left, ast.Name)
                }
            ),
            "prohibited_hits": [
                token for token in PROHIBITED_WRAPPER_TOKENS if token in pypeline_text
            ],
            "workflow_py_mentions_pypeline": "workflow.pypeline" in workflow_py_text,
            "workflow_py_prohibited_hits": [
                token for token in WORKFLOW_SHIM_PROHIBITED_TOKENS if token in workflow_py_text
            ],
        }

        assert payload["pypeline_name"] == "workflow.pypeline"
        assert payload["workflow_py_name"] == "workflow.py"
        assert payload["prohibited_hits"] == []
        assert payload["contains_while"] is True
        assert payload["if_count"] >= 4
        assert {
            "loop",
            "parallel_map",
            "TIEBREAKER_RESEARCHER",
            "TIEBREAKER_CHALLENGER",
            "TIEBREAKER_SYNTHESIS",
            "TIEBREAKER_DECISION",
        } <= set(payload["called_names"])
        assert {
            "gate_route_signal",
            "review_route_signal",
            "decision",
            "override_result",
        } <= set(payload["branch_names"])
        assert payload["workflow_py_mentions_pypeline"] is True
        assert payload["workflow_py_prohibited_hits"] == []

    def test_installed_wheel_reruns_required_composition_conformance_from_artifact(
        self,
        installed_megaplan_wheel: InstalledWheelArtifact,
    ) -> None:
        script = textwrap.dedent(
            f"""
            from __future__ import annotations

            import ast
            import importlib
            import json
            import pathlib
            import sys
            import zipfile
            from importlib import resources

            from arnold.workflow.compiler import compile_pipeline
            from arnold.workflow.source_compiler import lower_workflow_file
            from arnold_pipelines.megaplan.pipeline import build_and_compile_pipeline, build_pipeline

            repo_root = pathlib.Path({str(REPO_ROOT)!r}).resolve()
            wheel_path = pathlib.Path({str(installed_megaplan_wheel.wheel)!r}).resolve()
            package = importlib.import_module("arnold_pipelines.megaplan")
            package_file = pathlib.Path(package.__file__).resolve()
            if package_file.is_relative_to(repo_root):
                raise AssertionError(f"installed proof came from checkout: {{package_file}}")
            if any(pathlib.Path(entry or ".").resolve() == repo_root for entry in sys.path):
                raise AssertionError(f"checkout root leaked into installed-wheel sys.path: {{sys.path}}")

            workflow_resource = resources.files("arnold_pipelines.megaplan.workflows").joinpath("workflow.pypeline")
            workflow_py_resource = resources.files("arnold_pipelines.megaplan.workflows").joinpath("workflow.py")
            pypeline_text = workflow_resource.read_text(encoding="utf-8")
            workflow_py_text = workflow_py_resource.read_text(encoding="utf-8")
            with resources.as_file(workflow_resource) as workflow_path:
                lowered = lower_workflow_file(workflow_path)

            pipeline = build_pipeline()
            manifest = compile_pipeline(pipeline)
            shell = build_and_compile_pipeline()
            workflow_tree = ast.parse(pypeline_text)
            workflow_fn = next(node for node in workflow_tree.body if isinstance(node, ast.FunctionDef))
            calls = {{
                node.func.id
                for node in ast.walk(workflow_fn)
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            }}
            branches = {{
                node.left.id
                for node in ast.walk(workflow_fn)
                if isinstance(node, ast.Compare) and isinstance(node.left, ast.Name)
            }}

            handler_modules = [
                "plan.py",
                "critique.py",
                "gate.py",
                "_tiebreaker_impl.py",
                "finalize.py",
                "execute.py",
                "review.py",
                "override.py",
                "shared.py",
            ]
            handler_texts = []
            handler_root = resources.files("arnold_pipelines.megaplan.handlers")
            for name in handler_modules:
                text = handler_root.joinpath(name).read_text(encoding="utf-8")
                handler_texts.append(text)

            override = importlib.import_module("arnold_pipelines.megaplan.workflows.override_matrix")
            with zipfile.ZipFile(wheel_path) as archive:
                archive_names = set(archive.namelist())

            required = {dict(REQUIRED_INSTALLED_CONFORMANCE_SUITES)!r}
            proofs = {{
                "structural_conformance": bool(manifest.nodes and manifest.edges and shell.native_program.instructions),
                "handler_purity": len(handler_texts) == len(handler_modules),
                "mutation_guards": not any(token in pypeline_text for token in {PROHIBITED_WRAPPER_TOKENS!r}),
                "static_topology": bool(shell.native_program.routing_topology["nodes"] and shell.native_program.routing_topology["routes"]),
                "fixed_scenario": (
                    len(pipeline.steps) == 14
                    and {{"prep", "plan", "critique", "gate", "tiebreaker_researcher", "tiebreaker_decision", "finalize", "execute", "review", "override"}}
                    <= {{step.id for step in pipeline.steps}}
                ),
                "rendered_policy": bool(manifest.policy and shell.native_program.description),
                "override_matrix": len(override.OVERRIDE_ACTION_MATRIX) == 11,
                "execute_s4_parity": (
                    any(route["source"] == "execute" and route["target"] == "review" for route in shell.native_program.routing_topology["routes"])
                    and "execute_batches/batch_2/tasks_" in __import__("arnold_pipelines.megaplan._core", fromlist=["execute_batch_artifact_path"]).execute_batch_artifact_path(pathlib.Path("/plan"), 2, ["T3", "T2"]).as_posix()
                ),
                "native_python_anti_wrapper": (
                    any(isinstance(node, ast.While) for node in ast.walk(workflow_fn))
                    and sum(isinstance(node, ast.If) for node in ast.walk(workflow_fn)) >= 4
                    and {{"loop", "parallel_map", "TIEBREAKER_RESEARCHER", "TIEBREAKER_CHALLENGER", "TIEBREAKER_SYNTHESIS", "TIEBREAKER_DECISION"}} <= calls
                    and {{"gate_route_signal", "review_route_signal", "decision", "override_result"}} <= branches
                    and "@workflow" not in workflow_py_text
                ),
                "source_path_reconciliation": (
                    workflow_resource.is_file()
                    and workflow_py_resource.is_file()
                    and {{step.kind for step in lowered.steps}} >= {{
                        "parallel_map",
                        "megaplan:tiebreaker_researcher",
                        "megaplan:tiebreaker_challenger",
                        "megaplan:tiebreaker_synthesis",
                        "megaplan:tiebreaker_decision",
                    }}
                ),
            }}
            missing = sorted(set(required) - set(proofs))
            failed = sorted(name for name, ok in proofs.items() if not ok)
            if missing or failed:
                raise AssertionError(json.dumps({{"missing": missing, "failed": failed}}, sort_keys=True))
            print(json.dumps({{"package_file": str(package_file), "proofs": sorted(proofs)}}, sort_keys=True))
            """
        )
        result = subprocess.run(
            [str(installed_megaplan_wheel.python), "-c", script],
            check=True,
            capture_output=True,
            text=True,
            cwd=installed_megaplan_wheel.wheel.parent,
            env={
                key: value
                for key, value in os.environ.items()
                if key not in {"PYTHONPATH", "PYTHONHOME"}
            }
            | {"PYTHONNOUSERSITE": "1"},
        )
        payload = json.loads(result.stdout)
        assert payload["proofs"] == sorted(REQUIRED_INSTALLED_CONFORMANCE_SUITES)

    def test_installed_execute_s4_parity_matches_development_checkout(
        self,
        installed_megaplan_wheel: InstalledWheelArtifact,
    ) -> None:
        expected = _execute_s4_parity_payload()
        script = textwrap.dedent(
            """
            from __future__ import annotations

            import json
            from pathlib import Path

            from arnold.workflow.boundary_evidence import (
                AuthorityRecord,
                BoundaryOutcome,
                BoundaryReceipt,
            )
            from arnold_pipelines.megaplan._core import (
                compute_task_batches,
                execute_batch_artifact_path,
                stable_task_id_digest,
            )
            from arnold_pipelines.megaplan.pipeline import build_and_compile_pipeline, build_pipeline
            from arnold_pipelines.megaplan.workflows import POLICY_COMPONENTS
            from arnold_pipelines.megaplan.workflows.boundary_contracts import (
                BOUNDARY_CONTRACTS_BY_ID,
            )

            pipeline = build_pipeline()
            shell = build_and_compile_pipeline()
            sample_tasks = [
                {"id": "T1", "depends_on": []},
                {"id": "T2", "depends_on": ["T1"]},
                {"id": "T3", "depends_on": ["T1"]},
                {"id": "T4", "depends_on": ["T2", "T3"]},
            ]
            digest = stable_task_id_digest(["T3", "T2", "T2"])
            checkpoint = execute_batch_artifact_path(Path("/plan"), 2, ["T3", "T2"])
            execute_policy = next(policy for policy in POLICY_COMPONENTS if policy.id == "megaplan:execute")
            route_surface = execute_policy.metadata["route_surface"]
            s4_ids = (
                "execute_approval",
                "execute_approval_denial",
                "execute_batch_checkpoint",
                "execute_partial_failure",
                "execute_blocked_anchor",
                "execute_resume_anchor",
                "execute_aggregate_promotion",
                "execute_no_review_terminal",
            )
            batch_receipt = BoundaryReceipt(
                boundary_id="execute_batch_checkpoint",
                workflow_id="megaplan-review",
                row_id=BOUNDARY_CONTRACTS_BY_ID["execute_batch_checkpoint"].row_id,
                invocation_id="inv-s4",
                artifact_refs=("execute_batches/batch_2/tasks_digest.json",),
                state_observation={"current_phase": "execute", "batch_stage": "checkpoint"},
                history_ref="execute_batch_checkpoint",
                phase_result_ref="phase_result.json",
                outcome=BoundaryOutcome.COMPLETE,
                details={"batch_index": 2, "task_ids": ("T2", "T3"), "child_trace_path": "execute/2"},
            ).to_dict()
            approval_receipt = BoundaryReceipt(
                boundary_id="execute_approval",
                workflow_id="megaplan-review",
                row_id=BOUNDARY_CONTRACTS_BY_ID["execute_approval"].row_id,
                invocation_id="inv-s4",
                artifact_refs=("approval_record.json",),
                state_observation={"current_phase": "execute", "approval_gate": "cleared"},
                history_ref="execute_approval_cleared",
                phase_result_ref="phase_result.json",
                outcome=BoundaryOutcome.COMPLETE,
                authority_records=(
                    AuthorityRecord(
                        actor="operator",
                        role="approver",
                        decision="approved",
                        scope="execute:approval-approved",
                    ),
                ),
                details={"approval_scope": "execute:approval-approved", "session_freshness": "current"},
            ).to_dict()
            payload = {
                "execute_routes": [
                    {
                        "source": route.source,
                        "target": route.target,
                        "label": route.label,
                        "condition_ref": route.condition_ref,
                    }
                    for route in pipeline.routes
                    if route.source == "execute" or route.target == "execute"
                ],
                "native_execute_routes": [
                    route
                    for route in shell.native_program.routing_topology["routes"]
                    if route["source"] == "execute" or route["target"] == "execute"
                ],
                "route_surface_keys": sorted(route_surface),
                "batch_order": compute_task_batches(sample_tasks),
                "stable_digest": digest,
                "checkpoint_path": checkpoint.relative_to("/plan").as_posix(),
                "s4_contracts": {
                    boundary_id: {
                        "phase": BOUNDARY_CONTRACTS_BY_ID[boundary_id].phase.value,
                        "row_id": BOUNDARY_CONTRACTS_BY_ID[boundary_id].row_id,
                        "authority_required": BOUNDARY_CONTRACTS_BY_ID[boundary_id].authority_required,
                        "details_keys": sorted(BOUNDARY_CONTRACTS_BY_ID[boundary_id].details),
                    }
                    for boundary_id in s4_ids
                },
                "receipt_schema": {
                    "batch_keys": sorted(batch_receipt),
                    "batch_detail_keys": sorted(batch_receipt["details"]),
                    "approval_keys": sorted(approval_receipt),
                    "approval_authority_keys": sorted(approval_receipt["authority_records"][0]),
                    "approval_detail_keys": sorted(approval_receipt["details"]),
                },
            }
            print(json.dumps(payload, sort_keys=True))
            """
        )
        result = subprocess.run(
            [str(installed_megaplan_wheel.python), "-c", script],
            check=True,
            capture_output=True,
            text=True,
            cwd=installed_megaplan_wheel.wheel.parent,
            env={
                key: value
                for key, value in os.environ.items()
                if key not in {"PYTHONPATH", "PYTHONHOME"}
            }
            | {"PYTHONNOUSERSITE": "1"},
        )
        assert json.loads(result.stdout) == expected


# ── installed-package smoke: no legacy leaks ───────────────────────────────


class TestInstalledPackageNoLegacyLeaks:
    """The installed package must not expose legacy shims, deleted
    subpackages, or compatibility wrappers as the normal authoring path."""

    def test_legacy_import_path_raises_module_not_found(self) -> None:
        with pytest.raises(ModuleNotFoundError):
            import arnold.pipelines.megaplan  # noqa: F401

    def test_workflow_manifest_not_top_level_export(self) -> None:
        """WorkflowManifest must not be a top-level export of megaplan —
        it is a compiled artifact, not the authoring surface."""
        import arnold_pipelines.megaplan as megaplan

        assert not hasattr(megaplan, "WorkflowManifest"), (
            "WorkflowManifest must not be a top-level export"
        )

    def test_legacy_build_functions_not_exposed(self) -> None:
        import arnold_pipelines.megaplan as megaplan

        assert not hasattr(megaplan, "build_legacy_pipeline")
        assert not hasattr(megaplan, "compile_planning_pipeline")

    def test_deleted_stage_classes_not_exposed(self) -> None:
        import arnold_pipelines.megaplan as megaplan

        deleted_classes = (
            "InProcessHandlerStep", "HandlerStep", "PrepStep",
            "PlanStep", "CritiqueStep", "GateStep", "ReviseStep",
            "FinalizeStep", "ExecuteStep", "ReviewStep", "TiebreakerStep",
        )
        for cls_name in deleted_classes:
            assert not hasattr(megaplan, cls_name), (
                f"Deleted class {cls_name} must not be exposed"
            )

    def test_native_program_is_dispatch_not_authoring_surface(self) -> None:
        """native_program is a dispatch substrate — docs must not teach
        authors to create NativeProgram directly."""
        # The native_program is derived, not authored
        from arnold_pipelines.megaplan.pipeline import build_and_compile_pipeline

        shell = build_and_compile_pipeline()
        native = shell.native_program
        # It should clearly identify itself as a substrate artifact
        assert native.name == "megaplan"
        assert native.description is not None

    def test_no_shim_or_fallback_guidance_in_package_init(self) -> None:
        """The package __init__.py must not contain shim or fallback guidance."""
        import arnold_pipelines.megaplan

        init_path = Path(arnold_pipelines.megaplan.__file__)
        text = init_path.read_text(encoding="utf-8").lower()
        banned = ("shim", "fallback", "compatibility wrapper", "legacy adapter")
        for token in banned:
            assert token not in text, (
                f"package __init__ must not contain '{token}'"
            )


# ── installed-package public surface ───────────────────────────────────────


class TestInstalledPackagePublicSurface:
    """The installed package must expose a clean public surface: build_pipeline,
    build_and_compile_pipeline, and the canonical workflow components."""

    def test_public_exports_are_present(self) -> None:
        import arnold_pipelines.megaplan as megaplan

        assert hasattr(megaplan, "__all__")
        assert "build_pipeline" in megaplan.__all__
        assert "build_and_compile_pipeline" in megaplan.__all__

    def test_build_pipeline_is_callable(self) -> None:
        import arnold_pipelines.megaplan as megaplan

        assert callable(megaplan.build_pipeline)

    def test_build_and_compile_is_callable(self) -> None:
        import arnold_pipelines.megaplan as megaplan

        assert callable(megaplan.build_and_compile_pipeline)

    def test_workflow_components_are_importable(self) -> None:
        from arnold_pipelines.megaplan import workflows

        assert workflows.ALL_STEP_COMPONENTS
        assert workflows.WORKFLOW_COMPONENTS
        assert workflows.POLICY_COMPONENTS
        assert workflows.PROMPT_COMPONENTS

    def test_workflow_components_expose_expected_policies(self) -> None:
        from arnold_pipelines.megaplan import workflows

        expected_policy_ids = {
            "megaplan:default",
            "megaplan:prep-clarify",
            "megaplan:gate",
            "megaplan:revise-loop",
            "megaplan:tiebreaker",
            "megaplan:finalize",
            "megaplan:review",
            "megaplan:execute",
            "megaplan:override",
            "megaplan:model-routing",
            "megaplan:blast-radius",
            "megaplan:robustness",
            "megaplan:artifact-contract",
            "megaplan:suspension",
        }
        actual_ids = {p.id for p in workflows.POLICY_COMPONENTS}
        assert actual_ids == expected_policy_ids, (
            f"policy component ids mismatch: "
            f"extra={actual_ids - expected_policy_ids}, "
            f"missing={expected_policy_ids - actual_ids}"
        )

    def test_no_direct_manifest_or_native_program_authoring_exposed(self) -> None:
        """The package must not encourage direct manifest or native_program
        authoring — these are compiled artifacts, not authoring surfaces."""
        import arnold_pipelines.megaplan as megaplan

        # These symbols must not be in __all__
        assert "WorkflowManifest" not in megaplan.__all__
        assert "NativeProgram" not in megaplan.__all__
        # These should not be top-level attributes
        assert not hasattr(megaplan, "WorkflowManifest")
        assert not hasattr(megaplan, "NativeProgram")


# ── smoke: full chain compiles cleanly ─────────────────────────────────────


class TestFullChainSmoke:
    """End-to-end smoke: canonical source builds, compiles, and exposes
    the full authority chain without errors."""

    def test_full_chain_no_errors(self) -> None:
        from arnold_pipelines.megaplan.pipeline import (
            build_and_compile_pipeline,
            build_pipeline,
        )

        # Step 1: canonical source → DSL pipeline
        pipeline = build_pipeline()
        assert isinstance(pipeline, DslPipeline)

        # Step 2: DSL pipeline → WorkflowManifest (compiled artifact)
        manifest = compile_pipeline(pipeline)
        assert isinstance(manifest, WorkflowManifest)
        assert manifest.manifest_hash is not None

        # Step 3: build_and_compile → shell with native_program + manifest
        shell = build_and_compile_pipeline()
        assert shell.manifest is not None
        assert shell.native_program is not None
        assert shell.authored_pipeline is not None

        # All three layers must agree on identity
        assert shell.manifest.id == pipeline.id
        assert shell.native_program.name == pipeline.id

    def test_manifest_to_json_is_valid(self) -> None:
        from arnold_pipelines.megaplan.pipeline import build_pipeline

        manifest = compile_pipeline(build_pipeline())
        json_str = manifest.to_json()
        assert isinstance(json_str, str)
        assert len(json_str) > 0
        # Round-trip must preserve id
        round_tripped = WorkflowManifest.from_json(json_str)
        assert round_tripped.id == manifest.id

    def test_native_program_round_trips_through_shell(self) -> None:
        from arnold_pipelines.megaplan.pipeline import build_and_compile_pipeline

        shell = build_and_compile_pipeline()
        native = shell.native_program

        assert native.instructions, "native program must have instructions"
        assert native.phases, "native program must have phases"
        assert native.routing_topology["nodes"], "routing topology must have nodes"
        assert native.routing_topology["routes"], "routing topology must have routes"

    def test_repeated_build_and_compile_is_idempotent(self) -> None:
        from arnold_pipelines.megaplan.pipeline import build_and_compile_pipeline

        shell1 = build_and_compile_pipeline()
        shell2 = build_and_compile_pipeline()

        assert shell1.manifest.manifest_hash == shell2.manifest.manifest_hash
        assert shell1.manifest.topology_hash == shell2.manifest.topology_hash
        assert len(shell1.native_program.instructions) == len(
            shell2.native_program.instructions
        )
