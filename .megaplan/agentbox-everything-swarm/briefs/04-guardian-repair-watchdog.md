You are a DeepSeek subagent doing a read-only inventory for AgentBox. The user asked us to find EVERYTHING existing in this repo/local skills that overlaps with the desired Discord-first AgentBox: start tickets/epics/megaplans/chains from Discord, Guardian repairs/relaunches blocked runs, completed work gets pushed/PRd/consolidated, and DeepSeek/subagents can be used. The brief embeds local excerpts. Return a decisive inventory of reusable mechanics, with file refs, gaps, and concrete recommendations. Under 1200 words. Focus: Guardian repairs/relaunches blocked/stuck runs. Find watchdog, recovery, repair, supervise, scheduler mechanics to reuse.


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

--- FILE: scripts/megaplan_live_watchdog.py (1,260p) ---
#!/usr/bin/env python3
"""Megaplan Live Watchdog Supervisor CLI.

Scans the machine for likely-live Megaplan/Arnold runs, classifies their
health via the ``live-supervisor`` Arnold pipeline, and orchestrates a bounded
repair/relaunch/recheck loop for problem incidents.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from arnold.execution import run
from arnold.execution.backend import SkeletalBackend
from arnold.workflow import compile_pipeline
from arnold_pipelines.megaplan.pipelines.live_supervisor import build_pipeline
from arnold_pipelines.megaplan.pipelines.live_supervisor.model import HealthCategory, Triage
from arnold_pipelines.megaplan.watchdog.discovery import DEFAULT_SCAN_ROOTS
from arnold_pipelines.megaplan.watchdog.log import DEFAULT_LOG_PATH, log_event, setup_logging
from arnold_pipelines.megaplan.watchdog.registry import Observation, WatchdogRegistry
from arnold_pipelines.megaplan.watchdog.repair_runner import RepairRunner
from arnold_pipelines.megaplan.watchdog.retry import RetryLoop, RetryOutcome
from arnold_pipelines.megaplan.watchdog.snapshot import build_snapshot


DEFAULT_REGISTRY_PATH = "~/.megaplan/watchdog/registry.ndjson"


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Megaplan Live Watchdog Supervisor")
    parser.add_argument("--once", action="store_true", help="Run a single scan and exit.")
    parser.add_argument(
        "--roots",
        type=str,
        default=",".join(DEFAULT_SCAN_ROOTS),
        help="Comma-separated list of roots to scan.",
    )
    parser.add_argument(
        "--repair-runner",
        choices=("subprocess", "dry-run"),
        default="subprocess",
        help="How to execute allowlisted repair commands.",
    )
    parser.add_argument(
        "--report-path",
        type=str,
        default=None,
        help="Path for the JSON report (default: stdout).",
    )
    parser.add_argument(
        "--registry-path",
        type=str,
        default=DEFAULT_REGISTRY_PATH,
        help="Path to the NDJSON registry.",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Maximum repair attempts per incident.",
    )
    parser.add_argument(
        "--recheck-seconds",
        type=int,
        default=0,
        help="Seconds to wait between repair attempts (default 0 to avoid CLI hangs).",
    )
    parser.add_argument(
        "--recheck-after-seconds",
        type=int,
        default=0,
        help=(
            "After a successful repair, wait this many seconds and run a full "
            "recheck to verify the plan recovered. 0 disables post-repair recheck."
        ),
    )
    parser.add_argument(
        "--lookback-hours",
        type=float,
        default=24.0,
        help=(
            "Only include plans with a live process or recent activity "
            "(state/event mtime) within this many hours. Use 0 for no limit."
        ),
    )
    parser.add_argument(
        "--log-path",
        type=str,
        default=DEFAULT_LOG_PATH,
        help="Path to the watchdog log file.",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        help="Log level.",
    )
    return parser.parse_args(argv)


def _run_pipeline_once(snapshot_dict: dict[str, Any]) -> dict[str, Any]:
    """Run the live-supervisor workflow manifest and return artifact contents.

    M5 Phase 3: the pipeline is now an explicit-node ``arnold.workflow.Pipeline``
    executed through the neutral manifest runtime. The skeletal backend proves
    compile/run compatibility; a product-specific backend adapter is required to
    re-hydrate the legacy step artifacts (classifications.json, diagnoses.json,
    repair_decisions.json, recheck_emit.json) in a later phase.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        manifest = compile_pipeline(build_pipeline())
        run(
            manifest,
            artifact_root=tmpdir,
            backend=SkeletalBackend(),
        )
        # The legacy step shells are preserved for reference but are not
        # executed by the neutral runtime. Return an empty artifact mapping
        # until a Megaplan backend adapter is wired.
        artifacts: dict[str, Any] = {}
        artifact_names = {
            "classify": "classifications.json",
            "diagnose": "diagnoses.json",
            "repair_decision": "repair_decisions.json",
            "recheck_emit": "recheck_emit.json",
        }
        for stage, filename in artifact_names.items():
            artifact_path = Path(tmpdir) / stage / filename
            if artifact_path.is_file():
                artifacts[stage] = json.loads(artifact_path.read_text(encoding="utf-8"))
        return artifacts


_TERMINAL_STATES: frozenset[str] = frozenset({
    "completed",
    "failed",
    "aborted",
    "resolved",
    "cancelled",
    "finalized",
    "executed",
    "done",
    "reviewed",
    "accepted",
})


def _is_terminal_state(state: dict[str, Any] | None) -> bool:
    if not state:
        return False
    current = state.get("current_state")
    if isinstance(current, str) and current in _TERMINAL_STATES:
        return True
    return state.get("status") in _TERMINAL_STATES


