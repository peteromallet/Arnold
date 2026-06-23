You are a DeepSeek subagent doing a read-only inventory for AgentBox. The user asked us to find EVERYTHING existing in this repo/local skills that overlaps with the desired Discord-first AgentBox: start tickets/epics/megaplans/chains from Discord, Guardian repairs/relaunches blocked runs, completed work gets pushed/PRd/consolidated, and DeepSeek/subagents can be used. The brief embeds local excerpts. Return a decisive inventory of reusable mechanics, with file refs, gaps, and concrete recommendations. Under 1200 words. Focus: launch mechanics for Megaplan init/bootstrap/chain/cloud; operation creation; worktree launch; tmux/session/log path.


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

--- FILE: arnold_pipelines/megaplan/cli/__init__.py (1798,2138p) ---
def _setup_init_worktree(args: argparse.Namespace) -> None:
    """When ``--in-worktree`` is set on ``megaplan init``, create the worktree
    and rewrite ``args`` so the rest of the init flow lands inside it.

    Safety contract: this function MUST be strictly additive. It may only
    create one new branch + one new worktree directory. It never modifies the
    invoking repo, its branches (other than the one it creates), its remotes,
    its stash, or any other worktree. If anything looks ambiguous, it raises.
    """
    name = getattr(args, "in_worktree", None)
    clean_worktree = bool(getattr(args, "clean_worktree", False))
    carry_dirty_flag = bool(getattr(args, "carry_dirty", False))
    if clean_worktree and carry_dirty_flag:
        raise CliError(
            "invalid_args",
            "--clean-worktree and --carry-dirty are mutually exclusive",
        )
    if name is None:
        if getattr(args, "worktree_from", None):
            raise CliError(
                "invalid_args",
                "--worktree-from is only valid alongside --in-worktree",
            )
        if clean_worktree or carry_dirty_flag:
            raise CliError(
                "invalid_args",
                "--clean-worktree / --carry-dirty are only valid with --in-worktree",
            )
        return

    from arnold_pipelines.megaplan.bakeoff.worktree import (
        branch_exists,
        carry_dirty_state_atomic,
        create_named_worktree,
        ensure_no_inprogress_op,
        has_dirty_state,
        resolve_ref,
        validate_worktree_name,
        worktree_registered,
    )

    if getattr(args, "project_dir", None):
        raise CliError(
            "invalid_args",
            "pass either --project-dir or --in-worktree, not both",
        )

    validate_worktree_name(name)

    # Locate the invoking repo. We deliberately do NOT use --project-dir here
    # (we just rejected it above); we use cwd-walk-up so the user can run
    # `megaplan init --in-worktree foo` from anywhere inside the repo.
    invoking_repo = _find_git_root(Path.cwd().resolve())
    if invoking_repo is None:
        raise CliError(
            "not_a_git_repo",
            "--in-worktree requires running from inside a git repository",
        )

    ensure_no_inprogress_op(invoking_repo)

    target = (Path.home() / "Documents" / ".megaplan-worktrees" / name).resolve()
    if target.exists():
        raise CliError(
            "worktree_target_exists",
            f"refusing to create worktree: target path already exists: {target}",
        )
    if worktree_registered(invoking_repo, target):
        raise CliError(
            "worktree_already_registered",
            f"git already has a worktree registered at {target} "
            "(run `git worktree prune` manually if it's stale)",
        )
    if branch_exists(invoking_repo, name):
        raise CliError(
            "worktree_branch_exists",
            f"branch {name!r} already exists locally or on a remote; "
            "pick a different --in-worktree name",
        )

    base_ref = getattr(args, "worktree_from", None) or "HEAD"
    base_sha = resolve_ref(invoking_repo, base_ref)

    create_named_worktree(invoking_repo, target, base_sha, name)

    # Carry uncommitted state from the source repo into the new worktree
    # unless the caller explicitly opted out via --clean-worktree. The source
    # repo is read-only throughout: we only capture a diff and copy untracked
    # files; we never run stash/checkout/reset/clean on it.
    tracked_carried = 0
    untracked_carried = 0
    if not clean_worktree:
        should_carry = carry_dirty_flag or has_dirty_state(invoking_repo)
        if should_carry:
            tracked_carried, untracked_carried = carry_dirty_state_atomic(
                invoking_repo, target
            )

    # Rewrite args so the rest of the init flow lands inside the worktree.
    args.project_dir = str(target)
    # Stash audit data on args so handle_init can persist it into plan state.
    args._worktree_meta = {
        "name": name,
        "path": str(target),
        "branch": name,
        "base_ref": base_ref,
        "base_sha": base_sha,
        "source_repo": str(invoking_repo),
        "carried_tracked": tracked_carried,
        "carried_untracked": untracked_carried,
    }
    # Update work-dir override so subprocess workers run in the worktree.
    from arnold_pipelines.megaplan.workers import set_work_dir_override

    set_work_dir_override(target)

    print(
        f"Created worktree at {target} on branch {name} "
        f"(base {base_sha[:12]}); initializing plan inside it...",
        file=sys.stderr,
    )
    if tracked_carried or untracked_carried:
        print(
            f"warning: carried {tracked_carried} uncommitted file change(s) "
            f"and {untracked_carried} untracked file(s) from {invoking_repo} "
            f"into {target}. Source worktree is unchanged.\n"
            f"  * To start the worktree from a clean base instead, commit your "
            f"changes first or re-run with --clean-worktree.\n"
            f"  * Files were carried as unstaged in the new worktree (staging "
            f"information is not preserved). Run `git diff` or `git status` "
            f"inside the worktree to inspect.",
            file=sys.stderr,
        )


