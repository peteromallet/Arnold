You are a DeepSeek subagent doing a read-only inventory for AgentBox. The user asked us to find EVERYTHING existing in this repo/local skills that overlaps with the desired Discord-first AgentBox: start tickets/epics/megaplans/chains from Discord, Guardian repairs/relaunches blocked runs, completed work gets pushed/PRd/consolidated, and DeepSeek/subagents can be used. The brief embeds local excerpts. Return a decisive inventory of reusable mechanics, with file refs, gaps, and concrete recommendations. Under 1200 words. Focus: Discord-first user journey, resident runtime, auth, confirmations, messaging, how a user message becomes an agent/tool action.


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

--- FILE: arnold_pipelines/megaplan/resident/discord.py (1,220p) ---
"""Discord adapter boundary for resident Megaplan conversations."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
import os
from typing import Any

from .auth import AuthorizationSubject
from .runtime import InboundEvent, OutboundMessage, OutboundSink, ResidentRuntime

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class DiscordDeliveryTarget:
    guild_id: str | None
    channel_id: str
    thread_id: str | None = None
    dm_user_id: str | None = None

    @property
    def conversation_key(self) -> str:
        if self.dm_user_id:
            return f"discord:dm:{self.dm_user_id}"
        thread_part = f":thread:{self.thread_id}" if self.thread_id else ""
        return f"discord:guild:{self.guild_id}:channel:{self.channel_id}{thread_part}"

    @classmethod
    def from_conversation_key(cls, conversation_key: str) -> "DiscordDeliveryTarget":
        parts = [part for part in conversation_key.split(":") if part]
        if parts[:2] == ["discord", "dm"] and len(parts) == 3:
            return cls(guild_id=None, channel_id=parts[2], dm_user_id=parts[2])
        if parts[:2] == ["discord", "guild"] and len(parts) >= 5 and parts[3] == "channel":
            thread_id = parts[6] if len(parts) >= 7 and parts[5] == "thread" else None
            return cls(guild_id=parts[2], channel_id=parts[4], thread_id=thread_id)
        raise ValueError(f"Unsupported Discord conversation key: {conversation_key}")


@dataclass(frozen=True)
class DiscordInboundMessage:
    message_id: str
    author_id: str
    target: DiscordDeliveryTarget
    content: str

    @classmethod
    def from_discord_message(cls, message: Any) -> "DiscordInboundMessage":
        channel = message.channel
        guild = getattr(message, "guild", None)
        author = getattr(message, "author", None)
        guild_id = _optional_snowflake(getattr(guild, "id", None))
        author_id = _optional_snowflake(getattr(author, "id", None))
        channel_id = _optional_snowflake(getattr(channel, "id", None))
        thread_id = None
        dm_user_id = None
        parent = getattr(channel, "parent", None)
        if parent is not None and _optional_snowflake(getattr(parent, "id", None)):
            thread_id = channel_id
            channel_id = _optional_snowflake(getattr(parent, "id", None))
        if guild_id is None:
            dm_user_id = author_id
        if not author_id:
            raise ValueError("Discord message author has no stable id")
        if not channel_id:
            raise ValueError("Discord message channel has no stable id")
        return cls(
            message_id=str(message.id),
            author_id=author_id,
            target=DiscordDeliveryTarget(
                guild_id=guild_id,
                channel_id=channel_id,
                thread_id=thread_id,
                dm_user_id=dm_user_id,
            ),
            content=str(getattr(message, "content", "")),
        )

    def to_inbound_event(self) -> InboundEvent:
        return InboundEvent(
            idempotency_key=f"discord:message:{self.message_id}",
            conversation_key=self.target.conversation_key,
            subject=AuthorizationSubject(
                user_id=self.author_id,
                guild_id=self.target.guild_id,
                channel_id=self.target.channel_id,
            ),
            content=self.content,
            raw={
                "discord_message_id": self.message_id,
                "thread_id": self.target.thread_id,
                "dm_user_id": self.target.dm_user_id,
            },
        )


class DiscordOutboundSink(OutboundSink):
    """Deliver resident outbound messages to Discord using durable targets."""

    def __init__(self, client: Any | None = None) -> None:
        self.client = client

    def bind_client(self, client: Any) -> None:
        self.client = client

    async def send(self, message: OutboundMessage) -> None:
        if self.client is None:
            raise RuntimeError("Discord client is not bound")
        target = DiscordDeliveryTarget.from_conversation_key(message.conversation_key)
        channel = await self._resolve_channel(target)
        sent = await channel.send(message.content)
        if isinstance(message.metadata, dict):
            message.metadata["discord_message_id"] = str(getattr(sent, "id", ""))

    async def _resolve_channel(self, target: DiscordDeliveryTarget) -> Any:
        if target.dm_user_id:
            user = self.client.get_user(int(target.dm_user_id)) or await self.client.fetch_user(int(target.dm_user_id))
            return user.dm_channel or await user.create_dm()
        channel_id = int(target.thread_id or target.channel_id)
        channel = self.client.get_channel(channel_id)
        if channel is None:
            channel = await self.client.fetch_channel(channel_id)
        return channel


class ResidentDiscordService:
    """Thin discord.py service that feeds Discord events into ResidentRuntime."""

    def __init__(self, *, runtime: ResidentRuntime, token: str) -> None:
        if not token:
            raise ValueError("Discord token is required")
        self.runtime = runtime
        self.token = token

    async def start(self) -> None:
        try:
            import discord
        except ImportError as exc:
            raise RuntimeError("discord.py is required for `megaplan resident discord`") from exc

        logging.basicConfig(level=os.environ.get("MEGAPLAN_LOG_LEVEL", "INFO").upper())
        intents = discord.Intents.default()
        intents.message_content = True
        client = discord.Client(intents=intents)

        @client.event
        async def on_ready() -> None:
            outbound = getattr(self.runtime, "outbound", None)
            if isinstance(outbound, DiscordOutboundSink):
                outbound.bind_client(client)
            recovered = await self.runtime.recover_abandoned_turns()
            user = getattr(client, "user", None)
            guilds = getattr(client, "guilds", ())
            LOGGER.info(
                "Resident Discord service ready user_id=%s guild_count=%s recovered_turns=%s",
                getattr(user, "id", None),
                len(guilds),
                recovered,
            )

        @client.event
        async def on_message(message: Any) -> None:
            if getattr(getattr(message, "author", None), "bot", False):
                return
            try:
                inbound = DiscordInboundMessage.from_discord_message(message)
                LOGGER.info(
                    "Resident Discord inbound message_id=%s author_id=%s conversation_key=%s content_length=%s",
                    inbound.message_id,
                    inbound.author_id,
                    inbound.target.conversation_key,
                    len(inbound.content),
                )
                await self.runtime.receive(inbound.to_inbound_event())
            except Exception:
                LOGGER.exception("Resident Discord message handling failed")

        @client.event
        async def on_error(event_method: str, *args: Any, **kwargs: Any) -> None:
            LOGGER.exception("Resident Discord client event failed: %s", event_method)

        await client.start(self.token)

    def run(self) -> None:
        asyncio.run(self.start())


def discord_token_from_env(env_name: str) -> str | None:
    token = os.environ.get(env_name)
    return token.strip() if token and token.strip() else None


def _optional_snowflake(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None

--- FILE: arnold_pipelines/megaplan/resident/cli.py (1,190p) ---
"""CLI entry points for resident Megaplan orchestration."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan.store import DBStore, FileStore, Store
from arnold_pipelines.megaplan.types import CliError