def _is_stale_lock_only(incident: dict[str, Any]) -> bool:
    """True if the only doctor finding is a stale_lock and the plan has no live process."""
    signals = incident.get("signals", {})
    findings = signals.get("doctor_findings", [])
    if incident.get("triage") == Triage.LIVE.value:
        return False
    return len(findings) == 1 and findings[0].get("check") == "stale_lock"


def _select_problem_incidents(
    artifacts: dict[str, Any],
    incidents: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return non-all_good classifications split into problems and cleanup candidates.

    Terminal plans whose only issue is a stale lock are considered cleanup
    candidates, not active problems. Results are sorted so live/recent plans
    come first, then by most recent activity.
    """
    classifications = artifacts.get("classify", [])
    decisions = artifacts.get("repair_decision", [])
    decision_by_plan = {d["plan_id"]: d for d in decisions}
    incident_by_plan: dict[str, dict[str, Any]] = {i["plan_entry"]["plan_id"]: i for i in incidents}

    triage_order = {
        Triage.LIVE.value: 0,
        Triage.RECENT.value: 1,
        Triage.MAYBE_LIVE.value: 2,
        Triage.STALE.value: 3,
    }

    problems: list[dict[str, Any]] = []
    cleanup_candidates: list[dict[str, Any]] = []
    for classification in classifications:
        if classification["health_category"] == HealthCategory.ALL_GOOD.value:
            continue
        plan_id = classification["plan_id"]
        incident = incident_by_plan.get(plan_id, {})
        plan_entry = incident.get("plan_entry", {})
        signals = incident.get("signals", {})
        triage = incident.get("triage", Triage.STALE.value)
        last_event_age = signals.get("last_event_age_seconds") or float("inf")
        item = {
            "plan_id": plan_id,
            "health_category": classification["health_category"],
            "triage": triage,
            "last_event_age_seconds": last_event_age,
            "decision": decision_by_plan.get(plan_id, {}),
        }
        if _is_terminal_state(plan_entry.get("state")) and _is_stale_lock_only(incident):
            cleanup_candidates.append(item)
        else:
            problems.append(item)

    sort_key = lambda p: (triage_order.get(p["triage"], 99), p["last_event_age_seconds"])
    problems.sort(key=sort_key)
    cleanup_candidates.sort(key=sort_key)
    return problems, cleanup_candidates


def _run_repair(
    problem: dict[str, Any],
    runner: RepairRunner,
    max_retries: int,
    recheck_seconds: int,
    logger: logging.Logger,
) -> dict[str, Any]:
    """Run the bounded retry loop for one problem incident."""
    loop = RetryLoop(max_attempts=max_retries)
    attempts: list[dict[str, Any]] = []
    plan_id = problem["plan_id"]
    log_event(logger, "repair_start", plan_id=plan_id, health_category=problem.get("health_category"), triage=problem.get("triage"))

    while True:
        verdict = problem["decision"].get("verdict", {})
        action = verdict.get("action")
        if not action or not verdict.get("allowed"):
            outcome = RetryOutcome.UNRESOLVED
            reason = verdict.get("reason", "no allowed action")
            log_event(logger, "repair_skipped", plan_id=plan_id, reason=reason)
            attempts.append({"outcome": outcome.value, "reason": reason})
        else:
            command = action["command"]
            context = problem["decision"].get("context", {})
            plan_dir = context.get("plan_dir")
            project_dir = context.get("project_dir") or (
                str(Path(plan_dir).parents[2]) if plan_dir else None
            )
            log_event(logger, "repair_attempt", plan_id=plan_id, command=command, plan_dir=plan_dir, project_dir=project_dir)
            result = runner.run(command, plan_dir=plan_dir, project_dir=project_dir)
            attempts.append(
                {
                    "command": command,
                    "status": result.status,
                    "rc": result.rc,
                    "stdout": result.stdout,

--- FILE: scripts/megaplan_live_watchdog.py (260,560p) ---
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                }
            )
            if result.status == "success":
                outcome = RetryOutcome.RESOLVED
                log_event(logger, "repair_success", plan_id=plan_id, command=command)
            elif result.status == "command_unavailable":
                outcome = RetryOutcome.UNRESOLVED
                log_event(logger, "repair_unavailable", plan_id=plan_id, command=command, stderr=result.stderr)
            else:
                outcome = RetryOutcome.UNRESOLVED
                log_event(logger, "repair_failed", plan_id=plan_id, command=command, rc=result.rc, stderr=result.stderr)

        result, done = loop.attempt(outcome)
        if done:
            log_event(logger, "repair_final", plan_id=plan_id, final_outcome=result.value, attempt_count=loop.attempt_count)
            return {
                "plan_id": plan_id,
                "final_outcome": result.value,
                "attempt_count": loop.attempt_count,
                "attempts": attempts,
            }

        if recheck_seconds > 0:
            log_event(logger, "repair_recheck_wait", plan_id=plan_id, seconds=recheck_seconds)
            time.sleep(recheck_seconds)


def _record_observations_and_transitions(
    registry: WatchdogRegistry,
    snapshot: Any,
    classifications: list[dict[str, Any]],
    now: float,
    logger: logging.Logger,
) -> list[dict[str, Any]]:
    """Compute lifecycle transitions and record per-plan observations."""
    classification_by_plan = {c["plan_id"]: c["health_category"] for c in classifications}
    incident_by_plan = {i.plan_entry.plan_id: i for i in snapshot.incidents}
    current_observations: dict[str, Observation] = {}

    for plan in snapshot.plans:
        incident = incident_by_plan.get(plan.plan_id)
        triage = incident.triage.value if incident is not None else "unknown"
        has_live_process = incident is not None and incident.triage is Triage.LIVE
        state = plan.state.get("current_state") if isinstance(plan.state, dict) else None
        health_category = classification_by_plan.get(plan.plan_id, "unknown")

        current_observations[plan.plan_id] = Observation(
            ts=now,
            state=state,
            triage=triage,
            health_category=health_category,
            has_live_process=has_live_process,
        )

    # Plans that were in the registry but are no longer discovered.
    for entry in registry:
        if entry.plan_id in current_observations:
            continue
        current_observations[entry.plan_id] = Observation(
            ts=now,
            state=None,
            triage="disappeared",
            health_category="unknown",
            has_live_process=False,
        )

    # Compute transitions against the previously recorded observations, then persist.
    transitions = registry.compute_transitions(current_observations, now=now)
    for transition in transitions:
        log_event(
            logger,
            "plan_transition",
            plan_id=transition.plan_id,
            previous_status=transition.previous_status.value,
            current_status=transition.current_status.value,
            previous_state=transition.previous_state or "",
            current_state=transition.current_state or "",
        )

    for plan_id, observation in current_observations.items():
        registry.record_observation(plan_id, observation, now=now)

    return [t.to_dict() for t in transitions]


def _run_scan(
    args: argparse.Namespace,
    registry: WatchdogRegistry,
    logger: logging.Logger,
    iteration: int = 1,
) -> dict[str, Any]:
    """One scan/classify/repair/report cycle. Returns the report dict."""
    roots = tuple(r.strip() for r in args.roots.split(",") if r.strip())
    log_event(
        logger,
        "scan_start",
        iteration=iteration,
        roots=",".join(roots),
        lookback_hours=args.lookback_hours,
        repair_runner=args.repair_runner,
        max_retries=args.max_retries,
    )

    max_age_hours = None if args.lookback_hours <= 0 else args.lookback_hours
    snapshot = build_snapshot(roots=roots, max_age_hours=max_age_hours, logger=logger)
    snapshot_dict = snapshot.to_dict()

    log_event(
        logger,
        "snapshot_built",
        iteration=iteration,
        plans_found=len(snapshot.plans),
        incidents=len(snapshot.incidents),
        live_incidents=sum(1 for i in snapshot.incidents if i.triage.value == "live"),
        recent_incidents=sum(1 for i in snapshot.incidents if i.triage.value == "recent"),
        stale_incidents=sum(1 for i in snapshot.incidents if i.triage.value == "stale"),
    )

    registry.update_seen(snapshot.plans)
    registry.mark_disappeared(
        [e.plan_id for e in registry],
        [p.plan_id for p in snapshot.plans],
    )

    artifacts = _run_pipeline_once(snapshot_dict)
    classifications = artifacts.get("classify", [])
    problems, cleanup_candidates = _select_problem_incidents(
        artifacts, [i.to_dict() for i in snapshot.incidents]
    )

    incident_by_plan = {i.plan_entry.plan_id: i for i in snapshot.incidents}
    transitions = _record_observations_and_transitions(
        registry,
        snapshot,
        classifications,
        time.time(),
        logger,
    )

    log_event(
        logger,
        "classify_complete",
        iteration=iteration,
        problem_incidents=len(problems),
        cleanup_candidates=len(cleanup_candidates),
        transitions=len(transitions),
    )
    for problem in problems:
        log_event(
            logger,
            "problem_classified",
            iteration=iteration,
            plan_id=problem["plan_id"],
            health_category=problem["health_category"],
            triage=problem["triage"],
            recommended_command=problem["decision"].get("recommended_command"),
            allowed=problem["decision"].get("verdict", {}).get("allowed"),
        )
    for candidate in cleanup_candidates:
        log_event(
            logger,
            "cleanup_candidate",
            iteration=iteration,
            plan_id=candidate["plan_id"],
            health_category=candidate["health_category"],
            recommended_command=candidate["decision"].get("recommended_command"),
        )

    runner: RepairRunner
    if args.repair_runner == "dry-run":
        runner = RepairRunner(executable_search_path="")
    else:
        runner = RepairRunner()

    repair_results = []
    for problem in problems:
        result = _run_repair(
            problem,
            runner,
            max_retries=args.max_retries,
            recheck_seconds=args.recheck_seconds,
            logger=logger,
        )
        repair_results.append(result)
        registry.bump_retry(problem["plan_id"])

    registry.save()
    log_event(logger, "registry_saved", path=args.registry_path, entries=len(list(registry)))

    transition_summary: dict[str, list[str]] = {}
    for transition in transitions:
        transition_summary.setdefault(transition["current_status"], []).append(
            transition["plan_id"]
        )

    current_status_summary: dict[str, list[str]] = {}
    for plan in snapshot.plans:
        incident = incident_by_plan.get(plan.plan_id)
        status = "running" if incident is not None and incident.triage is Triage.LIVE else "idle"
        current_status_summary.setdefault(status, []).append(plan.plan_id)

    report = {
        "iteration": iteration,
        "scan_ts_utc": snapshot.scan_ts_utc,
        "roots": roots,
        "lookback_hours": args.lookback_hours,
        "plans_found": [p.plan_id for p in snapshot.plans],
        "currently_running": current_status_summary.get("running", []),
        "problem_incidents": problems,
        "cleanup_candidates": cleanup_candidates,
        "transitions": transitions,
        "transition_summary": transition_summary,
        "repair_results": repair_results,
        "artifacts": artifacts,
    }

    log_event(
        logger,
        "scan_complete",
        iteration=iteration,
        problem_incidents=len(problems),
        cleanup_candidates=len(cleanup_candidates),
        transitions=len(transitions),
        repair_attempts=sum(r["attempt_count"] for r in repair_results),
    )
    return report


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    logger = setup_logging(log_path=args.log_path, level=args.log_level)
    registry = WatchdogRegistry(Path(args.registry_path).expanduser())

    reports: list[dict[str, Any]] = []
    report = _run_scan(args, registry, logger, iteration=1)
    reports.append(report)

    # Optional post-repair recheck: wait and scan again to verify recovery.
    if args.recheck_after_seconds > 0:
        any_success = any(
            any(a.get("status") == "success" for a in r.get("attempts", []))
            for r in report.get("repair_results", [])
        )
        if any_success:
            log_event(
                logger,
                "recheck_wait",
                seconds=args.recheck_after_seconds,
            )
            time.sleep(args.recheck_after_seconds)
            recheck_report = _run_scan(args, registry, logger, iteration=2)
            reports.append(recheck_report)

    combined = {
        "reports": reports,
        "final_problem_incidents": reports[-1].get("problem_incidents", []),
        "final_cleanup_candidates": reports[-1].get("cleanup_candidates", []),
        "final_currently_running": reports[-1].get("currently_running", []),
    }

    if args.report_path:
        report_path = Path(args.report_path)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(combined, indent=2), encoding="utf-8")
        log_event(logger, "report_saved", path=str(report_path))
    else:
        print(json.dumps(combined, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())

--- FILE: arnold_pipelines/megaplan/cloud/supervise.py (1,320p) ---
"""Cloud chain supervisor — one-shot tick logic.

The supervisor observes a chain and makes safe progress decisions without
human approval.  It may restart missing runners and surface recoverable
blockers but must not invent approvals or force destructive git operations.
"""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path, PurePosixPath
from typing import Any


# ---------------------------------------------------------------------------
# Shared command helpers (imported from cli to keep session/log/env/quotes
# consistent across all entry points).
# ---------------------------------------------------------------------------

def _chain_tick_command(remote_spec_path: str, *, one_shot: bool = False) -> str:
    """Canonical ``megaplan chain start`` command string.

    session name, log path, trusted env, and quoting are shared with
    ``_run_chain_wrapper()`` via the same helper in ``megaplan.cloud.cli``.

    **M5d boundary note:** This function lives in the cloud tier, which is a
    long-lived host *above* the supervisor tier.  Cloud wraps the supervisor
    as a tick host and is explicitly anti-scope for M5d — it continues to
    construct and execute ``megaplan chain start`` commands regardless of
    whether the chain runner routes through the old engine or the new
    ``MEGAPLAN_SUPERVISOR_TIER=1`` path.  Cloud is not ported in M5d.
    """
    from arnold_pipelines.megaplan.cloud.cli import _chain_start_command as _cmd

    return _cmd(remote_spec_path, one_shot=one_shot)


def _remote_sync_refresh_command(
    workspace: str,
    remote_spec: str,
    *,
    branch: str | None = None,
    pr_number: int | None = None,
    extra_repos: list[str] | None = None,
    resolved_workspace: str | None = None,
    chain_session: str | None = None,
) -> str:
    """Construct a remote Python one-liner that calls ``_capture_sync_state``
    on the cloud runner.

    Every value interpolated into the Python snippet is a Python literal
    (via :func:`json.dumps` or :func:`repr`) — **not** :func:`shlex.quote`,
    which would produce bare identifiers instead of string literals.
    ``shlex.quote`` is used only for shell boundaries (``cd <workspace>``,
    ``python3 -c <snippet>``).
    """
    snippet = (
        "from arnold_pipelines.megaplan.chain import _capture_sync_state, ChainState, save_chain_state, load_chain_state; "
        "from pathlib import Path; "
        "_capture_sync_state("
        f"Path({json.dumps(workspace)}), Path({json.dumps(remote_spec)}), "
        f"branch={json.dumps(branch) if branch is not None else 'None'}, "
        f"pr_number={repr(pr_number)}, "
        f"extra_repos={json.dumps(extra_repos) if extra_repos is not None else 'None'}); "
    )
    # Persist resolved workspace and session into remote chain state so
    # subsequent status reads pick them up even without marker/chain_state
    # pre-population.
    if resolved_workspace or chain_session:
        snippet += (
            "s = load_chain_state(Path({})); ".format(json.dumps(remote_spec))
        )
        if resolved_workspace:
            snippet += (
                "s.resolved_workspace = {}; ".format(json.dumps(resolved_workspace))
            )
        if chain_session:
            snippet += (
                "s.chain_session = {}; ".format(json.dumps(chain_session))
            )
        snippet += (
            "save_chain_state(Path({}), s)".format(json.dumps(remote_spec))
        )
    return f"cd {shlex.quote(workspace)} && python3 -c {shlex.quote(snippet)}"


def _remote_pr_state_command(workspace: str, pr_number: int) -> str:
    """Return a shell command that probes the remote PR merge state."""
    return (
        f"cd {shlex.quote(workspace)} && "
        f"gh pr view {pr_number} --json state --jq .state 2>/dev/null "
        f"|| echo unknown"
    )


# ---------------------------------------------------------------------------
# Tick report builder
# ---------------------------------------------------------------------------

def _tick_report(
    *,
    success: bool,
    event: str,
    spec: str,
    effective_status: str,
    next_action: str,
    acted: bool,
    refused_reason: str | None,
    runner: dict[str, Any],
    sync: dict[str, Any],
    pr: dict[str, Any],
    logs: dict[str, Any],
    sync_refresh: dict[str, Any] | None = None,
    provider_consistency: dict[str, Any] | None = None,
    extra_repo_sync: list[dict[str, Any]] | None = None,
    human_verification: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the canonical supervisor tick report dict."""
    report: dict[str, Any] = {
        "success": success,
        "event": event,
        "spec": spec,
        "effective_status": effective_status,
        "next_action": next_action,
        "acted": acted,
        "refused_reason": refused_reason,
        "runner": runner,
        "sync": sync,
        "pr": pr,
        "logs": logs,
    }
    if sync_refresh is not None:
        report["sync_refresh"] = sync_refresh
    if provider_consistency is not None:
        report["provider_consistency"] = provider_consistency
    if extra_repo_sync is not None:
        report["extra_repo_sync"] = extra_repo_sync
    if human_verification is not None:
        report["human_verification"] = human_verification
    return report


# ---------------------------------------------------------------------------
# Safe action policy
# ---------------------------------------------------------------------------

# Statuses the supervisor will **never** mutate.
READ_ONLY_STATUSES = frozenset({
    "running",
    "complete",
    "human_prerequisite",
    "quality_gate",
})

# Statuses that trigger a read-only refusal (no mutation).
BLOCKED_REFUSAL_REASONS: dict[str, str] = {
    "human_prerequisite": "human prerequisite policy is 'required' and unmet; "
    "a human operator must resolve it via `megaplan user-action resolve` "
    "or `megaplan chain override`",
    "quality_gate": "validation policy is 'required' and quality gate is failing; "
    "a human operator must resolve the blocker or accept with debt",
}


# ---------------------------------------------------------------------------
# Main tick logic
# ---------------------------------------------------------------------------

def cloud_supervise_tick(
    root: Path,
    args: argparse.Namespace,
    spec: Any,
    provider: Any,
) -> dict[str, Any]:
    """Run a single supervisor tick and return a structured report.

    (a) Read chain status via ``cloud_chain_status_payload()``.
    (b) Refresh branch/PR/extra-repo sync (before any decisions).
    (c) Re-read ``cloud_chain_status_payload()``.
    (d) Block if provider consistency is mismatched.
    (e) Map refreshed ``effective_status`` to safe actions.
    (f) Execute only safe mutations.
    (g) Produce tick report with sync_refresh, provider_consistency,
        and extra_repo_sync always included.
    """
    # ── deferred imports to keep the module's top-level light ──────────
    from arnold_pipelines.megaplan.cloud.cli import (
        _resolve_remote_chain_spec,
        _tmux_chain_restart_command,
        cloud_chain_status_payload,
    )

    # ------------------------------------------------------------------
    # (a) Read initial chain status
    # ------------------------------------------------------------------
    try:
        payload = cloud_chain_status_payload(root, args, spec, provider)
    except Exception as exc:
        return _tick_report(
            success=False,
            event="supervisor_error",
            spec="",
            effective_status="unknown",
            next_action="none",
            acted=False,
            refused_reason=f"chain status read failed: {exc}",
            runner={},
            sync={},
            pr={},
            logs={},
        )

    remote_spec = _resolve_remote_chain_spec(root, args, spec)
    # Use resolved workspace/session from the payload for all downstream work.
    resolved_workspace: str = payload.get("resolved_workspace", spec.repo.workspace)
    resolved_session: str = payload.get("resolved_session", "megaplan-chain")
    extra_repos: list[str] = (
        payload.get("resolved_context", {}).get("extra_repos", [])
    )
    status = payload.get("effective_status", "unknown")
    runner = payload.get("runner", {})
    sync_info = payload.get("sync", {})
    pr_info = payload.get("pr", {})
    logs_info = payload.get("logs", {})
    provider_consistency = payload.get("provider_consistency", {})
    extra_repo_sync_info = payload.get("chain_state", {}).get("extra_repo_sync", [])
    # Human-verification status from the cloud status payload (T11).
    # When the payload already probed the remote chain, use its data.
    # Section (c2) refreshes this for human-verification-relevant statuses.
    human_verification: dict[str, Any] = payload.get(
        "human_verification",
        {"status": "unavailable", "reason": "not probed"},
    )

    # ------------------------------------------------------------------
    # (b) Refresh branch/PR sync — BEFORE any restart/advance/wake decisions
    # ------------------------------------------------------------------
    ssh_meth = getattr(provider, "ssh_exec", None)
    sync_refresh: dict[str, Any] = {"status": "skipped", "reason": "no ssh_exec"}
    sync_refreshed = False
    if ssh_meth is not None:
        try:
            chain_state_raw = payload.get("chain_state", {})
            pr_number_raw = (
                chain_state_raw.get("pr_number")
                if isinstance(chain_state_raw, dict)
                else None
            )
            pr_number: int | None = (
                int(pr_number_raw) if pr_number_raw is not None else None
            )
            sync_cmd = _remote_sync_refresh_command(
                resolved_workspace,
                remote_spec,
                branch=None,
                pr_number=pr_number,
                extra_repos=extra_repos if extra_repos else None,
                resolved_workspace=resolved_workspace,
                chain_session=resolved_session,
            )
            ssh_meth(sync_cmd)
            sync_refreshed = True
            sync_refresh = {"status": "ok"}
        except Exception as exc:
            # Sync refresh failure is now visible in the tick report.
            sync_refresh = {"status": "failed", "reason": str(exc)}

    # ------------------------------------------------------------------
    # (c) Re-read chain status after sync refresh
    # ------------------------------------------------------------------
    if sync_refreshed:
        try:
            payload = cloud_chain_status_payload(root, args, spec, provider)
            status = payload.get("effective_status", status)
            runner = payload.get("runner", runner)
            sync_info = payload.get("sync", sync_info)
            pr_info = payload.get("pr", pr_info)
            logs_info = payload.get("logs", logs_info)
            provider_consistency = payload.get("provider_consistency", provider_consistency)
            extra_repo_sync_info = (
                payload.get("chain_state", {}).get("extra_repo_sync", extra_repo_sync_info)
            )
            human_verification = payload.get(
                "human_verification", human_verification
            )
        except Exception:
            # Re-read failed; keep the pre-refresh values.
            sync_refresh["re_read"] = "failed"

    # ------------------------------------------------------------------
    # (c2) Probe remote human-verification status (T11)
    #
    # Only probe when the effective status is human-verification-related
    # (``awaiting_human_verify``, ``human_prerequisite``) so that mock-based
    # tests with ordered ``ssh_exec`` results are not disrupted when the
    # supervisor tick handles a non-human-verification status.
    # ------------------------------------------------------------------
    from arnold_pipelines.megaplan.cloud.cli import _remote_human_verification_status_command

    current_plan_name = (
        payload.get("chain_state", {}).get("current_plan_name")
        if isinstance(payload.get("chain_state"), dict)
        else None
    )
    _hv_relevant_statuses = {"awaiting_human_verify", "human_prerequisite"}
    if (
        ssh_meth is not None
        and current_plan_name
        and status in _hv_relevant_statuses
    ):
        try:
            cmd = _remote_human_verification_status_command(
                resolved_workspace, current_plan_name
            )
            result = ssh_meth(cmd)
            stdout = (result.stdout or "").strip()
            if not stdout:

--- FILE: arnold_pipelines/megaplan/watchdog/repair_runner.py (1,260p) ---
"""Repair-runner adapter with broken-CLI resilience."""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


@dataclass(frozen=True)
class RepairResult:
    status: str
    stdout: str
    stderr: str
    rc: int | None


_MEGAPLAN_SUBCOMMANDS: frozenset[str] = frozenset({
    "doctor",
    "auto",
    "resume",
    "chain",
})


class RepairRunner:
    """Run allowlisted repair commands via subprocess.

    Megaplan subcommands (``doctor``, ``auto``, ``resume``, ``chain``) are
    executed as ``python -m arnold.pipelines.megaplan <subcommand> ...`` inside
    the plan's project directory. System commands (``rm``, ``kill``) are run
    directly. If the executable is missing or the command cannot be run, returns
    a ``command_unavailable`` result instead of crashing.
    """

    def __init__(
        self,
        executable_search_path: Sequence[str] | None = None,
        python_bin: str | None = None,
    ) -> None:
        self._search_path = executable_search_path
        self._python_bin = python_bin or shutil.which("python3") or shutil.which("python") or "python"

    def _is_dry_run(self) -> bool:
        """An empty search path signals dry-run: do not execute anything."""
        return self._search_path is not None and len(self._search_path) == 0

    def _argv_for_command(self, command: str) -> tuple[list[str], str | None]:
        """Return (argv, cwd) for *command*.

        Megaplan subcommands are rewritten to ``python -m arnold.pipelines.megaplan``,
        or to a ``megaplan`` executable found on the search path if one exists.
        System commands are passed through. The returned cwd is the directory in
        which the command should run, or None for the current directory.
        """
        if self._is_dry_run():
            return [], None

        parts = command.split()
        if not parts:
            return [], None

        first = parts[0]
        # Detect an explicit project-dir marker injected by the CLI: "cd /path && cmd"
        if first == "cd" and len(parts) >= 4 and parts[2] == "&&":
            cwd = parts[1].strip("'\"")
            parts = parts[3:]
            first = parts[0] if parts else ""
        else:
            cwd = None

        if first in _MEGAPLAN_SUBCOMMANDS:
            # Prefer a real ``megaplan`` executable on PATH if available;
            # otherwise fall back to the module invocation.
            megaplan_exe = shutil.which("megaplan", path=self._search_path)
            if megaplan_exe is not None:
                return [megaplan_exe] + parts, cwd
            return [self._python_bin, "-m", "arnold_pipelines.megaplan"] + parts, cwd

        # Bare subcommands like "rm" or "kill" that are not standalone executables
        # but are safe shell builtins/utilities.
        if first in {"rm", "kill"}:
            return ["/bin/bash", "-c", " ".join(parts)], cwd

        executable = shutil.which(first, path=self._search_path)
        if executable is None:
            return [], cwd
        return [executable] + parts[1:], cwd

    def run(
        self,
        command: str,
        *,
        plan_dir: str | None = None,
        project_dir: str | None = None,
    ) -> RepairResult:
        """Execute *command* and return a structured result."""
        argv, argv_cwd = self._argv_for_command(command)
        if not argv:
            return RepairResult(
                status="command_unavailable",
                stdout="",
                stderr=f"executable not found or unsupported command: {command!r}",
                rc=None,
            )

        cwd = argv_cwd or project_dir
        if cwd is None and plan_dir is not None:
            # Fall back to the plan directory's repo root.
            try:
                cwd = str(Path(plan_dir).parents[2])
            except Exception:
                pass

        env = os.environ.copy()
        if cwd is not None:
            env["MEGAPLAN_PLAN_DIR"] = str(plan_dir) if plan_dir else cwd
            env["MEGAPLAN_PROJECT_DIR"] = cwd

        try:
            result = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                timeout=300,
                check=False,
                cwd=cwd,
                env=env,
            )
            status = "success" if result.returncode == 0 else "failed"
            return RepairResult(
                status=status,
                stdout=result.stdout,
                stderr=result.stderr,
                rc=result.returncode,
            )
        except (FileNotFoundError, OSError) as exc:
            return RepairResult(
                status="command_unavailable",
                stdout="",
                stderr=f"could not execute {argv!r}: {exc}",
                rc=None,
            )
        except subprocess.TimeoutExpired:
            return RepairResult(
                status="timeout",
                stdout="",
                stderr="command timed out after 300s",
                rc=None,
            )


