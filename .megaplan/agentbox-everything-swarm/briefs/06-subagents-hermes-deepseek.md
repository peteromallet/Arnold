You are a DeepSeek subagent doing a read-only inventory for AgentBox. The user asked us to find EVERYTHING existing in this repo/local skills that overlaps with the desired Discord-first AgentBox: start tickets/epics/megaplans/chains from Discord, Guardian repairs/relaunches blocked runs, completed work gets pushed/PRd/consolidated, and DeepSeek/subagents can be used. The brief embeds local excerpts. Return a decisive inventory of reusable mechanics, with file refs, gaps, and concrete recommendations. Under 1200 words. Focus: DeepSeek/subagent/Hermes mechanics already in repo; how Operator/Guardian can spin diagnostic/repair subagents.


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

--- FILE: /Users/peteromalley/Documents/poms_skills/subagent-launcher/SKILL.md (1,220p) ---
---
name: subagent-launcher
description: Launch an external model as a subagent for a second opinion, adversarial review, or delegated work. Default pathway is an agentic DeepSeek / Kimi / Zhipu GLM hermes subagent (file/web/terminal tools, one process or fanned out N-wide); also Codex (GPT-5.5) and Claude via the Agent tool. Use for independent root-cause analysis, cross-checking your reasoning, judge/jury panels, or handing implementation to a different model.
---

# Subagent launcher (multi-model)

Dispatch work to a model other than the one driving the conversation. Two payoffs: **independence** — a *different* model's judgement, not a copy of your own — and **context hygiene** — the subagent's tool calls and reasoning stay in *its* context; only the conclusion returns to you.

Three pathways:

| Pathway | Model | Invocation | Tools |
| --- | --- | --- | --- |
| **Hermes agentic** *(default)* | DeepSeek V4 (Pro/Flash), Kimi K2.7, Zhipu GLM, … | `launch_hermes_agent.py` — or `fan.py` to run N in one process | `file`, `web`, optional `terminal` |
| **Codex** | GPT-5.5 | `codex exec` (CLI) | sandboxed workspace |
| **Claude** | Claude (Opus/Sonnet/Haiku) | `launch_claude_agent.py --model=opus` or Claude Code `Agent` tool | Claude Code tools |

**Default to the hermes agentic pathway, and to DeepSeek within it** — different model family, cheap, tool-using. Reach for Codex or Claude only when you specifically want their strengths.

> **⚠️ Network sandbox warning for Codex subagents**
> `codex exec` runs its subprocess with `CODEX_SANDBOX_NETWORK_DISABLED=1`. Hermes agents (DeepSeek/Kimi/MiMo/GLM/OpenRouter) need outbound network to reach their provider APIs, so **launching them from inside a `codex exec` subagent will fail**. The launcher itself is fine; it fails only because the parent process has no network.
>
> **Workarounds:**
> 1. Launch the hermes subagent directly from a normal shell or Bash tool.
> 2. If you need a **Codex subagent to orchestrate hermes subagents**, run it with `--sandbox danger-full-access`. `read-only` and `workspace-write` both disable outbound network; only `danger-full-access` allows provider API calls from inside `codex exec`.
>
> This network restriction does not affect Codex or Claude subagents.

## Picking a pathway

- **Default — an independent DeepSeek/Kimi subagent that reads the repo itself?** → §1 (`launch_hermes_agent.py --toolsets="file,web"`). Need many at once (≥ ~5 parallel)? Same pathway, `fan.py`.
- **Pure chat opinion, no tools?** → §1 with `--toolsets=""`.
- **Most-different-from-Claude judgement, or write-heavy implementation in a sandbox?** → §2 Codex.
- **Same-*family* judgement but isolated from this thread, with explicit Opus/Sonnet selection?** → §3 Claude CLI launcher. If the host exposes the Claude Code `Agent` tool and model selection is not required, that is also fine.
- **Jury for a high-stakes call?** → fan the same prompt to Codex + hermes-DeepSeek + hermes-Kimi in parallel; divergence is the signal.
- **Bigger than ~a day or two of work?** → it's a *deliverable*, not a dispatch: run a `megaplan` (itself launched as a subagent) and size it with the **`megaplan-decision`** skill. Past ~2 weeks → an epic.
- **Already have the answer?** → don't dispatch. Subagents aren't free.

## Use the cheapest subagent that can do the job

Independence is the *why*; cost is the *which*. Default to the cheapest model that can plausibly succeed; escalate only on evidence.

1. **MiMo V2.5 Pro Ultraspeed** (`fast`, alias for `mimo:mimo-v2.5-pro-ultraspeed`) — very fast. High-volume, low-judgement work: scan files, extract facts, short first-pass research.
2. **DeepSeek V4 Flash** (`deepseek:deepseek-v4-flash`) — non-reasoning, fast, cheap. High-volume work that needs more coding-tuned behavior than MiMo.
3. **DeepSeek V4 Pro** (`deepseek:deepseek-v4-pro`, the default) — reasoning model. When the task needs judgement: root-cause analysis, "is this sound", "should this merge".
4. **GPT-5.5 (Codex) or Claude** — only for *real* complexity: subtle multi-step reasoning, write-heavy implementation, the strongest adversarial review.

