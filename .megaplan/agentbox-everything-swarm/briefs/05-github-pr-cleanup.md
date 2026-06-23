You are a DeepSeek subagent doing a read-only inventory for AgentBox. The user asked us to find EVERYTHING existing in this repo/local skills that overlaps with the desired Discord-first AgentBox: start tickets/epics/megaplans/chains from Discord, Guardian repairs/relaunches blocked runs, completed work gets pushed/PRd/consolidated, and DeepSeek/subagents can be used. The brief embeds local excerpts. Return a decisive inventory of reusable mechanics, with file refs, gaps, and concrete recommendations. Under 1200 words. Focus: how completed work moves to GitHub/main; push/PR/merge mechanics; loose branch cleanup skill; consolidation flow.


--- GLOBAL INVENTORY ---
# Relevant file inventory
arnold/agent/cron/scheduler.py
arnold/agent/hermes_cli/__init__.py
arnold/agent/hermes_cli/auth.py
arnold/agent/hermes_cli/colors.py
arnold/agent/hermes_cli/config.py
arnold/agent/hermes_cli/default_soul.py
arnold/agent/hermes_cli/env_loader.py
arnold/agent/hermes_cli/models.py
arnold/agent/hermes_constants.py
arnold/agent/hermes_state.py
arnold/agent/hermes_time.py
arnold/agent/tools/environments/ssh.py
arnold/agent/tools/mcp_oauth.py
arnold/control/__init__.py
arnold/control/interface.py
arnold/execution/state_store.py
arnold/kernel/control.py
arnold/patterns/control.py
arnold/supervisor/__init__.py
arnold/supervisor/model.py
arnold/supervisor/outcomes.py
arnold/workflow/authoring.py
arnold_pipelines/megaplan/_core/hermes_fanout.py
arnold_pipelines/megaplan/_core/scheduler/__init__.py
arnold_pipelines/megaplan/_core/scheduler/run.py
arnold_pipelines/megaplan/_core/scheduler/topo.py
arnold_pipelines/megaplan/_core/scheduler/types.py
arnold_pipelines/megaplan/_core/state_store.py
arnold_pipelines/megaplan/_core/worker_fanout.py
arnold_pipelines/megaplan/audits/hermes_vendoring.py
arnold_pipelines/megaplan/bakeoff/merge.py
arnold_pipelines/megaplan/bakeoff/worktree.py
arnold_pipelines/megaplan/briefs.py
arnold_pipelines/megaplan/chain/__init__.py
arnold_pipelines/megaplan/chain/ci_hook.py
arnold_pipelines/megaplan/chain/git_ops.py
arnold_pipelines/megaplan/chain/hinge_gate.py
arnold_pipelines/megaplan/chain/m3_dual_green.py
arnold_pipelines/megaplan/chain/m5_eval_gates.py
arnold_pipelines/megaplan/chain/spec.py
arnold_pipelines/megaplan/cloud/__init__.py
arnold_pipelines/megaplan/cloud/auth.py
arnold_pipelines/megaplan/cloud/cli.py
arnold_pipelines/megaplan/cloud/preflight.py
arnold_pipelines/megaplan/cloud/providers/__init__.py
arnold_pipelines/megaplan/cloud/providers/base.py
arnold_pipelines/megaplan/cloud/providers/local.py
arnold_pipelines/megaplan/cloud/providers/railway.py
arnold_pipelines/megaplan/cloud/providers/ssh.py
arnold_pipelines/megaplan/cloud/redact.py
arnold_pipelines/megaplan/cloud/spec.py
arnold_pipelines/megaplan/cloud/supervise.py
arnold_pipelines/megaplan/cloud/template.py
arnold_pipelines/megaplan/cloud/templates/Dockerfile
arnold_pipelines/megaplan/cloud/templates/__init__.py
arnold_pipelines/megaplan/cloud/templates/chain.yaml.example
arnold_pipelines/megaplan/cloud/templates/cloud.yaml.tmpl
arnold_pipelines/megaplan/cloud/templates/docker-compose.yaml.tmpl
arnold_pipelines/megaplan/cloud/templates/entrypoint.sh.tmpl
arnold_pipelines/megaplan/cloud/templates/healthserver.py
arnold_pipelines/megaplan/cloud/templates/railway.toml.tmpl
arnold_pipelines/megaplan/cloud/wrappers/__init__.py
arnold_pipelines/megaplan/cloud/wrappers/arnold-chain
arnold_pipelines/megaplan/cloud/wrappers/arnold-heartbeat
arnold_pipelines/megaplan/cloud/wrappers/arnold-run
arnold_pipelines/megaplan/cloud/wrappers/arnold-supervise
arnold_pipelines/megaplan/cloud/wrappers/mp-chain
arnold_pipelines/megaplan/cloud/wrappers/mp-heartbeat
arnold_pipelines/megaplan/cloud/wrappers/mp-run
arnold_pipelines/megaplan/cloud/wrappers/mp-supervise
arnold_pipelines/megaplan/control.py
arnold_pipelines/megaplan/control_interface.py
arnold_pipelines/megaplan/data/claude_subagent_appendix.md
arnold_pipelines/megaplan/data/cloud_skill.md
arnold_pipelines/megaplan/data/codex_subagent_appendix.md
arnold_pipelines/megaplan/data/epic_skill.md
arnold_pipelines/megaplan/data/tickets_skill.md
arnold_pipelines/megaplan/execute/merge.py
arnold_pipelines/megaplan/handlers/tickets.py
arnold_pipelines/megaplan/loop/git.py
arnold_pipelines/megaplan/orchestration/authority_readers.py
arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md
arnold_pipelines/megaplan/pipelines/epic-blitz/profiles/standard.toml
arnold_pipelines/megaplan/pipelines/epic-blitz/prompts/high/conceptual_fit.md
arnold_pipelines/megaplan/pipelines/epic-blitz/prompts/high/epic_decomposition.md
arnold_pipelines/megaplan/pipelines/epic-blitz/prompts/high/existing_system_reuse.md
arnold_pipelines/megaplan/pipelines/epic-blitz/prompts/high/missing_abstraction.md
arnold_pipelines/megaplan/pipelines/epic-blitz/prompts/high/strategic_risk.md
arnold_pipelines/megaplan/pipelines/epic-blitz/prompts/low/cli_ux_details.md
arnold_pipelines/megaplan/pipelines/epic-blitz/prompts/low/edge_cases.md
arnold_pipelines/megaplan/pipelines/epic-blitz/prompts/low/implementation_feasibility.md
arnold_pipelines/megaplan/pipelines/epic-blitz/prompts/low/migration_backcompat.md
arnold_pipelines/megaplan/pipelines/epic-blitz/prompts/low/testability.md
arnold_pipelines/megaplan/pipelines/epic-blitz/prompts/mid/agent_model_assignment.md
arnold_pipelines/megaplan/pipelines/epic-blitz/prompts/mid/blast_radius.md
arnold_pipelines/megaplan/pipelines/epic-blitz/prompts/mid/codebase_convention_fit.md
arnold_pipelines/megaplan/pipelines/epic-blitz/prompts/mid/data_artifact_model.md
arnold_pipelines/megaplan/pipelines/epic-blitz/prompts/mid/orchestration_semantics.md
arnold_pipelines/megaplan/pipelines/epic-blitz/prompts/reviser/high_revise.md
arnold_pipelines/megaplan/pipelines/epic-blitz/prompts/reviser/mid_revise.md
arnold_pipelines/megaplan/pipelines/epic-blitz/prompts/reviser/readiness.md
arnold_pipelines/megaplan/pipelines/epic_blitz.py
arnold_pipelines/megaplan/pipelines/live_supervisor/SKILL.md
arnold_pipelines/megaplan/pipelines/live_supervisor/__init__.py
arnold_pipelines/megaplan/pipelines/live_supervisor/model.py
arnold_pipelines/megaplan/pipelines/live_supervisor/pipelines.py
arnold_pipelines/megaplan/pipelines/live_supervisor/repair_agent.py
arnold_pipelines/megaplan/pipelines/live_supervisor/rules.py
arnold_pipelines/megaplan/pipelines/live_supervisor/steps.py
arnold_pipelines/megaplan/planning/control_binding.py
arnold_pipelines/megaplan/resident/__init__.py
arnold_pipelines/megaplan/resident/agent_loop.py
arnold_pipelines/megaplan/resident/auth.py
arnold_pipelines/megaplan/resident/cli.py
arnold_pipelines/megaplan/resident/cloud.py
arnold_pipelines/megaplan/resident/coalescing.py
arnold_pipelines/megaplan/resident/config.py
arnold_pipelines/megaplan/resident/discord.py
arnold_pipelines/megaplan/resident/profile.py
arnold_pipelines/megaplan/resident/runtime.py
arnold_pipelines/megaplan/resident/scheduler.py
arnold_pipelines/megaplan/resident/tool_registry.py
arnold_pipelines/megaplan/resident/tool_schemas.py
arnold_pipelines/megaplan/runtime/budget_authority.py
arnold_pipelines/megaplan/skills/megaplan-cloud/SKILL.md
arnold_pipelines/megaplan/skills/megaplan-epic/SKILL.md
arnold_pipelines/megaplan/skills/megaplan-tickets/SKILL.md
arnold_pipelines/megaplan/store/__init__.py
arnold_pipelines/megaplan/store/_db/__init__.py
arnold_pipelines/megaplan/store/_db/assets.py
arnold_pipelines/megaplan/store/_db/checklists.py
arnold_pipelines/megaplan/store/_db/common.py
arnold_pipelines/megaplan/store/_db/conversations.py
arnold_pipelines/megaplan/store/_db/epics.py
arnold_pipelines/megaplan/store/_db/events.py
arnold_pipelines/megaplan/store/_db/migration.py
arnold_pipelines/megaplan/store/_db/operations.py
arnold_pipelines/megaplan/store/_db/plans.py
arnold_pipelines/megaplan/store/_db/runtime.py
arnold_pipelines/megaplan/store/_db/sprints.py
arnold_pipelines/megaplan/store/_file/__init__.py
arnold_pipelines/megaplan/store/_file/checklists.py
arnold_pipelines/megaplan/store/_file/code_artifacts.py
arnold_pipelines/megaplan/store/_file/codebases.py
arnold_pipelines/megaplan/store/_file/common.py
arnold_pipelines/megaplan/store/_file/conversations.py
arnold_pipelines/megaplan/store/_file/epics.py
arnold_pipelines/megaplan/store/_file/events.py
arnold_pipelines/megaplan/store/_file/external_requests.py
arnold_pipelines/megaplan/store/_file/feedback.py
arnold_pipelines/megaplan/store/_file/images.py
arnold_pipelines/megaplan/store/_file/operations.py
arnold_pipelines/megaplan/store/_file/plans.py
arnold_pipelines/megaplan/store/_file/second_opinions.py
arnold_pipelines/megaplan/store/_file/sprints.py
arnold_pipelines/megaplan/store/_file/tickets.py
arnold_pipelines/megaplan/store/base.py
arnold_pipelines/megaplan/store/blob.py
arnold_pipelines/megaplan/store/capsule.py
arnold_pipelines/megaplan/store/compat.py
arnold_pipelines/megaplan/store/db.py
arnold_pipelines/megaplan/store/export.py
arnold_pipelines/megaplan/store/file.py
arnold_pipelines/megaplan/store/identity.py
arnold_pipelines/megaplan/store/legacy_migration.py
arnold_pipelines/megaplan/store/multi.py
arnold_pipelines/megaplan/store/plan_repository.py
arnold_pipelines/megaplan/store/snapshot.py
arnold_pipelines/megaplan/store/warrant.py
arnold_pipelines/megaplan/store/warrant_sources.py
arnold_pipelines/megaplan/supervisor/__init__.py
arnold_pipelines/megaplan/supervisor/bakeoff_binding.py
arnold_pipelines/megaplan/supervisor/bakeoff_runner.py
arnold_pipelines/megaplan/supervisor/chain_runner.py
arnold_pipelines/megaplan/supervisor/driver.py
arnold_pipelines/megaplan/supervisor/ladder.py
arnold_pipelines/megaplan/supervisor/model.py
arnold_pipelines/megaplan/supervisor/outcomes.py
arnold_pipelines/megaplan/supervisor/pr_merge.py
arnold_pipelines/megaplan/supervisor/state.py
arnold_pipelines/megaplan/tickets/__init__.py
arnold_pipelines/megaplan/tickets/core.py
arnold_pipelines/megaplan/tickets/files.py
arnold_pipelines/megaplan/tickets/identity.py
arnold_pipelines/megaplan/tickets/registry.py
arnold_pipelines/megaplan/watchdog/__init__.py
arnold_pipelines/megaplan/watchdog/correlate.py
arnold_pipelines/megaplan/watchdog/discovery.py
arnold_pipelines/megaplan/watchdog/log.py
arnold_pipelines/megaplan/watchdog/orphans.py
arnold_pipelines/megaplan/watchdog/processes.py
arnold_pipelines/megaplan/watchdog/registry.py
arnold_pipelines/megaplan/watchdog/repair_runner.py
arnold_pipelines/megaplan/watchdog/retry.py
arnold_pipelines/megaplan/watchdog/signals.py
arnold_pipelines/megaplan/watchdog/snapshot.py
arnold_pipelines/megaplan/watchdog/tmux_scan.py
arnold_pipelines/megaplan/workers/__init__.py
arnold_pipelines/megaplan/workers/_impl.py
arnold_pipelines/megaplan/workers/_mock_payloads.py
arnold_pipelines/megaplan/workers/_projection_caps.py
arnold_pipelines/megaplan/workers/hermes.py
arnold_pipelines/megaplan/workers/result_metadata.py
arnold_pipelines/megaplan/workers/shannon.py
arnold_pipelines/megaplan/workers/shannon_session.py
arnold_pipelines/megaplan/workers/shannon_stream.py
arnold_pipelines/megaplan/workers/subscription_gate.py
arnold_pipelines/megaplan/workers/turn_cap.py
docs/archive/agentkit-migration-chain.yaml
docs/archive/cloud-migration-from-reigh.md
docs/archive/m5/pipelines/briefs/validation/sequencing/PROGRAM.md
docs/archive/m5/pipelines/briefs/validation/sequencing/strangler-keep-alive.md
docs/archive/m5/pipelines/epic_blitz/__init__.py
docs/archive/m5/pipelines/epic_blitz/profiles/standard.toml
docs/archive/m5/pipelines/epic_blitz/prompts/high/conceptual_fit.md
docs/archive/m5/pipelines/epic_blitz/prompts/high/epic_decomposition.md
docs/archive/m5/pipelines/epic_blitz/prompts/high/existing_system_reuse.md
docs/archive/m5/pipelines/epic_blitz/prompts/high/missing_abstraction.md
docs/archive/m5/pipelines/epic_blitz/prompts/high/strategic_risk.md