__all__ = [
    "RepairResult",
    "RepairRunner",
]

--- FILE: arnold_pipelines/megaplan/watchdog/retry.py (1,220p) ---
"""Retry-loop state machine for the live watchdog."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RetryOutcome(str, Enum):
    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"
    TERMINAL = "terminal"


class RetryCapExceeded(Exception):
    """Raised when attempting a fourth retry."""


@dataclass
class RetryLoop:
    """Tracks up to three attempts per incident.

    Usage::

        loop = RetryLoop()
        while True:
            outcome = run_repair()
            result, done = loop.attempt(outcome)
            if done:
                break
    """

    max_attempts: int = 3
    attempt_count: int = field(default=0, init=False)

    def attempt(self, outcome: RetryOutcome) -> tuple[RetryOutcome, bool]:
        """Record one attempt and return (result, done).

        Returns done=True on success, terminal state, or after the third
        failure. Raises ``RetryCapExceeded`` if called after done=True was
        returned.
        """
        if self.attempt_count >= self.max_attempts:
            raise RetryCapExceeded(f"retry cap of {self.max_attempts} exceeded")

        self.attempt_count += 1

        if outcome is RetryOutcome.RESOLVED:
            return RetryOutcome.RESOLVED, True
        if outcome is RetryOutcome.TERMINAL:
            return RetryOutcome.TERMINAL, True
        if self.attempt_count >= self.max_attempts:
            return RetryOutcome.UNRESOLVED, True
        return RetryOutcome.UNRESOLVED, False

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_attempts": self.max_attempts,
            "attempt_count": self.attempt_count,
        }


__all__ = [
    "RetryLoop",
    "RetryOutcome",
    "RetryCapExceeded",
]

--- FILE: arnold_pipelines/megaplan/resident/scheduler.py (1,280p) ---
"""Durable scheduled-job worker and resident job handlers."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol
from uuid import uuid4