def _reset_chain_worktree_target(
    invoking_repo: Path,
    target: Path,
    branch: str,
    *,
    worktree_registered: Callable[[Path, Path], bool],
) -> None:
    """Clear the named chain worktree target for an explicit --fresh start."""
    if not (target.exists() or worktree_registered(invoking_repo, target)):
        return
    if worktree_registered(invoking_repo, target):
        proc = subprocess.run(
            ["git", "worktree", "remove", "--force", str(target)],
            cwd=str(invoking_repo),
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            raise CliError(
                "worktree_reset_failed",
                (
                    f"refusing --fresh worktree reset: could not remove registered "
                    f"worktree at {target}: {(proc.stderr or proc.stdout).strip()}"
                ),
            )
    if target.exists():
        shutil.rmtree(target)
    proc = subprocess.run(
        ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"],
        cwd=str(invoking_repo),
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode == 0:
        delete = subprocess.run(
            ["git", "branch", "-D", branch],
            cwd=str(invoking_repo),
            capture_output=True,
            text=True,
            check=False,
        )
        if delete.returncode != 0:
            raise CliError(
                "worktree_reset_failed",
                (
                    f"refusing --fresh worktree reset: could not delete local "
                    f"branch {branch!r}: {(delete.stderr or delete.stdout).strip()}"
                ),
            )


def _chain_worktree_base_ref(args: argparse.Namespace) -> str:
    """Resolve the git ref to fork the chain's shared worktree from.

    Explicit ``--worktree-from`` always wins. Otherwise default to the chain
    spec's ``base_branch`` — NOT the invoking ``HEAD``. The chain runs every
    milestone off ``base_branch`` (``git checkout -B <milestone> <base_branch>``),
    so forking the worktree from a stale invoking HEAD makes any carried-untracked
    file that is *tracked* on ``base_branch`` collide on that checkout
    ("untracked working tree files would be overwritten"; ticket 01KTQ35AB8).
    Forking from ``base_branch`` lands the carried dirt on top of the base the
    chain actually uses, so the checkout is a no-op base and never collides.
    Falls back to ``HEAD`` if the spec is absent or unreadable.
    """
    explicit = getattr(args, "worktree_from", None)
    if explicit:
        return explicit
    spec_path = getattr(args, "spec", None)
    if spec_path:
        try:
            from arnold_pipelines.megaplan.chain import load_spec

            return load_spec(Path(spec_path)).base_branch
        except CliError:
            pass
    return "HEAD"


def _setup_chain_worktree(args: argparse.Namespace) -> None:
    """Create a shared worktree for ``megaplan chain`` and reroot the command.

    Unlike ``megaplan init --in-worktree``, this creates one worktree for the
    entire chain. Every milestone plan initialized by the chain then receives
    ``--project-dir <that-worktree>`` from the chain driver.
    """
    name = getattr(args, "in_worktree", None)
    clean_worktree = bool(getattr(args, "clean_worktree", False))
    carry_dirty_flag = bool(getattr(args, "carry_dirty", False))
    action = getattr(args, "chain_action", None)
    if clean_worktree and carry_dirty_flag:
        raise CliError(
            "invalid_args",
            "--clean-worktree and --carry-dirty are mutually exclusive",
        )
    if name is None:
        if getattr(args, "worktree_from", None):
            raise CliError(
                "invalid_args",
                "--worktree-from is only valid alongside --in-worktree",
            )
        if clean_worktree or carry_dirty_flag:
            raise CliError(
                "invalid_args",
                "--clean-worktree / --carry-dirty are only valid with --in-worktree",
            )
        return

    if action not in (None, "start", "plan", "execute"):
        raise CliError(
            "invalid_args",
            "--in-worktree is only valid for `megaplan chain start`, `plan`, or `execute`",
        )
    if getattr(args, "project_dir", None):
        raise CliError(
            "invalid_args",
            "pass either --project-dir or --in-worktree, not both",
        )

    from arnold_pipelines.megaplan.bakeoff.worktree import (
        branch_exists,
        carry_dirty_state_atomic,
        create_named_worktree,
        ensure_no_inprogress_op,
        has_dirty_state,
        resolve_ref,
        validate_worktree_name,
        worktree_registered,
    )

    validate_worktree_name(name)

    invoking_repo = _find_git_root(Path.cwd().resolve())
    if invoking_repo is None:
        raise CliError(
            "not_a_git_repo",
            "--in-worktree requires running from inside a git repository",
        )
    ensure_no_inprogress_op(invoking_repo)

    target = (Path.home() / "Documents" / ".megaplan-worktrees" / name).resolve()
    if bool(getattr(args, "fresh", False)):
        _reset_chain_worktree_target(
            invoking_repo,
            target,
            name,
            worktree_registered=worktree_registered,
        )
    if target.exists():
        raise CliError(
            "worktree_target_exists",
            f"refusing to create worktree: target path already exists: {target}",
        )
    if worktree_registered(invoking_repo, target):
        raise CliError(
            "worktree_already_registered",
            f"git already has a worktree registered at {target} "
            "(run `git worktree prune` manually if it's stale)",
        )
    if branch_exists(invoking_repo, name):
        raise CliError(
            "worktree_branch_exists",
            f"branch {name!r} already exists locally or on a remote; "
            "pick a different --in-worktree name",
        )

    base_ref = _chain_worktree_base_ref(args)
    base_sha = resolve_ref(invoking_repo, base_ref)
    create_named_worktree(invoking_repo, target, base_sha, name)

    tracked_carried = 0
    untracked_carried = 0
    if not clean_worktree:
        should_carry = carry_dirty_flag or has_dirty_state(invoking_repo)
        if should_carry:
            tracked_carried, untracked_carried = carry_dirty_state_atomic(
                invoking_repo, target
            )

    args.project_dir = str(target)
    from arnold_pipelines.megaplan.workers import set_work_dir_override

    set_work_dir_override(target)

    # Point engine-isolation at the invoking (engine) checkout.  The target
    # worktree shadows the editable install when Python resolves ``arnold`` from
    # cwd, so ``megaplan_engine_root()`` needs an explicit anchor.
    os.environ["MEGAPLAN_ENGINE_ROOT"] = str(invoking_repo)

    print(
        f"Created chain worktree at {target} on branch {name} "
        f"(base {base_sha[:12]}); running chain inside it...",
        file=sys.stderr,
    )
    if tracked_carried or untracked_carried:
        print(
            f"warning: carried {tracked_carried} uncommitted file change(s) "
            f"and {untracked_carried} untracked file(s) from {invoking_repo} "
            f"into {target}. Source worktree is unchanged.",
            file=sys.stderr,
        )



def _handle_list_pipelines(args: argparse.Namespace) -> StepResponse:

--- FILE: arnold_pipelines/megaplan/cloud/cli.py (1,260p) ---
"""CLI entrypoints for arnold cloud commands."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import sys
from datetime import datetime, timezone
from dataclasses import dataclass, replace
from importlib import resources
from pathlib import Path, PurePosixPath
from tempfile import NamedTemporaryFile, TemporaryDirectory
from typing import Any

import yaml

from arnold_pipelines.megaplan.cloud.auth import seed_codex_oauth
from arnold_pipelines.megaplan.cloud.providers.base import (
    DeployReport,
    DeployStepReport,
    _write_redacted_output,
    get_provider,
)
from arnold_pipelines.megaplan.cloud.redact import redact
from arnold_pipelines.megaplan.cloud.spec import CloudSpec, RailwaySpec, apply_repo_overrides, load_spec as load_cloud_spec
from arnold_pipelines.megaplan.cloud.template import materialize_deploy_dir, render_ensure_repos_block
from arnold_pipelines.megaplan.types import CliError


load_spec = load_cloud_spec

# Cloud deployments always drive phases via subprocess (remote SSH exec);
# the substrate is pinned here so the cloud CLI explicitly declares its
# execution model to _phase_command (M3 Step 12 compatibility boundary).
cloud_substrate: str = "subprocess_isolated"


def _register_cloud_subcommands(cloud_parser: argparse.ArgumentParser) -> None:
    cloud_sub = cloud_parser.add_subparsers(dest="cloud_action", required=True)

    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument(
        "--cloud-yaml",
        default=None,
        help="Path to cloud.yaml (default: <project-root>/cloud.yaml)",
    )

    init_parser = cloud_sub.add_parser(
        "init",
        parents=[shared],
        help="Scaffold a cloud.yaml file at the project root",
    )
    init_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing cloud.yaml",
    )

    cloud_sub.add_parser("build", parents=[shared], help="Build the cloud image")
    cloud_sub.add_parser("deploy", parents=[shared], help="Deploy the cloud runner")

    chain_parser = cloud_sub.add_parser(
        "chain",
        parents=[shared],
        help="Upload a chain spec and start it remotely",
    )
    chain_parser.add_argument("spec", help="Local chain spec path")
    chain_parser.add_argument(
        "--idea-dir",
        default=None,
        help="Directory containing local idea files referenced by the chain spec",
    )
    chain_parser.add_argument(
        "--fresh",
        "--reset",
        dest="fresh",
        action="store_true",
        help="Reset this chain's remote state before launch",
    )
    chain_parser.add_argument(
        "--no-git-refresh",
        action="store_true",
        help=(
            "Pass --no-git-refresh to the remote `python -m arnold_pipelines.megaplan chain start`, "
            "skipping the automatic base-branch refresh."
        ),
    )
    _add_repo_override_args(chain_parser)

    bootstrap_parser = cloud_sub.add_parser(
        "bootstrap",
        parents=[shared],
        help="Upload an idea file and start arnold init remotely",
    )
    bootstrap_parser.add_argument("idea_file", help="Local idea file path")
    bootstrap_parser.add_argument("--plan-name", default=None, help="Optional remote plan name")
    bootstrap_parser.add_argument("--robustness", default="standard")
    _add_repo_override_args(bootstrap_parser)

    status_parser = cloud_sub.add_parser(
        "status",
        parents=[shared],
        help="Fetch remote `arnold status` JSON",
    )
    status_parser.add_argument(
        "--chain",
        action="store_true",
        help="Fetch remote chain_state.json and render core chain status",
    )
    status_parser.add_argument(
        "--all",
        action="store_true",
        help="List active cloud chain tmux sessions on the shared runner",
    )
    status_parser.add_argument(
        "--remote-spec",
        default=None,
        help="Explicit remote chain spec path for `cloud status --chain`",
    )
    status_parser.add_argument("--plan", help="Optional plan name to query remotely")

    attach_parser = cloud_sub.add_parser(
        "attach",
        parents=[shared],
        help="Attach to the remote tmux session",
    )
    attach_parser.add_argument(
        "--session",
        help="Override the remote tmux session name for providers that support sessions",
    )

    logs_parser = cloud_sub.add_parser(
        "logs",
        parents=[shared],
        help="Stream or fetch remote logs",
    )
    logs_parser.add_argument(
        "--no-follow",
        action="store_true",
        help="Fetch recent logs without streaming",
    )

    cloud_sub.add_parser(
        "chains",
        parents=[shared],
        help="List active cloud chain tmux sessions on the shared runner",
    )

    exec_parser = cloud_sub.add_parser(
        "exec",
        parents=[shared],
        help="Run an arbitrary remote command",
    )
    exec_parser.add_argument("command", help="Command string to execute remotely")

    resume_parser = cloud_sub.add_parser(
        "resume",
        parents=[shared],
        help="Resume the remote plan's next step",
    )
    resume_parser.add_argument("--plan", help="Optional plan name to resume")

    cloud_sub.add_parser("down", parents=[shared], help="Pause the deployment without deleting volume")

    supervise_parser = cloud_sub.add_parser(
        "supervise",
        parents=[shared],
        help="Run a one-shot supervisor tick against a cloud chain",
    )
    supervise_parser.add_argument(
        "--chain",
        action="store_true",
        help="Supervise the remote chain (required)",
    )
    supervise_parser.add_argument(
        "--remote-spec",
        default=None,
        help="Explicit remote chain spec path for supervision",
    )

    destroy_parser = cloud_sub.add_parser(
        "destroy",
        parents=[shared],
        help="Tear down the deployment and delete the volume if configured",
    )
    destroy_parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip the interactive destroy confirmation",
    )


def build_cloud_parser(subparsers: Any) -> None:
    cloud_parser = subparsers.add_parser(
        "cloud",
        help="Manage provider-backed arnold cloud runners",
    )
    _register_cloud_subcommands(cloud_parser)


def _add_repo_override_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--repo-url", default=None, help="Override cloud.yaml repo.url in memory")
    parser.add_argument("--repo-branch", default=None, help="Override cloud.yaml repo.branch in memory")
    parser.add_argument("--repo-workspace", default=None, help="Override cloud.yaml repo.workspace in memory")


def run_cloud_cli(root: Path, args: argparse.Namespace) -> int:
    try:
        action = getattr(args, "cloud_action")
        if action == "init":
            return _run_init(root, args)

        spec = _load_cloud_spec(root, args)
        provider = _provider_for_action(spec, args)

        if action == "chain":
            with _materialized_deploy_dir(spec):
                return _run_chain_wrapper(root, args, spec, provider)

        if action == "bootstrap":
            with _materialized_deploy_dir(spec):
                return _run_bootstrap_wrapper(args, spec, provider)

        if action == "build":
            with _materialized_deploy_dir(spec) as deploy_dir:
                return provider.build(deploy_dir)

        if action == "deploy":
            secrets = {name: os.environ.get(name, "") for name in spec.secrets}
            with _materialized_deploy_dir(spec) as deploy_dir:
                result = provider.deploy(deploy_dir, secrets=secrets)
                report = _coerce_deploy_report(result, spec=spec, deploy_dir=deploy_dir)
                report.steps = [
                    *_deploy_context_steps(deploy_dir),
                    *report.steps,
                ]
            if report.exit_code == 0:
                seed_messages: list[str] = []
                seed_result = seed_codex_oauth(spec, provider, writer=seed_messages.append)
                report.steps.append(
                    DeployStepReport(
                        name="seed Codex OAuth",
                        status="ok",
                        detail=_oauth_seed_detail(seed_result),
                        stderr="".join(seed_messages),
                        metadata=seed_result,
                    )
                )
            _emit_deploy_report(report, secret_names=spec.secrets, env=os.environ)
            return report.exit_code

        if action == "status":
            if bool(getattr(args, "all", False)):
                return _run_cloud_chains(spec, provider)
            if bool(getattr(args, "chain", False)):

--- FILE: arnold_pipelines/megaplan/cloud/cli.py (260,760p) ---
            if bool(getattr(args, "chain", False)):
                return _run_chain_status(root, args, spec, provider)
            payload = cloud_status_payload(args, spec, provider)
            sys.stdout.write(json.dumps(payload, indent=2) + "\n")
            return 0

        if action == "attach":
            return provider.attach()

        if action == "logs":
            return provider.logs(follow=not bool(getattr(args, "no_follow", False)))

        if action == "chains":
            return _run_cloud_chains(spec, provider)

        if action == "exec":
            result = provider.ssh_exec(args.command)
            _relay_output(result, secret_names=spec.secrets, env=os.environ)
            return 0

        if action == "resume":
            payload = provider.status_payload(
                plan=getattr(args, "plan", None),
                workspace=spec.repo.workspace,
            )
            next_step = payload.get("next_step")
            if not isinstance(next_step, str) or not next_step:
                raise CliError("invalid_status", "Remote status did not include a next_step")
            from arnold_pipelines.megaplan.auto import _phase_command

            argv = list(_phase_command(next_step, substrate=cloud_substrate))
            if getattr(args, "plan", None):
                argv.extend(["--plan", args.plan])
            command = f"cd {shlex.quote(spec.repo.workspace)} && arnold {shlex.join(argv)}"
            result = provider.ssh_exec(command)
            _relay_output(result, secret_names=spec.secrets, env=os.environ)
            return 0

        if action == "down":
            return provider.down()

        if action == "supervise":
            if bool(getattr(args, "chain", False)):
                return _run_supervise_tick(root, args, spec, provider)
            raise CliError(
                "invalid_args",
                "`cloud supervise` requires --chain. Try `arnold cloud supervise --chain`.",
            )

        if action == "destroy":
            if not bool(getattr(args, "yes", False)) and not _confirm_destroy(spec):
                return 1
            result = provider.destroy(volume=spec.resources.volume)
            _clear_persistent_deploy_dir(spec)
            return result

        raise CliError("invalid_args", f"Unknown cloud action: {action}")
    except CliError as exc:
        return _emit_error(exc)


def _cloud_yaml_path(root: Path, args: argparse.Namespace) -> Path:
    raw = getattr(args, "cloud_yaml", None)
    if not raw:
        return root / "cloud.yaml"
    return Path(raw).expanduser().resolve()


def _load_cloud_spec(root: Path, args: argparse.Namespace) -> CloudSpec:
    spec = load_spec(_cloud_yaml_path(root, args))
    return apply_repo_overrides(
        spec,
        repo_url=getattr(args, "repo_url", None),
        repo_branch=getattr(args, "repo_branch", None),
        repo_workspace=getattr(args, "repo_workspace", None),
    )


def _provider_for_action(spec: CloudSpec, args: argparse.Namespace):
    # Gate session overrides on provider capability, not on a provider-name special case.
    base_provider = get_provider(spec.provider, spec)
    session_name = getattr(args, "session", None)
    if not session_name:
        return base_provider
    supports_session = base_provider.supports_session
    if not supports_session:
        raise CliError("invalid_args", "--session is only supported for provider: railway")
    railway = spec.railway or RailwaySpec()
    overridden = replace(spec, railway=replace(railway, session=session_name))
    return get_provider(overridden.provider, overridden)


def _ensure_repo_command(spec: CloudSpec) -> str:
    # Clone the primary repo AND every declared `extra_repos` sibling. The
    # container entrypoint clones the full set at boot, but boot only runs once
    # per `cloud deploy`. A `cloud chain` launched against a container that
    # pre-dates an `extra_repos` edit would otherwise silently leave siblings
    # missing on the persistent volume, blocking any milestone that depends on
    # them.
    return render_ensure_repos_block(spec)


def _ensure_repo_checkout(spec: CloudSpec, provider, *, relay: bool = True) -> None:
    result = provider.ssh_exec(_ensure_repo_command(spec))
    if relay:
        _relay_output(result, secret_names=spec.secrets, env=os.environ)
    if result.returncode != 0:
        repos = [spec.repo, *spec.extra_repos]
        targets = ", ".join(f"{r.url}@{r.branch} into {r.workspace}" for r in repos)
        raise CliError(
            "provider_failed",
            f"ensure repo checkout failed for {targets} (exit {result.returncode})",
        )


def _run_init(root: Path, args: argparse.Namespace) -> int:
    target = _cloud_yaml_path(root, args)
    if target.exists() and not bool(getattr(args, "force", False)):
        raise CliError(
            "invalid_args",
            f"cloud spec already exists: {target}. Use --force to overwrite.",
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    template = resources.files("arnold_pipelines.megaplan.cloud.templates").joinpath("cloud.yaml.tmpl")
    target.write_text(template.read_text(encoding="utf-8"), encoding="utf-8")
    sys.stdout.write(json.dumps({"success": True, "cloud_yaml": str(target)}, indent=2) + "\n")
    return 0


def _relative_remote_path(*, workspace: str, remote_path: str) -> Path:
    remote = PurePosixPath(remote_path)
    workspace_path = PurePosixPath(workspace)
    if remote == workspace_path:
        return Path()
    elif str(remote).startswith(f"{workspace_path}/"):
        return Path(*remote.relative_to(workspace_path).parts)
    elif remote.is_absolute():
        return Path(*remote.parts[1:])
    return Path(*remote.parts)


def _append_unique_path(paths: list[Path], candidate: Path) -> None:
    if candidate not in paths:
        paths.append(candidate)


def _local_idea_source_candidates(*, root: Path, idea_dir: Path, workspace: str, remote_path: str) -> list[Path]:
    relative_remote = _relative_remote_path(workspace=workspace, remote_path=remote_path)
    candidates: list[Path] = []
    _append_unique_path(candidates, idea_dir / relative_remote)
    _append_unique_path(candidates, root / relative_remote)

    try:
        idea_dir_tail = idea_dir.relative_to(root)
    except ValueError:
        idea_dir_tail = None
    if idea_dir_tail is not None:
        try:
            deduped_tail = relative_remote.relative_to(idea_dir_tail)
        except ValueError:
            deduped_tail = None
        if deduped_tail is not None:
            _append_unique_path(candidates, idea_dir / deduped_tail)

    remote = PurePosixPath(remote_path)
    if remote.is_absolute() and not str(remote).startswith(f"{PurePosixPath(workspace)}/"):
        _append_unique_path(candidates, idea_dir / remote.name)
    return candidates


def _resolve_local_idea_source(*, root: Path, idea_dir: Path, workspace: str, remote_path: str) -> tuple[Path | None, list[Path]]:
    candidates = _local_idea_source_candidates(root=root, idea_dir=idea_dir, workspace=workspace, remote_path=remote_path)
    for candidate in candidates:
        if candidate.exists():
            return candidate, candidates
    return None, candidates


def _read_chain_yaml(path: Path) -> dict[str, Any]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return raw if isinstance(raw, dict) else {}


def _chain_spec_has_explicit_base_branch(path: Path) -> bool:
    return "base_branch" in _read_chain_yaml(path)


def _rewrite_remote_workspace_path(remote_path: str, *, source_workspace: str, target_workspace: str) -> str:
    source = PurePosixPath(source_workspace)
    target = PurePosixPath(target_workspace)
    path = PurePosixPath(remote_path)
    if path == source:
        return str(target)
    if path.is_absolute() and str(path).startswith(f"{source}/"):
        return str(target / path.relative_to(source))
    return remote_path


def _normalized_chain_upload_spec(
    local_spec_path: Path,
    *,
    base_branch: str,
    source_workspace: str | None = None,
    target_workspace: str | None = None,
    driver_overrides: dict[str, Any] | None = None,
) -> Path:
    raw = _read_chain_yaml(local_spec_path)
    workspace_changed = (
        bool(source_workspace)
        and bool(target_workspace)
        and source_workspace != target_workspace
    )
    if "base_branch" in raw and not workspace_changed and not driver_overrides:
        return local_spec_path
    normalized = dict(raw)
    if "base_branch" not in normalized:
        normalized["base_branch"] = base_branch
    if driver_overrides:
        driver = normalized.get("driver")
        driver_mapping = dict(driver) if isinstance(driver, dict) else {}
        driver_mapping.update(driver_overrides)
        normalized["driver"] = driver_mapping
    if workspace_changed and isinstance(normalized.get("milestones"), list):
        rewritten: list[Any] = []
        for item in normalized["milestones"]:
            if isinstance(item, dict) and isinstance(item.get("idea"), str):
                copied = dict(item)
                copied["idea"] = _rewrite_remote_workspace_path(
                    copied["idea"],
                    source_workspace=source_workspace or "",
                    target_workspace=target_workspace or "",
                )
                rewritten.append(copied)
            else:
                rewritten.append(item)
        normalized["milestones"] = rewritten
    with NamedTemporaryFile("w", suffix=".yaml", encoding="utf-8", delete=False) as handle:
        yaml.safe_dump(normalized, handle, sort_keys=False)
        return Path(handle.name)


def _missing_configured_secrets(spec: CloudSpec, env: dict[str, str]) -> list[str]:
    return sorted(name for name in spec.secrets if not env.get(name))


def _remote_dependency_check_command(commands: list[str]) -> str:
    quoted_commands = " ".join(shlex.quote(command) for command in commands)
    return (
        "missing=''; "
        f"for cmd in {quoted_commands}; do "
        'if ! command -v "$cmd" >/dev/null 2>&1; then missing="$missing $cmd"; fi; '
        "done; "
        'printf "%s\\n" "$missing"'
    )


def _run_remote_dependency_check(provider, commands: list[str]) -> list[str]:
    if not commands:
        return []
    result = provider.ssh_exec(_remote_dependency_check_command(commands))
    if result.returncode != 0:
        message = (result.stderr or result.stdout or "remote dependency check failed").strip()
        raise CliError("provider_failed", message)
    return sorted({part for part in result.stdout.split() if part})


def _remote_repo_head(provider, workspace: str) -> dict[str, str | None]:
    command = (
        f"git -C {shlex.quote(workspace)} rev-parse --abbrev-ref HEAD 2>/dev/null && "
        f"git -C {shlex.quote(workspace)} rev-parse HEAD 2>/dev/null"
    )
    result = provider.ssh_exec(command)
    if result.returncode != 0:
        return {"branch": None, "head": None}
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return {
        "branch": lines[0] if len(lines) >= 1 else None,
        "head": lines[1] if len(lines) >= 2 else None,
    }


def _tmux_launch_status(result, *, session_name: str = "megaplan-chain") -> str:
    output = f"{getattr(result, 'stdout', '')}\n{getattr(result, 'stderr', '')}"
    if "already running" in output:
        return "already_running"
    if f"started {session_name} session" in output:
        return "started"
    return "unknown"


def _resolved_phase_map_summary(preflight_summary: dict[str, Any]) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for milestone in preflight_summary.get("milestones", []):
        if not isinstance(milestone, dict):
            continue
        summaries.append(
            {
                "label": milestone.get("label"),
                "profile": milestone.get("profile"),
                "explicit_phase_model": milestone.get("explicit_phase_model", []),
                "resolved_phase_map": milestone.get("resolved_phase_map", {}),
                "required_agents": milestone.get("required_agents", []),
                "runtime_commands": milestone.get("runtime_commands", []),
                "env_hints": milestone.get("env_hints", []),
                "provider_requirements": milestone.get("provider_requirements", []),
            }
        )
    return summaries


def _cloud_chain_launch_provenance(
    *,
    spec: CloudSpec,
    ctx: ChainLaunchContext,
    chain_spec,
    preflight_summary: dict[str, Any],
    uploaded_idea_count: int,
    repo_head: dict[str, str | None],
    tmux_result,
    verification: dict[str, Any] | None = None,
) -> dict[str, Any]:
    current_milestone = chain_spec.milestones[0].label if chain_spec.milestones else None
    return {
        "success": True,
        "event": "cloud_chain_launched",
        "remote_spec": ctx.remote_spec_path,
        "current_milestone": current_milestone,
        "plan_name": None,
        "pr_number": None,
        "repo": {
            "url": spec.repo.url,
            "branch": spec.repo.branch,
            "workspace": ctx.workspace,
            "head": repo_head.get("head"),
            "checked_out_branch": repo_head.get("branch"),
        },
        "chain": {
            "base_branch": chain_spec.base_branch,
            "milestone_count": len(chain_spec.milestones),
            "resolved_phase_map_summary": _resolved_phase_map_summary(preflight_summary),
            "prerequisite_policy": chain_spec.prerequisite_policy,
            "validation_policy": chain_spec.validation_policy,
            "review_policy": dict(chain_spec.review_policy or {}),
        },
        "megaplan": {
            "ref": spec.megaplan.ref,
            "install_source": "cloud_image_runtime",
        },
        "uploaded_idea_count": uploaded_idea_count,
        "tmux": {
            "session": ctx.session_name,
            "status": _tmux_launch_status(tmux_result, session_name=ctx.session_name),
        },
        "log": {"chain_log": ctx.log_path},
        "launch": {
            "identity_digest": ctx.digest,
            "session_marker": ctx.marker_path,
            "derived_workspace": not spec.repo.workspace_explicit,
            "derived_session": not spec.chain_session_explicit,
        },
        "verification": verification or {},
    }


# ---------------------------------------------------------------------------
# Shared chain command helper — canonical session / log / env / quoting
# ---------------------------------------------------------------------------

CHAIN_SESSION_NAME = "megaplan-chain"
_CHAIN_LOG_RELATIVE = ".megaplan/cloud-chain.log"
_CHAIN_SESSION_MARKER_DIR = "/workspace/.megaplan/cloud-sessions"
_CHAIN_VERIFY_ATTEMPTS = 6
_CHAIN_VERIFY_SLEEP_SECONDS = 5


@dataclass(frozen=True)
class ChainLaunchContext:
    identity: str
    slug: str
    digest: str
    workspace: str
    remote_spec_path: str
    session_name: str
    log_relative: str
    log_path: str
    state_path: str
    marker_path: str


def _slugify_chain_identity(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip().lower()).strip(".-")
    return slug[:48] or "chain"


def _repo_dir_name(repo_url: str) -> str:
    tail = repo_url.rstrip("/").rsplit("/", 1)[-1] or "app"
    if tail.endswith(".git"):
        tail = tail[:-4]
    return _slugify_chain_identity(tail) or "app"


def _chain_identity_for(local_spec_path: Path, chain_spec: Any) -> tuple[str, str, str]:
    labels = ",".join(m.label for m in getattr(chain_spec, "milestones", []) if getattr(m, "label", None))
    seed = getattr(chain_spec, "seed_plan", None) or ""
    identity = f"{local_spec_path.stem}:{seed}:{labels}"
    digest = hashlib.sha1(identity.encode("utf-8")).hexdigest()[:10]
    return identity, _slugify_chain_identity(local_spec_path.stem), digest


def _derive_chain_launch_context(
    *,
    spec: CloudSpec,
    local_spec_path: Path,
    chain_spec: Any,
) -> ChainLaunchContext:
    from arnold_pipelines.megaplan import chain as chain_module

    identity, slug, digest = _chain_identity_for(local_spec_path, chain_spec)
    session_name = (
        spec.chain_session
        if spec.chain_session_explicit
        else f"{CHAIN_SESSION_NAME}-{slug}-{digest[:8]}"
    )
    workspace = (
        spec.repo.workspace
        if spec.repo.workspace_explicit
        else f"/workspace/{slug}-{digest[:8]}/{_repo_dir_name(spec.repo.url)}"
    )
    remote_spec_path = str(PurePosixPath(workspace) / "chain.yaml")
    state_path = str(chain_module._state_path_for(Path(remote_spec_path)))
    log_relative = f".megaplan/cloud-chain-{session_name}.log"
    log_path = str(PurePosixPath(workspace) / log_relative)
    marker_path = str(PurePosixPath(_CHAIN_SESSION_MARKER_DIR) / f"{session_name}.json")
    return ChainLaunchContext(
        identity=identity,
        slug=slug,
        digest=digest,
        workspace=workspace,
        remote_spec_path=remote_spec_path,
        session_name=session_name,
        log_relative=log_relative,
        log_path=log_path,
        state_path=state_path,
        marker_path=marker_path,
    )


def _get_provider_identity(spec: CloudSpec) -> str | None:
    """Return a stable provider-level identity for marker enrichment and
    consistency checks.

    This is the provider's *service/project identity*, never an SSH attach
    session name or chain tmux session name.
    """
    if spec.provider == "railway":
        if spec.railway is not None:
            return spec.railway.service
        return None
    if spec.provider == "local":
        if spec.local is not None:
            return spec.local.compose_project
        return None
    if spec.provider == "ssh":
        if spec.ssh is not None:
            return spec.ssh.host
        return None
    return None


def _deploy_log_hint(spec: CloudSpec) -> dict[str, Any]:
    if spec.provider == "railway":
        service = spec.railway.service if spec.railway is not None else "agent"
        return {"command": f"arnold cloud logs --no-follow", "service": service}
    if spec.provider == "local":
        return {"command": "arnold cloud logs --no-follow"}
    if spec.provider == "ssh":
        return {"command": "arnold cloud logs --no-follow"}
    return {"status": "unknown"}


def _deploy_context_steps(deploy_dir: Path) -> list[DeployStepReport]:
    steps: list[DeployStepReport] = []
    for relative in ("Dockerfile", "entrypoint.sh"):
        path = deploy_dir / relative
        if not path.exists():
            steps.append(
                DeployStepReport(
                    name=f"render {relative}",
                    status="missing",
                    detail=f"{relative} was not materialized",
                )
            )
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()[:12]
        steps.append(
            DeployStepReport(
                name=f"render {relative}",
                status="ok",
                detail=f"sha256={digest}",
                metadata={"path": str(path), "sha256": digest},
            )

--- FILE: arnold_pipelines/megaplan/resident/cloud.py (1,240p) ---
"""Constrained Megaplan cloud operation wrappers for resident tools."""

from __future__ import annotations

import argparse
import contextlib
from dataclasses import dataclass, field
from io import StringIO
import json
from pathlib import Path
from typing import Literal, Protocol

from arnold_pipelines.megaplan.cloud.cli import build_cloud_parser, run_cloud_cli

CloudClassification = Literal["running", "blocked", "failed", "gate-needed", "completed", "unknown"]
CloudOperation = Literal[
    "cloud_status",
    "cloud_status_chain",
    "cloud_start_chain",
    "cloud_bootstrap",
    "cloud_resume",
    "cloud_logs",
]


@dataclass(frozen=True)
class CloudToolRequest:
    operation: CloudOperation
    target_id: str | None = None
    arguments: dict[str, str] = field(default_factory=dict)
    confirmed: bool = False


@dataclass(frozen=True)
class CloudToolResult:
    classification: CloudClassification
    summary: str
    details: dict[str, object] = field(default_factory=dict)


class CloudToolBackend(Protocol):
    async def run(self, request: CloudToolRequest) -> CloudToolResult:
        """Execute one constrained cloud operation."""


class CloudCliBackend:
    """Default resident backend that dispatches through existing cloud CLI code."""

    async def run(self, request: CloudToolRequest) -> CloudToolResult:
        argv = _argv_for_request(request)
        root = Path(request.arguments.get("project_root") or ".").expanduser().resolve()
        parser = argparse.ArgumentParser()
        build_cloud_parser(parser.add_subparsers(dest="command", required=True))
        args = parser.parse_args(["cloud", *argv])
        stdout = StringIO()
        stderr = StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = run_cloud_cli(root, args)
        output = stdout.getvalue().strip()
        error_output = stderr.getvalue().strip()
        payload = _json_payload(output)
        classification = classify_cloud_payload(payload or {"returncode": code, "stderr": error_output})
        ok = code == 0
        summary = _summary_for_payload(request.operation, classification, payload, ok=ok)
        return CloudToolResult(
            classification=classification if ok else "failed",
            summary=summary,
            details={
                "returncode": code,
                "stdout": output,
                "stderr": error_output,
                "payload": payload,
                "argv": argv,
            },
        )


def classify_cloud_payload(payload: object) -> CloudClassification:
    """Classify status/chain payloads without depending on provider-specific text."""
    flat = " ".join(str(value).lower() for value in _walk_values(payload))
    if not flat.strip():
        return "unknown"
    if any(token in flat for token in ("gate-needed", "gate_needed", "gate pending", "gate_pending", "state_gated")):
        return "gate-needed"
    if any(token in flat for token in ("failed", "failure", "error", "state_failed", "traceback")):
        return "failed"
    if any(token in flat for token in ("blocked", "execution_blocked", "state_blocked")):
        return "blocked"
    if any(token in flat for token in ("completed", "complete", "done", "success", "state_done", "plan_done")):
        return "completed"
    if any(token in flat for token in ("running", "starting", "queued", "in_progress", "state_executing", "state_planning")):
        return "running"
    if isinstance(payload, dict) and payload.get("next_step"):
        return "running"
    return "unknown"


def progress_kind_for_classification(classification: CloudClassification) -> str:
    if classification == "completed":
        return "plan_done"
    if classification == "failed":
        return "plan_failed"
    if classification == "gate-needed":
        return "gate_pending"
    if classification == "blocked":
        return "execution_blocked"
    if classification == "running":
        return "phase_start"
    return "phase_end"


def cloud_run_status_for_classification(classification: CloudClassification) -> str:
    """Map resident cloud classifications onto CloudRun.status values."""
    if classification == "completed":
        return "completed"
    if classification == "failed":
        return "failed"
    if classification == "blocked":
        return "blocked"
    if classification == "gate-needed":
        return "gate-needed"
    if classification == "running":
        return "running"
    return "unknown"


def _argv_for_request(request: CloudToolRequest) -> list[str]:
    args = request.arguments
    cloud_yaml = args.get("cloud_yaml")
    argv: list[str] = []
    if request.operation == "cloud_status":
        argv = ["status"]
        if plan := args.get("plan"):
            argv.extend(["--plan", plan])
    elif request.operation == "cloud_status_chain":
        argv = ["status", "--chain"]
        if remote_spec := args.get("remote_spec"):
            argv.extend(["--remote-spec", remote_spec])
    elif request.operation == "cloud_start_chain":
        spec = args.get("spec")
        if not spec:
            raise ValueError("cloud_start_chain requires spec")
        argv = ["chain", spec]
        if idea_dir := args.get("idea_dir"):
            argv.extend(["--idea-dir", idea_dir])
        _append_repo_args(argv, args)
    elif request.operation == "cloud_bootstrap":
        idea_file = args.get("idea_file")
        if not idea_file:
            raise ValueError("cloud_bootstrap requires idea_file")
        argv = ["bootstrap", idea_file]
        if plan_name := args.get("plan_name"):
            argv.extend(["--plan-name", plan_name])
        if robustness := args.get("robustness"):
            argv.extend(["--robustness", robustness])
        _append_repo_args(argv, args)
    elif request.operation == "cloud_resume":
        argv = ["resume"]
        if plan := args.get("plan"):
            argv.extend(["--plan", plan])
    elif request.operation == "cloud_logs":
        argv = ["logs"]
        if args.get("no_follow") == "true":
            argv.append("--no-follow")
    else:
        raise ValueError(f"unsupported cloud operation: {request.operation}")
    if cloud_yaml:
        argv.extend(["--cloud-yaml", cloud_yaml])
    return argv


def _append_repo_args(argv: list[str], args: dict[str, str]) -> None:
    if repo_url := args.get("repo_url"):
        argv.extend(["--repo-url", repo_url])
    if repo_branch := args.get("repo_branch"):
        argv.extend(["--repo-branch", repo_branch])
    if repo_workspace := args.get("repo_workspace"):
        argv.extend(["--repo-workspace", repo_workspace])


def _summary_for_payload(
    operation: CloudOperation,
    classification: CloudClassification,
    payload: object,
    *,
    ok: bool,
) -> str:
    if not ok:
        return f"{operation} failed"
    if isinstance(payload, dict):
        next_step = payload.get("next_step")
        if isinstance(next_step, str) and next_step:
            return f"{operation}: next step {next_step}"
        summary = payload.get("summary")
        if isinstance(summary, dict):
            current = summary.get("current")
            if current:
                return f"{operation}: {current}"
    return f"{operation}: {classification}"


def _json_payload(text: str) -> object | None:
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _walk_values(value: object) -> list[object]:
    if isinstance(value, dict):
        values: list[object] = []
        for key, item in value.items():
            values.append(key)
            values.extend(_walk_values(item))
        return values
    if isinstance(value, list):
        values = []
        for item in value:
            values.extend(_walk_values(item))
        return values
    return [value]

--- FILE: arnold_pipelines/megaplan/bakeoff/worktree.py (1,220p) ---
"""Git worktree lifecycle helpers for bake-offs."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

from arnold_pipelines.megaplan._core.io import atomic_write_json, now_utc
from arnold_pipelines.megaplan.types import CliError


def _git(repo: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", *args],
            cwd=repo,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise CliError("bakeoff_git_failed", str(exc)) from exc


def _git_error_detail(result: subprocess.CompletedProcess[str]) -> str:
    return (result.stderr or result.stdout or "").strip() or "git command failed"


# ---- Shared primitives (used by --in-worktree on `megaplan init` too) ----

_WORKTREE_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")


def validate_worktree_name(name: str) -> str:
    if not isinstance(name, str) or not _WORKTREE_NAME_RE.match(name):
        raise CliError(
            "invalid_worktree_name",
            "worktree name must match ^[a-z0-9][a-z0-9._-]{0,63}$ "
            "(lowercase alnum, dot, underscore, hyphen; 1-64 chars; "
            f"must start alnum). Got: {name!r}",
        )
    return name


def ensure_no_inprogress_op(repo: Path) -> None:
    """Refuse if the repo is mid-rebase/merge/cherry-pick/bisect.

    Untracked / modified files are fine; an interrupted operation is not,
    because forking a worktree off such a state is asking for confusion.
    """
    git_dir_result = _git(repo, ["rev-parse", "--git-dir"])
    if git_dir_result.returncode != 0:
        raise CliError("not_a_git_repo", _git_error_detail(git_dir_result))
    git_dir = Path(git_dir_result.stdout.strip())
    if not git_dir.is_absolute():
        git_dir = (repo / git_dir).resolve()
    markers = {
        "rebase-merge": "in-progress rebase (rebase-merge)",
        "rebase-apply": "in-progress rebase (rebase-apply)",
        "MERGE_HEAD": "in-progress merge",
        "CHERRY_PICK_HEAD": "in-progress cherry-pick",
        "REVERT_HEAD": "in-progress revert",
        "BISECT_LOG": "in-progress bisect",
    }
    for marker, label in markers.items():
        if (git_dir / marker).exists():
            raise CliError(
                "repo_busy",
                f"refusing to create worktree: {label} detected in {git_dir}",
            )


def resolve_ref(repo: Path, ref: str) -> str:
    """Resolve *ref* to a full SHA in *repo*; raises if unknown."""
    result = _git(repo, ["rev-parse", "--verify", f"{ref}^{{commit}}"])
    if result.returncode != 0:
        raise CliError(
            "invalid_worktree_ref",
            f"--worktree-from ref does not resolve in this repo: {ref}",
        )
    return result.stdout.strip()


def branch_exists(repo: Path, branch: str) -> bool:
    """Return True if *branch* exists locally or on any remote."""
    # Local branches
    local = _git(repo, ["show-ref", "--verify", "--quiet", f"refs/heads/{branch}"])
    if local.returncode == 0:
        return True
    # Remote-tracking branches across all remotes
    listing = _git(repo, ["for-each-ref", "--format=%(refname)", "refs/remotes/"])
    if listing.returncode == 0:
        suffix = f"/{branch}"
        for line in listing.stdout.splitlines():
            # refs/remotes/<remote>/<branch> — strip first three components
            tail = line.removeprefix("refs/remotes/")
            if "/" in tail and tail.split("/", 1)[1] == branch:
                return True
            # Defensive: in case branch contains slashes
            if tail.endswith(suffix):
                return True
    return False


def worktree_registered(repo: Path, target: Path) -> bool:
    """Return True if *target* is registered in `git worktree list` even if its
    on-disk directory was deleted by hand (a 'prunable' worktree)."""
    result = _git(repo, ["worktree", "list", "--porcelain"])
    if result.returncode != 0:
        return False
    target_resolved = str(target.resolve())
    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            wt = line.removeprefix("worktree ").strip()
            try:
                if str(Path(wt).resolve()) == target_resolved:
                    return True
            except OSError:
                if wt == str(target):
                    return True
    return False


def create_named_worktree(
    repo: Path,
    target: Path,
    base_ref: str,
    branch: str,
) -> None:
    """Create a new worktree at *target* on a brand-new *branch* off *base_ref*.

    Unlike :func:`create_worktree` (which checks out detached for bakeoff),
    this allocates a real branch — useful when the user intends to commit
    inside the worktree.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    result = _git(
        repo,
        ["worktree", "add", "-b", branch, str(target), base_ref],
    )
    if result.returncode != 0:
        raise CliError("worktree_create_failed", _git_error_detail(result))


def capture_base_sha(repo: Path) -> str:
    result = _git(repo, ["rev-parse", "HEAD"])
    if result.returncode != 0:
        raise CliError("bakeoff_git_failed", _git_error_detail(result))
    return result.stdout.strip()


def create_worktree(repo: Path, target: Path, base_sha: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    result = _git(
        repo,
        ["worktree", "add", "--detach", str(target), base_sha],
    )
    if result.returncode != 0:
        raise CliError("bakeoff_worktree_failed", _git_error_detail(result))


def remove_worktree(target: Path, force: bool = True) -> None:
    if not target.exists():
        return
    repo = _main_worktree_for(target)
    args = ["worktree", "remove"]
    if force:
        args.append("--force")
    args.append(str(target))
    result = _git(repo, args)
    if result.returncode != 0:
        raise CliError("bakeoff_worktree_failed", _git_error_detail(result))
    _remove_empty_parent(target.parent)


def mark_crashed(target: Path, reason: str) -> None:
    target.mkdir(parents=True, exist_ok=True)
    atomic_write_json(
        target / "BAKEOFF_CRASHED",
        {
            "reason": reason,
            "ts": now_utc(),
            "pid": os.getpid(),
        },
    )


def ensure_main_worktree_clean(repo: Path, *, allow_dirty: bool = False) -> None:
    if allow_dirty:
        return
    result = _git(repo, ["status", "--porcelain"])
    if result.returncode != 0:
        raise CliError("bakeoff_git_failed", _git_error_detail(result))
    if result.stdout.strip():
        raise CliError(
            "bakeoff_dirty_worktree",
            "main worktree is dirty; run `git status` or pass --allow-dirty.",
        )


def _main_worktree_for(target: Path) -> Path:
    result = _git(target, ["worktree", "list", "--porcelain"])
    if result.returncode != 0:
        raise CliError("bakeoff_worktree_failed", _git_error_detail(result))
    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            return Path(line.removeprefix("worktree ")).resolve()
    raise CliError("bakeoff_worktree_failed", "could not locate main worktree")


def _remove_empty_parent(path: Path) -> None:
    try:
        path.rmdir()
    except OSError:
        pass