from .agent_loop import OpenAICompatibleAgentRunner
from .auth import StoreBackedConfirmationManager, ResidentAuthorizer
from .cloud import CloudCliBackend
from .config import ResidentConfig
from .discord import DiscordOutboundSink, ResidentDiscordService, discord_token_from_env
from .profile import MegaplanResidentProfile
from .runtime import ResidentRuntime
from .scheduler import make_store_scheduler


def _register_resident_subcommands(parser: argparse.ArgumentParser) -> None:
    sub = parser.add_subparsers(dest="resident_action", required=True)
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument("--store-root", help="Use a local FileStore root for resident state")
    shared.add_argument("--mode", choices=["dev", "production"], help="Override MEGAPLAN_RESIDENT_MODE")

    discord_parser = sub.add_parser("discord", parents=[shared], help="Start the resident Discord service")
    discord_parser.add_argument("--dry-run", action="store_true", help="Validate configuration without connecting to Discord")

    scheduler_parser = sub.add_parser("scheduler-once", parents=[shared], help="Claim and process due resident jobs once")
    scheduler_parser.add_argument("--worker-id", default="resident-cli-scheduler")

    health_parser = sub.add_parser("health", parents=[shared], help="Report resident orchestration health")
    health_parser.add_argument("--limit", type=int, default=10)


def run_resident_cli(root: Path, args: argparse.Namespace) -> dict[str, Any]:
    config = _resident_config(args)
    store = _resident_store(root, args)
    try:
        action = args.resident_action
        if action == "health":
            return _resident_health(store, config, limit=args.limit)
        if action == "scheduler-once":
            return asyncio.run(_resident_scheduler_once(store, config, worker_id=args.worker_id))
        if action == "discord":
            return _resident_discord(root, store, config, dry_run=args.dry_run)
    finally:
        close = getattr(store, "close", None)
        if callable(close):
            close()
    raise CliError("invalid_args", f"Unknown resident action: {getattr(args, 'resident_action', None)!r}")


def _resident_config(args: argparse.Namespace) -> ResidentConfig:
    config = ResidentConfig.from_env()
    mode = getattr(args, "mode", None)
    return config.model_copy(update={"mode": mode}) if mode else config


def _resident_store(root: Path, args: argparse.Namespace) -> Store:
    if getattr(args, "store_root", None):
        return FileStore(Path(args.store_root).expanduser().resolve())
    config = _resident_config(args)
    if config.is_production:
        return DBStore(actor_id="resident")
    return FileStore(root / ".megaplan" / "resident")


def _resident_health(store: Store, config: ResidentConfig, *, limit: int) -> dict[str, Any]:
    pending_jobs = store.list_scheduled_jobs(status="pending", limit=limit)
    claimed_jobs = store.list_scheduled_jobs(status="claimed", limit=limit)
    recent_runs = store.list_cloud_runs(limit=limit)
    conversations = store.list_resident_conversations(transport="discord", limit=limit)
    stale_control = store.list_stale_control_messages(
        older_than_seconds=int(config.stale_control_claim_timeout_s),
        limit=limit,
    )
    pending_confirmations = StoreBackedConfirmationManager(config, store).pending()
    abandoned_turns = [
        turn
        for turn in store.list_recent_turns(n=limit * 2)
        if turn.status == "abandoned"
    ][:limit]
    return {
        "success": True,
        "step": "resident",
        "action": "health",
        "mode": config.mode,
        "store": type(store).__name__,
        "scheduled_backlog": {
            "pending": len(pending_jobs),
            "claimed": len(claimed_jobs),
            "pending_jobs": [_model(row) for row in pending_jobs],
            "claimed_jobs": [_model(row) for row in claimed_jobs],
        },
        "resident_conversations": [_model(row) for row in conversations],
        "abandoned_turns": [_model(row) for row in abandoned_turns],
        "recent_cloud_runs": [_model(row) for row in recent_runs],
        "pending_cloud_confirmations": [_confirmation_model(row) for row in pending_confirmations[:limit]],
        "stale_control_messages": {
            "count": len(stale_control),
            "messages": [_model(row) for row in stale_control],
        },
    }