from arnold_pipelines.megaplan.schemas import CloudRun, ResidentConversation, ScheduledJob
from arnold_pipelines.megaplan.store import ProgressEventInput, ScheduledJobInput, Store, deterministic_idempotency_key

from .auth import ConfirmationManager
from .cloud import (
    CloudClassification,
    CloudToolBackend,
    CloudToolRequest,
    CloudToolResult,
    cloud_run_status_for_classification,
    progress_kind_for_classification,
)
from .config import ResidentConfig
from .runtime import EmitProtocol, OutboundMessage, OutboundSink

JobHandler = Callable[[dict[str, Any]], Awaitable[None]]
TERMINAL_OR_INPUT_NEEDED: frozenset[CloudClassification] = frozenset(
    {"blocked", "failed", "gate-needed", "completed"}
)


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class SchedulerRunResult:
    claimed: int = 0
    fired: int = 0
    retried: int = 0
    cancelled: int = 0


class ScheduledJobBackend(Protocol):
    async def claim_due_jobs(self, *, worker_id: str, now: datetime) -> list[dict[str, Any]]:
        """Atomically claim due jobs and return job payloads."""

    async def mark_fired(self, job_id: str, *, now: datetime) -> None:
        """Mark a claimed job as fired."""

    async def mark_failed(self, job_id: str, error: str, *, now: datetime) -> bool:
        """Record failure and return whether the job will be retried."""