Two rules: **start low, escalate on evidence** (don't reach for the frontier model "to be safe"); and **prepare the context so a cheap model can win** — most "cheap model failed" cases are under-specified prompts. A moment spent scoping the task is cheaper than burning a Claude subagent on something Flash could do.

Beware the asymmetry: reasoning models handed mechanical briefs refactor (because that's what reasoning does); non-reasoning models handed architectural briefs literally execute fragments without understanding the intent. Match brief shape to model mode, not just model to task.

---

## 1. Hermes agentic (DeepSeek / Kimi / Zhipu GLM) — the default

A real tool-using agent in a non-Claude model's voice, far lighter than a `megaplan` run. It wraps megaplan's `AIAgent` primitive as a standalone CLI: the agent reads files, searches the codebase, fetches URLs, and (with `terminal`) runs commands — single-turn, no plan state or critique loop. For a pure-chat opinion with no repo access, run the same command with `--toolsets=""`.

```bash
PYENV_VERSION=3.11.11 python ~/.claude/skills/subagent-launcher/launch_hermes_agent.py \
  --toolsets="file,web" \
  --query-file=/tmp/brief.md \
  --max-tokens=65536 \
  --project-dir="$PWD"
# Final response → stdout; tool progress/timings → stderr.
```

Key flags:

- **`--model`** (default `deepseek:deepseek-v4-pro`). Prefix convention from the megaplan key pool:
  - `fast`, `mimo`, `mimo-fast` → `mimo:mimo-v2.5-pro-ultraspeed` (very fast MiMo path; requires `MIMO_API_KEY`)
  - `deepseek:deepseek-v4-pro` (default) / `deepseek:deepseek-v4-flash` (faster, non-reasoning) → DeepSeek API
  - `kimi:kimi-k2.7-code` → Kimi coding API (requires `KIMI_API_KEY` or `MOONSHOT_API_KEY`)
  - `zhipu:glm-5.2` / `zhipu:glm-4.6` → Zhipu GLM API (requires `ZHIPU_API_KEY`)
  - `google:gemini-…`, `minimax:MiniMax-M2`, … — see `megaplan/runtime/key_pool.py:resolve_model`
- **`--toolsets`** (default `"file,web"`): `file` (`read_file`/`write_file`/`patch`/`search_files`), `web` (`fetch_url`), `terminal` (shell — **no sandbox**, runs as you; never for untrusted prompts). `""` = pure chat.
- **Note:** in the standalone `launch_hermes_agent.py` entrypoint, the `file` toolset is only available when `terminal` is also enabled, because file operations are routed through the terminal environment. If the agent emits tool-call markup but does not actually read files (or claims it has no filesystem access), pass `--toolsets="file,web,terminal"`.
- **`--query` / `--query-file`** — pass exactly one; use `--query-file` for anything past a sentence.
- **`--max-tokens`** (default 65536 — model output ceiling for DeepSeek V4). **In normal use, do not pass this flag.** The launcher already defaults to the model's ceiling, so adding it yourself just creates copy-paste noise and makes it easy to accidentally inflate the cap for no benefit. These are reasoning models; reasoning tokens are billed and counted against `max_tokens`, so a brief that fires 20+ tool calls can burn the entire budget on reasoning before emitting a single output token — the result is an empty answer (`finish_reason: length`) with the tool history visible in stderr. The built-in ceiling protects against that silent failure. **Only pass `--max-tokens` when you specifically want a shorter cap** because you have already scoped the brief to ≤5 tool calls and want to bound cost/output length. Other ceilings: Kimi K2.7 ~32768, Zhipu GLM-5.2 / GLM-4.6 ~32768, DeepSeek Flash 8192 (non-reasoning, doesn't burn budget on thinking so 8K is fine).
- **`--project-dir`** — chdir so the `file` tool resolves relative paths as you expect.
- **`--context-budget-tokens`** — raise the auto-compaction floor when a broad file audit on a long-context model compacts too early, e.g. `--context-budget-tokens=100000`.

Output is **freeform text** — if you want JSON, ask for it in the prompt and parse defensively; for an *enforced* schema, use megaplan, not this pathway.

### Fan out N at once — `fan.py`

`launch_hermes_agent.py` is one subprocess per call; each re-imports the megaplan tree (~180 MB). For **≥ ~5 parallel agents or programmatic batches**, `fan.py` runs N `AIAgent`s in one process (imports once, ~5–15× less RAM). Same flags, plus a briefs directory and per-task output:

```bash
PYENV_VERSION=3.11.11 python ~/.claude/skills/subagent-launcher/fan.py \
  --briefs-dir=/tmp/briefs --output-dir=/tmp/results \
  --max-workers=5 --model="deepseek:deepseek-v4-pro" \
  --toolsets="file,web" --max-tokens=65536 --task-timeout=1800 --project-dir="$PWD"
# Or positional brief paths instead of --briefs-dir.
# Per-brief models: --model-map="fast:scan-*.md,pro:verdict-*.md"
```

Each brief `<stem>.md` yields `<stem>.txt` (response), `<stem>.meta.json` (status/timing/tool_calls), and an aggregate `_report.json`. Kill a running fan from another shell: `fan_kill.py --output-dir=… [--hard]`. Default `--task-timeout=1800` (30 min — forensic work with ≥10 tool calls routinely exceeds 10 min; the old 600s default would silently SIGKILL agents mid-investigation). Bump higher for very heavy briefs (e.g. `--task-timeout=3600` for cross-file audits). Add `--isolation=processes` if you need to SIGKILL one task without touching the rest. Below ~5 parallel, just launch `launch_hermes_agent.py` N times in parallel Bash calls — simpler.

### Use `megaplan` instead when you need

multi-phase orchestration (plan → critique → revise → execute → gate → review), schema-enforced output, persistent plan state / approval gates, or the megaplan sandbox. See *Multi-phase delegation* below.

### Liveness

The script logs `[tool]` / `[done]` to stderr every 1–5 s while alive and ends with `[launch_hermes_agent] done in N.Ns`. No new tool lines for minutes = wedged. For `fan.py`, watch `.meta.json` files appearing under `--output-dir`.

---

## 2. Codex (GPT-5.5)

`codex exec` from Bash (the `/codex:*` plugin wraps the same call).

```bash
codex exec --sandbox read-only "$(cat /tmp/prompt.md)" </dev/null > /tmp/out.txt 2>&1
```

- `--sandbox read-only | workspace-write | danger-full-access` — analysis / let it edit files / full shell.
- `-c model_reasoning_effort=low|medium|high` — `medium` default.
- `codex exec review [--pr <n>]` for PR review; `codex apply` to apply its last diff.
- **Always seal stdin with `</dev/null`.** Otherwise `codex exec` blocks forever at `Reading additional input from stdin...` (0% CPU, no error) even when the prompt is in argv. That banner prints on healthy runs too — the wedge signal is the output file *not growing*. Wrap long runs in `timeout 1800` (30 min — review and write-heavy briefs routinely run 15+ min; 600s is too tight).

## 3. Claude (Opus/Sonnet/Haiku)

Use the Claude CLI launcher when you need an explicit model selector from any
host, including Codex sessions where the platform `spawn_agent` tool does not
expose a model field:

```bash
python ~/.claude/skills/subagent-launcher/launch_claude_agent.py \
  --model=opus \
  --query-file=/tmp/brief.md \
  --project-dir="$PWD" \
  --tools="Read,Grep,Glob" \
  --timeout=1800
```

`--model` accepts Claude Code aliases such as `opus` / `sonnet` / `haiku` or a
full model name such as `claude-opus-4-8`. The launcher invokes
`claude --print --model <model>` with `--project-dir` as the subprocess cwd and
prints the final answer to stdout while diagnostics go to stderr. It leaves
Claude Code's default tool policy alone unless you pass `--tools`; use
`--permission-mode` deliberately. It adds `--no-session-persistence` by default
so one-off subagents do not clutter Claude history; pass `--keep-session` when
you want resumability.

When you are already inside Claude Code and the `Agent` tool is available,
you can still dispatch through it — cleanly-scoped, no memory of the outer
conversation, so the prompt must be self-contained. Subagent types:
`general-purpose` (full tools), `Explore` (fast read-only search), `Plan`
(architect, no code), `claude-code-guide`, `code-reviewer`.

```
Agent({ description: "…", subagent_type: "general-purpose",
        prompt: "<self-contained brief: working dir, files, what to return, length cap>" })
```

Prefer Claude over Codex when you want the *same family* of judgement isolated from this thread (keeping the main context clean), or specifically want Opus judgement. For genuinely different model-family judgement, prefer Codex, DeepSeek, or Kimi.

---

## Multi-phase delegation (when a single-turn agent isn't enough)

When DeepSeek/Kimi need a full plan-execute-review cycle across many files, route through megaplan:

```bash
PYENV_VERSION=3.11.11 megaplan init --project-dir "$PWD" \
  --profile all-deepseek-pro-direct --robustness light "<task>"
# Kimi: --profile all-open
```

`--robustness light` is a fast single pass; drop it for the full workflow (default `full`). The **`megaplan-decision`** skill covers the profile / robustness / depth dials.

## Writing the prompt (any pathway)

The receiving model has **zero context** from your conversation. Brief it like a smart colleague who just walked in:

**Is your brief a spec or a memo?** A spec lists inputs and outputs (do X at line Y, then Z). A memo explains context and asks for judgement. Reasoning models will treat any memo as license to architect — even if the underlying ask was 5 mechanical edits. If the work is mechanical, strip the rationale; the "why" belongs in the commit message, not the brief.

- Working directory and **exact** file paths (not "the relevant files").
- Goal + why it matters; what you've already ruled out.
- Output shape and a length cap ("ranked list, < 300 words").
- For adversarial / second-opinion work, tell it to take a position and not hedge — otherwise it hedges.
- Anti-pattern: the options menu. "Pick whichever of A/B/C fits" reliably invites a reasoning model to optimize across the options and often produce a fourth one you didn't ask for. One ask, one solution path. Save options menus for genuine judgement calls — and when you do use them, route the work to a non-reasoning model that can't optimize past them.

Don't dispatch what you already know, and don't re-ask what you've answered — add a twist (rank these, find the flaw, argue the other side) or skip it.

## Judge / jury for high-stakes calls

Send the same unbiased prompt to several models in parallel (Codex + hermes-DeepSeek + hermes-Kimi, optionally a Claude `Agent`) and compare — convergence on a subtle call is far stronger than one model's confidence; divergence is signal. Reserve it for risky pre-merge reviews, hard-to-reverse architecture calls, security-sensitive paths. Don't fan out routine work. For a multi-lens sense-check of one proposal (human-user / agent-user / abstraction lenses), give each agent only its own lens and never show one's output to another.

## Detecting hangs

Check liveness **30–60 s after launch**, not 10 minutes in.

- **Codex** — see the `</dev/null` wedge above; the tell is an output file stuck at the banner size while wall-clock climbs.
- **Hermes / fan.py** — `--max-tokens` too low → empty answer (`finish_reason: length`); else watch the stderr `[tool]`/`[done]` heartbeat.
- **Claude Agent / launcher** — synchronous, rarely wedges; the common failure is a terse prompt → shallow hedged answer in < 30 s. Cap length and demand a position.
- **megaplan** — an "stuck" run is usually a gated step awaiting approval; `megaplan status --plan <name>`.

**Liveness ≠ correctness.** A subagent can stream for 10 minutes and still answer uselessly — read the response; there's no shortcut.

## Quick reference

```bash
# 1. Hermes agentic (default) — DeepSeek/Kimi/Zhipu GLM with tools
PYENV_VERSION=3.11.11 python ~/.claude/skills/subagent-launcher/launch_hermes_agent.py \
  --model="deepseek:deepseek-v4-pro" --toolsets="file,web" \
  --query-file=/tmp/brief.md --max-tokens=65536 --project-dir="$PWD"
# Very fast: --model=fast   Flash: --model="deepseek:deepseek-v4-flash"   Kimi: --model="kimi:kimi-k2.7-code"   GLM: --model="zhipu:glm-5.2"
# Pure chat: --toolsets=""    Fan N≥5: fan.py --briefs-dir=… --output-dir=… --max-workers=5 --task-timeout=1800

# 2. Codex — always seal stdin with </dev/null, allow 30 min
timeout 1800 codex exec --sandbox read-only "<prompt>" </dev/null              # analysis
timeout 1800 codex exec --sandbox workspace-write "<prompt>" </dev/null        # implementer
timeout 1800 codex exec --sandbox danger-full-access "<prompt>" </dev/null     # orchestrates hermes subagents (network required)
codex exec review --pr 123

# 3. Claude — explicit Opus selector via Claude CLI
python ~/.claude/skills/subagent-launcher/launch_claude_agent.py \
  --model=opus --query-file=/tmp/prompt.md --project-dir="$PWD"

--- FILE: arnold_pipelines/megaplan/workers/hermes.py (1,220p) ---
"""Hermes Agent worker for megaplan — runs phases via AIAgent with OpenRouter."""

from __future__ import annotations

import hashlib
import html
import json
import os
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from typing import TextIO

import re

from arnold_pipelines.megaplan.types import CliError, MOCK_ENV_VAR, PlanState
from arnold_pipelines.megaplan.prompts import create_hermes_prompt
from arnold_pipelines.megaplan.prompts._projection import check_prompt_size
from arnold_pipelines.megaplan.workers._impl import (
    STEP_SCHEMA_FILENAMES,
    WorkerResult,
    _check_mock_safe,
    _contains_mutating_deepseek_tool_markup,
    _deepseek_tool_markup_names,
    _json_decode_error_for_raw,
    _repair_worker_json_once,
    mock_worker_output,
    session_key_for,
)
from arnold_pipelines.megaplan._core import creative_form_id, read_json, schemas_root, touch_active_step
from arnold.pipeline import StepInvocation
from arnold_pipelines.megaplan.model_seam import (
    ModelBudgetError,
    ModelStructuralAuditError,
    ModelTier,
    capture_step_output,
    render_prompt_for_dispatch,
    render_step_message,
)


def _pre_dispatch_budget_check(
    agent,
    *,
    conversation_history,
    user_message,
    system,
    tool_manifest,
    schema,
    step,
    model_name,
    tier,
    worker,
):
    """Pre-dispatch combined-input budget guard.

    Builds a StepInvocation populating the text-budget fields and routes through
    render_step_message; ModelBudgetError must propagate so an oversized prompt
    cannot reach the provider.
    """
    metadata = {
        "system": system,
        "history": conversation_history,
        "prompt": user_message,
        "tools": tool_manifest,
        "schema": schema,
        "worker": worker,
        "model": model_name,
        "normalized_model": model_name,
        "validation_step": step,
        "tier": tier.value if isinstance(tier, ModelTier) else tier,
    }
    invocation = StepInvocation(kind="model", metadata=metadata)
    try:
        return render_step_message(invocation)
    except ModelBudgetError:
        raise


def _sanitize_db_name(identifier: str) -> str:
    """Sanitize a task/session identifier for use as a safe filename component."""
    sanitized = re.sub(r'[^a-zA-Z0-9_-]', '_', identifier)
    sanitized = re.sub(r'_+', '_', sanitized).strip('_')
    if len(sanitized) > 100:
        sanitized = sanitized[:100]
    return sanitized or "default"


def _worker_db_path(plan_dir: Path, identifier: str) -> Path:
    """Derive a per-worker SessionDB path from a plan directory and stable identifier."""
    sanitized = _sanitize_db_name(identifier)
    return plan_dir / '.hermes_state' / f'state_{sanitized}.db'


def _normalize_worker_options(worker_options: dict[str, object] | None) -> dict[str, object]:
    """Validate the small picklable worker-options surface used by fan-out callers."""
    if worker_options is None:
        return {}
    if not isinstance(worker_options, dict):
        raise CliError("invalid_args", "Hermes worker options must be a dict")

    normalized: dict[str, object] = {}
    for key in ("output_path", "template_path", "session_db_path"):
        value = worker_options.get(key)
        if value is None:
            continue
        if not isinstance(value, (str, Path)):
            raise CliError("invalid_args", f"Hermes worker option '{key}' must be a string path")
        normalized[key] = str(value)

    for key in ("check_id", "question"):
        value = worker_options.get(key)
        if value is None:
            continue
        if not isinstance(value, str):
            raise CliError("invalid_args", f"Hermes worker option '{key}' must be a string")
        normalized[key] = value

    resolved_model = worker_options.get("resolved_model")
    if resolved_model is not None:
        if not isinstance(resolved_model, str) or not resolved_model.strip():
            raise CliError("invalid_args", "Hermes worker option 'resolved_model' must be a non-empty string")
        normalized["resolved_model"] = resolved_model

    max_tokens = worker_options.get("max_tokens")
    if max_tokens is not None:
        try:
            normalized["max_tokens"] = int(max_tokens)
        except (TypeError, ValueError) as exc:
            raise CliError("invalid_args", "Hermes worker option 'max_tokens' must be an int") from exc
        if normalized["max_tokens"] <= 0:
            raise CliError("invalid_args", "Hermes worker option 'max_tokens' must be positive")

    reasoning_config = worker_options.get("reasoning_config")
    if reasoning_config is not None:
        if not isinstance(reasoning_config, dict):
            raise CliError("invalid_args", "Hermes worker option 'reasoning_config' must be a dict")
        normalized["reasoning_config"] = dict(reasoning_config)

    return normalized


def _import_hermes_runtime():
    """Resolve the vendored hermes runtime packages.

    The agent code now lives under ``arnold.agent``; ensure the agent directory
    is on ``sys.path`` so the vendored ``run_agent`` / ``hermes_state`` modules
    are resolvable by their legacy absolute names.
    """
    import importlib
    import sys
    from pathlib import Path

    import arnold.agent  # noqa: F401

    agent_dir = str(Path(arnold.agent.__file__).resolve().parent)
    if agent_dir not in sys.path:
        sys.path.insert(0, agent_dir)

    try:
        from run_agent import AIAgent
        from hermes_state import SessionDB
    except ImportError as exc:
        from arnold_pipelines.megaplan.types import CliError

        raise CliError(
            "agent_deps_missing",
            "hermes backend requires the bundled runtime packages: pip install arnold (or pip install -e . in a source checkout; '[agent]' is only a no-op compatibility extra).",
        ) from exc
    _install_content_tool_call_normalizer(AIAgent)
    return AIAgent, SessionDB


_CONTENT_TOOL_ALIASES = {
    "read": "read_file",
    "read_file": "read_file",
    "file_read": "read_file",
    "search": "search_files",
    "search_files": "search_files",
    "file_search": "search_files",
    "web_extract": "web_extract",
    "fetch_url": "web_extract",
    "web_search": "web_search",
}
_CONTENT_TOOL_NAMES = frozenset(_CONTENT_TOOL_ALIASES)
_CONTENT_ARG_ALIASES = {
    "read_file": {"filePath": "path", "filepath": "path"},
}
_XML_ATTR_RE = re.compile(
    r"(?P<key>[A-Za-z_][A-Za-z0-9_-]*)\s*=\s*"
    r"(?P<quote>[\"'])(?P<value>.*?)(?P=quote)",
    re.DOTALL,
)


def _coerce_xml_tool_value(raw: str) -> object:
    text = html.unescape(raw).strip()
    if re.fullmatch(r"-?\d+", text):
        try:
            return int(text)
        except ValueError:
            return text
    if re.fullmatch(r"-?(?:\d+\.\d*|\d*\.\d+)", text):
        try:
            return float(text)
        except ValueError:
            return text
    lowered = text.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered in {"null", "none"}:
        return None
    return text


def _make_content_tool_call(name: str, args: dict[str, object], index: int) -> SimpleNamespace:

--- FILE: arnold_pipelines/megaplan/workers/hermes.py (1720,1810p) ---
    fresh = fresh or step != "execute"
    if step == "execute" and os.getenv("MEGAPLAN_HERMES_EXECUTE_PERSIST_SESSION") != "1":
        fresh = True

    AIAgent, SessionDB = _import_hermes_runtime()
    # Logging is configured once at process startup by entry points such as
    # the CLI, gateway, and ACP adapter. Do not call configure_logging() from
    # this per-worker path: it mutates process-global logger state and is not
    # safe for in-process worker concurrency.

    project_dir = Path(state["config"]["project_dir"])
    plan_mode = state["config"].get("mode", "code")
    from arnold_pipelines.megaplan.schemas import get_execution_schema_key
    schema_name = (
        get_execution_schema_key(plan_mode, form=creative_form_id(state))
        if step == "execute"
        else STEP_SCHEMA_FILENAMES[step]
    )
    schema = read_json(schemas_root(root) / schema_name)
    normalized_worker_options = _normalize_worker_options(worker_options)
    from arnold_pipelines.megaplan.runtime.key_pool import resolve_model as _resolve_model, acquire_key, report_429
    resolved_model, agent_kwargs = _resolve_model(model)
    effective_resolved_model = str(normalized_worker_options.get("resolved_model") or resolved_model or "")
    explicit_output_path = output_path
    if explicit_output_path is None and normalized_worker_options.get("output_path"):
        explicit_output_path = Path(str(normalized_worker_options["output_path"]))
    template_path = normalized_worker_options.get("template_path")
    template_seed_path = (
        Path(str(template_path))
        if template_path is not None
        else None
    )
    template_seed_text: str | None = None
    if template_seed_path is not None and template_seed_path.exists():
        template_seed_text = template_seed_path.read_text(encoding="utf-8")
    output_path = explicit_output_path

    # Session management
    session_key = session_key_for(step, "hermes", model=model)
    session = state["sessions"].get(session_key, {})
    session_id = session.get("id") if not fresh else None

    # Reload conversation history for session continuity
    conversation_history = None
    if session_id:
        try:
            db = SessionDB()
            conversation_history = db.get_messages_as_conversation(session_id)
        except Exception:
            conversation_history = None

    # Generate new session ID if needed
    if not session_id:
        import uuid
        session_id = str(uuid.uuid4())

    toolsets = _toolsets_for_phase(step)
    seam_tier = ModelTier.ENFORCED if not toolsets else ModelTier.NON_ENFORCED

    # Build prompt — megaplan prompts embed the JSON schema, but some models
    # ignore formatting instructions buried in long prompts.  Append a clear
    # reminder so the final response is valid JSON, not markdown.
    prompt_text = prompt_override
    rendered_step = render_prompt_for_dispatch(
        "hermes",
        step,
        state,
        plan_dir,
        root=root,
        model=resolved_model,
        normalized_model=resolved_model,
        tier=seam_tier,
        schema=schema,
        prompt_override=prompt_text,
    )
    prompt = rendered_step.prompt
    # Add web search guidance only when the web toolset is actually enabled.
    # Local project files must be read with file tools; web_extract cannot
    # process file:// URLs or absolute local paths reliably.
    has_web_tools = bool(toolsets and "web" in toolsets)
    if has_web_tools and step in ("plan", "critique", "revise"):
        prompt += (
            "\n\nWEB SEARCH: You have web_search and web_extract tools. "
            "Use file tools for local repository paths; do not use web_extract "
            "for file:// URLs or absolute local filesystem paths. "
            "If the task involves a framework API you're not certain about — "
            "for example a specific Next.js feature, a particular import path, "
            "or a config flag that might have changed between versions — "
            "search for the current documentation before committing to an approach. "
            "Your training data may be outdated for newer framework features."
        )

--- FILE: arnold_pipelines/megaplan/runtime/key_pool.py (1,280p) ---
"""Dynamic API key pooling for Hermes-backed providers.

KeyPool is re-exported from the canonical SSoT at arnold.agent.providers.pool.
This module retains the megaplan-specific wrappers, blocking guards, and the
_pool singleton that wires envelope/governor context.
"""

from __future__ import annotations

import sys

# ---------------------------------------------------------------------------
# Re-export KeyPool from the SSoT (arnold.agent.providers.pool)
# ---------------------------------------------------------------------------
from arnold.agent.providers.pool import (  # noqa: F401
    KeyEntry,
    KeyPool as _BaseKeyPool,
    minimax_openrouter_model,
    resolve_kimi_base_url,
    _DEFAULT_BASE_URLS,
    _ENV_ALIASES,
    _PROVIDER_BASE_URL_VARS,
    _PROVIDER_KEY_VARS,
)

# KeyPathSource that resolves the megaplan api_keys.json path.
import os
from pathlib import Path
from arnold.agent.providers.pool import KeyPathSource as _KeyPathSource


class _MegaplanKeyPathSource:
    """Supplies the api_keys.json path for the megaplan-local key pool."""

    def keys_path(self) -> Path:
        override = os.environ.get("MEGAPLAN_API_KEYS_PATH")
        if override:
            return Path(override).expanduser()
        repo_root = Path(__file__).resolve().parents[1]
        candidates = (
            repo_root / "auto_improve" / "api_keys.json",
        )
        for path in candidates:
            if path.exists():
                return path
        return candidates[0]


class KeyPool(_BaseKeyPool):
    """Megaplan-aware key pool that charges the active Governor on acquire."""

    current_envelope = staticmethod(lambda: _current_envelope())

    def acquire(self, provider: str) -> str:
        key = super().acquire(provider)
        if key:
            _charge_governor_for_current_envelope(self)
        return key


_pool = KeyPool(keys_path_source=_MegaplanKeyPathSource())


def _current_envelope(*_args):  # type: ignore[no-untyped-def]
    """Return the envelope visible to this task via ContextVar, or ``None``.

    Wired onto _pool so governor/envelope integration works without subclassing.
    """
    from arnold.runtime.envelope import _envelope_ctx

    return _envelope_ctx.get()


def _load_hermes_env() -> dict[str, str]:
    return _pool.load_hermes_env()
def _get_api_credential(env_var: str, hermes_env: dict[str, str] | None = None) -> str:
    return _pool.get_api_credential(env_var, hermes_env)
def _charge_governor_for_current_envelope(pool: KeyPool | None = None) -> None:
    """Charge the governor for the current task envelope if one is active.

    Invoked outside the KeyPool lock so a BudgetExceeded raised here
    does not strand the pool lock.  charge() is a no-op when no governor
    is attached to this execution tree.
    """
    active_pool = pool or _pool
    envelope = active_pool.current_envelope()
    if envelope is not None:
        from arnold_pipelines.megaplan.runtime.governor import current_governor

        gov = current_governor()
        if gov is not None:
            gov.charge(envelope)


def acquire_key(provider: str) -> str:
    return _pool.acquire(provider)
def report_429(provider: str, key: str, cooldown_secs: float = 60) -> None:
    _pool.report_429(provider, key, cooldown_secs)
def report_failure(provider: str, key: str) -> None:
    _pool.report_failure(provider, key)
def has_keys(provider: str) -> bool:
    return _pool.has_keys(provider)
def _raise_claude_via_openrouter_blocked(reason: str) -> None:
    """Refuse to silently route Claude through OpenRouter.

    The harness historically defaulted bare hermes calls (model=None, or a
    non-prefixed ``anthropic/claude-*`` slash form) to OpenRouter's
    ``anthropic/claude-opus-4.6`` endpoint. That route consumes OPENROUTER_API_KEY
    quotas instead of the operator's Claude Code (shannon) subscription, and the
    fallback was completely silent. The user pays for Claude Code; they do not
    want Claude calls billed against OpenRouter without explicit opt-in.

    We block the silent path here and tell the caller exactly how to recover.
    Explicit ``openrouter:`` prefixed models still work — only the silent
    *default* is removed.
    """
    # Import lazily to keep this module import-cycle-safe (megaplan.types is
    # otherwise independent of megaplan.runtime, but the lazy import is
    # the cheapest insurance).
    from arnold_pipelines.megaplan.types import CliError

    raise CliError(
        code="claude_via_openrouter_blocked",
        message=(
            "Refusing to route Claude through OpenRouter. " + reason + " "
            "The megaplan harness silently defaulted Claude calls to "
            "anthropic/claude-opus-4.6 via OpenRouter, but the operator has a "
            "Claude Code subscription that should be used instead. Pick an "
            "explicit path:\n"
            "  --agent shannon   (use Claude Code, recommended)\n"
            "  --agent claude    (same as shannon)\n"
            "  --phase-model <phase>=claude:claude-opus-4-7:medium\n"
            "If you actually want OpenRouter for some reason, set the model "
            "explicitly with a provider prefix, e.g. "
            "--hermes openrouter:anthropic/claude-opus-4.6"
        ),
        valid_next=[
            "rerun with --agent shannon",
            "rerun with --phase-model <phase>=claude:claude-opus-4-7:medium",
            "rerun with --hermes openrouter:anthropic/claude-opus-4.6 (explicit)",
        ],
    )


def _is_claude_model_name(name: str) -> bool:
    lowered = name.lower()
    return (
        lowered.startswith("anthropic/claude")
        or lowered.startswith("claude-")
        or lowered.startswith("claude/")
    )


def _is_codex_model_name(name: str) -> bool:
    """Match codex gpt-5.x family (case-insensitive)."""
    lowered = name.lower()
    return lowered.startswith("gpt-5")


def _is_deepseek_model_name(name: str) -> bool:
    """Match bare deepseek model names (case-insensitive)."""
    lowered = name.lower()
    return lowered.startswith("deepseek-") or lowered.startswith("deepseek/")


def _fireworks_deepseek_model_name(name: str) -> str | None:
    """Return the bare DeepSeek model from a Fireworks model id, if present."""

    lowered = name.lower()
    marker = "/models/"
    candidate = name
    if marker in lowered:
        candidate = name[lowered.rfind(marker) + len(marker):]
    candidate = candidate.strip("/")
    if _is_deepseek_model_name(candidate):
        return candidate
    return None


def _raise_codex_via_openrouter_blocked(reason: str) -> None:
    """Refuse to silently route codex/gpt-5.x through OpenRouter.

    The harness would otherwise default bare ``gpt-5.5`` (etc.) to OpenRouter,
    silently consuming OPENROUTER_API_KEY quotas.  The user intends these models
    to run through the proper codex path, not OpenRouter.

    Explicit ``openrouter:`` prefixed models still work — only the silent
    *default* is removed.
    """
    from arnold_pipelines.megaplan.types import CliError

    raise CliError(
        code="codex_via_openrouter_blocked",
        message=(
            "Refusing to route codex/gpt-5.x through OpenRouter. " + reason + " "
            "Codex models (gpt-5.5, gpt-5.4, etc.) will not be silently billed "
            "to your OpenRouter key. Pick an explicit path:\n"
            "  --agent codex                    (use the codex vendor path)\n"
            "  --hermes openrouter:gpt-5.5      (explicit OpenRouter opt-in)\n"
            "If you actually want OpenRouter, set the model explicitly with "
            "an ``openrouter:`` prefix."
        ),
        valid_next=[
            "rerun with --agent codex",
            "rerun with --hermes openrouter:gpt-5.5 (explicit)",
        ],
    )


def _raise_generic_openrouter_blocked(reason: str) -> None:
    """Refuse to silently route an unrecognised model through OpenRouter.

    Any model not matching a known provider prefix or bare model guard
    MUST NOT silently fall through to OpenRouter.  The caller must use
    an explicit ``openrouter:`` prefix if they genuinely want OpenRouter.
    """
    from arnold_pipelines.megaplan.types import CliError

    raise CliError(
        code="openrouter_blocked",
        message=(
            "Refusing to silently route an unrecognised model through OpenRouter. "
            + reason
            + " "
            "To use OpenRouter, prefix the model with ``openrouter:``. "
            "To use a native provider, use the appropriate prefix "
            "(``deepseek:``, ``fireworks:``, ``google:``, ``kimi:``, "
            "``zhipu:``, ``minimax:``, ``mimo:``) or the ``hermes:`` agent."
        ),
        valid_next=[
            "rerun with --hermes openrouter:<model>",
            "rerun with --hermes deepseek:<model>",
            "rerun with --hermes kimi:<model>",
            "rerun with --hermes mimo:<model>",
            "rerun with --agent claude / --agent codex / --agent shannon",
        ],
    )


def resolve_model(model: str | None) -> tuple[str, dict[str, str]]:
    agent_kwargs: dict[str, str] = {}
    if model is None or not str(model).strip():
        # No model specified — the previous behaviour silently defaulted to
        # anthropic/claude-opus-4.6 via OpenRouter. Refuse that silent path.
        _raise_claude_via_openrouter_blocked(
            "No model was specified, so no provider could be selected."
        )
    resolved_model = str(model).strip()
    # Allow an explicit ``openrouter:`` prefix to opt into OpenRouter for any
    # model (Claude included). This is the documented escape hatch.
    if resolved_model.startswith("openrouter:"):
        resolved_model = resolved_model[len("openrouter:"):]
        agent_kwargs["base_url"] = _DEFAULT_BASE_URLS["openrouter"]
        agent_kwargs["api_key"] = acquire_key("openrouter")
        return resolved_model, agent_kwargs
    if resolved_model.startswith("zhipu:"):
        resolved_model = resolved_model[len("zhipu:"):]
        agent_kwargs["base_url"] = _get_api_credential(_PROVIDER_BASE_URL_VARS["zhipu"]) or _DEFAULT_BASE_URLS["zhipu"]
        agent_kwargs["api_key"] = acquire_key("zhipu")
    elif resolved_model.startswith("kimi:"):
        resolved_model = resolved_model[len("kimi:"):]
        kimi_key = acquire_key("kimi")
        agent_kwargs["api_key"] = kimi_key
        agent_kwargs["base_url"] = resolve_kimi_base_url(
            kimi_key,
            _DEFAULT_BASE_URLS["kimi"],
            _get_api_credential(_PROVIDER_BASE_URL_VARS["kimi"]),
        )
    elif resolved_model.startswith("google:"):
        resolved_model = resolved_model[len("google:"):]
        agent_kwargs["base_url"] = _DEFAULT_BASE_URLS["google"]
        agent_kwargs["api_key"] = acquire_key("google")
    elif resolved_model.startswith("deepseek:"):
        resolved_model = resolved_model[len("deepseek:"):]
        agent_kwargs["base_url"] = _get_api_credential(_PROVIDER_BASE_URL_VARS["deepseek"]) or _DEFAULT_BASE_URLS["deepseek"]
        agent_kwargs["api_key"] = acquire_key("deepseek")
    elif resolved_model.startswith("fireworks:"):
        resolved_model = resolved_model[len("fireworks:"):]
        direct_deepseek_model = _fireworks_deepseek_model_name(resolved_model)
        if direct_deepseek_model is not None:

--- FILE: arnold_pipelines/megaplan/orchestration/parallel_critique.py (130,220p) ---
        :func:`~megaplan._core.scatter_worker_units` instead.  This
        function is retained only so existing tests that import it
        continue to compile.
    """
    import uuid as _uuid

    from arnold_pipelines.megaplan._core import with_429_openrouter_fallback as _with_429_fallback
    from arnold_pipelines.megaplan.workers.hermes import (
        _import_hermes_runtime,
        _pre_dispatch_budget_check,
        _streaming_run_kwargs,
        _toolsets_for_phase,
        _worker_db_path,
        clean_parsed_payload,
        parse_agent_output,
    )
    from arnold_pipelines.megaplan.runtime.key_pool import resolve_model as _resolve_model

    AIAgent, SessionDB = _import_hermes_runtime()

    _critique_db_path = _worker_db_path(plan_dir, f"critique_{check['id']}")
    output_path = write_single_check_template(plan_dir, state, check, f"critique_check_{check['id']}.json")
    prompt_builder = (
        single_check_critique_joke_prompt
        if state.get("config", {}).get("mode", "code") == "joke"
        else single_check_critique_prompt
    )
    prompt = prompt_builder(state, plan_dir, root, check, output_path)
    resolved_model, agent_kwargs = _resolve_model(model)

    _model_lower = (resolved_model or "").lower()
    _reasoning_families = ("qwen/qwen3", "deepseek/deepseek-r1")
    _reasoning_off = (
        {"enabled": False}
        if any(_model_lower.startswith(prefix) for prefix in _reasoning_families)
        else None
    )

    # Cap output tokens to match the main-line hermes worker (Qwen repetition
    # mitigation). Drives the Fireworks streaming gate below.
    agent_max_tokens = 32768
    _stream = output_stream if output_stream is not None else sys.stderr

    def _make_agent(m: str, kw: dict) -> "AIAgent":
        a = AIAgent(
            model=m,
            quiet_mode=True,
            skip_context_files=True,
            skip_memory=True,
            enabled_toolsets=_toolsets_for_phase("critique"),
            session_id=str(_uuid.uuid4()),
            session_db=SessionDB(db_path=_critique_db_path),
            max_tokens=agent_max_tokens,
            reasoning_config=_reasoning_off,
            **kw,
        )
        a._print_fn = lambda *args, **kwargs: print(*args, **kwargs, file=_stream)
        return a

    def _failure_reason(exc: Exception) -> str:
        if isinstance(exc, CliError):
            return exc.message
        return str(exc) or exc.__class__.__name__

    def _run_attempt(current_agent, current_output_path: Path, *, current_model: str | None = None) -> tuple[dict[str, Any], dict[str, Any], list[str], list[str], float, int, int, int]:
        # Force streaming for providers that require it at this max_tokens
        # (Fireworks rejects max_tokens > 4096 unless stream=true).  The
        # streaming response is reassembled into the same shape non-streaming
        # would return — downstream code is unchanged.
        run_kwargs = _streaming_run_kwargs(current_model or model, agent_max_tokens)
        # _pre_dispatch_budget_check sentinel: budget guard for dispatch
        _pre_dispatch_budget_check(
            current_agent,
            conversation_history=None,
            user_message=prompt,
            system=None,
            tool_manifest=None,
            schema=schema,
            step="critique",
            model_name=getattr(current_agent, "model", current_model or model),
            tier=ModelTier.NON_ENFORCED,
            worker="hermes",
        )
        current_result = current_agent.run_conversation(
            user_message=prompt,
            **run_kwargs,
        )
        try:
            payload, raw_output = parse_agent_output(
                current_agent,
                current_result,

--- FILE: arnold_pipelines/megaplan/review/parallel.py (1,220p) ---
"""Parallel Hermes review runner.

The preloaded-template-ID convention is the preferred way to get structured
output from focused review agents: write the exact slot shape first, then have
each agent fill that file instead of inventing IDs in free-form JSON.

This module intentionally mirrors `megaplan.orchestration.parallel_critique` so the two phase
runners remain easy to compare and later extract into a shared utility.
"""

from __future__ import annotations

import argparse
import re
import time
from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan._core import WorkerUnit, WorkerUnitResult, load_flag_registry, read_json, schemas_root, scatter_worker_units
from arnold_pipelines.megaplan.model_seam import ModelTier
from arnold_pipelines.megaplan.prompts.review import (
    _filtered_prior_flags,
    _write_criteria_verdict_review_template,
    _write_single_check_review_template,
    parallel_criteria_review_prompt,
    single_check_review_prompt,
)
from arnold_pipelines.megaplan.types import AgentMode, CliError, PlanState
from arnold_pipelines.megaplan.workers import STEP_SCHEMA_FILENAMES, WorkerResult
from arnold_pipelines.megaplan.workers.result_metadata import aggregate_rate_limits

from arnold_pipelines.megaplan.runtime.key_pool import (
    resolve_model as _resolve_model,
)


def _clean_review_check_payload(payload: dict[str, Any]) -> None:
    checks = payload.get("checks")
    if not isinstance(checks, list):
        return
    for check in checks:
        if not isinstance(check, dict):
            continue
        check.pop("guidance", None)
        check.pop("prior_findings", None)


def _merge_unique(groups: list[list[str]]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for item in group:
            if item not in seen:
                seen.add(item)
                merged.append(item)
    return merged


def _review_worker_db_path(plan_dir: Path, identifier: str) -> Path:
    sanitized = re.sub(r"[^a-zA-Z0-9_-]", "_", identifier)
    sanitized = re.sub(r"_+", "_", sanitized).strip("_")
    if len(sanitized) > 100:
        sanitized = sanitized[:100]
    return plan_dir / ".hermes_state" / f"state_{sanitized or 'default'}.db"


def _review_reasoning_config(resolved_model: str | None) -> dict[str, bool] | None:
    model_lower = (resolved_model or "").lower()
    reasoning_families = ("qwen/qwen3", "deepseek/deepseek-r1")
    if any(model_lower.startswith(prefix) for prefix in reasoning_families):
        return {"enabled": False}
    return None


def _review_agent_mode(model: str | None, resolved_model: str | None) -> AgentMode:
    return AgentMode(
        agent="hermes",
        mode="persistent",
        refreshed=False,
        model=model,
        resolved_model=resolved_model,
    )


def _review_worker_options(
    *,
    output_path: Path,
    session_db_path: Path,
    resolved_model: str | None,
) -> dict[str, object]:
    options: dict[str, object] = {
        "output_path": str(output_path),
        "template_path": str(output_path),
        "session_db_path": str(session_db_path),
        "max_tokens": 32768,
    }
    if resolved_model:
        options["resolved_model"] = resolved_model
    reasoning_config = _review_reasoning_config(resolved_model)
    if reasoning_config is not None:
        options["reasoning_config"] = reasoning_config
    return options


def _parse_parallel_review_result(
    index: int,
    item: WorkerUnitResult,
    unit: WorkerUnit,
) -> tuple[int, dict[str, Any], list[str], list[str], float, int, int, int, dict[str, Any] | None]:
    del index
    payload = item.payload
    if not isinstance(payload, dict):
        raise CliError("worker_parse_error", "Review worker payload must be a dict")
    _clean_review_check_payload(payload)
    payload_checks = payload.get("checks")
    if not isinstance(payload_checks, list) or len(payload_checks) != 1 or not isinstance(payload_checks[0], dict):
        check_id = unit.extra.get("check_id", "?")
        raise CliError(
            "worker_parse_error",
            f"Parallel review output for check '{check_id}' did not contain exactly one check",
            extra={"raw_output": item.raw_output},
        )
    verified = payload.get("verified_flag_ids", [])
    disputed = payload.get("disputed_flag_ids", [])
    return (
        int(unit.extra.get("index", 0) or 0),
        payload_checks[0],
        verified if isinstance(verified, list) else [],
        disputed if isinstance(disputed, list) else [],
        item.cost_usd,
        item.prompt_tokens,
        item.completion_tokens,
        item.total_tokens,
        item.rate_limit,
    )


def _parse_parallel_review_side_result(
    index: int,
    item: WorkerUnitResult,
    unit: WorkerUnit,
) -> tuple[dict[str, Any], float, int, int, int, dict[str, Any] | None]:
    del index, unit
    payload = item.payload
    if not isinstance(payload, dict):
        raise CliError("worker_parse_error", "Review criteria payload must be a dict")
    return (
        payload,
        item.cost_usd,
        item.prompt_tokens,
        item.completion_tokens,
        item.total_tokens,
        item.rate_limit,
    )


def run_parallel_review(
    state: PlanState,
    plan_dir: Path,
    *,
    root: Path,
    model: str | None,
    checks: tuple[Any, ...],
    pre_check_flags: list[dict[str, Any]],
    max_concurrent: int | None = None,
) -> WorkerResult:
    started = time.monotonic()
    read_json(schemas_root(root) / STEP_SCHEMA_FILENAMES["review"])
    prior_flags = load_flag_registry(plan_dir).get("flags", [])
    resolved_model, _agent_kwargs = _resolve_model(model)
    resolved = _review_agent_mode(model, resolved_model)
    schema = read_json(schemas_root(root) / STEP_SCHEMA_FILENAMES["review"])

    units: list[WorkerUnit] = []
    for index, check in enumerate(checks):
        check_id = check["id"] if isinstance(check, dict) else getattr(check, "id")
        output_path = _write_single_check_review_template(plan_dir, state, check, f"review_check_{check_id}.json")
        prompt = single_check_review_prompt(
            state,
            plan_dir,
            root,
            check,
            output_path,
            pre_check_flags,
            _filtered_prior_flags(check, prior_flags),
        )
        units.append(
            WorkerUnit(
                step="review",
                resolved=resolved,
                prompt=prompt,
                output_path=output_path,
                read_only=True,
                validation_step="review",
                schema=schema,
                model=resolved_model,
                tier=ModelTier.ENFORCED,
                extra={
                    "index": index,
                    "check_id": check_id,
                    "ledger_step_label": check_id,
                    "worker_options": _review_worker_options(
                        output_path=output_path,
                        session_db_path=_review_worker_db_path(plan_dir, f"review_{check_id}"),
                        resolved_model=resolved_model,
                    ),
                },
            )
        )

    criteria_output_path = _write_criteria_verdict_review_template(plan_dir, state, "review_criteria_verdict.json")
    criteria_unit = WorkerUnit(
        step="review",
        resolved=resolved,
        prompt=parallel_criteria_review_prompt(state, plan_dir, root, criteria_output_path),
        output_path=criteria_output_path,
        read_only=True,
        validation_step="review",
        schema=schema,
        model=resolved_model,