async def _resident_scheduler_once(store: Store, config: ResidentConfig, *, worker_id: str) -> dict[str, Any]:
    worker = make_store_scheduler(
        store=store,
        config=config,
        cloud_backend=CloudCliBackend(),
        outbound=None,
        confirmation_manager=StoreBackedConfirmationManager(config, store),
        worker_id=worker_id,
    )
    result = await worker.run_due_once()
    return {
        "success": True,
        "step": "resident",
        "action": "scheduler-once",
        "result": result.__dict__,
    }


def _resident_discord(root: Path, store: Store, config: ResidentConfig, *, dry_run: bool) -> dict[str, Any]:
    token = discord_token_from_env(config.discord_bot_token_env)
    if dry_run:
        return {
            "success": True,
            "step": "resident",
            "action": "discord",
            "dry_run": True,
            "token_configured": bool(token),
            "conversation_count": len(store.list_resident_conversations(transport="discord", limit=100)),
        }
    if token is None:
        raise CliError("missing_discord_token", f"{config.discord_bot_token_env} is required")
    authorizer = ResidentAuthorizer(config)
    outbound = DiscordOutboundSink()
    runtime = ResidentRuntime(
        config=config,
        authorizer=authorizer,
        store=store,
        profile=MegaplanResidentProfile(
            store=store,
            authorizer=authorizer,
            config=config,
            confirmation_manager=StoreBackedConfirmationManager(config, store),
            cloud_backend=CloudCliBackend(),
        ),
        runner=OpenAICompatibleAgentRunner(config),
        outbound=outbound,
    )
    service = ResidentDiscordService(runtime=runtime, token=token)
    service.run()
    return {"success": True, "step": "resident", "action": "discord", "stopped": True, "project_root": str(root)}


def _model(row: Any) -> dict[str, Any]:
    return row.model_dump(mode="json")


def _confirmation_model(row: Any) -> dict[str, Any]:
    return {
        "id": row.id,
        "action": row.action,
        "target_summary": row.target_summary,
        "expires_at": row.expires_at.isoformat().replace("+00:00", "Z"),
        "created_at": row.created_at.isoformat().replace("+00:00", "Z"),
        "subject": {
            "user_id": row.subject.user_id,
            "guild_id": row.subject.guild_id,
            "channel_id": row.subject.channel_id,
        },
        "metadata": row.metadata,
    }

