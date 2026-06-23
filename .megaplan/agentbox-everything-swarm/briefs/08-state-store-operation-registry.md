You are a DeepSeek subagent doing a read-only inventory for AgentBox. The user asked us to find EVERYTHING existing in this repo/local skills that overlaps with the desired Discord-first AgentBox: start tickets/epics/megaplans/chains from Discord, Guardian repairs/relaunches blocked runs, completed work gets pushed/PRd/consolidated, and DeepSeek/subagents can be used. The brief embeds local excerpts. Return a decisive inventory of reusable mechanics, with file refs, gaps, and concrete recommendations. Under 1200 words. Focus: store/state models that can back AgentBox operation registry, conversations, scheduled jobs, cloud runs, confirmations, events.


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

--- FILE: arnold_pipelines/megaplan/store/base.py (1,260p) ---
"""Core storage contracts, record shapes, and compatibility helpers."""

from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime
import hashlib
import re
from pathlib import PurePosixPath
from types import TracebackType
from typing import Any, Iterator, Mapping, Protocol, Sequence, TypeAlias, runtime_checkable

from pydantic import Field

from arnold_pipelines.megaplan.schemas import (
    AutomationActor,
    BotTurn,
    ChecklistItem,
    CodeArtifact,
    Codebase,
    ControlMessage,
    CloudRun,
    Epic,
    EpicEvent,
    EpicLock,
    EpicSnapshot,
    ExecutionLease,
    ExternalRequest,
    Feedback,
    Image,
    Message,
    Plan,
    ProgressEvent,
    ResidentConversation,
    ScheduledJob,
    SecondOpinion,
    Sprint,
    SprintItem,
    StorageModel,
    SystemLog,
    Ticket,
    TicketEpicLink,
    ToolCall,
)
from arnold_pipelines.megaplan.schemas.arnold import (
    ChecklistSource,
    ChecklistStatus,
    EpicSummary,
    SprintItemComplexity,
    SprintItemStatus,
)
from arnold_pipelines.megaplan.schemas.base import Backend, NormalizedDict, utc_now
from arnold_pipelines.megaplan.schemas.sprint1 import ControlIntent
JSONDict: TypeAlias = dict[str, Any]
_IDEMPOTENCY_PART_RE = re.compile(r"[^A-Za-z0-9_.:-]+")


def deterministic_idempotency_key(*parts: object) -> str:
    """Build a stable, readable idempotency key from caller-owned values."""
    raw = ":".join(str(part) for part in parts if part is not None)
    slug = _IDEMPOTENCY_PART_RE.sub("-", raw).strip("-") or "operation"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:10]
    return f"{slug}:{digest}"


class StoreError(RuntimeError):
    """Base exception for store-contract failures."""


EPIC_UPDATE_FIELDS = frozenset({
    "title",
    "goal",
    "body",
    "state",
    "home_backend",
    "migrated_to",
    "last_active_at",
    "planned_at",
})


def validate_epic_update_fields(changes: Mapping[str, object]) -> None:
    unknown = sorted(set(changes) - EPIC_UPDATE_FIELDS)
    if unknown:
        allowed = ", ".join(sorted(EPIC_UPDATE_FIELDS))
        raise StoreError(f"Unknown epic update field(s): {', '.join(unknown)}. Allowed fields: {allowed}")


class RevisionConflict(StoreError):
    """Raised when an optimistic-concurrency write sees a stale revision."""


class LockConflict(StoreError):
    """Raised when an epic lock is held by another actor."""


class LeaseConflict(StoreError):
    """Raised when an execution lease is already held."""


class ChecklistItemInput(StorageModel):
    id: str | None = None
    content: str
    status: ChecklistStatus = "open"
    position: int | None = Field(default=None, gt=0)
    source: ChecklistSource = "bot_inferred"
    skip_reason: str | None = None
    superseded_by_item_id: str | None = None
    created_at: datetime | None = None
    completed_at: datetime | None = None


class SprintItemInput(StorageModel):
    id: str | None = None
    content: str
    estimated_complexity: SprintItemComplexity = "medium"
    status: SprintItemStatus = "open"
    source_section: str | None = None
    position: int | None = Field(default=None, gt=0)
    created_at: datetime | None = None


class MessageSearchHit(Message):
    snippet: str | None = None
    rank: float | int | None = None


class SprintWithItems(Sprint):
    items: list[SprintItem] = Field(default_factory=list)


class HotContext(StorageModel):
    epic: Epic | None = None
    recent_messages: list[Message] = Field(default_factory=list)
    recent_tool_calls: list[ToolCall] = Field(default_factory=list)
    active_feedback: list[Feedback] = Field(default_factory=list)
    unresolved_observations: list[Feedback] = Field(default_factory=list)
    sprints: list[SprintWithItems] = Field(default_factory=list)
    codebases: list[Codebase] = Field(default_factory=list)
    recent_code_artifacts: list[CodeArtifact] = Field(default_factory=list)
    active_images: list[Image] = Field(default_factory=list)
    recent_second_opinions: list[SecondOpinion] = Field(default_factory=list)
    all_sprints_pending_no_queued: bool = False