--- SYMBOL MATCHES ---
# High-signal symbol matches
scripts/check_workflow_pipeline_inventory.py:92:    "arnold_pipelines/megaplan/pipelines/epic_blitz.py": {
scripts/check_workflow_pipeline_inventory.py:104:    "arnold/pipelines/epic_blitz": {
scripts/check_workflow_pipeline_inventory.py:120:    "arnold/pipelines/briefs": {
scripts/check_workflow_pipeline_inventory.py:165:    "arnold_pipelines/megaplan/pipelines/epic-blitz": {
scripts/check_workflow_pipeline_inventory.py:201:    "arnold/pipelines/epic_blitz",
scripts/check_workflow_pipeline_inventory.py:205:    "arnold/pipelines/briefs",
scripts/check_workflow_pipeline_inventory.py:208:    "arnold_pipelines/megaplan/pipelines/epic_blitz.py",
scripts/check_workflow_pipeline_inventory.py:209:    "arnold_pipelines/megaplan/pipelines/epic-blitz",
scripts/check_workflow_pipeline_inventory.py:231:    "docs/arnold/arnold-megaplan-cleanup-plan.md",
scripts/check_workflow_pipeline_inventory.py:232:    "docs/arnold/arnold-megaplan-subagent-review-synthesis.md",
scripts/check_workflow_pipeline_inventory.py:243:def _normalize_root(path: Path) -> str:
scripts/check_workflow_pipeline_inventory.py:247:def _discover_shipped_roots() -> list[Path]:
scripts/check_workflow_pipeline_inventory.py:260:def _is_archival(path: Path) -> bool:
scripts/check_workflow_pipeline_inventory.py:268:def _check_forbidden_strings(path: Path) -> list[str]:
scripts/check_workflow_pipeline_inventory.py:281:def _check_forbidden_doc_strings(path: Path) -> list[str]:
scripts/check_workflow_pipeline_inventory.py:294:def _python_files_under(root: Path) -> list[Path]:
scripts/check_workflow_pipeline_inventory.py:300:def main(argv: list[str] | None = None) -> int:
arnold_pipelines/megaplan/store/snapshot.py:1:"""Canonical epic snapshot helpers shared by store backends."""
arnold_pipelines/megaplan/store/snapshot.py:13:def _canonicalize(value: Any) -> Any:
arnold_pipelines/megaplan/store/snapshot.py:25:def canonical_json_dumps(value: Any) -> str:
arnold_pipelines/megaplan/store/snapshot.py:30:def canonical_sha256(value: Any) -> str:
arnold_pipelines/megaplan/store/snapshot.py:34:class SnapshotStore(Protocol):
arnold_pipelines/megaplan/store/snapshot.py:35:    def load_epic(self, epic_id: str) -> Any | None:
arnold_pipelines/megaplan/store/snapshot.py:38:    def load_body(self, epic_id: str) -> str:
arnold_pipelines/megaplan/store/snapshot.py:41:    def list_checklist_items(self, epic_id: str, *, status: str | None = None) -> list[Any]:
arnold_pipelines/megaplan/store/snapshot.py:44:    def list_sprints(self, epic_id: str, *, status: str | None = None) -> list[Any]:
arnold_pipelines/megaplan/store/snapshot.py:47:    def list_sprint_items(self, sprint_id: str) -> list[Any]:
arnold_pipelines/megaplan/store/snapshot.py:50:    def list_images(self, *, epic_id: str, source: str | None = None, active: bool | None = True) -> list[Any]:
arnold_pipelines/megaplan/store/snapshot.py:53:    def list_second_opinions(self, epic_id: str, *, limit: int | None = None) -> list[Any]:
arnold_pipelines/megaplan/store/snapshot.py:57:def _model_json(value: Any) -> dict[str, Any]:
arnold_pipelines/megaplan/store/snapshot.py:63:def capture_epic_snapshot(store: SnapshotStore, epic_id: str) -> EpicSnapshot:
arnold_pipelines/megaplan/store/snapshot.py:64:    epic = store.load_epic(epic_id)
arnold_pipelines/megaplan/store/snapshot.py:65:    if epic is None:
arnold_pipelines/megaplan/store/snapshot.py:66:        raise FileNotFoundError(epic_id)
arnold_pipelines/megaplan/store/snapshot.py:68:        store.list_checklist_items(epic_id),
arnold_pipelines/megaplan/store/snapshot.py:72:        store.list_sprints(epic_id),
arnold_pipelines/megaplan/store/snapshot.py:80:        store.list_images(epic_id=epic_id, active=None),
arnold_pipelines/megaplan/store/snapshot.py:84:        store.list_second_opinions(epic_id, limit=None),
arnold_pipelines/megaplan/store/snapshot.py:89:        for part in (epic.title, epic.goal, store.load_body(epic_id))
arnold_pipelines/megaplan/store/snapshot.py:93:        epic_id=epic_id,
arnold_pipelines/megaplan/store/snapshot.py:94:        revision=epic.revision,
arnold_pipelines/megaplan/store/snapshot.py:95:        epic=_model_json(epic),
arnold_pipelines/megaplan/store/snapshot.py:96:        body=store.load_body(epic_id),
scripts/chain_done_gate.py:18:def _chain_state_path_for(spec_path: Path) -> Path:
scripts/chain_done_gate.py:25:        / ".chains"
scripts/chain_done_gate.py:30:def _load_json(path: Path) -> dict[str, Any]:
scripts/chain_done_gate.py:42:def _load_yaml(path: Path) -> dict[str, Any]:
scripts/chain_done_gate.py:52:def _milestone_labels(spec: dict[str, Any]) -> list[str]:
scripts/chain_done_gate.py:55:        raise ValueError("chain spec must contain a milestones list")
scripts/chain_done_gate.py:64:def _plans_root_candidates(
scripts/chain_done_gate.py:95:def _read_plan_state(plan_name: str, plans_roots: list[Path]) -> tuple[Path | None, dict[str, Any] | None]:
scripts/chain_done_gate.py:104:def _open_blockers(blockers_path: Path | None) -> list[str]:
scripts/chain_done_gate.py:127:def check_chain_done(
scripts/chain_done_gate.py:135:    state = _load_json(state_path or _chain_state_path_for(spec_path))
scripts/chain_done_gate.py:142:            "completion_contract_mode must be enforce before chain completion "
scripts/chain_done_gate.py:148:            "full_suite_backstop_mode must be enforce before chain completion "
scripts/chain_done_gate.py:154:        errors.append("chain state completed field must be a list")
scripts/chain_done_gate.py:165:            errors.append(f"milestone {label!r} is not recorded in chain_state.completed")
scripts/chain_done_gate.py:194:def main(argv: list[str] | None = None) -> int:
scripts/chain_done_gate.py:197:            "Fail a chain completion if any milestone's plan state is not done, "
scripts/chain_done_gate.py:198:            "if chain backstops are non-blocking, or if review blockers remain open."
scripts/chain_done_gate.py:201:    parser.add_argument("--spec", type=Path, help="Path to chain.yaml")
scripts/chain_done_gate.py:202:    parser.add_argument("--state", type=Path, help="Path to the persisted chain state JSON")
scripts/chain_done_gate.py:230:            errors = check_chain_done(
scripts/chain_done_gate.py:237:        print(f"chain done gate failed: {exc}", file=sys.stderr)
scripts/chain_done_gate.py:242:            print(f"chain done gate failed: {error}", file=sys.stderr)
scripts/chain_done_gate.py:244:    print("chain done gate passed")
scripts/simulate_watchdog_end_to_end.py:2:"""End-to-end simulation of the live watchdog repair + relaunch + recheck flow.
scripts/simulate_watchdog_end_to_end.py:4:This script creates a synthetic blocked plan, runs the watchdog against it with a
scripts/simulate_watchdog_end_to_end.py:5:fake megaplan CLI, and verifies the watchdog:
scripts/simulate_watchdog_end_to_end.py:30:def _write_json(path: Path, data: dict[str, object]) -> None:
scripts/simulate_watchdog_end_to_end.py:34:def _make_fake_megaplan_cli(bin_dir: Path) -> Path:
scripts/simulate_watchdog_end_to_end.py:48:project_dir = os.environ.get("MEGAPLAN_PROJECT_DIR", os.getcwd())
scripts/simulate_watchdog_end_to_end.py:54:def now_utc():
scripts/simulate_watchdog_end_to_end.py:57:def read_state():
scripts/simulate_watchdog_end_to_end.py:63:def write_state(state):
scripts/simulate_watchdog_end_to_end.py:66:def append_event(kind, payload=None):
scripts/simulate_watchdog_end_to_end.py:81:if cmd == "watchdog-worker":
scripts/simulate_watchdog_end_to_end.py:83:    # Keep this process alive so the watchdog sees a live megaplan-correlated
scripts/simulate_watchdog_end_to_end.py:109:    # Start a fake worker process so the next watchdog scan sees a live process.
scripts/simulate_watchdog_end_to_end.py:113:        [sys.executable, str(Path(__file__).resolve()), "watchdog-worker", str(plan_dir)],
scripts/simulate_watchdog_end_to_end.py:125:if cmd == "chain":
scripts/simulate_watchdog_end_to_end.py:126:    print("[fake megaplan chain] noop")
scripts/simulate_watchdog_end_to_end.py:138:def _setup_blocked_plan(repo_dir: Path) -> Path:
scripts/simulate_watchdog_end_to_end.py:172:def _run_watchdog(args: list[str], env: dict[str, str]) -> dict[str, object]:
scripts/simulate_watchdog_end_to_end.py:173:    """Run the watchdog CLI and return the combined report."""
scripts/simulate_watchdog_end_to_end.py:175:        [sys.executable, "-B", str(REPO_ROOT / "scripts" / "megaplan_live_watchdog.py"), *args],
scripts/simulate_watchdog_end_to_end.py:183:        raise RuntimeError(f"watchdog failed with rc={result.returncode}")
scripts/simulate_watchdog_end_to_end.py:193:def main() -> int:
scripts/simulate_watchdog_end_to_end.py:205:        log_path = tmp / "watchdog.log"
scripts/simulate_watchdog_end_to_end.py:216:        print("\n=== Running watchdog (repair + 10s recheck) ===")
scripts/simulate_watchdog_end_to_end.py:217:        report = _run_watchdog(
scripts/simulate_watchdog_end_to_end.py:237:            print(f"cleanup_candidates: {len(r['cleanup_candidates'])}")
scripts/simulate_watchdog_end_to_end.py:269:        # Best-effort cleanup of the detached fake worker so we do not leave
scripts/m6_purge_gate.py:15:DEFAULT_PRODUCT_ROOTS = ("arnold_pipelines",)
scripts/m6_purge_gate.py:23:def _iter_product_roots(repo_root: Path, roots: Iterable[str]) -> list[Path]:
scripts/m6_purge_gate.py:27:def _legacy_dirs(product_root: Path) -> list[Path]:
scripts/m6_purge_gate.py:37:def _top_level_function_names(path: Path) -> set[str]:
scripts/m6_purge_gate.py:49:def _literal_all_exports(path: Path) -> set[str]:
scripts/m6_purge_gate.py:78:def _init_surface_errors(init_path: Path, repo_root: Path) -> list[str]:
scripts/m6_purge_gate.py:156:def _pipeline_surface_errors(repo_root: Path) -> list[str]:
scripts/m6_purge_gate.py:183:class _TestUsageVisitor(ast.NodeVisitor):
scripts/m6_purge_gate.py:194:    def __init__(self, legacy_names: set[str]) -> None:
scripts/m6_purge_gate.py:200:    def visit(self, node: ast.AST) -> None:
scripts/m6_purge_gate.py:207:    def visit_Import(self, node: ast.Import) -> None:
scripts/m6_purge_gate.py:219:    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
scripts/m6_purge_gate.py:233:    def visit_Call(self, node: ast.Call) -> None:
scripts/m6_purge_gate.py:274:    def visit_Name(self, node: ast.Name) -> None:
scripts/m6_purge_gate.py:285:    def _is_func_of_parent_call(self, node: ast.Name) -> bool:
scripts/m6_purge_gate.py:294:    def _is_hasattr_call(node: ast.Call) -> bool:
scripts/m6_purge_gate.py:302:    def _is_getattr_call(node: ast.Call) -> bool:
scripts/m6_purge_gate.py:309:    def _in_negation_context(self) -> bool:
scripts/m6_purge_gate.py:327:    def _is_pytest_raises_attrerror(expr: ast.expr) -> bool:
scripts/m6_purge_gate.py:347:def _is_allowlisted_test_keepalive_path(path: Path, repo_root: Path) -> bool:
scripts/m6_purge_gate.py:358:def _test_keepalive_errors(repo_root: Path, test_roots: Iterable[str]) -> list[str]:
scripts/m6_purge_gate.py:412:def check_m6_purge(
scripts/m6_purge_gate.py:415:    product_roots: Iterable[str] = DEFAULT_PRODUCT_ROOTS,
scripts/m6_purge_gate.py:430:def main(argv: list[str] | None = None) -> int:
scripts/m6_purge_gate.py:454:            product_roots=args.product_root or DEFAULT_PRODUCT_ROOTS,
scripts/generate_arnold_docs.py:74:def _now() -> str:
scripts/generate_arnold_docs.py:78:def _relative(path: Path) -> str:
scripts/generate_arnold_docs.py:85:def _provenance_header(
scripts/generate_arnold_docs.py:100:def _annotation_name(annotation: Any) -> str:
scripts/generate_arnold_docs.py:124:def _dataclass_field_rows(model: type[Any]) -> list[tuple[str, str, str]]:
scripts/generate_arnold_docs.py:138:def _table(headers: tuple[str, ...], rows: Iterable[tuple[Any, ...]]) -> list[str]:
scripts/generate_arnold_docs.py:139:    def cell(value: Any) -> str:
scripts/generate_arnold_docs.py:151:def _node_name(node: ast.AST) -> str | None:
scripts/generate_arnold_docs.py:163:def _source_lines_for_symbols(path: Path, symbols: Iterable[str]) -> str:
scripts/generate_arnold_docs.py:189:def _extract_step_symbols(steps_path: Path) -> tuple[str, ...]:
scripts/generate_arnold_docs.py:200:def _builder_target(info: ShippedPipelineInfo) -> str:
scripts/generate_arnold_docs.py:207:def _compile_and_validate(info: ShippedPipelineInfo) -> WorkflowManifest:
scripts/generate_arnold_docs.py:219:def _fake_run(manifest: WorkflowManifest) -> None:
scripts/generate_arnold_docs.py:232:def _render_example(info: ShippedPipelineInfo) -> Path | None:
scripts/generate_arnold_docs.py:329:def render_examples() -> dict[Path, str]:
scripts/generate_arnold_docs.py:342:def _workflow_subcommand_rows(parser: argparse.ArgumentParser) -> list[tuple[str, str]]:
scripts/generate_arnold_docs.py:355:def _manifest_field_rows() -> list[tuple[str, str, str]]:
scripts/generate_arnold_docs.py:359:def _node_field_rows() -> list[tuple[str, str, str]]:
scripts/generate_arnold_docs.py:363:def _edge_field_rows() -> list[tuple[str, str, str]]:
scripts/generate_arnold_docs.py:367:def _pipeline_registry_rows() -> list[tuple[str, str, str, str, str]]:
scripts/generate_arnold_docs.py:385:def render_reference() -> str:
scripts/generate_arnold_docs.py:457:def _render_skill(info: ShippedPipelineInfo) -> str:
scripts/generate_arnold_docs.py:503:def render_codex_skills() -> dict[Path, str]:
scripts/generate_arnold_docs.py:513:def _render_composed_skill(name: str, description: str) -> str:
scripts/generate_arnold_docs.py:556:def render_composed_rules() -> dict[Path, str]:
scripts/generate_arnold_docs.py:570:def _registries_to_update() -> dict[Path, tuple[ShippedPipelineInfo, ...]]:
scripts/generate_arnold_docs.py:588:def _load_registry(path: Path) -> dict[str, Any]:
scripts/generate_arnold_docs.py:594:def render_registries() -> dict[Path, str]:
scripts/generate_arnold_docs.py:619:def generated_files() -> dict[Path, str]:
scripts/generate_arnold_docs.py:629:def _is_gitignored(path: Path) -> bool:
scripts/generate_arnold_docs.py:642:def _check_files(files: dict[Path, str]) -> list[str]:
scripts/generate_arnold_docs.py:664:def write_files(files: dict[Path, str]) -> None:
scripts/generate_arnold_docs.py:670:def main(argv: list[str] | None = None) -> int:
arnold/conformance/routing.py:32:def iter_pipeline_stages(pipeline: Pipeline) -> list[Stage | ParallelStage]:
arnold/conformance/routing.py:45:def iter_pipeline_stage_names(pipeline: Pipeline) -> list[str]:
arnold/conformance/routing.py:58:def _has_routing_vocabulary(stage: Stage | ParallelStage) -> bool:
arnold/conformance/routing.py:63:def _has_routing_edges(stage: Stage | ParallelStage) -> bool:
arnold/conformance/routing.py:71:def detect_routing_stages(
arnold/conformance/routing.py:99:def check_vocabulary_coverage(
arnold/conformance/routing.py:153:def check_vocabulary_edge_consistency(
arnold/conformance/routing.py:227:def check_resolve_edge_normal_match(
arnold/conformance/routing.py:286:def check_resolve_edge_decision_match(
arnold/conformance/routing.py:333:def check_resolve_edge_override_match(
arnold/conformance/routing.py:380:def check_resolve_edge_halt(
arnold/conformance/routing.py:408:def check_resolve_edge_unmatched_signal(
arnold/conformance/routing.py:451:def check_resolve_edge_vocabulary_validation(
arnold/conformance/routing.py:512:def run_routing_conformance_suite(
arnold/workflow/dry_run.py:18:def dry_run(manifest: WorkflowManifest) -> dict[str, Any]:
arnold/workflow/dry_run.py:67:def to_data(report: dict[str, Any]) -> dict[str, Any]:
arnold/workflow/validation.py:33:FORBIDDEN_PRODUCT_IMPORTS = (
arnold/workflow/validation.py:50:class ManifestValidationError(ValueError):
arnold/workflow/validation.py:54:def validate_manifest(manifest: WorkflowManifest) -> None:
arnold/workflow/validation.py:121:def _validate_id(name: str, value: str, errors: list[str]) -> None:
arnold/workflow/validation.py:125:def _validate_ref(name: str, value: str, errors: list[str]) -> None:
arnold/workflow/validation.py:133:def _validate_optional_ref(name: str, value: str | None, errors: list[str]) -> None:
arnold/workflow/validation.py:138:def _validate_hash(name: str, value: str | None, errors: list[str]) -> None:
arnold/workflow/validation.py:143:def _validate_policy(name: str, policy: WorkflowPolicy | None, errors: list[str]) -> None:
arnold/workflow/validation.py:182:def _validate_suspension_route(
arnold/workflow/validation.py:204:def _validate_timing_policy(name: str, timing: TimingPolicy | None, errors: list[str]) -> None:
arnold/workflow/validation.py:212:def _validate_idempotency_policy(
arnold/workflow/validation.py:225:def _validate_effects(name: str, effects: Iterable[EffectRef], errors: list[str]) -> None:
arnold/workflow/validation.py:231:def _validate_effect_ref(
arnold/workflow/validation.py:248:def _validate_reducers(name: str, reducers: Iterable[ReducerRef], errors: list[str]) -> None:
arnold/workflow/validation.py:259:def _validate_compensation_policy(
arnold/workflow/validation.py:275:def _validate_compensation_target(
arnold/workflow/validation.py:290:def _validate_escalation_policy(
arnold/workflow/validation.py:310:def _validate_control_transitions(
arnold/workflow/validation.py:329:def _validate_topology_overlays(
arnold/workflow/validation.py:348:def _validate_authority_requirements(
arnold/workflow/validation.py:367:def _validate_optional_hash(name: str, value: str | None, errors: list[str]) -> None:
arnold/workflow/validation.py:372:def _validate_optional_positive_int(name: str, value: int | None, errors: list[str]) -> None:
arnold/workflow/validation.py:379:def _validate_optional_positive_number(name: str, value: float | None, errors: list[str]) -> None:
arnold/workflow/validation.py:391:def _validate_metadata(name: str, metadata: Mapping[str, Any], errors: list[str]) -> None:
arnold/workflow/validation.py:398:def _validate_json_value(name: str, value: Any, errors: list[str]) -> None:
arnold/workflow/validation.py:419:def _validate_cycles(
arnold/workflow/validation.py:436:    def visit(node_id: str) -> None:
arnold/workflow/validation.py:463:def _cycle_has_bounded_reentry(
arnold/workflow/validation.py:478:def _edges_between(
arnold/workflow/validation.py:486:def _is_explicit_bounded_reentry(
arnold/workflow/validation.py:510:def check_neutral_import_boundary(paths: Iterable[Path]) -> dict[str, tuple[str, ...]]:
arnold/workflow/validation.py:531:def _record_forbidden_import(module: str, hits: set[str]) -> None:
arnold/workflow/validation.py:532:    for forbidden in FORBIDDEN_PRODUCT_IMPORTS:
arnold/workflow/expressions.py:17:class ExpressionRef:
arnold/workflow/expressions.py:24:    def __post_init__(self) -> None:
arnold/workflow/expressions.py:33:    def key(self) -> str:
arnold/workflow/expressions.py:39:    def __bool__(self) -> bool:
arnold/workflow/expressions.py:42:    def __str__(self) -> str:
arnold/workflow/expressions.py:46:def expression_ref(
scripts/render_package_disposition_md.py:51:def _load_manifest(path: Path) -> dict[str, Any]:
scripts/render_package_disposition_md.py:60:def _group_rows_by_disposition(
scripts/render_package_disposition_md.py:71:def _group_rows_by_source_prefix(
scripts/render_package_disposition_md.py:83:def _split_parents_and_children(
scripts/render_package_disposition_md.py:105:def _md_code(s: str) -> str:
scripts/render_package_disposition_md.py:112:def _md_bullet_list(items: list[str], indent: int = 0) -> str:
scripts/render_package_disposition_md.py:118:def _md_bullet_list_from_strs(items: list[Any], indent: int = 0) -> str:
scripts/render_package_disposition_md.py:124:def _obj_list_to_table(
scripts/render_package_disposition_md.py:145:def _render_header() -> str:
scripts/render_package_disposition_md.py:155:def _render_overview(data: dict[str, Any]) -> str:
scripts/render_package_disposition_md.py:188:def _render_exclusions(data: dict[str, Any]) -> str:
scripts/render_package_disposition_md.py:207:def _render_row_detail(row: dict[str, Any], heading_level: int = 3) -> str:
scripts/render_package_disposition_md.py:311:def _render_split_section(
scripts/render_package_disposition_md.py:340:def _render_rows_by_disposition(data: dict[str, Any]) -> str:
scripts/render_package_disposition_md.py:358:def _render_parity_gates(data: dict[str, Any]) -> str:
scripts/render_package_disposition_md.py:375:def _render_runtime_settings_gates(data: dict[str, Any]) -> str:
scripts/render_package_disposition_md.py:396:def _render_next_milestone_recommendations(data: dict[str, Any]) -> str:
scripts/render_package_disposition_md.py:429:def _render_import_policy_summary(data: dict[str, Any]) -> str:
scripts/render_package_disposition_md.py:497:def render_markdown(data: dict[str, Any]) -> str:
scripts/render_package_disposition_md.py:524:def main(argv: list[str] | None = None) -> int:
scripts/validate_package_disposition.py:65:class Row:
scripts/validate_package_disposition.py:74:    def label(self) -> str:
scripts/validate_package_disposition.py:78:def _normalize_path(raw: str, *, allow_glob: bool) -> str:
scripts/validate_package_disposition.py:104:def _load_yaml(path: Path) -> dict[str, Any]:
scripts/validate_package_disposition.py:111:def _tracked_python_files(repo_root: Path) -> list[str]:
scripts/validate_package_disposition.py:126:def _canonical_source_path(raw: str) -> str:
scripts/validate_package_disposition.py:133:def _expect_string_list(
scripts/validate_package_disposition.py:152:def _validate_object_list(
scripts/validate_package_disposition.py:174:def _matches(pattern: str, tracked_files: list[str]) -> list[str]:
scripts/validate_package_disposition.py:180:def _directory_members(path: str, tracked_files: list[str]) -> list[str]:
scripts/validate_package_disposition.py:185:def _validate_top_level(data: dict[str, Any], errors: list[str]) -> None:
scripts/validate_package_disposition.py:199:            "valid_dispositions must exactly match the approved enum list in order"
scripts/validate_package_disposition.py:211:def _parse_rows(data: dict[str, Any], tracked_files: list[str], errors: list[str]) -> list[Row]:
scripts/validate_package_disposition.py:359:def _validate_gates(data: dict[str, Any], errors: list[str]) -> None:
scripts/validate_package_disposition.py:395:def _validate_exclusions(
scripts/validate_package_disposition.py:429:def _validate_coverage(
scripts/validate_package_disposition.py:506:def validate_manifest(data: dict[str, Any], tracked_files: list[str]) -> list[str]:
scripts/validate_package_disposition.py:516:def render_summary(data: dict[str, Any], tracked_files: list[str]) -> str:
scripts/validate_package_disposition.py:541:def main(argv: list[str] | None = None) -> int:
scripts/README.md:8:- `adopt_plan.py` adopts a finalized plan directory into an existing chain so
scripts/README.md:9:  the chain can resume at execute.
scripts/README.md:12:- `chain_done_gate.py` blocks chain completion when persisted chain state says a
scripts/README.md:19:  handlers and direct `stderr` writes, then classifies them for the M3a cleanup
scripts/README.md:28:python scripts/chain_done_gate.py \
scripts/README.md:29:  --spec .megaplan/briefs/workflow-manifest-runtime/chain.yaml \
scripts/README.md:30:  --state .megaplan/briefs/workflow-manifest-runtime/.megaplan/plans/.chains/chain-dd4726d3997c.json \
scripts/README.md:31:  --blockers .megaplan/briefs/workflow-manifest-runtime/blockers.json
scripts/check_pipeline_id_registry.py:27:def discover_registry_files(root: Path | None = None) -> list[Path]:
scripts/check_pipeline_id_registry.py:72:def _is_under(path: Path, parent: Path) -> bool:
scripts/check_pipeline_id_registry.py:80:def _repo_root() -> Path:
scripts/check_pipeline_id_registry.py:93:def _fallback_glob(root: Path) -> list[Path]:
scripts/check_pipeline_id_registry.py:103:def _load_registry_json(path: str | Path) -> dict[str, Any]:

--- FILE: /Users/peteromalley/Documents/poms_skills/cleanup-loose-branches/SKILL.md (1,220p) ---
---
name: cleanup-loose-branches
description: >
  Survey every place loose work hides in a git repo — starting with the
  current checkout's own uncommitted/untracked/unpushed work, then local
  branches, all worktrees (`.megaplan-worktrees`, `.megaplan/bakeoffs/*`,
  agent-tool worktrees), stashes, detached HEADs, interrupted rebases/merges,
  submodules, remote branches on origin and other remotes, fork PR refs,
  sibling repo variants, other clones of this repo elsewhere on disk,
  megaplan cloud workspaces, and GitHub Codespaces — classify each as
  land-on-main / delete / parked with reasoning, and act only on explicit
  per-item approval. Use when the user says "clean up loose branches",
  "prune branches", "what branches can I delete", "clean up worktrees",
  "review my stashes", "what's lying around in this repo", or asks for
  branch / worktree / stash housekeeping.
---

# cleanup-loose-branches

**Goal:** land every loose piece of work on `main` or drop it. Never delete without explicit per-item approval. Two phases: **survey** (read-only) → **walk-through** (per-item).

**The bias is STRONGLY toward landing on `main`.** The target end-state is: everything valuable is on `main`, and the only things not on `main` have a *specific, stated, good reason* (genuinely abandoned, superseded by better work, or a deliberate not-yet-ready effort the user named). "It would take a lot of work to consolidate" is **not** a good reason — it is the expected cost of this skill. **Be happy to spend lots of time refactoring, untangling, resolving conflicts, rewriting tests, and reconciling divergent work to get it onto `main`.** A clean `main` that absorbs the loose work is worth hours of careful consolidation. Parking work on a branch "for later" is the lazy outcome and usually the wrong one — prefer to do the integration now. Reach for subagents (`subagent-launcher`) to parallelize the heavy investigation so the effort is cheap, but do not let the *size* of a consolidation talk you out of it.

**What "loose work" means — read this first.** Loose work is **anything that exists in only one place.** The name says "branches" but branches are the *least* of it. Rank by how easily it is lost, highest first:

1. **Uncommitted changes in the current checkout's working tree** — committed nowhere, pushed nowhere. One `git checkout .` away from gone. THE most exposed work in any repo, and the one a "branch survey" skips by construction. **Always survey this. It is item zero, not out of scope.**
2. **Untracked files** (`git ls-files --others`) — same exposure, plus invisible to `git diff`.
3. **Uncommitted work in other worktrees** — same as #1 but easier to forget because it's not your current directory.
4. **Committed but unpushed** — survives local mistakes, dies with the disk.
5. **Pushed but only on a branch / single clone / single cloud volume** — the actual "loose branch."

A branch named `main` with a dirty tree is **not** outside this skill's scope. Neither is your own current checkout. If you ever find yourself thinking "that's just the main checkout's dirty state, not my problem," stop — that is the exact failure this skill exists to prevent. Account for **every** tier above before you claim the survey is done.

**Done when:** every row in the survey has been acted on or explicitly parked, the "Cleaned up / Kept / Still to decide" report has been printed, AND every tier of loose work above (including the current checkout's own uncommitted/untracked/unpushed work) has an explicit verdict. No silent drops, no items left in `uncertain`, no working-tree work left unaccounted for.

**Workflow:** run the survey **immediately** — don't ask "want me to look around?" or "should I make recommendations?" The process is:

1. **Loose direction:** survey everything read-only and produce an initial cleanup map. Make the best provisional call you can for every item, but name the uncertain/high-value decisions that need deeper judgement.
2. **Fan out medium-or-higher ambiguity:** if the first survey does not already give a clear go/no-go decision for an item, use targeted read-only DeepSeek/subagent briefs. Do not treat subagents as heavyweight escalation; they are the cheap default for clearing up uncertainty around big branches, stale PRs, overlapping worktrees, docs-vs-code residue, hidden loose state, or any recommendation you would otherwise hedge.
3. **Strong go/no-go recommendation:** read the reports, cross-check load-bearing claims, then collapse everything into a decisive table: land, delete, keep-until-X, or explicitly park. The goal of investigation is a go/no-go cleanup decision, not more notes. Only stop and ask at the phase 1 → phase 2 handoff, and again before any per-item destructive action.

`keep` is only for: open/draft PR, protected branch, or current active work the user has not said is ready. A dirty worktree is **risk**, not a recommendation. If the user says "everything except X is in scope", dirty worktrees outside X still need a landing/deletion recommendation: preserve artifacts, port useful work, then delete after approval. Everything else with unique commits gets a landing rec (`merge-then-delete` / `PR-then-merge` / `cherry-pick-then-delete`) or `delete`. "Recent branch with work on it" is not a reason to `keep` — pick a landing route.

**Do not stop after the first cleanup pass if the user asks about "all the other branches" or "loose threads."** Re-run the survey against the remaining branches/worktrees and classify the leftovers. The common failure mode is treating dirty parked worktrees as implicitly protected; only explicitly named active work is protected.

**If the user asks "is there other work too?" or "have you been thorough?" — treat it as a near-certain sign you scoped too narrowly.** Do not just re-assert your table. The two pools most often missed: (a) the **current checkout's own uncommitted/untracked/unpushed work** (item zero above), and (b) **non-branch loose state** — `.megaplan/tickets/` (deferred intent), stashes, other on-disk clones, cloud volumes. Run the sections you skipped, name what you missed plainly, and say *why* it was missed ("a branch listing can't show an uncommitted diff"). Answer the thoroughness question honestly — if you weren't thorough, say so and fix it; don't defend a partial sweep.

**Make a strong rec for every row after synthesis.** "Inspect" is not a rec. Hedging is a failure mode. The first survey may carry provisional uncertainty, but the final survey after fan-out must turn that into a decision. If you genuinely can't classify after the checks below, use `uncertain` and name the blocker plus the exact next investigation needed.

**Deploy a subagent (`subagent-launcher` or Agent tool) for any medium-or-higher ambiguity.** Concrete triggers include: 5+ unique commits, conflicts, no PR but load-bearing-looking commits, stale-but-possibly-valuable work, dirty worktrees whose payload might overlap, branch name diverging from PR `headRefName`, unclear base branch, uncertain supersession, or any row where your first-pass recommendation would be "inspect" / "maybe" / "probably." Brief: branch/item, unique commits, key files, known facts, "is each commit already on main or the true base as a different SHA?", "what would be lost if dropped?", and "give a go/no-go recommendation." Surface its per-commit or per-payload verdict in the walk-through. If there is no meaningful ambiguity because direct evidence already proves `delete`, `merge`, `PR`, or `keep`, do not spawn an agent just to rubber-stamp it. When the repo is mid-megaplan-epic, has multiple overlapping efforts, or has heavy uncommitted work across worktrees, escalate to the full **Deep-investigation mode** below — a parallel read-only DeepSeek fan-out plus a written consolidation plan. That section is the distilled best-practice from a real multi-epic cleanup; reach for it whenever a single survey pass can't relieve the ambiguity.

## Phase 1 — survey (read-only, parallel)

Resolve main, fetch, build the worktree map first:

```bash
MAIN=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')
MAIN=${MAIN:-main}
git fetch --all --prune --quiet 2>/dev/null
```

### The current checkout's own working tree (ITEM ZERO — most easily missed, highest exposure)

Do this **before** worktrees. The current checkout's uncommitted and untracked work is loose work that lives in exactly one place; a branch listing never shows it.

```bash
git status --short --branch                      # ahead/behind + dirty + untracked at a glance
git diff --stat HEAD                             # tracked uncommitted changes
git ls-files --others --exclude-standard         # untracked files (NOT shown by git diff)
git log --oneline @{u}..HEAD 2>/dev/null         # committed-but-unpushed commits
```

Then **isolate what is genuinely unique to this checkout** — work that exists on no branch, no other worktree, and no remote. The trap: a checkout's dirty diff often overlaps with worktrees forked from it, so most of it may be preserved elsewhere while a few files are unique and at risk:

```bash
# For each modified file, is its content reachable on any branch/worktree, or only here?
git diff HEAD --name-only | while read f; do
  git log --all --oneline -1 -- "$f" >/dev/null 2>&1 || true
done
# Most reliable: compare against any worktree forked from this checkout (see worktree section),
# and against $MAIN's tip: `git diff $MAIN -- <file>`. Files unique here = highest-risk row.
```

Surface this as explicit survey rows, not a footnote: **unique uncommitted work** (rec: checkpoint-to-branch + push, or commit to $MAIN if it belongs there), **untracked keepers vs. junk** (logs/caches/`.megaplan-agentic` = junk; new source/tests/briefs = keepers), and **unpushed commits** (rec: push, or note why held). Never recommend deleting or force-checking-out the current tree; preserve first.

**FOOTGUN — preserving the current checkout's dirty tree without disturbing it.** `git switch -c wip && git add -u && commit && git switch back` does **not** leave the dirty work behind — it *moves* it onto the new branch, and switching back leaves the original checkout **clean** (changes reverted, untracked keepers that got committed are removed). If the user is actively working in this checkout, that silently wipes their working state. Two safe patterns: (a) **record a fingerprint first** (`git diff HEAD | git hash-object --stdin` + the untracked list), do the snapshot-branch + push, then **restore**: `git checkout <wip-branch> -- . && git reset -q HEAD`, and verify the fingerprint matches; or (b) snapshot via a **scratch worktree** (`git worktree add /tmp/wip -b checkpoint/wip $MAIN`) and copy the dirty files in there, never touching the live checkout. Always verify the original tree is byte-identical afterward.

### Worktrees (FIRST among other worktrees — pinned branches can't be `-d`'d)

```bash
git worktree list --porcelain
ls -d "$PWD/.megaplan-worktrees"/* "$PWD/../"*"/.megaplan-worktrees"/* 2>/dev/null
find "$HOME/Documents/.megaplan-worktrees" "$HOME/.megaplan-worktrees" \
  -maxdepth 1 -mindepth 1 -type d 2>/dev/null
find "$PWD" -maxdepth 3 -type d \( -name '.worktrees' -o -name 'worktrees' \) 2>/dev/null
find "$PWD/.megaplan/bakeoffs" -maxdepth 3 -type d -name 'worktrees' 2>/dev/null
ls -d ~/.claude/projects/*/worktrees/* 2>/dev/null
```

**Do not trust `git worktree list` as complete.** It only shows worktrees registered
to the current repo's `.git/worktrees`. Megaplan and agent runs can leave standalone
or chained checkouts under a shared directory such as
`~/Documents/.megaplan-worktrees/<topic>` whose `.git` belongs to a different clone
or whose `origin` points to another local checkout. These are still loose work and
must be mini-surveyed. For every candidate directory above, accept both `.git`
directories and `.git` files:

```bash
for wt in "$HOME/Documents/.megaplan-worktrees"/* "$HOME/.megaplan-worktrees"/*; do
  git -C "$wt" rev-parse --git-dir >/dev/null 2>&1 || continue
  echo "== $wt =="
  git -C "$wt" remote -v
  git -C "$wt" rev-parse --show-toplevel
  git -C "$wt" branch --show-current
  git -C "$wt" log -1 --oneline
  git -C "$wt" status --porcelain
  git -C "$wt" ls-files --others --exclude-standard | head -80
done
```

If `remote get-url origin` is this repo, a local path to this repo, or a local path
to another checkout that ultimately points at this repo, classify it in this cleanup.
If it is a different repo, list it separately as "other repo loose work" and do not
merge it into the current repo. A directory can contain source/tests entirely as
untracked files; that is highest-risk loose work even when branch tables are clean.

Per registered or unregistered worktree: branch, origin chain, ahead/behind vs `$MAIN`
when it belongs to this repo, `git -C <path> status --porcelain`, and untracked file
summary. Dirty/untracked source = highest risk, flag red. Also note `prunable` entries
(`git worktree prune` fixes them).

**Build a `branch → worktree path` map now** — later sections check it to flag pinned branches (which refuse `git branch -d`).

### Local branches

```bash
git for-each-ref \
  --format='%(refname:short)|%(committerdate:iso8601)|%(committerdate:relative)|%(upstream:short)|%(upstream:track)|%(objectname:short)|%(contents:subject)' \
  refs/heads/
```

Per branch (skip `$MAIN`):
- ahead/behind: `git rev-list --left-right --count $MAIN...<br>`
- merged ancestor: `git merge-base --is-ancestor <br> $MAIN`
- **`cherry +N` (load-bearing — catches squash-merges and post-merge fixups):** `git cherry $MAIN <br> | grep -c '^+'`. Zero `+` = every patch already on main. Always compute before applying any merged-PR rule.
- conflicts: `git merge-tree $(git merge-base $MAIN <br>) $MAIN <br> | grep -c '<<<<<<<'`
- diff shape: `git diff --stat $MAIN...<br>`
- pinned: from the worktree map
- upstream `[gone]`: remote was deleted (PR auto-delete-on-merge)

### Stashes

```bash
git stash list --format='%gd|%cr|%s'
for s in $(git stash list --format='%gd'); do git stash show --stat "$s"; done
```

Cross-reference each stash's base branch against the branch table. A stash on a flagged-for-delete branch is the highest-risk row in the survey — surface the linkage; stash approval is always separate from branch approval.

### Remote branches + PR state

```bash
git branch -r --format='%(refname:short)|%(committerdate:iso8601)|%(committerdate:relative)'
gh pr list --state all --limit 200 \
  --json number,state,headRefName,baseRefName,title,updatedAt,isDraft,mergedAt,author > /tmp/prs.json
```

Join PRs by `headRefName`; most recent wins. If many `[gone]` upstreams, mention GitHub's auto-delete-head-branches setting.

### Interrupted operations (carry real work, not visible elsewhere)

```bash
ls .git/MERGE_HEAD .git/CHERRY_PICK_HEAD .git/REVERT_HEAD .git/REBASE_HEAD 2>/dev/null
ls -d .git/rebase-apply .git/rebase-merge .git/sequencer 2>/dev/null
```

Any hit → flag `keep` until user resolves the in-progress op. Show `git status` so the user can see what's mid-flight.

### Submodules

```bash
git submodule foreach --recursive \
  'echo "== $name =="; git status --porcelain; git stash list; git log --oneline @{u}.. 2>/dev/null'
```

Each submodule with dirty state, stashes, or unpushed commits gets its own row in the survey.

### Detached HEAD orphans

```bash
git fsck --unreachable --no-reflogs 2>/dev/null | grep -c '^unreachable commit'
```

Surface the count only; offer to dig in if the user's lost work.

### Untracked / patch / merge-tool leftovers

```bash
git ls-files --others --exclude-standard
find "$PWD" -maxdepth 3 -type f \
  \( -name '*.patch' -o -name '*.diff' \
     -o -name '*.orig' -o -name '*.BACKUP.*' -o -name '*.LOCAL.*' -o -name '*.REMOTE.*' -o -name '*.BASE.*' \) 2>/dev/null
```

`*.orig` / `*.BACKUP.*` / `*.LOCAL.*` / `*.REMOTE.*` / `*.BASE.*` are merge-tool leftovers — often partial work the user never finished resolving.

### Tags, odd refs, fork PR refs

```bash
git for-each-ref \
  --format='%(refname:short)|%(objectname:short)|%(committerdate:relative)|%(contents:subject)' \
  refs/notes refs/replace refs/original 2>/dev/null
git ls-remote origin 'refs/pull/*/head' | head -20
gh pr list --state open --limit 100 \
  --json number,headRepositoryOwner,headRefName,baseRefName,title,isDraft,url
```

Tags, `refs/notes`, `refs/replace`, `refs/original`: surface as **context only — never delete candidates**. External-head PRs (forks): PR work to keep/review, not branch cleanup.

### Non-origin remotes

--- FILE: arnold_pipelines/megaplan/chain/git_ops.py (1,360p) ---
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan.types import CliError


@dataclass(frozen=True)
class CommitResult:
    committed: bool
    pushed: bool
    commit_sha: str | None = None
    previous_ref: str | None = None
    previous_sha: str | None = None
    base_branch: str | None = None
    audit_notes: list[str] = field(default_factory=list)


def _compat():
    module = sys.modules.get(__package__)
    if module is None:  # pragma: no cover - defensive import guard
        raise RuntimeError(f"{__package__} not loaded")
    return module


def _refresh_base_branch(
    root: Path,
    base_branch: str,
    *,
    writer,
    no_git_refresh: bool = False,
) -> None:
    """Run a best-effort refresh of ``base_branch`` before milestone work.

    When ``no_git_refresh`` is True, this is a no-op (still logs that it was
    skipped). This guard exists so developer checkouts running ``megaplan
    chain`` do not get their currently checked-out branch stomped by an
    automatic base-branch checkout.

    ``git checkout <base_branch>`` is intentionally avoided because Git refuses
    to check out a branch that is active in a sibling worktree. The remote
    ``origin/<base_branch>`` ref is refreshed and used as the fork point; a
    local fast-forward pull is only attempted when this worktree is already on
    the base branch.
    """
    if no_git_refresh:
        writer("[chain] skipping git refresh (--no-git-refresh)\n")
        return
    fetch_cmd = ["git", "fetch", "origin", base_branch]
    try:
        proc = _compat().subprocess.run(
            fetch_cmd, cwd=str(root), capture_output=True, text=True, check=False, timeout=120
        )
        writer(f"[chain] {' '.join(fetch_cmd)} -> rc={proc.returncode}\n")
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "").strip()
            if detail:
                writer(f"[chain] {' '.join(fetch_cmd)} output:\n{detail}\n")
            raise CliError(
                "git_refresh_failed",
                (
                    "Chain git refresh failed before milestone initialization: "
                    f"{' '.join(fetch_cmd)} exited {proc.returncode}. "
                    "Resolve the fetch failure or rerun with --no-git-refresh."
                ),
                extra={
                    "command": fetch_cmd,
                    "returncode": proc.returncode,
                    "stdout": proc.stdout,
                    "stderr": proc.stderr,
                },
            )
    except (_compat().subprocess.TimeoutExpired, FileNotFoundError) as exc:
        writer(f"[chain] {' '.join(fetch_cmd)} failed: {exc}\n")
        raise CliError(
            "git_refresh_failed",
            (
                "Chain git refresh failed before milestone initialization: "
                f"{' '.join(fetch_cmd)} failed with {exc}. "
                "Resolve the fetch failure or rerun with --no-git-refresh."
            ),
            extra={"command": fetch_cmd, "error": str(exc)},
        ) from exc

    current_cmd = ["git", "symbolic-ref", "--short", "HEAD"]
    current = _compat().subprocess.run(
        current_cmd, cwd=str(root), capture_output=True, text=True, check=False, timeout=120
    )
    writer(f"[chain] {' '.join(current_cmd)} -> rc={current.returncode}\n")
    if current.returncode != 0 or current.stdout.strip() != base_branch:
        writer(
            f"[chain] using refreshed origin/{base_branch} as the milestone fork point; "
            f"local {base_branch} checkout refresh skipped\n"
        )
        return

    pull_cmd = ["git", "pull", "--ff-only", "origin", base_branch]
    try:
        proc = _compat().subprocess.run(
            pull_cmd, cwd=str(root), capture_output=True, text=True, check=False, timeout=120
        )
        writer(f"[chain] {' '.join(pull_cmd)} -> rc={proc.returncode}\n")
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "").strip()
            if detail:
                writer(f"[chain] {' '.join(pull_cmd)} output:\n{detail}\n")
            writer(
                "[chain] warning: fast-forward refresh failed; "
                f"continuing with refreshed origin/{base_branch}. "
                "This is expected when the local base has milestone commits "
                "or origin moved independently.\n"
            )
    except (_compat().subprocess.TimeoutExpired, FileNotFoundError) as exc:
        writer(f"[chain] {' '.join(pull_cmd)} failed: {exc}\n")
        writer(
            "[chain] warning: fast-forward refresh failed; "
            f"continuing with refreshed origin/{base_branch}. "
            "This is expected when the local base has milestone commits "
            "or origin moved independently.\n"
        )


def _run_command(
    root: Path,
    cmd: list[str],
    *,
    writer,
    timeout: float = 120,
    error_code: str = "command_failed",
) -> subprocess.CompletedProcess[str]:
    """Run a git/gh command and raise CliError with captured output on failure."""
    try:
        proc = _compat().subprocess.run(
            cmd,
            cwd=str(root),
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except (_compat().subprocess.TimeoutExpired, FileNotFoundError) as exc:
        writer(f"[chain] {' '.join(cmd)} failed: {exc}\n")
        raise CliError(
            error_code,
            f"{' '.join(cmd)} failed with {exc}",
            extra={"command": cmd, "error": str(exc)},
        ) from exc
    if _compat()._should_retry_gh_without_env(cmd, proc):
        writer(
            "[chain] gh auth failed with GH_TOKEN/GITHUB_TOKEN present; "
            "retrying with gh env tokens cleared\n"
        )
        try:
            proc = _compat().subprocess.run(
                cmd,
                cwd=str(root),
                env=_compat()._command_env(cmd),
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout,
            )
        except (_compat().subprocess.TimeoutExpired, FileNotFoundError) as exc:
            writer(f"[chain] {' '.join(cmd)} failed: {exc}\n")
            raise CliError(
                error_code,
                f"{' '.join(cmd)} failed with {exc}",
                extra={"command": cmd, "error": str(exc)},
            ) from exc
    writer(f"[chain] {' '.join(cmd)} -> rc={proc.returncode}\n")
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        if detail:
            writer(f"[chain] {' '.join(cmd)} output:\n{detail}\n")
        raise CliError(
            error_code,
            f"{' '.join(cmd)} exited {proc.returncode}",
            extra={
                "command": cmd,
                "returncode": proc.returncode,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
            },
        )
    return proc


def _should_retry_gh_without_env(cmd: list[str], proc: subprocess.CompletedProcess[str]) -> bool:
    if not cmd or cmd[0] != "gh" or proc.returncode == 0:
        return False
    if "GH_TOKEN" not in os.environ and "GITHUB_TOKEN" not in os.environ:
        return False
    combined = f"{proc.stdout or ''}\n{proc.stderr or ''}".lower()
    return any(
        marker in combined
        for marker in (
            "bad credentials",
            "authentication failed",
            "invalid token",
            "requires authentication",
            "http 401",
            "status code 401",
        )
    )


def _command_env(cmd: list[str]) -> dict[str, str] | None:
    """Return a subprocess env for commands whose auth can be poisoned by env.

    gh gives GH_TOKEN/GITHUB_TOKEN precedence over the logged-in keychain auth.
    In long agent sessions those variables are often stale or scoped for a
    different identity, so chain-managed gh calls should prefer gh's own auth.
    """
    if not cmd or cmd[0] != "gh":
        return None
    env = os.environ.copy()
    env.pop("GH_TOKEN", None)
    env.pop("GITHUB_TOKEN", None)
    return env


def _remote_branch_exists(root: Path, branch: str, *, writer) -> bool:
    proc = _compat().subprocess.run(
        ["git", "ls-remote", "--exit-code", "--heads", "origin", branch],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    writer(f"[chain] git ls-remote --heads origin {branch} -> rc={proc.returncode}\n")
    if proc.returncode == 0:
        return True
    if proc.returncode == 2:
        return False
    detail = (proc.stderr or proc.stdout or "").strip()
    raise CliError(
        "git_branch_lookup_failed",
        f"git ls-remote --heads origin {branch} exited {proc.returncode}: {detail}",
        extra={"returncode": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr},
    )


def _clean_worktree_for_chain(root: Path, writer) -> None:
    """Reset tracked changes and remove megaplan-generated untracked files.

    Chain execution re-creates .megaplan metadata each phase; stale working-tree
    changes from a previous run (modified schemas, deleted events.jsonl files,
    telemetry dumps, lock files) would otherwise block branch checkouts.
    """
    writer("[chain] cleaning worktree for automated branch checkout\n")
    _compat()._run_command(
        root,
        ["git", "reset", "--hard", "HEAD"],
        writer=writer,
        error_code="git_clean_failed",
    )
    # Remove stale untracked source/output files while preserving megaplan plan
    # state (which lives under .megaplan and may be needed across phases).
    _compat()._run_command(
        root,
        ["git", "clean", "-fd", "-e", ".megaplan"],
        writer=writer,
        error_code="git_clean_failed",
    )
    for subdir in ("epics", "schemas", "telemetry", ".state-locks"):
        path = root / ".megaplan" / subdir
        if path.exists():
            _compat()._run_command(
                root,
                ["git", "clean", "-fd", str(path.relative_to(root))],
                writer=writer,
                error_code="git_clean_failed",
            )


def _checkout_milestone_branch(
    root: Path,
    branch: str,
    *,
    base_branch: str,
    writer,
    from_origin: bool = False,
) -> None:
    """Create or resume the milestone branch and push it to origin.

    When ``from_origin`` is True, a new milestone branch forks from
    ``origin/<base_branch>`` so it includes prior squash-merged milestone PRs.
    Local ``<base_branch>`` can be stale in that workflow because the squash
    merge creates a fresh commit only on the remote base branch.
    """
    if _compat()._remote_branch_exists(root, branch, writer=writer):
        _clean_worktree_for_chain(root, writer)
        _compat()._run_command(root, ["git", "fetch", "origin", branch], writer=writer, error_code="git_branch_failed")
        _compat()._run_command(
            root,
            ["git", "checkout", "-B", branch, f"origin/{branch}"],
            writer=writer,
            error_code="git_branch_failed",
        )
        return
    _clean_worktree_for_chain(root, writer)
    fork_point = base_branch
    if from_origin:
        fetch = _compat().subprocess.run(
            ["git", "fetch", "origin", base_branch],
            cwd=str(root),
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
        writer(f"[chain] git fetch origin {base_branch} -> rc={fetch.returncode}\n")
        if fetch.returncode == 0:
            fork_point = f"origin/{base_branch}"
            writer(
                f"[chain] forking {branch} from {fork_point} "
                "(authoritative merged history)\n"
            )
        else:
            detail = (fetch.stderr or fetch.stdout or "").strip()
            writer(
                f"[chain] fetch failed; forking {branch} from local "
                f"{base_branch}{(': ' + detail) if detail else ''}\n"
            )
    _compat()._run_command(root, ["git", "checkout", "-B", branch, fork_point], writer=writer, error_code="git_branch_failed")
    _compat()._run_command(root, ["git", "push", "--no-verify", "-u", "origin", branch], writer=writer, error_code="git_push_failed")


def _parse_pr_number_from_url(output: str) -> int | None:
    match = re.search(r"/pull/(\d+)", output)
    return int(match.group(1)) if match else None


def _list_open_pr_for_branch(root: Path, branch: str, *, writer) -> dict[str, Any] | None:
    proc = _compat()._run_command(
        root,
        ["gh", "pr", "list", "--head", branch, "--state", "open", "--json", "number,state"],
        writer=writer,
        timeout=120,
        error_code="gh_pr_lookup_failed",
    )
    try:
        payload = json.loads(proc.stdout or "[]")
    except json.JSONDecodeError as exc:
        raise CliError("gh_pr_lookup_failed", f"gh pr list produced non-JSON output: {exc}") from exc
    if isinstance(payload, list) and payload:
        first = payload[0]
        return first if isinstance(first, dict) else None
    return None


--- FILE: arnold_pipelines/megaplan/chain/git_ops.py (1080,1320p) ---
            claimed_nested_repo_roots.add(repo.resolve().relative_to(root_abs).as_posix())
        except (OSError, ValueError):
            _compat()._warn_chain_fallback(
                "M3A_WARN_COMMIT_PUSH_PATH",
                reason="path_normalization",
                context={"repo": repo.as_posix()},
            )
            continue
    preexisting_unclaimed: list[Path] = []
    for path in preexisting_dirty_paths or []:
        try:
            rel = path.resolve().relative_to(root_abs).as_posix()
        except (OSError, ValueError):
            _compat()._warn_chain_fallback(
                "M3A_WARN_COMMIT_PUSH_PATH2",
                reason="path_normalization",
                context={"path": path.as_posix()},
            )
            continue
        if rel not in claimed_root_paths and rel not in claimed_nested_repo_roots:
            preexisting_unclaimed.append(path)
    # Only unstage *tracked* preexisting-unclaimed paths. Untracked files that
    # happen to share a path with preexisting dirt are typically new work
    # produced by the current plan; resetting them would drop them from the
    # milestone commit. Tracked preexisting changes are left unstaged so they
    # do not pollute the milestone diff.
    tracked_preexisting_unclaimed: list[Path] = []
    for path in preexisting_unclaimed:
        try:
            rel = path.resolve().relative_to(root_abs).as_posix()
        except (OSError, ValueError):
            continue
        tracked_check = _compat().subprocess.run(
            ["git", "ls-files", "--error-unmatch", "--", rel],
            cwd=str(root),
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
        if tracked_check.returncode == 0:
            tracked_preexisting_unclaimed.append(path)
    _compat()._reset_staged_paths(root, tracked_preexisting_unclaimed, writer=writer)
    staged = _compat().subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    if staged.returncode != 0 and staged.returncode != 1:
        raise CliError(
            "git_commit_failed",
            f"git diff --cached --quiet exited {staged.returncode}",
            extra={"stdout": staged.stdout, "stderr": staged.stderr},
        )
    nothing_staged = staged.returncode == 0
    message = f"megaplan: {plan} {phase}"
    # --no-verify: a programmatic milestone commit must not run the repo's
    # interactive pre-commit hooks. Those hooks are authored for human commits
    # and routinely fail for reasons unrelated to whether the milestone's code
    # should land — e.g. a worktree that shares the umbrella .git's hooks but has
    # intentionally removed the package the hook drives (the arnold migration
    # worktree tombstones `megaplan`, so the megaplan-regen pre-commit hook errors
    # and would block every milestone commit). The chain owns its own staging and
    # verification; hook side effects here are noise that turns a healthy
    # milestone into a hard chain stall.
    commit_argv = ["git", "commit", "--no-verify", "-m", message]
    if nothing_staged:
        if phase != "init":
            writer(f"[chain] no changes to commit after {phase}\n")
            return None
        # Anchor the milestone branch with an empty init commit so a draft PR
        # can be opened before any phase produces a real diff.
        commit_argv.insert(2, "--allow-empty")
    _compat()._run_command(root, commit_argv, writer=writer, error_code="git_commit_failed")
    return _git_stdout(root, ["git", "rev-parse", "HEAD"], error_code="git_commit_failed")


def _commit_and_push_phase(
    root: Path,
    branch: str,
    plan: str,
    phase: str,
    *,
    writer,
    preexisting_dirty_paths: list[Path] | None = None,
) -> None:
    """Commit any current diff and push the milestone branch."""
    committed_sha = _commit_phase(
        root, plan, phase, writer=writer, preexisting_dirty_paths=preexisting_dirty_paths
    )
    # Execution/output aggregation can append plan state (events.jsonl, lock
    # files) and preexisting-unclaimed untracked files can survive the first
    # commit. Stage and commit any remaining tracked or untracked changes so
    # the subsequent rebase/push sees a clean worktree and no milestone file
    # is left unpublished.
    # The cleanup commit intentionally does NOT reset preexisting-unclaimed
    # paths, so that plan-state files (chain-state.json, events.jsonl, etc.)
    # that were modified after the first commit are themselves committed and
    # the worktree is clean before rebase/push.
    _commit_phase(
        root,
        plan,
        f"{phase}-cleanup",
        writer=writer,
        preexisting_dirty_paths=[],
    )
    if committed_sha is None:
        # Nothing committed (and not an init anchor) — nothing to publish.
        return
    # Reconcile with origin so a resumed chain whose local branch diverged
    # from the remote milestone branch (e.g. reset to base) can still push.
    fetch = _compat().subprocess.run(
        ["git", "fetch", "origin", branch],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    writer(f"[chain] git fetch origin {branch} -> rc={fetch.returncode}\n")
    if fetch.returncode == 0:
        rebase = _compat().subprocess.run(
            ["git", "rebase", f"origin/{branch}"],
            cwd=str(root),
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
        writer(f"[chain] git rebase origin/{branch} -> rc={rebase.returncode}\n")
        if rebase.returncode != 0:
            detail = (rebase.stderr or rebase.stdout or "").strip()
            writer(
                f"[chain] rebase failed; aborting and falling back to force push"
                f"{(': ' + detail) if detail else ''}\n"
            )
            _compat()._run_command(
                root,
                ["git", "rebase", "--abort"],
                writer=writer,
                error_code="git_push_failed",
            )
            _compat()._run_command(
                root,
                ["git", "push", "--no-verify", "--force-with-lease", "origin", branch],
                writer=writer,
                error_code="git_push_failed",
            )
            return
    _compat()._run_command(root, ["git", "push", "--no-verify", "origin", branch], writer=writer, error_code="git_push_failed")


def _mark_pr_ready(root: Path, pr_number: int, *, writer) -> None:
    _compat()._run_command(root, ["gh", "pr", "ready", str(pr_number)], writer=writer, error_code="gh_pr_ready_failed")


def _enable_auto_merge(root: Path, pr_number: int, *, writer) -> str:
    def _dirty() -> bool:
        status = _compat().subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(root),
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
        return bool(status.stdout.strip())

    def _stash() -> bool:
        if not _dirty():
            return False
        _compat()._run_command(
            root,
            ["git", "stash", "push", "-u", "-m", "megaplan pre-merge cleanup"],
            writer=writer,
            error_code="git_stash_failed",
        )
        return True

    def _pop_stash() -> None:
        try:
            _compat()._run_command(
                root,
                ["git", "stash", "pop"],
                writer=writer,
                error_code="git_stash_failed",
            )
        except CliError:
            # If pop fails the working tree is at least clean for merge; the
            # chain can recompute state from disk. Log and move on.
            writer("[chain] stash pop failed; leaving stash for manual recovery\n")

    stash_created = False
    try:
        stash_created = _stash()
        try:
            _compat()._run_command(
                root,
                ["gh", "pr", "merge", str(pr_number), "--auto", "--squash", "--delete-branch"],
                writer=writer,
                timeout=120,
                error_code="gh_pr_merge_failed",
            )
            return "merged" if _compat()._pr_state(root, pr_number, writer=writer) == "merged" else "open"
        except CliError as exc:
            combined = f"{exc.message} {exc.extra.get('stdout', '')} {exc.extra.get('stderr', '')}"
            if "already checked out" in combined:
                # --delete-branch needs a local branch switch, which fails when the
                # chain runs in a git worktree whose base branch is checked out
                # elsewhere. Retry without local branch deletion (remote branch is
                # cleaned up by GitHub's delete-on-merge or left for manual GC).
                writer("[chain] --delete-branch impossible from worktree; retrying auto-merge without it\n")
                _compat()._run_command(
                    root,
                    ["gh", "pr", "merge", str(pr_number), "--auto", "--squash"],
                    writer=writer,
                    timeout=120,
                    error_code="gh_pr_merge_failed",
                )
                return "merged" if _compat()._pr_state(root, pr_number, writer=writer) == "merged" else "open"
            if "Auto merge is not allowed" not in combined:
                raise
            writer("[chain] auto-merge unavailable; falling back to immediate squash merge\n")
        finally:
            if stash_created:
                _pop_stash()
        _compat()._run_command(
            root,
            ["gh", "pr", "merge", str(pr_number), "--squash", "--delete-branch"],
            writer=writer,
            timeout=120,
            error_code="gh_pr_merge_failed",
        )
        return "merged"
    finally:
        # Ensure stash is restored even if the immediate squash merge path above
        # raised before the inner finally could run.
        if stash_created and _compat().subprocess.run(

--- FILE: arnold_pipelines/megaplan/chain/__init__.py (1590,1665p) ---
        )
    chain_spec.save_chain_state(spec_path, state)
    preexisting_dirty_paths = _dirty_worktree_paths(root)
    push_enabled = not no_push and os.environ.get("MEGAPLAN_CHAIN_NO_PUSH") not in {"1", "true", "TRUE", "yes", "YES"}

    events: list[dict[str, Any]] = []

    def log(msg: str, **fields: Any) -> None:
        events.append({"msg": msg, **fields})
        writer(f"[chain] {msg}\n")

    # ---- Seed phase ----
    if spec.seed_plan and state.current_milestone_index < 0:
        seed_state = _plan_state(root, spec.seed_plan, timeout=spec.status_timeout)
        log(f"seed plan {spec.seed_plan} state={seed_state}")
        if seed_state not in TERMINAL_SKIP_STATES:
            state.current_plan_name = spec.seed_plan
            chain_spec.save_chain_state(spec_path, state)
            outcome = _drive_plan_with_blocked_execute_recovery(
                root,
                spec.seed_plan,
                spec,
                writer=writer,
            )
            state.last_state = outcome.status
            chain_spec.save_chain_state(spec_path, state)
            decision = _handle_outcome(outcome, spec=spec, writer=writer, root=root)
            if decision == "authority_blocked":
                state.last_state = "authority_divergence"
                chain_spec.save_chain_state(spec_path, state)
                return _result(
                    "blocked",
                    state,
                    events,
                    spec=spec,
                    reason=f"seed plan terminal outcome lacks authority",
                )
            if decision == "stop":
                return _result("stopped", state, events, spec=spec, reason=f"seed plan {outcome.status}")
            if decision == "retry":
                # Recursive retry kept simple: re-drive seed once.
                outcome = _drive_plan_with_blocked_execute_recovery(
                    root,
                    spec.seed_plan,
                    spec,
                    writer=writer,
                )
                state.last_state = outcome.status
                chain_spec.save_chain_state(spec_path, state)
                if outcome.status != "done":
                    return _result("stopped", state, events, spec=spec, reason="seed retry failed")
                authoritative, reason = _plan_terminal_completion_is_authoritative(
                    root, spec.seed_plan
                )
                if not authoritative:
                    writer(
                        f"[chain] seed retry {spec.seed_plan} outcome=done lacks authority; "
                        f"stopping: {reason}\n"
                    )
                    state.last_state = "authority_divergence"
                    chain_spec.save_chain_state(spec_path, state)
                    return _result(
                        "blocked",
                        state,
                        events,
                        spec=spec,
                        reason=f"seed retry terminal outcome lacks authority: {reason}",
                    )
            # skip / advance both proceed to milestones
        else:
            authoritative, reason = _plan_terminal_completion_is_authoritative(
                root, spec.seed_plan
            )
            if not authoritative:
                writer(
                    f"[chain] seed plan {spec.seed_plan} terminal state={seed_state} "

--- FILE: arnold_pipelines/megaplan/chain/__init__.py (2100,2325p) ---
            result = full_suite_backstop_gate.get("result")
            if isinstance(result, dict):
                if _persist_full_suite_backstop_baseline(
                    spec_path,
                    result,
                    captured_at_sha=_current_head_sha(root),
                    milestone_label=milestone.label,
                ):
                    log(
                        "full_suite_backstop baseline updated "
                        f"milestone={milestone.label}"
                    )
        # advance or skip
        completed_record = {
            "label": milestone.label,
            "plan": plan_name,
            "status": outcome.status,
            "pr_number": state.pr_number,
            "pr_state": state.pr_state,
        }
        if local_commit_sha is not None:
            completed_record["local_commit_sha"] = local_commit_sha
            completed_record["plan_branch"] = spec.base_branch
        if full_suite_backstop_summary is not None:
            completed_record["full_suite_backstop"] = full_suite_backstop_summary
        state.completed.append(completed_record)
        idx += 1
        state.current_milestone_index = idx
        state.current_plan_name = None
        state.pr_number = None
        state.pr_state = None
        chain_spec.save_chain_state(spec_path, state)
        if one:
            log(f"paused after milestone {milestone.label}")
            return _result(
                "paused",
                state,
                events,
                spec=spec,
                reason=f"completed one milestone: {milestone.label}",
            )

    log("all milestones complete")
    return _result("done", state, events, spec=spec)


def _result(
    status: str, state: ChainState, events: list[dict[str, Any]], *, spec: ChainSpec | None = None, reason: str = ""
) -> dict[str, Any]:
    result = {
        "status": status,
        "reason": reason,
        "chain_state": state.to_dict(),
        "events": events,
    }
    if spec is not None:
        result["base_branch"] = spec.base_branch
    return result


def format_chain_status(spec: ChainSpec, state: ChainState) -> dict[str, Any]:
    completed_labels = {
        entry.get("label")
        for entry in state.completed
        if isinstance(entry, dict) and isinstance(entry.get("label"), str)
    }
    current_milestone: dict[str, Any] | None = None
    if 0 <= state.current_milestone_index < len(spec.milestones):
        milestone = spec.milestones[state.current_milestone_index]
        current_milestone = {
            "label": milestone.label,
            "index": state.current_milestone_index,
        }
        if milestone.branch:
            current_milestone["branch"] = milestone.branch

    per_milestone: list[dict[str, Any]] = []
    completed: list[dict[str, Any]] = []
    remaining: list[dict[str, Any]] = []
    for index, milestone in enumerate(spec.milestones):
        if milestone.label in completed_labels:
            status = "completed"
        elif index == state.current_milestone_index and state.current_plan_name:
            status = "in_progress"
        else:
            status = "pending"
        entry = {"label": milestone.label, "index": index, "status": status}
        per_milestone.append(entry)
        if status == "completed":
            completed.append({"label": milestone.label, "index": index})
        else:
            remaining.append({"label": milestone.label, "index": index})

    sync: dict[str, Any] = {
        "branch_head": state.branch_head,
        "pr_head": state.pr_head,
        "last_pushed_commit": state.last_pushed_commit,
        "dirty_flag": state.dirty_flag,
        "sync_state": state.sync_state,
    }
    summary = {
        "current_milestone": current_milestone,
        "completed": completed,
        "remaining": remaining,
        "per_milestone": per_milestone,
        "seed_plan": spec.seed_plan,
        "base_branch": spec.base_branch,
        "current_plan_name": state.current_plan_name,
        "last_state": state.last_state,
        "sync": sync,
        "policy": {
            "prerequisite_policy": spec.prerequisite_policy,
            "validation_policy": spec.validation_policy,
            "review_policy": dict(spec.review_policy or {}),
        },
    }
    if state.pr_number is not None:
        summary["pr_number"] = state.pr_number
        summary["pr_state"] = state.pr_state
    return summary


def _write_chain_status_pretty(summary: dict[str, Any], *, writer) -> None:
    current = summary.get("current_milestone")
    current_label = "none"
    if isinstance(current, dict):
        current_label = f"{current['label']} (index {current['index']})"
    completed = summary.get("completed") or []
    remaining = summary.get("remaining") or []
    completed_labels = ", ".join(item["label"] for item in completed) if completed else "none"
    remaining_labels = ", ".join(item["label"] for item in remaining) if remaining else "none"
    writer(f"Current milestone: {current_label}\n")
    writer(f"Completed: {completed_labels}\n")
    writer(f"Remaining: {remaining_labels}\n")
    if summary.get("seed_plan"):
        writer(f"Seed plan: {summary['seed_plan']}\n")
    writer(f"Base branch: {summary.get('base_branch') or 'main'}\n")
    if summary.get("current_plan_name"):
        writer(f"Current plan: {summary['current_plan_name']}\n")
    if summary.get("last_state"):
        writer(f"Last state: {summary['last_state']}\n")
    if summary.get("pr_number"):
        writer(f"Current PR: #{summary['pr_number']} ({summary.get('pr_state') or 'unknown'})\n")
    # Sync section (branch/PR sync state)
    sync = summary.get("sync") or {}
    if any(v is not None for v in sync.values()) or sync.get("dirty_flag"):
        writer("Sync:\n")
        if sync.get("branch_head"):
            writer(f"  Branch head: {sync['branch_head']}\n")
        if sync.get("pr_head"):
            writer(f"  PR head: {sync['pr_head']}\n")
        if sync.get("last_pushed_commit"):
            writer(f"  Last pushed: {sync['last_pushed_commit']}\n")
        if sync.get("dirty_flag"):
            writer("  Dirty: yes\n")
        if sync.get("sync_state"):
            writer(f"  Sync state: {sync['sync_state']}\n")
    # Policy section (chain-level policies)
    policy = summary.get("policy") or {}
    if policy:
        writer("Policy:\n")
        writer(f"  Prerequisite: {policy.get('prerequisite_policy', 'none')}\n")
        writer(f"  Validation: {policy.get('validation_policy', 'none')}\n")
        review_policy = policy.get("review_policy") or {}
        writer(f"  Review (clean_milestone_pr): {review_policy.get('clean_milestone_pr', 'auto')}\n")
    writer("Per-milestone:\n")
    for item in summary.get("per_milestone") or []:
        writer(f"  - [{item['status']}] {item['label']} (index {item['index']})\n")


# ---------------------------------------------------------------------------
# CLI plumbing
# ---------------------------------------------------------------------------


def build_chain_parser(subparsers: Any) -> None:
    chain_parser = subparsers.add_parser(
        "chain",
        help="Drive a pipeline of milestone plans described by a YAML spec",
    )
    chain_sub = chain_parser.add_subparsers(dest="chain_action")
    # No action == run. `start` is the explicit spelling, kept in sync with the
    # backcompat top-level alias.
    chain_parser.add_argument(
        "--spec",
        required=False,
        help="Path to the chain spec YAML (required at top-level or on subcommands)",
    )
    chain_parser.add_argument(
        "--project-dir",
        required=False,
        help="Run the chain against this project directory instead of discovering from CWD.",
    )
    _add_chain_worktree_args(chain_parser)
    chain_parser.add_argument(
        "--no-git-refresh",
        action="store_true",
        help=(
            "Skip the automatic base-branch checkout and pull that runs "
            "before each milestone. Use this on developer checkouts where "
            "you do not want chain to stomp on the currently checked-out "
            "branch. Default: refresh enabled (preserves CI/orchestrator "
            "behavior)."
        ),
    )
    chain_parser.add_argument(
        "--no-push",
        action="store_true",
        help=(
            "Disable milestone branch creation, PR creation, commits, and pushes. "
            "Also enabled by MEGAPLAN_CHAIN_NO_PUSH=1; intended for local/no-network tests."
        ),
    )
    chain_parser.add_argument(
        "--one",
        action="store_true",
        help="Drive at most one pending milestone, persist progress, then stop cleanly.",
    )

    start_parser = chain_sub.add_parser("start", help="Drive a chain spec")
    start_parser.add_argument("--spec", required=True, help="Path to the chain spec YAML")
    start_parser.add_argument(
        "--project-dir",
        required=False,
        help="Run the chain against this project directory instead of discovering from CWD.",
    )