--- FILE: arnold_pipelines/megaplan/resident/runtime.py (1,340p) ---
"""Reusable resident runtime seams for durable chat orchestration."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from arnold_pipelines.megaplan.schemas import Message, ProgressEvent, ResidentConversation, SystemLog
from arnold_pipelines.megaplan.store import ProgressEventInput, ResidentConversationInput, Store, deterministic_idempotency_key
from arnold_pipelines.megaplan.schemas.base import utc_now
from arnold_pipelines.megaplan.model_seam import render_step_message
from arnold_pipelines.megaplan.runtime.key_pool import resolve_model
from arnold.pipeline import StepInvocation

from .agent_loop import AgentRequest, AgentResponse, AgentRunner
from .auth import AuthorizationSubject, ResidentAuthorizer
from .coalescing import AsyncBurstCoalescer, BurstBatch
from .config import ResidentConfig
from .profile import MegaplanResidentProfile


@dataclass(frozen=True)
class InboundEvent:
    idempotency_key: str
    conversation_key: str
    subject: AuthorizationSubject
    content: str
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OutboundMessage:
    conversation_key: str
    content: str
    idempotency_key: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class OutboundSink(Protocol):
    async def send(self, message: OutboundMessage) -> None:
        """Deliver a resident response."""


class EmitProtocol(Protocol):
    """Resident event-write surface exposed by the shared Store emit path."""

    def log_system_event(
        self,
        *,
        level: str,
        category: str,
        event_type: str,
        message: str,
        details: dict[str, Any] | None = None,
        turn_id: str | None = None,
        epic_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> SystemLog:
        ...

    def append_progress_event(
        self,
        event: ProgressEventInput,
        *,
        idempotency_key: str | None = None,
    ) -> ProgressEvent:
        ...


@dataclass(frozen=True)
class PersistedInboundEvent:
    event: InboundEvent
    conversation: ResidentConversation
    message: Message


class ResidentRuntime:
    """Shared resident flow: authorize, coalesce, run profile, and emit output."""

    def __init__(
        self,
        *,
        config: ResidentConfig,
        authorizer: ResidentAuthorizer,
        store: Store,
        profile: MegaplanResidentProfile,
        runner: AgentRunner,
        outbound: OutboundSink,
    ) -> None:
        self.config = config
        self.authorizer = authorizer
        self.store = store
        self.emitter: EmitProtocol = store
        self.profile = profile
        self.runner = runner
        self.outbound = outbound
        self.coalescer: AsyncBurstCoalescer[str, PersistedInboundEvent] = AsyncBurstCoalescer(
            self._handle_batch,
            idle_delay_s=config.burst_idle_delay_s,
            max_delay_s=config.burst_max_delay_s,
        )

    async def receive(self, event: InboundEvent) -> None:
        decision = self.authorizer.authorize_inbound(event.subject)
        if not decision.allowed:
            if decision.audit is not None:
                self.emitter.log_system_event(
                    level="warn",
                    category="system",
                    event_type="resident_inbound_denied",
                    message="Resident inbound event denied before execution",
                    details={"reason": decision.reason, "audit": decision.audit},
                    idempotency_key=deterministic_idempotency_key("resident-denial", event.idempotency_key),
                )
            return
        persisted = self._persist_inbound_event(event)
        if persisted.message.bot_turn_id is not None:
            return
        await self.coalescer.submit(persisted.conversation.id, persisted)

    async def recover_abandoned_turns(self) -> int:
        recovered = 0
        for turn in self.store.find_abandoned_turns(int(self.config.stale_turn_timeout_s)):
            self.store.update_turn(
                turn.id,
                status="abandoned",
                warnings_issued=list(turn.warnings_issued or []) + ["recovered as abandoned on resident startup"],
                idempotency_key=deterministic_idempotency_key("resident-turn-abandoned", turn.id),
            )
            recovered += 1
        return recovered

    def _persist_inbound_event(self, event: InboundEvent) -> PersistedInboundEvent:
        raw = dict(event.raw)
        conversation = self.store.upsert_resident_conversation(
            ResidentConversationInput(
                transport="discord",
                conversation_key=event.conversation_key,
                active_epic_id=_optional_string(raw.get("active_epic_id")),
                guild_id=event.subject.guild_id,
                channel_id=event.subject.channel_id,
                thread_id=_optional_string(raw.get("thread_id")),
                dm_user_id=_optional_string(raw.get("dm_user_id")),
                metadata={"last_subject_user_id": event.subject.user_id, **dict(raw.get("conversation_metadata") or {})},
            ),
            idempotency_key=deterministic_idempotency_key("resident-conversation", event.conversation_key),
        )
        message = self.store.create_message(
            epic_id=conversation.active_epic_id,
            conversation_id=conversation.id,
            direction="inbound",
            content=event.content,
            discord_message_id=_optional_string(raw.get("discord_message_id")),
            idempotency_key=event.idempotency_key,
            has_code_attachment=bool(raw.get("has_code_attachment", False)),
            has_image_attachment=bool(raw.get("has_image_attachment", False)),
            was_voice_message=bool(raw.get("was_voice_message", False)),
            audio_storage_url=_optional_string(raw.get("audio_storage_url")),
            transcription_metadata=_optional_dict(raw.get("transcription_metadata")),
        )
        self.store.update_resident_conversation(
            conversation.id,
            last_inbound_message_id=message.id,
            delivery_cursor=message.id,
            last_active_at=utc_now(),
            idempotency_key=deterministic_idempotency_key("resident-conversation-inbound", conversation.id, message.id),
        )
        conversation = self.store.load_resident_conversation(conversation.id) or conversation
        return PersistedInboundEvent(event=event, conversation=conversation, message=message)

    async def _handle_batch(self, batch: BurstBatch[str, PersistedInboundEvent]) -> None:
        items = _dedupe_persisted_events(batch.items)
        if not items:
            return
        conversation = self.store.load_resident_conversation(batch.key) or items[-1].conversation
        active_epic_id = conversation.active_epic_id
        system_prompt = self.profile.system_prompt()
        hot_context = await self.profile.load_hot_context(conversation.id)
        message_ids = [item.message.id for item in items]
        turn = self.store.create_turn(
            epic_id=active_epic_id,
            triggered_by_message_ids=message_ids,
            prompt_snapshot={
                "system_prompt": system_prompt,
                "message_count": len(items),
                "tool_catalog": self.profile.tools().as_schema_catalog(),
            },
            prompt_version=hot_context.get("prompt_version") if isinstance(hot_context, dict) else None,
            state_at_turn=hot_context,
            model_version=self.config.model_name,
            idempotency_key=deterministic_idempotency_key("resident-turn", conversation.id, *message_ids),
        )
        for item in items:
            self.store.update_message(
                item.message.id,
                bot_turn_id=turn.id,
                in_burst_with=[msg_id for msg_id in message_ids if msg_id != item.message.id] or None,
                idempotency_key=deterministic_idempotency_key("resident-message-turn", item.message.id, turn.id),
            )
        model_seam_metadata = self._model_seam_metadata(
            conversation_id=conversation.id,
            messages=tuple({"role": "user", "content": item.event.content} for item in items),
            system_prompt=system_prompt,
            hot_context=hot_context,
        )
        request = AgentRequest(
            conversation_id=conversation.id,
            messages=tuple({"role": "user", "content": item.event.content} for item in items),
            system_prompt=system_prompt,
            hot_context=hot_context,
            model_seam_metadata=model_seam_metadata,
        )
        try:
            response = await self.runner.run(request, self.profile.tools())
        except Exception as exc:
            self.store.update_turn(
                turn.id,
                status="failed",
                warnings_issued=[f"{exc.__class__.__name__}: {exc}"],
                idempotency_key=deterministic_idempotency_key("resident-turn-failed", turn.id),
            )
            raise
        self._record_tool_calls(turn.id, response)
        final_message_id = None
        if response.final_text:
            outbound = self.store.create_message(
                epic_id=active_epic_id,
                conversation_id=conversation.id,
                direction="outbound",
                content=response.final_text,
                bot_turn_id=turn.id,
                idempotency_key=deterministic_idempotency_key("resident-outbound", turn.id, "final"),
            )
            final_message_id = outbound.id
            await self.outbound.send(
                OutboundMessage(
                    conversation_key=conversation.conversation_key,
                    content=response.final_text,
                    idempotency_key=outbound.idempotency_key,
                    metadata={"conversation_id": conversation.id, "message_id": outbound.id, "turn_id": turn.id},
                )
            )
            self.store.update_resident_conversation(
                conversation.id,
                last_outbound_message_id=outbound.id,
                delivery_cursor=outbound.id,
                last_active_at=utc_now(),
                idempotency_key=deterministic_idempotency_key("resident-conversation-outbound", conversation.id, outbound.id),
            )
        self.store.update_turn(
            turn.id,
            status="completed",
            final_output_message_id=final_message_id,
            message_sent=bool(final_message_id),
            idempotency_key=deterministic_idempotency_key("resident-turn-completed", turn.id),
        )

    def _record_tool_calls(self, turn_id: str, response: AgentResponse) -> None:
        for record in response.tool_calls:
            self.store.record_tool_call(
                turn_id=turn_id,
                tool_name=record.tool_name,
                operation_kind=record.operation_kind,
                arguments=record.arguments,
                result=record.result,
                duration_ms=record.duration_ms,
                idempotency_key=deterministic_idempotency_key("resident-tool-call", turn_id, record.id),
            )

    def _model_seam_metadata(
        self,
        *,
        conversation_id: str,
        messages: tuple[dict[str, Any], ...],
        system_prompt: str,
        hot_context: dict[str, Any],
    ) -> dict[str, Any]:
        try:
            normalized_model, agent_kwargs = resolve_model(self.config.model_name)
        except Exception:
            if ":" in self.config.model_name:
                raise
            normalized_model, agent_kwargs = self.config.model_name, {}
        rendered = render_step_message(
            StepInvocation(
                kind="model",
                metadata={
                    "tier": "non_enforced",
                    "worker": "resident",
                    "model": normalized_model,
                    "normalized_model": normalized_model,
                    "system": system_prompt,
                    "messages": messages,
                    "history": messages,
                    "hot_context": hot_context,
                    "prompt": "\n".join(str(message.get("content", "")) for message in messages),
                },
            )
        )
        return {
            "conversation_id": conversation_id,
            "validation_step": "resident",
            "tier": "non_enforced",
            "model": normalized_model,
            "normalized_model": normalized_model,
            "agent_kwargs": agent_kwargs,
            "rendered": rendered.to_json(),
        }


def _dedupe_persisted_events(items: Sequence[PersistedInboundEvent]) -> tuple[PersistedInboundEvent, ...]:
    seen: set[str] = set()
    deduped: list[PersistedInboundEvent] = []
    for item in items:
        if item.message.id in seen:
            continue
        seen.add(item.message.id)
        deduped.append(item)
    return tuple(deduped)


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _optional_dict(value: object) -> dict[str, Any] | None:
    return dict(value) if isinstance(value, dict) else None

--- FILE: arnold_pipelines/megaplan/resident/auth.py (1,260p) ---
"""Authorization primitives for resident inbound events and tool actions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import hashlib
import secrets
from typing import Any, Literal