class StoreScheduledJobBackend:
    """Store-backed scheduled-job claiming and retry/cancel policy."""

    def __init__(
        self,
        store: Store,
        *,
        stale_after_seconds: int,
        batch_size: int,
        retry_delay_seconds: int | None = None,
    ) -> None:
        self.store = store
        self.stale_after_seconds = stale_after_seconds
        self.batch_size = batch_size
        self.retry_delay_seconds = retry_delay_seconds or 30

    async def claim_due_jobs(self, *, worker_id: str, now: datetime) -> list[dict[str, Any]]:
        jobs = self.store.claim_due_scheduled_jobs(
            worker_id=worker_id,
            now=now,
            stale_after_seconds=self.stale_after_seconds,
            max=self.batch_size,
            idempotency_key=deterministic_idempotency_key("resident-scheduler-claim", worker_id, now.isoformat()),
        )
        return [job.model_dump(mode="json") for job in jobs]

    async def mark_fired(self, job_id: str, *, now: datetime) -> None:
        self.store.update_scheduled_job(
            job_id,
            status="fired",
            fired_at=now,
            claimed_by=None,
            claimed_at=None,
            idempotency_key=deterministic_idempotency_key("resident-scheduler-fired", job_id),
        )

    async def mark_failed(self, job_id: str, error: str, *, now: datetime) -> bool:
        job = self.store.load_scheduled_job(job_id)
        if job is None:
            return False
        retrying = job.attempt_count < job.max_attempts
        if retrying:
            self.store.update_scheduled_job(
                job.id,
                status="pending",
                scheduled_for=now + timedelta(seconds=self.retry_delay_seconds),
                claimed_by=None,
                claimed_at=None,
                last_error=error,
                idempotency_key=deterministic_idempotency_key("resident-scheduler-retry", job.id, job.attempt_count, error),
            )
        else:
            self.store.update_scheduled_job(
                job.id,
                status="cancelled",
                cancelled_at=now,
                claimed_by=None,
                claimed_at=None,
                last_error=error,
                idempotency_key=deterministic_idempotency_key("resident-scheduler-cancel", job.id, job.attempt_count, error),
            )
        return retrying


