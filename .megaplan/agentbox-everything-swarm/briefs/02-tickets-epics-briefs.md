You are a DeepSeek subagent doing a read-only inventory for AgentBox. The user asked us to find EVERYTHING existing in this repo/local skills that overlaps with the desired Discord-first AgentBox: start tickets/epics/megaplans/chains from Discord, Guardian repairs/relaunches blocked runs, completed work gets pushed/PRd/consolidated, and DeepSeek/subagents can be used. The brief embeds local excerpts. Return a decisive inventory of reusable mechanics, with file refs, gaps, and concrete recommendations. Under 1200 words. Focus: tickets, briefs, epics, chain specs, and how Discord Operator could add a ticket, set up an epic, set up a Megaplan, or launch a chain.


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

--- FILE: arnold_pipelines/megaplan/tickets/core.py (1,260p) ---
"""Core ticket operations — mode-aware dispatch.

Local-only mode: writes/reads ``.megaplan/tickets/*.md`` files only.
Store-configured mode: writes files **and** mirrors through the
:class:`~megaplan.store.base.Store` ticket protocol.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from ulid import ULID

from arnold_pipelines.megaplan.schemas import Ticket, TicketEpicLink
from arnold_pipelines.megaplan.store import Store

from .files import (
    _FRONTMATTER_FIELDS,
    iterate_ticket_files,
    read_ticket_file,
    slugify,
    ticket_file_path,
    tickets_dir,
    write_ticket_file,
)
from .identity import repo_codebase_identity, repo_owner_name, repo_root_sha


# ---------------------------------------------------------------------------
# Mode detection
# ---------------------------------------------------------------------------


def is_cloud_store(store: Store) -> bool:
    """Return *True* when *store* supports facade-backed ticket operations.

    This is the **single canonical predicate** used by every operation to
    decide whether to hit a Store backend in addition to the file system.
    """
    from arnold_pipelines.megaplan.store.db import DBStore  # lazy to avoid import cycles
    from arnold_pipelines.megaplan.store.file import FileStore
    from arnold_pipelines.megaplan.store.multi import MultiStore

    return isinstance(store, DBStore | FileStore | MultiStore)


# ---------------------------------------------------------------------------
# Store resolution
# ---------------------------------------------------------------------------


def _resolve_store() -> Store | None:
    """Return the currently configured store, or *None* for local-only.

    Reuses megaplan's existing ``build_store`` convention: checks
    ``MEGAPLAN_BACKEND`` env and ``--backend`` CLI args by inspecting
    the CLI context if available, otherwise falls back to env.
    """
    backend = os.environ.get("MEGAPLAN_BACKEND")
    if backend == "db":
        from arnold_pipelines.megaplan.store import DBStore, require_actor_id, resolve_actor_id

        actor_id = require_actor_id(resolve_actor_id(None))
        return DBStore(actor_id=actor_id)
    return None


# ---------------------------------------------------------------------------
# Source derivation
# ---------------------------------------------------------------------------


def _derive_source() -> tuple[str, str | None, str | None]:
    """Return ``(source, filed_in_turn_id, filed_by_actor_id)``.

    - ``MEGAPLAN_TURN_ID`` set  → ``source = 'agent'``, ``filed_in_turn_id`` populated.
    - Unset                     → ``source = 'human'``.
    - ``MEGAPLAN_ACTOR_ID``     → ``filed_by_actor_id`` populated.
    """
    turn_id = os.environ.get("MEGAPLAN_TURN_ID")
    actor_id = os.environ.get("MEGAPLAN_ACTOR_ID")
    if turn_id:
        return ("agent", turn_id, actor_id or None)
    return ("human", None, actor_id or None)


# ---------------------------------------------------------------------------
# Codebase identity resolution
# ---------------------------------------------------------------------------


def _resolve_codebase_id(store: Store | None, cwd: Path | None = None) -> str | None:
    """Determine the codebase identity from the current working directory.

    Returns a ``codebase_id`` string, or *None* if we're in local-only mode
    and identity doesn't matter for file-only storage.
    """
    if store is None or not is_cloud_store(store):
        return None  # local-only: no codebase_id needed
    try:
        sha = repo_root_sha(cwd)
    except Exception:
        sha = None

    if sha:
        existing = store.resolve_codebase_by_root_sha(sha)
        if existing:
            return existing.id
    return None


def _ensure_codebase(
    store: Store,
    cwd: Path | None = None,
) -> str:
    """Ensure a ``codebases`` row exists for the current repo and return its id.

    Auto-registers if needed (with ``root_commit_sha`` populated).
    Only meaningful in cloud mode; raises in local-only.
    """
    assert is_cloud_store(store)
    identity = repo_codebase_identity(cwd)
    existing = store.resolve_codebase_by_root_sha(identity.root_commit_sha)
    if existing:
        return existing.id

    cb = store.upsert_codebase(
        owner=identity.owner,
        name=identity.name,
        default_branch=identity.default_branch,
        root_commit_sha=identity.root_commit_sha,
    )
    return cb.id


# ---------------------------------------------------------------------------
# Public API — create
# ---------------------------------------------------------------------------


def new(
    title: str,
    *,
    body: str = "",
    tags: Sequence[str] | None = None,
    store: Store | None = None,
    cwd: Path | None = None,
) -> str:
    """Create a new ticket and return its ULID.

    Parameters
    ----------
    title:
        Ticket title (required).
    body:
        Markdown body.  ``"-"`` means read from stdin (empty input is rejected).
    tags:
        Optional tags.
    store:
        Explicit store.  If *None*, resolved from environment.
    cwd:
        Working directory for git operations.

    Returns
    -------
    str
        The ULID of the newly created ticket (printed to stdout).
    """
    # Handle stdin body
    if body == "-":
        body = sys.stdin.read()
        if not body.strip():
            raise ValueError("stdin body is empty — body is required")

    if store is None:
        store = _resolve_store()

    source, turn_id, actor_id = _derive_source()
    ticket_id = str(ULID())
    slug = slugify(title)
    now = datetime.now(timezone.utc)

    # Determine codebase_id (cloud mode only)
    codebase_id: str | None
    if store is not None and is_cloud_store(store):
        codebase_id = _ensure_codebase(store, cwd)
    else:
        codebase_id = None

    # Build record dict for file
    record: dict[str, Any] = {
        "id": ticket_id,
        "title": title,
        "status": "open",
        "source": source,
        "tags": list(tags or []),
        "filed_by_actor_id": actor_id,
        "filed_in_turn_id": turn_id,
        "codebase_id": codebase_id,
        "created_at": now,
        "last_edited_at": now,
        "resolution_note": None,
        "addressed_at": None,
        "epics": [],
        "__body__": body,
    }

    # Write file (both modes)
    if cwd:
        repo_root = str(cwd)
    else:
        repo_root = os.getcwd()
    fpath = ticket_file_path(repo_root, ticket_id, slug)
    write_ticket_file(fpath, record)

    # Store-backed facade: write Store row
    if store is not None and is_cloud_store(store) and codebase_id:
        store.create_ticket(
            codebase_id=codebase_id,
            title=title,
            body=body,
            source=source,
            tags=list(tags or []),
            filed_by_actor_id=actor_id,
            filed_in_turn_id=turn_id,
            slug=slug,
            ticket_id=ticket_id,
        )

    # Print only the ULID to stdout (per spec)
    print(ticket_id, flush=True)
    return ticket_id


# ---------------------------------------------------------------------------
# Public API — list
# ---------------------------------------------------------------------------


def list_tickets(
    *,
    status: str | None = None,
    tags: Sequence[str] | None = None,
    store: Store | None = None,
    cwd: Path | None = None,
    json_output: bool = False,
) -> list[dict[str, Any]]:
    """List tickets, optionally filtered.

    In local-only mode reads from ``.megaplan/tickets/*.md``.
    In store-backed facade mode queries the Store.
    """
    if store is None:
        store = _resolve_store()

    results: list[dict[str, Any]] = []

--- FILE: arnold_pipelines/megaplan/tickets/cli.py (1,260p) ---

--- FILE: arnold_pipelines/megaplan/chain/spec.py (1,220p) ---
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover - import guard
    raise RuntimeError(
        "megaplan chain requires PyYAML. Install with `pip install pyyaml`."
    ) from exc

from arnold_pipelines.megaplan.auto import (
    DEFAULT_MAX_ITERATIONS,
    DEFAULT_PHASE_TIMEOUT_SECONDS,
    DEFAULT_POLL_SLEEP_SECONDS,
    DEFAULT_STALL_THRESHOLD,
    DEFAULT_STATUS_TIMEOUT_SECONDS,
    ESCALATE_ACTIONS,
)
from arnold_pipelines.megaplan._core import resolve_plan_dir
from arnold_pipelines.megaplan._core.user_config import VALID_VENDORS
from arnold_pipelines.megaplan.profiles import (
    VALID_CRITIC_CHOICES,
    VALID_DEEPSEEK_PROVIDER_CHOICES,
    VALID_DEPTH_CHOICES,
)
from arnold_pipelines.megaplan.types import CliError

log = logging.getLogger("megaplan")


VALID_FAILURE_ACTIONS = (
    "stop_chain",
    "skip_milestone",
    "resume_milestone",
    "retry_milestone",
    "bump_profile",
    "bump_robustness",
)
VALID_MERGE_POLICIES = ("auto", "review", "manual")
VALID_CHAIN_DEEPSEEK_PROVIDER_CHOICES = ("direct", "fireworks")

# Autonomy-ladder bump ordering. These are the *one-tier-up* escalation maps
# the chain applies when a milestone exhausts its retry budget. There is no
# tier above ``apex`` (apex.toml is the top premium profile) — a bump_profile
# at apex is a no-op + warning, never an error.
PROFILE_BUMP_ORDER = ("premium", "apex")
ROBUSTNESS_BUMP_ORDER = ("thorough", "extreme")
DEPTH_BUMP_ORDER = ("high", "max")

# Default per-milestone retry budget (FRESH re-inits) before the ladder bumps.
# Capped at 1 for apex profile / extreme robustness milestones to bound cost.
DEFAULT_MILESTONE_RETRY_CAP = 2
APEX_EXTREME_RETRY_CAP = 1


def _bump_one_tier(current: str | None, order: tuple[str, ...]) -> tuple[str | None, bool]:
    """Return (next_tier, bumped). At/above the top tier this is a no-op.

    *current* of ``None`` (unset) is treated as the bottom of the ladder so a
    bump moves to the second rung — the first explicit escalation tier.
    """
    if current is None:
        return order[1] if len(order) > 1 else order[0], len(order) > 1
    try:
        idx = order.index(current)
    except ValueError:
        # Unknown/custom tier — leave it alone rather than guess.
        return current, False
    if idx >= len(order) - 1:
        return current, False
    return order[idx + 1], True


@dataclass(frozen=True)
class FailurePolicy:
    """Structured autonomy ladder for ``on_failure`` / ``on_escalate``.

    YAML may declare either a plain string (abort-only, back-compat)::

        on_failure: stop_chain

    or a structured ladder mapping::

        on_failure:
          retry: retry_milestone     # walked first, bounded by a counter
          escalate: bump_profile     # walked once after retries exhaust
          abort: stop_chain          # terminal action

    ``retry`` / ``escalate`` are optional; ``abort`` defaults to ``stop_chain``.
    """

    abort: str = "stop_chain"
    retry: str | None = None
    escalate: str | None = None

    @classmethod
    def from_yaml(
        cls, value: Any, section: str, default_abort: str = "stop_chain"
    ) -> "FailurePolicy":
        # Plain string (or absent) → abort-only, back-compat.
        if value is None:
            return cls(abort=default_abort)
        if isinstance(value, str):
            if value not in VALID_FAILURE_ACTIONS:
                raise CliError(
                    "invalid_spec",
                    f"{section} must be one of {VALID_FAILURE_ACTIONS}; got {value!r}",
                )
            return cls(abort=value)
        if not isinstance(value, dict):
            raise CliError(
                "invalid_spec",
                f"`{section}` must be a string or a mapping of retry/escalate/abort",
            )

        def _check(key: str, fallback: str | None) -> str | None:
            raw = value.get(key, fallback)
            if raw is None:
                return None
            if raw not in VALID_FAILURE_ACTIONS:
                raise CliError(
                    "invalid_spec",
                    f"{section}.{key} must be one of {VALID_FAILURE_ACTIONS}; got {raw!r}",
                )
            return raw

        abort = _check("abort", default_abort) or default_abort
        retry = _check("retry", None)
        escalate = _check("escalate", None)
        return cls(abort=abort, retry=retry, escalate=escalate)


# Chain-level policy enums — conservative values following the
# VALID_MERGE_POLICIES module-level tuple pattern. These are
# operator-facing contracts; renaming later is a breaking change.
# Validated in ChainSpec.from_dict() with CliError("invalid_spec", ...).
VALID_PREREQUISITE_POLICIES = ("none", "required")
VALID_VALIDATION_POLICIES = ("none", "required")
VALID_CLEAN_MILESTONE_PR_POLICIES = ("auto", "manual")
BLOCKED_EXECUTE_OUTCOME_STATUSES = {"blocked", "worker_blocked"}


def _warn_chain_fallback(
    token: str,
    *,
    reason: str,
    path: Path | None = None,
    context: dict[str, Any] | None = None,
) -> None:
    details = [f"reason={reason}"]
    if path is not None:
        details.append(f"path={path}")
    if context:
        for key in sorted(context):
            details.append(f"{key}={context[key]!r}")
    log.warning("%s chain fallback (%s)", token, ", ".join(details), exc_info=True)


def _optional_choice(
    raw: dict[str, Any],
    key: str,
    choices: tuple[str, ...],
    *,
    index: int,
) -> str | None:
    value = raw.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise CliError("invalid_spec", f"milestones[{index}].{key} must be a string")
    if value not in choices:
        raise CliError(
            "invalid_spec",
            f"milestones[{index}].{key} must be one of {choices}; got {value!r}",
        )
    return value


def _optional_bool(raw: dict[str, Any], key: str, *, index: int) -> bool:
    value = raw.get(key, False)
    if not isinstance(value, bool):
        raise CliError("invalid_spec", f"milestones[{index}].{key} must be a boolean")
    return value


@dataclass
class MilestoneSpec:
    label: str
    idea: str
    branch: str | None = None
    profile: str | None = None
    robustness: str | None = None
    vendor: str | None = None
    depth: str | None = None
    critic: str | None = None
    deepseek_provider: str | None = None
    with_prep: bool = False
    with_feedback: bool = False
    prep_clarify: bool = True
    prep_direction: str | None = None
    phase_model: list[str] = field(default_factory=list)
    bakeoff: dict[str, Any] | None = None
    notes: str | None = None
    # Validation-only dependency edges (labels of milestones that MUST appear
    # earlier in the list). The chain runs strictly serial-in-listed-order — a
    # single cursor — so ``depends_on`` does NOT reorder or parallelize
    # execution. It is a topological-sort ASSERTION: ``ChainSpec.from_dict``
    # fails loud if a milestone declares a dependency that is not listed before
    # it, so the non-negotiable edges cannot silently drift out of order in a
    # hand-edited chain.yaml. ``∥`` parallel tracks stay prose — concurrency is
    # never introduced here.
    depends_on: list[str] = field(default_factory=list)

    @classmethod

--- FILE: arnold_pipelines/megaplan/chain/spec.py (500,660p) ---
        )


@dataclass
class ChainState:
    """Persisted progress for a chain run."""

    current_milestone_index: int = -1
    current_plan_name: str | None = None
    current_milestone_base_sha: str | None = None
    last_state: str | None = None
    pr_number: int | None = None
    pr_state: str | None = None
    completed: list[dict[str, Any]] = field(default_factory=list)
    branch_head: str | None = None
    pr_head: str | None = None
    last_pushed_commit: str | None = None
    dirty_flag: bool = False
    sync_state: str | None = None
    extra_repos: list[str] = field(default_factory=list)
    chain_session: str | None = None
    resolved_workspace: str | None = None
    extra_repo_sync: list[dict[str, Any]] = field(default_factory=list)
    completion_contract_mode: str = "shadow"
    full_suite_backstop_mode: str = "shadow"
    retry_counts: dict[str, int] = field(default_factory=dict)
    ladder_stage: dict[str, str] = field(default_factory=dict)
    profile_bumps: dict[str, str] = field(default_factory=dict)
    robustness_bumps: dict[str, str] = field(default_factory=dict)
    depth_bumps: dict[str, str] = field(default_factory=dict)
    enforce_revise_counts: dict[str, int] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    schema_version: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "current_milestone_index": self.current_milestone_index,
            "current_plan_name": self.current_plan_name,
            "current_milestone_base_sha": self.current_milestone_base_sha,
            "last_state": self.last_state,
            "pr_number": self.pr_number,
            "pr_state": self.pr_state,
            "completed": list(self.completed),
            "branch_head": self.branch_head,
            "pr_head": self.pr_head,
            "last_pushed_commit": self.last_pushed_commit,
            "dirty_flag": self.dirty_flag,
            "sync_state": self.sync_state,
            "extra_repos": list(self.extra_repos),
            "chain_session": self.chain_session,
            "resolved_workspace": self.resolved_workspace,
            "extra_repo_sync": list(self.extra_repo_sync),
            "completion_contract_mode": self.completion_contract_mode,
            "full_suite_backstop_mode": self.full_suite_backstop_mode,
            "retry_counts": dict(self.retry_counts),
            "ladder_stage": dict(self.ladder_stage),
            "profile_bumps": dict(self.profile_bumps),
            "robustness_bumps": dict(self.robustness_bumps),
            "depth_bumps": dict(self.depth_bumps),
            "enforce_revise_counts": dict(self.enforce_revise_counts),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "ChainState":
        extra_repos = raw.get("extra_repos")
        if not isinstance(extra_repos, list) or any(
            not isinstance(item, str) or not item for item in extra_repos
        ):
            extra_repos = []

        chain_session = raw.get("chain_session")
        if chain_session is not None and (
            not isinstance(chain_session, str) or not chain_session.strip()
        ):
            chain_session = None

        resolved_workspace = raw.get("resolved_workspace")
        if resolved_workspace is not None and (
            not isinstance(resolved_workspace, str) or not resolved_workspace.strip()
        ):
            resolved_workspace = None

        extra_repo_sync = raw.get("extra_repo_sync")
        if not isinstance(extra_repo_sync, list):
            extra_repo_sync = []

        from arnold_pipelines.megaplan.orchestration.completion_contract import normalize_contract_mode
        from arnold_pipelines.megaplan.orchestration.full_suite_backstop import (
            normalize_full_suite_backstop_mode,
        )

        completion_contract_mode = normalize_contract_mode(
            raw.get("completion_contract_mode")
        )
        full_suite_backstop_mode = normalize_full_suite_backstop_mode(
            raw.get("full_suite_backstop_mode")
        )

        def _str_int_map(value: Any) -> dict[str, int]:
            if not isinstance(value, dict):
                return {}
            out: dict[str, int] = {}
            for key, val in value.items():
                if isinstance(key, str):
                    try:
                        out[key] = int(val)
                    except (TypeError, ValueError):
                        continue
            return out

        def _str_str_map(value: Any) -> dict[str, str]:
            if not isinstance(value, dict):
                return {}
            return {
                key: val
                for key, val in value.items()
                if isinstance(key, str) and isinstance(val, str)
            }

        metadata = raw.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}
        return cls(
            current_milestone_index=int(raw.get("current_milestone_index", -1)),
            current_plan_name=raw.get("current_plan_name"),
            current_milestone_base_sha=raw.get("current_milestone_base_sha"),
            last_state=raw.get("last_state"),
            pr_number=int(raw["pr_number"]) if raw.get("pr_number") is not None else None,
            pr_state=raw.get("pr_state"),
            completed=list(raw.get("completed") or []),
            branch_head=raw.get("branch_head"),
            pr_head=raw.get("pr_head"),
            last_pushed_commit=raw.get("last_pushed_commit"),
            dirty_flag=bool(raw.get("dirty_flag", False)),
            sync_state=raw.get("sync_state"),
            extra_repos=extra_repos,
            chain_session=chain_session,
            resolved_workspace=resolved_workspace,
            extra_repo_sync=extra_repo_sync,
            completion_contract_mode=completion_contract_mode,
            full_suite_backstop_mode=full_suite_backstop_mode,
            retry_counts=_str_int_map(raw.get("retry_counts")),
            ladder_stage=_str_str_map(raw.get("ladder_stage")),
            profile_bumps=_str_str_map(raw.get("profile_bumps")),
            robustness_bumps=_str_str_map(raw.get("robustness_bumps")),
            depth_bumps=_str_str_map(raw.get("depth_bumps")),
            enforce_revise_counts=_str_int_map(raw.get("enforce_revise_counts")),
            metadata=dict(metadata),
        )


def _state_path_for(spec_path: Path) -> Path:
    spec_resolved = spec_path.resolve()
    digest = hashlib.sha1(str(spec_resolved).encode("utf-8")).hexdigest()[:12]
    return (
        spec_resolved.parent
        / ".megaplan"
        / "plans"
        / ".chains"

--- FILE: arnold_pipelines/megaplan/skills/megaplan-epic/SKILL.md (1,220p) ---
---
name: megaplan-epic
description: Run an epic — a chain of sprint-sized megaplans driven sequentially via `megaplan chain`. Use when the work is bigger than ~2 weeks and needs to be decomposed into multiple plans with state, ordering, and failure semantics handled by the harness.
---

# Megaplan Epic

An **epic** is work too big for a single megaplan, decomposed into an ordered chain of sprint-sized megaplans driven sequentially by `megaplan chain`. Each milestone in the chain is a full megaplan run (its own brief, plan, critique, execute, review); the chain handles ordering, state persistence, branch/PR lifecycle, and failure semantics.

If your work fits in one megaplan, you don't need this skill — read **megaplan-prep** and run a single sprint. Reach for the epic flow when the answer to "size each megaplan to ~2 weeks of work" is "this doesn't fit."

## When to reach for an epic

- **Scope is genuinely >2 weeks** and the deliverable is a single coherent thing (a feature, a migration, a cross-cutting refactor) — not separate unrelated efforts that should each be their own sprint.
- **Sequential dependencies between sprints** — milestone B needs the schema / interface / artifact that milestone A produces. Each handoff is a written artifact the next milestone can cite.
- **Multiple major architectural decisions** that each deserve their own brief + critique pass — pretending it's one sprint flattens decisions that need separate deliberation.
- **You want the chain to keep running unattended** — chains persist state and resume; one milestone failing doesn't lose the work the prior milestones produced.

## When NOT to use an epic

- **Single sprint fits the work.** If you can hold the whole scope in a 2-week brief, a chain just adds ceremony.
- **Exploration / discovery work** where you don't yet know the milestone breakdown. Run a single megaplan first to scope; then write the chain spec.
- **Truly independent sprints.** If sprints don't depend on each other, just run them sequentially as plain `megaplan init` calls — a chain spec is overhead with no benefit.
- **Anything where the milestone breakdown isn't pre-decided.** Chains run unattended through the declared spec; if you'd want to look at milestone 1's output and decide what milestone 2 should be, just run them as separate megaplans.

## Terminology — epic vs chain vs `megaplan epic`

Three names, three meanings:

- **Epic** (this skill) — the *concept*: multi-sprint work decomposed into a chain of megaplans.
- **`megaplan chain`** — the *imperative verb* that drives the flow. This is what you actually run.
- **`megaplan epic`** — a *data-admin verb* for snapshot / migrate / export of the editorial epic record. Not the orchestration entry point. Don't confuse the two.

## The spec — `chain.yaml`

A chain spec is a YAML file declaring the base branch, an optional seed plan, and an ordered list of milestones. Each milestone has its own rubric knobs (profile, robustness, depth, vendor, prep/feedback flags).

Store durable epic artifacts under `.megaplan/briefs/<epic-slug>/`: put the executable `chain.yaml` there and keep the milestone brief files beside it. Single-plan idea briefs that are not part of an epic live directly under `.megaplan/briefs/<slug>.md`. `.megaplan/plans/` remains generated runtime state; `.megaplan/briefs/` is the committed source material that creates runs.

```yaml
base_branch: main

# Optional: a pre-existing plan whose output seeds the first milestone's repo state.
seed:
  plan: scoping-from-docs-20260415-0217

milestones:
  - label: m1-schema
    idea: .megaplan/briefs/artifact-store/m1-schema.md
    branch: epic/m1-schema           # optional, informational for now
    profile: apex                    # tier 5 — schema everyone downstream builds on
    robustness: thorough
    depth: high

  - label: m2-storage
    idea: .megaplan/briefs/artifact-store/m2-storage.md
    profile: premium                 # tier 4 — production migration logic
    robustness: thorough
    depth: high

  - label: m3-api
    idea: .megaplan/briefs/artifact-store/m3-api.md
    profile: partnered               # tier 3 — once schema+storage are locked, the API is mechanical
    depth: medium

  - label: m4-docs
    idea: .megaplan/briefs/artifact-store/m4-docs.md
    profile: directed                # tier 2 — docs benefit from a smart plan, cheap to execute

on_failure:
  abort: stop_chain                  # stop_chain | skip_milestone | retry_milestone
on_escalate:
  abort: stop_chain
merge_policy: auto                   # auto | manual

driver:
  robustness: standard               # default if a milestone doesn't override
  auto_approve: true
  max_iterations: 60
  poll_sleep: 8.0
```

### Milestone fields

| Field | Required | Meaning |
|---|---|---|
| `label` | yes | Short identifier (e.g. `m1`, `m2-storage`). Used in branch names and state files. |
| `idea` | yes | Path to the brief markdown file. Same as `megaplan init <idea>`. |
| `profile` | no | `solo` / `directed` / `partnered` / `premium` / `apex`. See megaplan-prep. |
| `robustness` | no | `bare` / `light` / `full` / `thorough` / `extreme`. Falls back to `driver.robustness`. |
| `depth` | no | `low` / `medium` / `high` / `xhigh` / `max`. |
| `vendor` | no | `claude` / `codex`. |
| `with_prep`, `with_feedback` | no | Booleans. |
| `phase_model` | no | List of `phase=spec` strings — the surgical escape hatch. |
| `deepseek_provider` | no | `direct` / `fireworks`. |
| `bakeoff` | no | Bake-off spec; rarely needed inside a chain. |
| `notes` | no | Free text retained in state for the audit trail. |

### Failure semantics

Two knobs control what the chain does when a milestone fails (`on_failure`) or hits an escalation (`on_escalate`):

- **`stop_chain`** — halt. The chain state is preserved; you re-run after fixing whatever broke.
- **`skip_milestone`** — record the milestone as skipped, continue to the next.
- **`retry_milestone`** — re-attempt the same milestone from scratch.

Default is `stop_chain` for both — failures should halt unless you've deliberately said otherwise.

## Per-milestone rubric — same dials as megaplan-prep

Each milestone is a full megaplan. The three dials (`profile` / `robustness` / `depth`) apply per-milestone — see **megaplan-prep** for how to pick them. **Milestones in the same chain can be different tiers.** A typical epic has one or two high-stakes milestones at `premium` or `apex` and several mechanical milestones at `partnered` or `directed`.

The shorthand from megaplan-prep works for chain-spec notes: a milestone block annotated `# partnered//high +prep` in your chain.yaml comments tells the reader the intent at a glance.

## Running the chain

```bash
# Drive the full chain until completion (or failure).
megaplan chain start --spec /path/to/chain.yaml

# Drive at most one pending milestone, persist progress, stop cleanly.
megaplan chain start --spec /path/to/chain.yaml --one

# Read-only: show current chain progress without driving anything.
megaplan chain status --spec /path/to/chain.yaml
```

### Flags worth knowing

- **`--one`** — single-step the chain. Useful when you want to inspect each milestone's output before letting the next one kick off, or when running under an external supervisor that wants tick-by-tick control.
- **`--no-git-refresh`** — skip the automatic base-branch checkout + pull that runs before each milestone. Use this on dev checkouts where chain shouldn't stomp the currently checked-out branch.
- **`--no-push`** — disable branch creation, PR creation, commits, and pushes. For local / no-network runs.

### State and resuming

Progress is persisted under `.megaplan/plans/.chains/<spec-stem>-<digest>.json`. The digest is computed from the resolved spec path, so the same spec resumes deterministically. To resume after an interruption, just re-run `megaplan chain start --spec <same path>` — the driver reads the state file, skips completed milestones, and picks up at the current one.

State persistence means:

- A crash, restart, or SIGINT mid-milestone doesn't lose prior milestones' work.
- Failed milestones can be re-attempted by deleting the milestone's plan directory and re-running — the chain will redrive that milestone.
- Editing the spec after milestones have completed only affects un-started milestones; completed entries in state stay as-is.

## Cloud chain mode

For chains that need to outlive your terminal session, run them inside `megaplan cloud` with `mode: chain` in `cloud.yaml`. The container drives the chain unattended; you observe via `megaplan cloud status` / `cloud logs` / `cloud attach`. See `docs/cloud.md` for the cloud reference.

When supervising a long cloud chain, follow the cadence in the main megaplan skill: check after launch, again after 10-15 min, then hourly.

## End-to-end example

Scope: build a new artifact store that downstream sprints will consume. ~5 weeks of work, four sequential milestones.

**1. Decompose into milestones.** Create an epic directory under `.megaplan/briefs/` and write one idea file per milestone, each sized to ~1 week:

```
.megaplan/briefs/artifact-store/m1-schema.md         # schema + invariants
.megaplan/briefs/artifact-store/m2-storage.md        # storage layer against the schema
.megaplan/briefs/artifact-store/m3-api.md            # public API over storage
.megaplan/briefs/artifact-store/m4-docs.md           # docs + migration guide
.megaplan/briefs/artifact-store/chain.yaml           # chain spec
```

Each idea file is a full brief (see the "What goes in the brief" section of megaplan-prep) — outcome, scope, locked decisions, open questions, constraints, done criteria, touchpoints, anti-scope. Briefs are locked at init; later edits are not re-read.

**2. Write `chain.yaml`** (see the spec example above). Pick a tier per milestone:

- m1 schema → `apex` (kernel invariant, every downstream sprint depends on it)
- m2 storage → `premium` (production migration logic)
- m3 api → `partnered` (cross-cutting but mechanical once schema+storage are locked)
- m4 docs → `directed` (docs benefit from a smart plan; execution is cheap)

**3. Drive it.**

```bash
megaplan chain start --spec .megaplan/briefs/artifact-store/chain.yaml
```

For a long unattended run, do this inside `megaplan cloud` so it survives the terminal.

**4. Observe.**

```bash
megaplan chain status --spec .megaplan/briefs/artifact-store/chain.yaml
```

Shows current milestone index, current plan name, last state, completed milestones, and PR state if applicable.

**5. If a milestone fails or escalates**, the chain halts (with default `stop_chain`). Investigate the failing plan via `megaplan status --plan <name>` and `megaplan audit --plan <name>`. Once you've fixed the brief or escalated the rubric (via `megaplan override set-profile` etc.), re-run `megaplan chain start --spec` and the chain resumes.

## Common pitfalls

- **Don't decompose so finely that each milestone is <2 days of work.** A chain of 10 micro-milestones is harder to follow than 4 right-sized ones, and the harness overhead dominates the actual work.
- **Don't reach for a chain when you don't know the breakdown yet.** Run a scoping megaplan first; let it produce the milestone list; then write the chain spec.
- **Don't tier-flatten** — uniformly picking `partnered` for every milestone misses the point of the per-milestone rubric. Differentiate; the high-stakes milestone deserves a higher tier and the cheap milestone doesn't.
- **Don't bake-off inside a chain unless you genuinely need it.** Bakeoffs are independent runs; nesting them inside a chain spec multiplies the cost without typically producing useful signal.
- **Don't edit the spec mid-flight expecting completed milestones to re-run.** State is sticky for completed entries by design — that's how resume works.

--- FILE: arnold_pipelines/megaplan/skills/megaplan-tickets/SKILL.md (1,220p) ---
---
name: megaplan-tickets
description: File and manage megaplan tickets — short, repo-scoped notes on problems or observations that get folded into epics and auto-addressed when the resolving epic completes.
---

# Megaplan tickets

Tickets are short, repo-scoped notes on problems, bugs, or "we should look at this" observations against a codebase. They live as committed `.md` files under `<repo>/.megaplan/tickets/` and (when a cloud store is configured) mirror to `tickets` / `ticket_epics` tables. Tickets are inert until folded into an epic — they capture problems, not work.

## When to file a ticket

Reach for `megaplan ticket new` when:
- During epic or plan execution you notice an **out-of-scope problem** that should be tracked but isn't blocking the current task.
- The user explicitly asks you to **capture an observation** ("file a ticket for that", "make a note of this for later").
- You want to log a rough edge or potential bug whose fix would be its own piece of work.

Do **not** use tickets for:
- Guidance/corrections to *how the tooling itself behaves* — that's `megaplan feedback` (a separate, plan-scoped concept).
- In-flight task state — that's the executor's own checklist.
- General notes or chat — write them in the conversation.

## Filing

```bash
megaplan ticket new "<title>" -b "<body>" [--tags tag1,tag2]
```

Conventions:
- `-b "..."`, `--edit` (open `$EDITOR`), and `-` (read body from stdin) are mutually exclusive; one is required.
- `ticket new` prints **only the ULID** on stdout on success (logs go to stderr). Capture it for piping.
- `--tags` is comma-separated. Tags are freeform; common ones: `bug`, `refactor`, `tech-debt`, `observability`, `docs`, `cross-repo`.
- `source` is auto-derived: if `MEGAPLAN_TURN_ID` is set (the agent is running under a megaplan-launched worker), `source=agent` and the turn id is recorded; otherwise `source=human`.
- The repo is resolved from cwd via its root commit SHA (`git rev-list --max-parents=0 HEAD`). Identity survives rename / transfer / remote change.

Multi-line body via stdin:
```bash
cat <<'EOF' | megaplan ticket new "Title here" --tags tag1,tag2 -
First paragraph of the body.

More detail in a second paragraph.
EOF
```

## Reading

```bash
megaplan ticket list   [--status open|addressed|dismissed] [--tags t1,t2] [--json]
megaplan ticket show   <id> [--json]
megaplan ticket search [KW ...] [--all] [--project P]... [--all-projects]
                       [--status ...] [--tags ...]
                       [--sort created|edited|length|title] [--asc]
                       [--limit N] [--json] [--no-snippet]
```

`--json` on read commands emits structured output; safe for piping.

### Searching across repos

`ticket search` is the cross-cutting reader. Defaults:

- **Scope** — current repo. Pass `--all-projects` to scan every known repo (locally: the auto-maintained `~/.config/megaplan/known_repos.json` registry; cloud: every codebase). Pass `--project PATH|owner/name|name` (repeatable) to scope to specific repos.
- **Keywords** — multiple positional args. Default is **OR** (any keyword matches). Pass `--all` to require all keywords. Match is case-insensitive substring across **title, body, tags, and resolution_note**.
- **Sort** — `--sort {created,edited,length,title}`; `--asc` flips to ascending. Default: created, descending.
- **Snippets** — human output shows a 120-char snippet around the first match. `--no-snippet` to hide.

Examples:

```bash
# Anything mentioning "stderr" or "timeout" in this repo:
megaplan ticket search stderr timeout

# Same, but require BOTH terms:
megaplan ticket search stderr timeout --all

# Across every repo on this machine, only open, sorted by longest body first:
megaplan ticket search redis --all-projects --status open --sort length --json

# Scoped to two specific repos:
megaplan ticket search auth --project ~/Documents/reigh-app --project banodoco/megaplan
```

## Editing and linking

```bash
megaplan ticket edit    <id> [--title ...] [--body ...] [--status ...] [--add-tag ...] [--remove-tag ...]
megaplan ticket link    <ticket> <epic> [--resolves]
megaplan ticket unlink  <ticket> <epic>
megaplan ticket addressed <id> [--note "..."]
megaplan ticket dismiss   <id> [--reason "..."]
megaplan ticket reopen    <id>
```

`link ... --resolves` marks the join with `resolves_on_complete=true`. When the linked epic transitions to `done`, the ticket auto-flips to `addressed` and gets a `resolution_note` referencing the epic. Idempotent — re-running on an already-addressed ticket is a no-op.

## Modes

Megaplan runs in one of two modes; tickets work transparently in both:

- **Local-only** (no cloud store configured) — `.md` files on disk are the sole source of truth. `codebase_id` will be `null` in frontmatter; identity is computed on demand from the repo's root SHA.
- **Cloud-configured** (`SUPABASE_DB_URL` or megaplan config points at a store) — every operation writes the `.md` file **and** mirrors to the `tickets` / `ticket_epics` tables. Auto-registers the codebase on first ticket if needed.

You do not need to detect the mode yourself; the CLI dispatches based on whether a store is configured.

## Local format

```
<repo>/.megaplan/tickets/{ulid}-{slug}.md
```

```markdown
---
id: 01HXY...
title: Execute step retries swallow stderr on timeout
tags: [execute, observability]
status: open
source: agent
codebase_id: null            # null in local-only, populated in cloud
created_at: 2026-05-11T14:22:00Z
epics:
  - id: epic_01HZ...
    resolves_on_complete: true
---

# Body

Markdown prose describing the issue.
```

Commit ticket files. The `.md` is the human-readable artifact and (in local-only) the system of record.

## Discovery at planning time

When a new epic is created or refined for the current repo, the planner automatically surfaces open tickets ranked by tag overlap with the epic's goal and recency. The planner may propose links with `resolves_on_complete=true`. You don't need to remind it — discovery is built into the plan-phase prompt assembly.

## Quick reference

| You want to … | Run |
|---|---|
| File a ticket | `megaplan ticket new "title" -b "body" [--tags t1,t2]` |
| Pipe a multi-line body | `cat body.md \| megaplan ticket new "title" -` |
| List open tickets | `megaplan ticket list --status open --json` |
| Search by keyword in this repo | `megaplan ticket search foo bar` |
| Search across every repo | `megaplan ticket search foo --all-projects` |
| Link a ticket to an epic so it auto-closes | `megaplan ticket link <tid> <eid> --resolves` |
| Mark addressed manually | `megaplan ticket addressed <tid> --note "..."` |
| Reopen a closed ticket | `megaplan ticket reopen <tid>` |

That's the whole surface. The auto-address hook does the rest.