from arnold_pipelines.megaplan.store.base import JSONDict, ScheduledJobInput, Store, deterministic_idempotency_key

from .config import ResidentConfig

ActionKind = Literal[
    "read",
    "write",
    "cloud_start",
    "cloud_read",
    "admin",
    "repo_write",
    "artifact_write",
    "export",
    "archive_logs",
    "reconcile_apply",
]
ConfirmationStatus = Literal["pending", "approved", "denied", "expired"]

HIGH_IMPACT_ACTIONS: frozenset[ActionKind] = frozenset(
    {
        "cloud_start",
        "admin",
        "repo_write",
        "artifact_write",
        "export",
        "archive_logs",
        "reconcile_apply",
    }
)

CONFIRMED_HIGH_IMPACT_ACTIONS: frozenset[ActionKind] = frozenset(
    {
        "repo_write",
        "artifact_write",
        "export",
        "archive_logs",
        "reconcile_apply",
    }
)


@dataclass(frozen=True)
class AuthorizationSubject:
    user_id: str
    guild_id: str | None = None
    channel_id: str | None = None


@dataclass(frozen=True)
class AuthorizationDecision:
    allowed: bool
    reason: str | None = None
    audit: dict[str, object] | None = None


@dataclass(frozen=True)
class AuthorizationDenialRecord:
    user_id: str
    guild_id: str | None
    channel_id: str | None
    action: str
    reason: str
    occurred_at: datetime

    def redacted(self) -> JSONDict:
        return {
            "user_id": self.user_id,
            "guild_id": self.guild_id,
            "channel_id": self.channel_id,
            "action": self.action,
            "reason": self.reason,
            "occurred_at": self.occurred_at.isoformat().replace("+00:00", "Z"),
        }


@dataclass(frozen=True)
class ConfirmationRequest:
    id: str
    subject: AuthorizationSubject
    action: ActionKind
    target_summary: str
    exact_phrase: str
    expires_at: datetime
    metadata: JSONDict
    created_at: datetime


@dataclass(frozen=True)
class ConfirmationDecision:
    status: ConfirmationStatus
    allowed: bool
    request_id: str | None = None
    reason: str | None = None


class ResidentAuthorizer:
    """Allowlist-based authorization with admin checks for side effects."""

    def __init__(self, config: ResidentConfig) -> None:
        self.config = config
        self.denials: list[AuthorizationDenialRecord] = []

    def authorize_inbound(self, subject: AuthorizationSubject) -> AuthorizationDecision:
        if self.config.allowed_user_ids and subject.user_id not in self.config.allowed_user_ids:
            return self._deny(subject, "inbound", "user_not_allowed")
        if self.config.allowed_guild_ids and subject.guild_id not in self.config.allowed_guild_ids:
            return self._deny(subject, "inbound", "guild_not_allowed")
        if self.config.allowed_channel_ids and subject.channel_id not in self.config.allowed_channel_ids:
            return self._deny(subject, "inbound", "channel_not_allowed")
        return AuthorizationDecision(True)

    def authorize_action(self, subject: AuthorizationSubject, action: ActionKind) -> AuthorizationDecision:
        inbound = self.authorize_inbound(subject)
        if not inbound.allowed:
            return inbound
        if action in HIGH_IMPACT_ACTIONS and subject.user_id not in self.config.admin_user_ids:
            return self._deny(subject, action, "admin_required")
        return AuthorizationDecision(True)

    def _deny(self, subject: AuthorizationSubject, action: str, reason: str) -> AuthorizationDecision:
        denial = AuthorizationDenialRecord(
            user_id=subject.user_id,
            guild_id=subject.guild_id,
            channel_id=subject.channel_id,
            action=action,
            reason=reason,
            occurred_at=datetime.now(UTC),
        )
        self.denials.append(denial)
        return AuthorizationDecision(False, reason, audit=denial.redacted())