class ScheduledJobWorker:
    """Runtime scheduler shell; storage-specific claiming arrives in store code."""

    def __init__(
        self,
        backend: ScheduledJobBackend,
        *,
        handlers: dict[str, JobHandler] | None = None,
        worker_id: str | None = None,
    ) -> None:
        self.backend = backend
        self.worker_id = worker_id or f"resident-scheduler-{uuid4()}"
        self.handlers = handlers or {}

    async def run_due_once(self, *, now: datetime | None = None) -> SchedulerRunResult:
        now = now or utc_now()
        jobs = await self.backend.claim_due_jobs(worker_id=self.worker_id, now=now)
        fired = retried = cancelled = 0
        for job in jobs:
            job_type = str(job.get("job_type") or job.get("type") or "")
            handler = self.handlers.get(job_type)
            if handler is None:
                retrying = await self.backend.mark_failed(str(job["id"]), f"no handler for {job_type}", now=now)
                retried += int(retrying)
                cancelled += int(not retrying)
                continue
            try:
                await handler(job)
            except Exception as exc:
                retrying = await self.backend.mark_failed(str(job["id"]), str(exc), now=now)
                retried += int(retrying)
                cancelled += int(not retrying)
            else:
                await self.backend.mark_fired(str(job["id"]), now=now)
                fired += 1
        return SchedulerRunResult(claimed=len(jobs), fired=fired, retried=retried, cancelled=cancelled)