class ArtifactRef(StorageModel):
    plan_id: str
    name: str
    kind: str | None = None
    role: str | None = None
    size_bytes: int | None = None
    sha256: str | None = None
    updated_at: datetime | None = None


class ArtifactStat(StorageModel):
    plan_id: str
    name: str
    size_bytes: int
    sha256: str | None = None
    updated_at: datetime = Field(default_factory=utc_now)


@dataclass(frozen=True)
class StoredEvent:
    """Store-neutral event record used by observability projections."""

    kind: str
    phase: str | None
    payload: Mapping[str, Any]
    occurred_at: datetime | str | None = None
    id: str | None = None
    seq: int | None = None
    run_id: str | None = None
    source: str | None = None


def validate_plan_artifact_name(name: str) -> str:
    """Return a normalized relative artifact path or reject unsafe names."""
    if not name:
        raise ValueError("Plan artifact name must be non-empty")
    if "\\" in name:
        raise ValueError(f"Unsafe plan artifact name: {name!r}")
    path = PurePosixPath(name)
    if path.is_absolute() or str(path) != name:
        raise ValueError(f"Unsafe plan artifact name: {name!r}")
    if any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"Unsafe plan artifact name: {name!r}")
    return name


class ControlMessageInput(StorageModel):
    epic_id: str
    actor_id: str
    intent: ControlIntent
    target_id: str
    payload: NormalizedDict = Field(default_factory=dict)
    idempotency_key: str


class ResidentConversationInput(StorageModel):
    transport: str = "discord"
    conversation_key: str
    active_epic_id: str | None = None
    guild_id: str | None = None
    channel_id: str | None = None
    thread_id: str | None = None
    dm_user_id: str | None = None
    metadata: NormalizedDict = Field(default_factory=dict)


class ScheduledJobInput(StorageModel):
    job_type: str
    conversation_id: str | None = None
    cloud_run_id: str | None = None
    epic_id: str | None = None
    payload: NormalizedDict = Field(default_factory=dict)
    scheduled_for: datetime
    max_attempts: int = Field(default=3, ge=1)


class CloudRunInput(StorageModel):
    operation: str
    conversation_id: str | None = None
    epic_id: str | None = None
    sprint_id: str | None = None
    plan_id: str | None = None
    provider: str | None = None
    provider_run_id: str | None = None
    target_id: str | None = None
    command_summary: str | None = None
    metadata: NormalizedDict = Field(default_factory=dict)
    idempotency_key: str | None = None
    started_by_actor_id: str | None = None


class ProgressEventInput(StorageModel):
    epic_id: str
    plan_id: str | None = None
    sprint_id: str | None = None
    idempotency_key: str | None = None
    kind: str
    summary: str
    details: NormalizedDict = Field(default_factory=dict)


Lease = ExecutionLease


@runtime_checkable
class Transaction(Protocol):
    """Context-manager shape used by Store.transaction()."""

    def __enter__(self) -> Transaction:
        ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,