class ConfirmationManager:
    """Exact-phrase confirmation guard for high-impact resident actions."""

    def __init__(self, config: ResidentConfig) -> None:
        self.config = config
        self._pending: dict[str, ConfirmationRequest] = {}

    def required_for(self, action: ActionKind) -> bool:
        if action == "cloud_start":
            return self.config.require_cloud_start_confirmation
        return action in CONFIRMED_HIGH_IMPACT_ACTIONS

    def request_confirmation(
        self,
        *,
        subject: AuthorizationSubject,
        action: ActionKind,
        target_summary: str,
        metadata: JSONDict | None = None,
        now: datetime | None = None,
    ) -> ConfirmationRequest:
        created_at = _aware_now(now)
        seed = f"{subject.user_id}:{action}:{target_summary}:{created_at.isoformat()}:{secrets.token_hex(4)}"
        request_id = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]
        exact_phrase = f"confirm {action} {request_id}"
        if action == "cloud_start":
            exact_phrase = f"{exact_phrase} {target_summary}"
        request = ConfirmationRequest(
            id=request_id,
            subject=subject,
            action=action,
            target_summary=target_summary,
            exact_phrase=exact_phrase,
            expires_at=created_at + timedelta(seconds=self.config.confirmation_expiry_s),
            metadata=dict(metadata or {}),
            created_at=created_at,
        )
        self._pending[request.id] = request
        return request

    def confirm(
        self,
        *,
        request_id: str,
        subject: AuthorizationSubject,
        phrase: str,
        now: datetime | None = None,
    ) -> ConfirmationDecision:
        request = self._pending.get(request_id)
        if request is None:
            return ConfirmationDecision("denied", False, request_id=request_id, reason="confirmation_not_found")
        current = _aware_now(now)
        if request.expires_at <= current:
            self._pending.pop(request_id, None)
            return ConfirmationDecision("expired", False, request_id=request_id, reason="confirmation_expired")
        if request.subject.user_id != subject.user_id:
            return ConfirmationDecision("denied", False, request_id=request_id, reason="confirmation_user_mismatch")
        if phrase.strip() != request.exact_phrase:
            return ConfirmationDecision("denied", False, request_id=request_id, reason="confirmation_phrase_mismatch")
        self._pending.pop(request_id, None)
        return ConfirmationDecision("approved", True, request_id=request_id)

    def expire_due(self, *, now: datetime | None = None) -> list[ConfirmationRequest]:
        current = _aware_now(now)
        expired = [request for request in self._pending.values() if request.expires_at <= current]
        for request in expired:
            self._pending.pop(request.id, None)
        return sorted(expired, key=lambda request: (request.expires_at, request.id))

    def pending(self) -> tuple[ConfirmationRequest, ...]:
        return tuple(sorted(self._pending.values(), key=lambda request: (request.expires_at, request.id)))


class StoreBackedConfirmationManager(ConfirmationManager):
    """Confirmation manager that persists pending requests as scheduled jobs."""

    def __init__(self, config: ResidentConfig, store: Store) -> None:
        super().__init__(config)
        self.store = store

    def request_confirmation(
        self,
        *,
        subject: AuthorizationSubject,
        action: ActionKind,
        target_summary: str,
        metadata: JSONDict | None = None,
        now: datetime | None = None,
    ) -> ConfirmationRequest:
        request = super().request_confirmation(
            subject=subject,
            action=action,
            target_summary=target_summary,
            metadata=metadata,
            now=now,
        )
        self.store.create_scheduled_job(
            ScheduledJobInput(
                job_type="confirmation_expiry",
                payload={"confirmation": _confirmation_to_payload(request)},
                scheduled_for=request.expires_at,
                max_attempts=1,
            ),
            idempotency_key=deterministic_idempotency_key("resident-confirmation-request", request.id),
        )
        return request

    def confirm(
        self,
        *,
        request_id: str,
        subject: AuthorizationSubject,
        phrase: str,
        now: datetime | None = None,
    ) -> ConfirmationDecision:
        self._hydrate_request(request_id)
        decision = super().confirm(request_id=request_id, subject=subject, phrase=phrase, now=now)
        if decision.allowed:

--- FILE: arnold_pipelines/megaplan/resident/profile.py (1,260p) ---
"""Megaplan-specific resident bot profile and constrained tool surface."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import Field

from arnold_pipelines.megaplan.control import ControlTargetResolver
from arnold_pipelines.megaplan.editorial import body as editorial_body
from arnold_pipelines.megaplan.editorial import checklist as editorial_checklist
from arnold_pipelines.megaplan.editorial import gating as editorial_gating
from arnold_pipelines.megaplan.editorial import sprints as editorial_sprints
from arnold_pipelines.megaplan.store import (
    CloudRunInput,
    ControlMessageInput,
    ProgressEventInput,
    ScheduledJobInput,
    SprintItemInput,
    Store,
    deterministic_idempotency_key,
)
from arnold_pipelines.megaplan.store.export import collect_epic_export, write_epic_export_tar
from arnold_pipelines.megaplan.types import CliError

from .auth import ActionKind, AuthorizationSubject, ConfirmationManager, ResidentAuthorizer, StoreBackedConfirmationManager
from .cloud import (
    CloudCliBackend,
    CloudOperation,
    CloudToolBackend,
    CloudToolRequest,
    CloudToolResult,
    cloud_run_status_for_classification,
    progress_kind_for_classification,
)
from .config import ResidentConfig
from .tool_registry import ToolRegistration, ToolRegistry
from .tool_schemas import ToolInput, ToolResult

MEGAPLAN_RESIDENT_PROMPT_VERSION = "megaplan-resident-v1"


class ActorToolInput(ToolInput):
    actor_user_id: str | None = None
    guild_id: str | None = None
    channel_id: str | None = None


class CreateEpicInput(ActorToolInput):
    title: str
    goal: str
    body: str


class SelectEpicInput(ActorToolInput):
    conversation_id: str
    epic_id: str


class EpicInput(ActorToolInput):
    epic_id: str


class EditEpicBodyInput(EpicInput):
    body: str
    expected_revision: int | None = None


class AddChecklistItemsInput(EpicInput):
    items: list[str] = Field(min_length=1)


class UpdateChecklistItemInput(EpicInput):
    item_id: str
    content: str | None = None
    status: Literal["open", "done", "skipped", "superseded"] | None = None
    position: int | None = Field(default=None, gt=0)
    skip_reason: str | None = None
    superseded_by_item_id: str | None = None


class SprintItemSpec(ToolInput):
    content: str
    estimated_complexity: str = "medium"
    status: str = "open"
    source_section: str | None = None


class SprintSpec(ToolInput):
    sprint_id: str | None = None
    sprint_number: int = Field(gt=0)
    name: str
    goal: str
    target_weeks: int = Field(default=2, gt=0)
    expected_revision: int | None = None
    items: list[SprintItemSpec] = Field(default_factory=list)


class CreateOrUpdateSprintsInput(EpicInput):
    sprints: list[SprintSpec] = Field(min_length=1)


class QueueSprintsInput(EpicInput):
    ordered_sprint_ids: list[str] = Field(default_factory=list)
    pending: dict[str, str] = Field(default_factory=dict)


class TransitionEpicStateInput(EpicInput):
    target_state: Literal["shaping", "sprinting", "planned", "paused", "archived"]
    expected_revision: int | None = None
    force: bool = False


class ControlToolInput(ActorToolInput):
    conversation_id: str | None = None
    epic_id: str
    target_id: str
    project_root: str
    plan: str | None = None
    reason: str | None = None
    note: str | None = None
    auto_continue: bool = False
    confirmation_request_id: str | None = None
    confirmation_phrase: str | None = None


class CloudToolInput(ActorToolInput):
    conversation_id: str | None = None
    epic_id: str | None = None
    sprint_id: str | None = None
    plan_id: str | None = None
    cloud_run_id: str | None = None
    project_root: str = "."
    cloud_yaml: str | None = None
    codebase_id: str | None = None
    repo_url: str | None = None
    repo_branch: str | None = None
    repo_workspace: str | None = None


class CloudStatusInput(CloudToolInput):
    plan: str | None = None


class CloudStatusChainInput(CloudToolInput):
    remote_spec: str | None = None


class ConfirmedCloudToolInput(CloudToolInput):
    confirmation_request_id: str | None = None
    confirmation_phrase: str | None = None


class CloudStartChainInput(ConfirmedCloudToolInput):
    spec: str
    idea_dir: str | None = None


class CloudBootstrapInput(ConfirmedCloudToolInput):
    idea_file: str
    plan_name: str | None = None
    robustness: str = "standard"


class CloudResumeInput(ConfirmedCloudToolInput):
    plan: str | None = None


class CloudLogsInput(CloudToolInput):
    no_follow: bool = True


class ScheduleCloudCheckInput(CloudToolInput):
    interval_seconds: int = Field(default=60, gt=0)
    scheduled_for: datetime | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    max_attempts: int = Field(default=3, ge=1)


class CancelCloudCheckInput(ActorToolInput):
    scheduled_job_id: str


class ListCloudChecksInput(ActorToolInput):
    conversation_id: str | None = None
    cloud_run_id: str | None = None
    epic_id: str | None = None
    status: Literal["pending", "claimed", "fired", "cancelled", "failed"] | None = None
    limit: int = Field(default=10, gt=0, le=50)


class SearchMessagesInput(ActorToolInput):
    query: str = ""
    conversation_id: str | None = None
    epic_id: str | None = None
    limit: int = Field(default=10, gt=0, le=50)


class SearchEpicsInput(ActorToolInput):
    query: str = ""
    state: str | None = None
    limit: int = Field(default=10, gt=0, le=50)


class SearchPlansInput(ActorToolInput):
    query: str = ""
    epic_id: str | None = None
    sprint_id: str | None = None
    limit: int = Field(default=10, gt=0, le=50)


class SearchCodeArtifactsInput(ActorToolInput):
    query: str = ""
    codebase_id: str | None = None
    epic_id: str | None = None
    kind: str | None = None
    source: str | None = None
    file_path: str | None = None
    limit: int = Field(default=10, gt=0, le=50)


class ListCodebasesInput(ActorToolInput):
    scope: str | None = None
    group_name: str | None = None
    epic_id: str | None = None
    include_global: bool = True
    limit: int = Field(default=25, gt=0, le=100)


class RegisterCodebaseInput(ActorToolInput):
    owner: str
    name: str
    repo_url: str
    repo_workspace: str | None = None
    default_branch: str = "main"
    scope: Literal["global", "epic_specific"] = "global"
    group_name: str | None = None
    associated_epic_id: str | None = None
    notes: str | None = None
    confirmation_request_id: str | None = None
    confirmation_phrase: str | None = None


class ListReposInput(ListCodebasesInput):
    pass


class ReconcileEpicInput(EpicInput):
    apply: bool = False
    confirmation_request_id: str | None = None
    confirmation_phrase: str | None = None



--- FILE: arnold/agent/tools/send_message_tool.py (1,180p) ---
"""Send Message Tool -- cross-channel messaging via platform APIs.