@dataclass
class ResidentJobHandlers:
    """Handlers for resident durable scheduled jobs."""

    store: Store
    config: ResidentConfig
    cloud_backend: CloudToolBackend
    outbound: OutboundSink | None = None
    confirmation_manager: ConfirmationManager | None = None
    runtime_flush: Callable[[], Awaitable[None]] | None = None
    worker_id: str = "resident-scheduler"
    reschedule_interval_s: int | None = None

    def handlers(self) -> dict[str, JobHandler]:
        return {
            "cloud_check": self.handle_cloud_check,
            "deferred_turn": self.handle_deferred_turn,
            "heartbeat": self.handle_heartbeat,
            "confirmation_expiry": self.handle_confirmation_expiry,
        }

    async def handle_cloud_check(self, job_payload: dict[str, Any]) -> None:
        job = _job_from_payload(job_payload)
        if not job.cloud_run_id:
            raise ValueError("cloud_check job requires cloud_run_id")
        if not job.conversation_id:
            raise ValueError("cloud_check job requires conversation_id")
        run = self.store.load_cloud_run(job.cloud_run_id)
        if run is None:
            raise ValueError(f"cloud run {job.cloud_run_id!r} was not found")
        conversation = self.store.load_resident_conversation(job.conversation_id)
        if conversation is None:
            raise ValueError(f"resident conversation {job.conversation_id!r} was not found")

        result = await self.cloud_backend.run(_cloud_request_for_job(job, run))
        previous_status = run.status
        updated = self._persist_cloud_result(run, result)
        classification = result.classification
        if classification == "running":
            self._reschedule_cloud_check(job, updated)
        elif classification in TERMINAL_OR_INPUT_NEEDED:
            await self._notify_cloud_transition(
                conversation=conversation,
                run=updated,
                classification=classification,
                summary=result.summary,
            )
        self._log_cloud_check(job, updated, result, previous_status=previous_status)

    async def handle_deferred_turn(self, job_payload: dict[str, Any]) -> None:
        job = _job_from_payload(job_payload)
        if self.runtime_flush is not None:
            await self.runtime_flush()
        self._emit_sink().log_system_event(
            level="info",
            category="system",
            event_type="resident_deferred_turn",
            message="Resident deferred turn job processed",
            details={"job_id": job.id, "conversation_id": job.conversation_id},
            idempotency_key=deterministic_idempotency_key("resident-deferred-turn", job.id, job.attempt_count),
        )

    async def handle_heartbeat(self, job_payload: dict[str, Any]) -> None:
        job = _job_from_payload(job_payload)
        self._emit_sink().log_system_event(
            level="info",
            category="system",
            event_type="resident_scheduler_heartbeat",
            message="Resident scheduler heartbeat",
            details={"job_id": job.id, "worker_id": self.worker_id},
            idempotency_key=deterministic_idempotency_key("resident-heartbeat", job.id, job.attempt_count),
        )

    async def handle_confirmation_expiry(self, job_payload: dict[str, Any]) -> None:
        job = _job_from_payload(job_payload)
        expired = self.confirmation_manager.expire_due() if self.confirmation_manager is not None else []
        self._emit_sink().log_system_event(
            level="info",
            category="system",
            event_type="resident_confirmation_expiry",
            message="Expired resident confirmation requests",
            details={"job_id": job.id, "expired_request_ids": [request.id for request in expired]},
            idempotency_key=deterministic_idempotency_key("resident-confirmation-expiry", job.id, job.attempt_count),
        )

    def _persist_cloud_result(
        self,
        run: CloudRun,
        result: CloudToolResult,
    ) -> CloudRun:
        now = utc_now()
        status = cloud_run_status_for_classification(result.classification)
        last_status = {
            "cloud_status": result.classification,
            "summary": result.summary,
            "details": result.details,
            "checked_at": now.isoformat().replace("+00:00", "Z"),
        }
        changes: dict[str, Any] = {
            "status": status,
            "progress_summary": result.summary,
            "last_status": last_status,
            "last_checked_at": now,
        }
        if status in {"completed", "failed", "blocked", "gate-needed"}:
            changes["completed_at"] = now
        updated = self.store.update_cloud_run(
            run.id,
            **changes,
            idempotency_key=deterministic_idempotency_key(
                "resident-cloud-check-status",
                run.id,
                result.classification,
                result.summary,
            ),
        )
        should_append_progress = run.status != updated.status or not run.last_status
        if should_append_progress and updated.epic_id:
            self._emit_sink().append_progress_event(
                ProgressEventInput(
                    epic_id=updated.epic_id,
                    plan_id=updated.plan_id,
                    sprint_id=updated.sprint_id,
                    kind=progress_kind_for_classification(result.classification),