--- FILE: arnold_pipelines/megaplan/store/base.py (500,760p) ---
        payload: Mapping[str, Any],
        *,
        scope: str | None = None,
    ) -> JSONDict:
        ...

    def events_for_plan(self, plan_id: str) -> Iterator[StoredEvent]:
        ...

    # ---------- Messages / turns ----------
    def create_message(
        self,
        *,
        epic_id: str | None,
        direction: str,
        content: str,
        discord_message_id: str | None = None,
        bot_turn_id: str | None = None,
        has_code_attachment: bool = False,
        has_image_attachment: bool = False,
        in_burst_with: Sequence[str] | None = None,
        was_voice_message: bool = False,
        audio_storage_url: str | None = None,
        transcription_metadata: JSONDict | None = None,
        synthesize_outbound_id: bool = True,
        conversation_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> Message:
        ...

    def load_message(self, message_id: str) -> Message | None:
        ...

    def load_messages(self, message_ids: Sequence[str]) -> list[Message]:
        ...

    def update_message(self, message_id: str, *, idempotency_key: str | None = None,
        **changes: Any) -> Message:
        ...

    def latest_outbound_message(self, *, epic_id: str | None = None) -> Message | None:
        ...

    def create_turn(
        self,
        *,
        epic_id: str | None,
        triggered_by_message_ids: Sequence[str],
        prompt_snapshot: JSONDict | None = None,
        prompt_version: str | None = None,
        state_at_turn: JSONDict | None = None,
        model_version: str | None = None,
        idempotency_key: str | None = None,
    ) -> BotTurn:
        ...

    def update_turn(self, turn_id: str, *, idempotency_key: str | None = None,
        **changes: Any) -> BotTurn:
        ...

    def find_abandoned_turns(self, older_than_seconds: int) -> list[BotTurn]:
        ...

    def list_recent_turns(
        self,
        *,
        n: int = 10,
        epic_id: str | None = None,
    ) -> list[BotTurn]:
        ...

    def search_messages(
        self,
        *,
        query: str,
        epic_id: str | None = None,
        limit: int = 20,
    ) -> list[MessageSearchHit]:
        ...

    def record_tool_call(
        self,
        *,
        turn_id: str,
        tool_name: str,
        operation_kind: str,
        arguments: JSONDict,
        result: JSONDict,
        duration_ms: int,
        idempotency_key: str | None = None,
    ) -> ToolCall:
        ...

    def search_tool_calls_by(
        self,
        *,
        tool_name: str | None = None,
        epic_id: str | None = None,
        since: str | None = None,
        limit: int = 20,
    ) -> list[ToolCall]:
        ...

    def log_system_event(
        self,
        *,
        level: str,
        category: str,
        event_type: str,
        message: str,
        details: JSONDict | None = None,
        turn_id: str | None = None,
        epic_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> SystemLog:
        ...

    def load_hot_context(self, epic_id: str | None) -> HotContext:
        ...

    def find_unprocessed_messages(
        self,
        epic_id: str,
        started_at: str,
        exclude_ids: Sequence[str],
    ) -> list[Message]:
        ...

    # ---------- External request ledger ----------
    def insert_pending(
        self,
        *,
        idempotency_key: str,
        provider: str,
        endpoint: str,
        request_summary: JSONDict,
        request_body: JSONDict | None = None,
        turn_id: str | None = None,
        tool_call_id: str | None = None,
    ) -> ExternalRequest:
        ...

    def mark_confirmed(
        self,
        request_id: str,
        *,
        provider_request_id: str | None = None,
        provider_response_summary: JSONDict | None = None,
        idempotency_key: str | None = None,
    ) -> ExternalRequest:
        ...

    def mark_failed(
        self,
        request_id: str,
        *,
        error_details: JSONDict,
        idempotency_key: str | None = None,
    ) -> ExternalRequest:
        ...

    def find_pending_external_requests(self, older_than_seconds: int) -> list[ExternalRequest]:
        ...

    def mark_orphaned(
        self,
        request_id: str,
        *,
        error_details: JSONDict,
        idempotency_key: str | None = None,
    ) -> ExternalRequest:
        ...

    # ---------- Images ----------
    def create_image(
        self,
        *,
        epic_id: str,
        source: str,
        storage_url: str,
        prompt: str | None = None,
        quality: str | None = None,
        size: str | None = None,
        reference_key: str | None = None,
        description: str | None = None,
        caption: str | None = None,
        in_body: bool = False,
        active: bool = True,
        discord_attachment_id: str | None = None,
        blob_backend: str | None = None,
        blob_id: str | None = None,
        blob_sha256: str | None = None,
        blob_size_bytes: int | None = None,
        content_type: str | None = None,
        idempotency_key: str | None = None,
    ) -> Image:
        ...

    def attach_image(
        self,
        *,
        epic_id: str,
        content: bytes,
        content_type: str,
        reference_key: str,
        source: str = "user_uploaded",
        prompt: str | None = None,
        quality: str | None = None,
        size: str | None = None,
        description: str | None = None,
        caption: str | None = None,
        in_body: bool = True,
        idempotency_key: str | None = None,
    ) -> Image:
        ...

    def resolve_image_reference(
        self,
        epic_id: str,
        reference: str,
        *,
        signed: bool = False,
        ttl: int = 3600,
    ) -> str | None:
        ...

    def load_image(self, image_id: str) -> Image | None:
        ...

    def list_images(
        self,
        *,
        epic_id: str,
        source: str | None = None,
        active: bool | None = True,
    ) -> list[Image]:
        ...

    def update_image(self, image_id: str, *, idempotency_key: str | None = None,
        **changes: Any) -> Image:
        ...

    def list_active_images(self, epic_id: str) -> list[Image]:
        ...

    def load_active_image_by_reference(self, epic_id: str, reference_key: str) -> Image | None:
        ...

    def active_image_reference_exists(self, epic_id: str, reference_key: str) -> bool:
        ...

    def deactivate_active_image_reference(self, epic_id: str, reference_key: str,
        *,
        idempotency_key: str | None = None,
    ) -> list[Image]:
        ...

    # ---------- Second opinions ----------
    def create_second_opinion(
        self,
        *,

--- FILE: arnold_pipelines/megaplan/store/_file/conversations.py (1,160p) ---
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, Sequence

from arnold_pipelines.megaplan._core.io import normalize_text
from arnold_pipelines.megaplan.schemas import BotTurn, Message, SystemLog, ToolCall
from arnold_pipelines.megaplan.schemas.base import utc_now

from ..base import HotContext, MessageSearchHit
from .common import _new_id, _parse_datetime, _utc_key


class FileConversationMixin:
    def _next_invocation_message_id(self, turn_id: str) -> str:
        count = sum(1 for row in self._messages() if row.bot_turn_id == turn_id and row.direction == "outbound")
        return f"inv_{turn_id}_{count + 1}"

    def create_message(
        self,
        *,
        epic_id: str | None,
        direction: str,
        content: str,
        discord_message_id: str | None = None,
        bot_turn_id: str | None = None,
        has_code_attachment: bool = False,
        has_image_attachment: bool = False,
        in_burst_with: Sequence[str] | None = None,
        was_voice_message: bool = False,
        audio_storage_url: str | None = None,
        transcription_metadata: dict[str, Any] | None = None,
        synthesize_outbound_id: bool = True,
        conversation_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> Message:
        if idempotency_key is not None:
            for existing in self._messages():
                if existing.idempotency_key == idempotency_key:
                    return existing
        if synthesize_outbound_id and direction == "outbound" and discord_message_id is None and bot_turn_id:
            discord_message_id = self._next_invocation_message_id(bot_turn_id)
        message = Message(
            id=_new_id("msg"),
            epic_id=epic_id,
            conversation_id=conversation_id,
            idempotency_key=idempotency_key,
            direction=direction,
            content=content,
            sent_at=utc_now(),
            discord_message_id=discord_message_id,
            has_code_attachment=has_code_attachment,
            has_image_attachment=has_image_attachment,
            in_burst_with=list(in_burst_with or []),
            was_voice_message=was_voice_message,
            audio_storage_url=audio_storage_url,
            transcription_metadata=transcription_metadata,
            bot_turn_id=bot_turn_id,
        )
        self._save_model(self._message_path(message.id), message, journal_root=self.root)
        return message

    def load_message(self, message_id: str) -> Message | None:
        return self._load_model(self._message_path(message_id), Message)

    def load_messages(self, message_ids: Sequence[str]) -> list[Message]:
        by_id = {message.id: message for message in self._messages()}
        return [by_id[msg_id] for msg_id in message_ids if msg_id in by_id]

    def update_message(self, message_id: str, *, idempotency_key: str | None = None,
        **changes: Any) -> Message:
        return self._update_model(
            self._message_path(message_id),
            Message,
            journal_root=self.root,
            **changes,
        )

    def latest_outbound_message(self, *, epic_id: str | None = None) -> Message | None:
        messages = [row for row in self._messages() if row.direction == "outbound"]
        if epic_id is not None:
            messages = [row for row in messages if row.epic_id == epic_id]
        messages.sort(key=lambda row: (_utc_key(row.sent_at), row.id), reverse=True)
        return messages[0] if messages else None

    def create_turn(
        self,
        *,
        epic_id: str | None,
        triggered_by_message_ids: Sequence[str],
        prompt_snapshot: dict[str, Any] | None = None,
        prompt_version: str | None = None,
        state_at_turn: dict[str, Any] | None = None,
        model_version: str | None = None,
        idempotency_key: str | None = None,
    ) -> BotTurn:
        turn = BotTurn(
            id=_new_id("turn"),
            epic_id=epic_id,
            triggered_by_message_ids=list(triggered_by_message_ids),
            prompt_snapshot=prompt_snapshot,
            prompt_version=prompt_version,
            status="in_progress",
            state_at_turn=state_at_turn,
            model_version=model_version,
            started_at=utc_now(),
        )
        self._save_model(self._turn_path(turn.id), turn, journal_root=self.root)
        return turn

    def update_turn(self, turn_id: str, *, idempotency_key: str | None = None,
        **changes: Any) -> BotTurn:
        return self._update_model(self._turn_path(turn_id), BotTurn, journal_root=self.root, **changes)

    def find_abandoned_turns(self, older_than_seconds: int) -> list[BotTurn]:
        cutoff = datetime.now(UTC) - timedelta(seconds=older_than_seconds)
        return sorted(
            [
                turn
                for turn in self._turns()
                if turn.status == "in_progress" and turn.started_at <= cutoff
            ],
            key=lambda turn: (turn.started_at, turn.id),
        )

    def list_recent_turns(self, *, n: int = 10, epic_id: str | None = None) -> list[BotTurn]:
        turns = self._turns()
        if epic_id is not None:
            turns = [turn for turn in turns if turn.epic_id == epic_id]
        turns.sort(key=lambda turn: (_utc_key(turn.started_at), turn.id), reverse=True)
        return turns[:n]

    def search_messages(self, *, query: str, epic_id: str | None = None, limit: int = 20) -> list[MessageSearchHit]:
        needle = normalize_text(query)
        hits: list[tuple[int, Message]] = []
        for message in self._messages():
            if epic_id is not None and message.epic_id != epic_id:
                continue
            content = normalize_text(message.content)
            if needle in content:
                hits.append((content.count(needle), message))
        hits.sort(key=lambda item: (-item[0], item[1].id))
        return [
            MessageSearchHit.model_validate({**msg.model_dump(mode="json"), "rank": score})
            for score, msg in hits[:limit]
        ]

    def record_tool_call(
        self,
        *,
        turn_id: str,
        tool_name: str,
        operation_kind: str,
        arguments: dict[str, Any],
        result: dict[str, Any],
        duration_ms: int,
        idempotency_key: str | None = None,
    ) -> ToolCall:
        tool_call = ToolCall(
            id=_new_id("tool"),

--- FILE: arnold_pipelines/megaplan/store/_db/conversations.py (1,140p) ---
"""Conversation and turn mixins for DBStore."""

from __future__ import annotations

import uuid
from typing import Any, Sequence

from arnold_pipelines.megaplan.schemas import BotTurn, CodeArtifact, Codebase, Epic, Feedback, Image, Message, SecondOpinion, ToolCall
from arnold_pipelines.megaplan.store.base import HotContext, MessageSearchHit, RevisionConflict

from .common import _OBSERVATION_KINDS, _jb

class DBConversationMixin:
    def _next_invocation_message_id(self, turn_id: str) -> str:
        conn = self._get_conn()
        row = conn.execute(
            """
            SELECT count(*) AS count
            FROM messages
            WHERE bot_turn_id = %s AND direction = 'outbound'
            """,
            [turn_id],
        ).fetchone()
        return f"inv_{turn_id}_{int(row['count']) + 1}"

    def create_message(
        self,
        *,
        epic_id: str | None,
        direction: str,
        content: str,
        discord_message_id: str | None = None,
        bot_turn_id: str | None = None,
        has_code_attachment: bool = False,
        has_image_attachment: bool = False,
        in_burst_with: Sequence[str] | None = None,
        was_voice_message: bool = False,
        audio_storage_url: str | None = None,
        transcription_metadata: dict[str, Any] | None = None,
        synthesize_outbound_id: bool = True,
        conversation_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> Message:
        conn = self._get_conn()
        if synthesize_outbound_id and direction == "outbound" and discord_message_id is None and bot_turn_id:
            discord_message_id = self._next_invocation_message_id(bot_turn_id)
        if discord_message_id is not None:
            existing = conn.execute(
                "SELECT * FROM messages WHERE discord_message_id = %s",
                [discord_message_id],
            ).fetchone()
            if existing is not None:
                changes: dict[str, Any] = {}
                if conversation_id is not None and existing["conversation_id"] is None:
                    changes["conversation_id"] = conversation_id
                if idempotency_key is not None and existing["idempotency_key"] is None:
                    changes["idempotency_key"] = idempotency_key
                if bot_turn_id is not None and existing["bot_turn_id"] is None:
                    changes["bot_turn_id"] = bot_turn_id
                if changes:
                    set_parts = [f"{column} = %s" for column in changes]
                    existing = conn.execute(
                        f"UPDATE messages SET {', '.join(set_parts)} WHERE id = %s RETURNING *",
                        [*changes.values(), existing["id"]],
                    ).fetchone()
                return Message(**existing)
        row = conn.execute(
            """
            INSERT INTO messages (
                id, epic_id, conversation_id, idempotency_key, direction, content, discord_message_id, bot_turn_id,
                has_code_attachment, has_image_attachment, in_burst_with,
                was_voice_message, audio_storage_url, transcription_metadata
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (idempotency_key) WHERE idempotency_key IS NOT NULL DO UPDATE
            SET idempotency_key = EXCLUDED.idempotency_key
            RETURNING *
            """,
            [
                str(uuid.uuid4()), epic_id, conversation_id, idempotency_key,
                direction, content, discord_message_id,
                bot_turn_id, has_code_attachment, has_image_attachment,
                _jb(list(in_burst_with) if in_burst_with is not None else None),
                was_voice_message, audio_storage_url, _jb(transcription_metadata),
            ],
        ).fetchone()
        return Message(**row)

    def load_message(self, message_id: str) -> Message | None:
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM messages WHERE id = %s", [message_id]).fetchone()
        return Message(**row) if row else None

    def load_messages(self, message_ids: Sequence[str]) -> list[Message]:
        conn = self._get_conn()
        if not message_ids:
            return []
        rows = conn.execute(
            "SELECT * FROM messages WHERE id = ANY(%s::text[]) ORDER BY array_position(%s::text[], id)",
            [list(message_ids), list(message_ids)],
        ).fetchall()
        return [Message(**row) for row in rows]

    def update_message(self, message_id: str, *, idempotency_key: str | None = None,
        **changes: Any) -> Message:
        conn = self._get_conn()
        if not changes:
            row = conn.execute("SELECT * FROM messages WHERE id = %s", [message_id]).fetchone()
            if row is None:
                raise RevisionConflict(f"Message {message_id!r} not found")
            return Message(**row)
        set_parts = [f"{k} = %s" for k in changes]
        values = list(changes.values()) + [message_id]
        row = conn.execute(
            f"UPDATE messages SET {', '.join(set_parts)} WHERE id = %s RETURNING *",
            values,
        ).fetchone()
        if row is None:
            raise RevisionConflict(f"Message {message_id!r} not found")
        return Message(**row)

    def latest_outbound_message(self, *, epic_id: str | None = None) -> Message | None:
        conn = self._get_conn()
        if epic_id is not None:
            row = conn.execute(
                "SELECT * FROM messages WHERE direction = 'outbound' AND epic_id = %s ORDER BY sent_at DESC LIMIT 1",
                [epic_id],
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM messages WHERE direction = 'outbound' ORDER BY sent_at DESC LIMIT 1",
            ).fetchone()
        return Message(**row) if row else None

    def search_messages(
        self,
        *,
        query: str,
        epic_id: str | None = None,
        limit: int = 20,
    ) -> list[MessageSearchHit]:

--- FILE: arnold_pipelines/megaplan/schemas/arnold.py (1,260p) ---
"""Pydantic mirrors of the Arnold Supabase tables."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import ConfigDict, Field, field_validator, model_validator

from .base import (
    HomeBackend,
    NormalizedDict,
    NormalizedList,
    NormalizedStringList,
    StorageModel,
    utc_now,
)

EpicState = Literal["shaping", "sprinting", "planned", "paused", "archived"]
ARNOLD_EPIC_STATES: tuple[str, ...] = ("shaping", "sprinting", "planned", "paused", "archived")
ARNOLD_TO_MEGAPLAN_EPIC_STATE: dict[str, str] = {state: state for state in ARNOLD_EPIC_STATES}


def map_arnold_epic_state(state: str) -> EpicState:
    """Return the Megaplan epic state for an Arnold editorial state."""
    try:
        return ARNOLD_TO_MEGAPLAN_EPIC_STATE[state]  # type: ignore[return-value]
    except KeyError as exc:
        raise ValueError(f"Unsupported Arnold epic state: {state}") from exc
BotTurnStatus = Literal["in_progress", "completed", "failed", "abandoned"]
MessageDirection = Literal["inbound", "outbound"]
ResidentConversationTransport = Literal["discord"]
ToolOperationKind = Literal["read", "write", "cloud_read", "cloud_start", "control"]
SystemLogLevel = Literal["debug", "info", "warn", "error"]
SystemLogCategory = Literal["system", "application", "tool", "llm", "external_api", "recovery"]
ExternalRequestProvider = Literal["anthropic", "openai", "groq", "github", "discord", "supabase_storage"]
ExternalRequestStatus = Literal["pending", "sent", "confirmed", "failed", "orphaned"]
ImageSource = Literal["agent_generated", "user_uploaded", "caller_uploaded"]
ChecklistStatus = Literal["open", "done", "skipped", "superseded"]
ChecklistSource = Literal["bot_inferred", "user_requested", "carried_over", "default_seed", "second_opinion"]
EpicEventType = Literal[
    "body_edit",
    "checklist_change",
    "sprints_change",
    "state_change",
    "forced_handoff",
    "created",
    "code_referenced",
    "codebase_added",
    "image_generated",
    "second_opinion_requested",
    "reverted_to",
    "sprint_status_change",
]
FeedbackKind = Literal[
    "style",
    "process",
    "epic_specific",
    "friction",
    "ambiguity",
    "tool_failure",
    "confusion",
    "pattern_noticed",
]
FeedbackSource = Literal[
    "user_volunteered",
    "agent_proposed_user_confirmed",
    "explicit_save_request",
    "agent_observation",
]
SprintStatus = Literal["proposed", "queued", "pending", "running", "done", "failed", "blocked", "cancelled"]
SprintItemComplexity = Literal["small", "medium", "large"]
SprintItemStatus = Literal["open", "in_progress", "done"]
SecondOpinionRequester = Literal["user", "auto_state_gate"]
CodebaseScope = Literal["global", "epic_specific"]
CodeArtifactKind = Literal["excerpt", "summary", "api_cache"]
CodeArtifactSource = Literal["conversation", "codebase"]
CodeArtifactScope = Literal["file", "directory", "cross_codebase"]


class Epic(StorageModel):
    id: str
    title: str
    goal: str
    body: str
    state: EpicState
    home_backend: HomeBackend = "file"
    migrated_to: str | None = None
    revision: int = 0
    created_at: datetime = Field(default_factory=utc_now)
    last_edited_at: datetime = Field(default_factory=utc_now)
    last_active_at: datetime | None = None
    planned_at: datetime | None = None


class BotTurn(StorageModel):
    id: str
    epic_id: str | None = None
    triggered_by_message_ids: NormalizedStringList = Field(default_factory=list)
    prompt_snapshot: NormalizedDict | None = None
    prompt_version: str | None = None
    reasoning: str | None = None
    final_output_message_id: str | None = None
    status_message_id: str | None = None
    status: BotTurnStatus
    state_at_turn: NormalizedDict | None = None
    plan_edited: bool = False
    code_consulted: bool = False
    image_generated: bool = False
    second_opinion_requested: bool = False
    message_sent: bool = False
    warnings_issued: NormalizedList | None = None
    current_activity: str | None = None
    started_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None
    model_version: str | None = None


class ResidentConversation(StorageModel):
    id: str
    transport: ResidentConversationTransport = "discord"
    conversation_key: str
    active_epic_id: str | None = None
    guild_id: str | None = None
    channel_id: str | None = None
    thread_id: str | None = None
    dm_user_id: str | None = None
    last_inbound_message_id: str | None = None
    last_outbound_message_id: str | None = None
    delivery_cursor: str | None = None
    metadata: NormalizedDict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    last_active_at: datetime | None = None


class Message(StorageModel):
    id: str
    epic_id: str | None = None
    conversation_id: str | None = None
    idempotency_key: str | None = None
    direction: MessageDirection
    content: str
    sent_at: datetime = Field(default_factory=utc_now)
    discord_message_id: str | None = None
    has_code_attachment: bool = False
    has_image_attachment: bool = False
    in_burst_with: NormalizedStringList | None = None
    was_voice_message: bool = False
    audio_storage_url: str | None = None
    transcription_metadata: NormalizedDict | None = None
    bot_turn_id: str | None = None


class ToolCall(StorageModel):
    id: str
    turn_id: str
    tool_name: str
    operation_kind: ToolOperationKind
    arguments: NormalizedDict = Field(default_factory=dict)
    result: NormalizedDict = Field(default_factory=dict)
    called_at: datetime = Field(default_factory=utc_now)
    duration_ms: int = Field(default=0, ge=0)


class SystemLog(StorageModel):
    id: str
    level: SystemLogLevel
    category: SystemLogCategory
    event_type: str
    message: str
    details: NormalizedDict = Field(default_factory=dict)
    turn_id: str | None = None
    epic_id: str | None = None
    occurred_at: datetime = Field(default_factory=utc_now)


class EpicLock(StorageModel):
    epic_id: str
    holder_id: str
    acquired_at: datetime = Field(default_factory=utc_now)
    expires_at: datetime


class ExternalRequest(StorageModel):
    id: str
    idempotency_key: str
    provider: ExternalRequestProvider
    endpoint: str
    tool_call_id: str | None = None
    turn_id: str | None = None
    request_summary: NormalizedDict = Field(default_factory=dict)
    request_body: NormalizedDict | None = None
    status: ExternalRequestStatus
    provider_request_id: str | None = None
    provider_response_summary: NormalizedDict | None = None
    attempt_count: int = Field(default=1, ge=1)
    first_attempted_at: datetime = Field(default_factory=utc_now)
    last_attempted_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None
    error_details: NormalizedDict | None = None


class Image(StorageModel):
    id: str
    epic_id: str | None = None
    source: ImageSource
    prompt: str | None = None
    storage_url: str
    quality: str | None = None
    size: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    reference_key: str
    description: str | None = None
    caption: str | None = None
    in_body: bool = False
    active: bool = True
    discord_attachment_id: str | None = None
    blob_backend: str | None = None
    blob_id: str | None = None
    blob_sha256: str | None = None
    blob_size_bytes: int | None = Field(default=None, ge=0)
    content_type: str | None = None


class ChecklistItem(StorageModel):
    id: str
    epic_id: str
    content: str
    status: ChecklistStatus | None = None
    position: int = Field(gt=0)
    source: ChecklistSource | None = None
    skip_reason: str | None = None
    superseded_by_item_id: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None


class EpicEvent(StorageModel):
    id: str
    epic_id: str
    transaction_id: str
    event_type: EpicEventType | None = None
    summary: str
    prior_state: NormalizedDict | None = None
    pre_state: NormalizedDict | None = None
    post_state: NormalizedDict | None = None
    pre_state_canonical_json: str | None = None
    post_state_canonical_json: str | None = None
    pre_state_sha256: str | None = None
    post_state_sha256: str | None = None
    turn_id: str | None = None
    occurred_at: datetime = Field(default_factory=utc_now)


class EpicSnapshot(StorageModel):
    epic_id: str
    revision: int
    epic: NormalizedDict
    body: str

--- FILE: arnold_pipelines/megaplan/types.py (1,160p) ---
"""Type definitions, constants, and exceptions for megaplan."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal, NotRequired, TypedDict

from arnold.runtime.errors import ArnoldError

# Re-export AgentSpec, format_agent_spec, and parse_agent_spec from the SSoT
# so that identity holds across the megaplan/arnold.agent boundary.
from arnold.agent.contracts import AgentMode, AgentSpec, format_agent_spec, parse_agent_spec

if TYPE_CHECKING:
    from arnold_pipelines.megaplan.planning.state import PlanCurrentState

# ---------------------------------------------------------------------------
# States
# ---------------------------------------------------------------------------
DriverOutcomeStatus = Literal[
    "done",
    "finalized",
    "paused",
    "stalled",
    "escalated",
    "failed",
    "aborted",
    "cancelled",
    "cap",
    "blocked",
    "cost_cap_exceeded",
    "context_retry_exhausted",
    "worker_blocked",
    "infrastructure_error",
    "human_required",
    "awaiting_human",
    "tiebreaker_pending",
    "tiebreaker_ready",
]


# ---------------------------------------------------------------------------
# TypedDicts
# ---------------------------------------------------------------------------

class PlanConfig(TypedDict, total=False):
    project_dir: str
    auto_approve: bool
    robustness: str
    mode: str
    output_path: str
    from_doc: str
    agents: dict[str, str]
    workers: NotRequired[dict[str, Any]]
    max_tiebreakers_per_plan: int
    tiebreaker_blocklist: list[str]
    allow_tiebreaker: bool
    tiebreaker_token_budget: int
    tiebreaker_time_budget_minutes: int
    strict_notes: NotRequired[bool]
    prep_clarify: NotRequired[bool]
    # Completion-verification contract mode: off | shadow | warn | enforce.
    # Default "shadow" = compute + persist + log a verdict, never block, never
    # run the suite. warn/enforce are not yet implemented (behave like shadow +
    # a logged WARNING). See megaplan/orchestration/completion_contract.py.
    completion_contract_mode: NotRequired[str]
    # Full-suite backstop mode: off | shadow | enforce.
    # Default "shadow" = run and record one unscoped suite before milestone
    # advance, never block. enforce blocks only on computed suite failures.
    full_suite_backstop_mode: NotRequired[str]
    # Shell command the harness uses to run the test suite (e.g. "pytest").
    test_command: NotRequired[str]
    # Timeout in seconds for the baseline-capture / verification test run.
    test_baseline_timeout: NotRequired[int]


class PlanMeta(TypedDict, total=False):
    significant_counts: list[int]
    weighted_scores: list[float]
    plan_deltas: list[float | None]
    recurring_critiques: list[str]
    total_cost_usd: float
    overrides: list[dict[str, Any]]
    notes: list[dict[str, Any]]
    imported_decisions: list["SettledDecisionFromDoc"]
    user_approved_gate: bool


class SessionInfo(TypedDict, total=False):
    id: str
    mode: str
    created_at: str
    last_used_at: str
    refreshed: bool
    # Fingerprint of the sandbox-affecting config captured when this session
    # was created (see megaplan.workers._sandbox_fingerprint). At resume
    # time we refuse to reuse a session whose fingerprint no longer matches
    # the current invocation — otherwise codex silently keeps the old
    # sandbox when the operator toggles MEGAPLAN_TRUSTED_CONTAINER or
    # changes --work-dir, leading to repeated invisible failures.
    sandbox_hash: str


class ActivePhase(TypedDict, total=False):
    phase: str
    agent: str
    mode: str
    model: str
    run_id: str
    session_id: str
    started_at: str
    attempt: int
    last_activity_at: str
    last_activity_kind: str
    last_activity_detail: str


class PlanVersionRecord(TypedDict, total=False):
    version: int
    file: str
    hash: str
    timestamp: str


class HistoryEntry(TypedDict, total=False):
    step: str
    timestamp: str
    duration_ms: int
    cost_usd: float
    result: str
    session_mode: str
    session_id: str
    agent: str
    output_file: str
    artifact_hash: str
    finalize_hash: str
    raw_output_file: str
    message: str
    flags_count: int
    flags_addressed: list[Any]
    recommendation: str
    approval_mode: str
    environment: dict[str, bool]


class ClarificationRecord(TypedDict, total=False):
    refined_idea: str
    intent_summary: str
    questions: list[str]
    # 'prep' when halt is from prep ambiguity; absent for criteria-verification halts.
    # Convention: gate serializes blocking items as human-readable strings
    # (e.g. "[blocking] <question>"); structured data (severity/assumption) lives
    # only in prep.json, not here.
    source: str


class LastGateRecord(TypedDict, total=False):
    """Deprecated legacy state cache; prefer plan_dir/gate_carry.json."""

    recommendation: str
    rationale: str