Sends a message to a user or channel on any connected messaging platform
(Telegram, Discord, Slack). Supports listing available targets and resolving
human-friendly channel names to IDs. Works in both CLI and gateway contexts.
"""

import json
import logging
import os
import re
import ssl
import time

logger = logging.getLogger(__name__)

_TELEGRAM_TOPIC_TARGET_RE = re.compile(r"^\s*(-?\d+)(?::(\d+))?\s*$")
_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
_VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".3gp"}
_AUDIO_EXTS = {".ogg", ".opus", ".mp3", ".wav", ".m4a"}
_VOICE_EXTS = {".ogg", ".opus"}


SEND_MESSAGE_SCHEMA = {
    "name": "send_message",
    "description": (
        "Send a message to a connected messaging platform, or list available targets.\n\n"
        "IMPORTANT: When the user asks to send to a specific channel or person "
        "(not just a bare platform name), call send_message(action='list') FIRST to see "
        "available targets, then send to the correct one.\n"
        "If the user just says a platform name like 'send to telegram', send directly "
        "to the home channel without listing first."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["send", "list"],
                "description": "Action to perform. 'send' (default) sends a message. 'list' returns all available channels/contacts across connected platforms."
            },
            "target": {
                "type": "string",
                "description": "Delivery target. Format: 'platform' (uses home channel), 'platform:#channel-name', 'platform:chat_id', or Telegram topic 'telegram:chat_id:thread_id'. Examples: 'telegram', 'telegram:-1001234567890:17585', 'discord:#bot-home', 'slack:#engineering', 'signal:+15551234567'"
            },
            "message": {
                "type": "string",
                "description": "The message text to send"
            }
        },
        "required": []
    }
}


def send_message_tool(args, **kw):
    """Handle cross-channel send_message tool calls."""
    action = args.get("action", "send")

    if action == "list":
        return _handle_list()

    return _handle_send(args)


def _handle_list():
    """Return formatted list of available messaging targets."""
    try:
        from gateway.channel_directory import format_directory_for_display
        return json.dumps({"targets": format_directory_for_display()})
    except Exception as e:
        return json.dumps({"error": f"Failed to load channel directory: {e}"})


def _handle_send(args):
    """Send a message to a platform target."""
    target = args.get("target", "")
    message = args.get("message", "")
    if not target or not message:
        return json.dumps({"error": "Both 'target' and 'message' are required when action='send'"})

    parts = target.split(":", 1)
    platform_name = parts[0].strip().lower()
    target_ref = parts[1].strip() if len(parts) > 1 else None
    chat_id = None
    thread_id = None

    if target_ref:
        chat_id, thread_id, is_explicit = _parse_target_ref(platform_name, target_ref)
    else:
        is_explicit = False

    # Resolve human-friendly channel names to numeric IDs
    if target_ref and not is_explicit:
        try:
            from gateway.channel_directory import resolve_channel_name
            resolved = resolve_channel_name(platform_name, target_ref)
            if resolved:
                chat_id, thread_id, _ = _parse_target_ref(platform_name, resolved)
            else:
                return json.dumps({
                    "error": f"Could not resolve '{target_ref}' on {platform_name}. "
                    f"Use send_message(action='list') to see available targets."
                })
        except Exception:
            return json.dumps({
                "error": f"Could not resolve '{target_ref}' on {platform_name}. "
                f"Try using a numeric channel ID instead."
            })

    from arnold.agent.tools.interrupt import is_interrupted
    if is_interrupted():
        return json.dumps({"error": "Interrupted"})

    try:
        from gateway.config import load_gateway_config, Platform
        config = load_gateway_config()
    except Exception as e:
        return json.dumps({"error": f"Failed to load gateway config: {e}"})

    platform_map = {
        "telegram": Platform.TELEGRAM,
        "discord": Platform.DISCORD,
        "slack": Platform.SLACK,
        "whatsapp": Platform.WHATSAPP,
        "signal": Platform.SIGNAL,
        "matrix": Platform.MATRIX,
        "mattermost": Platform.MATTERMOST,
        "homeassistant": Platform.HOMEASSISTANT,
        "dingtalk": Platform.DINGTALK,
        "email": Platform.EMAIL,
        "sms": Platform.SMS,
    }
    platform = platform_map.get(platform_name)
    if not platform:
        avail = ", ".join(platform_map.keys())
        return json.dumps({"error": f"Unknown platform: {platform_name}. Available: {avail}"})

    pconfig = config.platforms.get(platform)
    if not pconfig or not pconfig.enabled:
        return json.dumps({"error": f"Platform '{platform_name}' is not configured. Set up credentials in ~/.hermes/config.yaml or environment variables."})

    from gateway.platforms.base import BasePlatformAdapter

    media_files, cleaned_message = BasePlatformAdapter.extract_media(message)
    mirror_text = cleaned_message.strip() or _describe_media_for_mirror(media_files)

    used_home_channel = False
    if not chat_id:
        home = config.get_home_channel(platform)
        if home:
            chat_id = home.chat_id
            used_home_channel = True
        else:
            return json.dumps({
                "error": f"No home channel set for {platform_name} to determine where to send the message. "
                f"Either specify a channel directly with '{platform_name}:CHANNEL_NAME', "
                f"or set a home channel via: hermes config set {platform_name.upper()}_HOME_CHANNEL <channel_id>"
            })

    duplicate_skip = _maybe_skip_cron_duplicate_send(platform_name, chat_id, thread_id)
    if duplicate_skip:
        return json.dumps(duplicate_skip)

    try:
        from arnold.agent.tools.model_tools import _run_async
        result = _run_async(
            _send_to_platform(
                platform,
                pconfig,
                chat_id,
                cleaned_message,
                thread_id=thread_id,
                media_files=media_files,
            )
        )
        if used_home_channel and isinstance(result, dict) and result.get("success"):
            result["note"] = f"Sent to {platform_name} home channel (chat_id: {chat_id})"

        # Mirror the sent message into the target's gateway session
