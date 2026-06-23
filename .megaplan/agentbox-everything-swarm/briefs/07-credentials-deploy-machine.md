You are a DeepSeek subagent doing a read-only inventory for AgentBox. The user asked us to find EVERYTHING existing in this repo/local skills that overlaps with the desired Discord-first AgentBox: start tickets/epics/megaplans/chains from Discord, Guardian repairs/relaunches blocked runs, completed work gets pushed/PRd/consolidated, and DeepSeek/subagents can be used. The brief embeds local excerpts. Return a decisive inventory of reusable mechanics, with file refs, gaps, and concrete recommendations. Under 1200 words. Focus: Hetzner/Railway/SSH provisioning, credential sync, OAuth/Claude/Codex, secrets, runtime env.


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

--- FILE: docs/cloud.md (1,180p) ---
# Megaplan Cloud

`python -m arnold.pipelines.megaplan cloud` keeps cloud orchestration thin. Core megaplan owns plan, auto, and chain behavior; cloud subcommands stage files, pick a transport, and run the core commands remotely.

Examples below use `python -m arnold.pipelines.megaplan ...`; reuse that verified module launcher for every cloud command. Add `--cloud-yaml /path/to/cloud.yaml` when `cloud.yaml` is not at the project root.

## Providers

| Provider | Use case | Notes |
|---|---|---|
| `railway` | Hosted runner with Railway SSH/logs/volume primitives | Good default for shared remote runs. |
| `local` | Fast local iteration and CI-friendly smoke tests | Uses `docker compose` from a persistent deploy dir under `~/.megaplan/cloud/<compose_project>/`. |
| `ssh` | Any reachable Docker host over SSH | Syncs the deploy dir to `ssh.remote_dir` with `rsync`, or `scp -r` when `rsync` is unavailable. |

`provider: fly` remains reserved for a future release.

## Quick Start

1. Scaffold:

```bash
python -m arnold.pipelines.megaplan cloud init
```

2. Edit `cloud.yaml` for repo, provider, mode, secrets, and optional toolchains.

   See [docs/configuration.md](configuration.md) for where local config files, provider keys, cloud secrets, and database-mode environment variables are read from.

3. Export the local secrets named under `secrets:`:

```bash
export OPENAI_API_KEY=...
export GITHUB_TOKEN=...        # optional, but recommended for push/private clone
export ANTHROPIC_API_KEY=...   # optional
```

4. Build and deploy:

```bash
python -m arnold.pipelines.megaplan cloud build
python -m arnold.pipelines.megaplan cloud deploy
```

5. Start work remotely:

```bash
python -m arnold.pipelines.megaplan cloud bootstrap .megaplan/briefs/tiny-plan.md
python -m arnold.pipelines.megaplan cloud chain .megaplan/briefs/my-epic/chain.yaml
```

6. Inspect and connect:

```bash
python -m arnold.pipelines.megaplan cloud status
python -m arnold.pipelines.megaplan cloud status --chain
python -m arnold.pipelines.megaplan cloud logs
python -m arnold.pipelines.megaplan cloud attach
```

## `cloud.yaml` Reference

### Top-level fields

| Field | Required | Default | Meaning |
|---|---|---:|---|
| `provider` | no | `railway` | One of `railway`, `local`, or `ssh`. |
| `mode` | no | `idle` | Runner mode: `auto`, `chain`, or `idle`. |
| `secrets` | no | `[]` | Local env var names uploaded during `python -m arnold.pipelines.megaplan cloud deploy` and redacted from cloud log output where possible. |
| `toolchains` | no | `[]` | Extra language toolchains layered into the image. Use aliases `rust`, `go`, `java`, or `{name, install}` mappings. |

### `repo`

| Field | Required | Default | Meaning |
|---|---|---:|---|
| `repo.url` | yes | none | Git URL cloned into the remote workspace. |
| `repo.branch` | no | `main` | Branch checked out on clone. |
| `repo.workspace` | no | `/workspace/app` | Absolute repo path used for remote `cd`, tmux, file uploads, and wrapper commands. |

### `agents`

| Field | Required | Default | Meaning |
|---|---|---:|---|
| `agents.default` | no | `codex` | Default megaplan agent for routed steps. |
| `agents.<step>` | no | inherits `default` | Optional per-step override such as `plan`, `review`, `execute`, or `loop_execute`. |

### `codex`

| Field | Required | Default | Meaning |
|---|---|---:|---|
| `codex.model` | no | `gpt-5.4` | Written into `/root/.codex/config.toml` on boot. |
| `codex.reasoning` | no | `high` | Reasoning level written into `/root/.codex/config.toml` on boot. |
| `megaplan.codex_auth` | no | `chatgpt` | `chatgpt` forces the ChatGPT-subscription OAuth (`preferred_auth_method=chatgpt`; codex uses `chatgpt.com/backend-api/codex` even when `OPENAI_API_KEY` is set) and seeds your local `~/.codex`/`~/.hermes` OAuth onto the volume. `apikey` opts into standard API-key billing. See the "Codex auth" section in the cloud skill. |

> **Codex auth gotcha:** without `codex_auth=chatgpt`, a stray `OPENAI_API_KEY` makes the codex CLI use API-key mode → `api.openai.com` billing → `ERROR: Quota exceeded. Check your plan and billing details.` even with a working ChatGPT subscription.

### `auto`

Used only when `mode: auto`.

| Field | Required in `auto` mode | Default | Meaning |
|---|---|---:|---|
| `auto.plan_name` | yes | none | Remote plan name for boot-time `python -m arnold.pipelines.megaplan auto --plan ...`. |
| `auto.idea_file` | yes | none | Absolute remote path to the idea file already staged on the workspace volume. |
| `auto.robustness` | no | `standard` | Robustness for the boot-time init fallback. |

### `chain`

Used only when `mode: chain`.

| Field | Required in `chain` mode | Default | Meaning |
|---|---|---:|---|
| `chain.spec` | yes | none | Absolute remote path to the already-staged chain spec. |

### `megaplan`

| Field | Required | Default | Meaning |
|---|---|---:|---|
| `megaplan.ref` | no | `main` | Branch, tag, or SHA installed on boot via `pip install --upgrade git+...@<ref>`. |

### `resources`

| Field | Required | Default | Meaning |
|---|---|---:|---|
| `resources.volume` | no | none | Provider-specific persistent volume name. `destroy` deletes it only when set. |
| `resources.port` | no | `8080` | Health server port exposed by the container. |

### `railway`

| Field | Required | Default | Meaning |
|---|---|---:|---|
| `railway.service` | no | `agent` | Railway service name used by `deploy`, `logs`, and `down`. |
| `railway.session` | no | `agent` | Railway SSH session name used for interactive attaches. |
| `railway.project` | no | unset | Optional project passed to Railway commands. |
| `railway.environment` | no | unset | Optional environment passed to Railway commands. |

### `local`

| Field | Required when `provider: local` | Default | Meaning |
|---|---|---:|---|
| `local.compose_project` | no | `megaplan-cloud` | Docker Compose project name used for build, logs, exec, and teardown. |
| `local.workdir` | no | `workspace` | Bind-mounted directory inside the persistent local deploy dir. |

### `ssh`

| Field | Required when `provider: ssh` | Default | Meaning |
|---|---|---:|---|
| `ssh.host` | yes | none | Remote SSH host. |
| `ssh.user` | no | unset | Optional SSH username. |
| `ssh.port` | no | `22` | SSH port. |
| `ssh.identity_file` | no | unset | Optional identity file passed to `ssh`, `scp`, and `rsync`. |
| `ssh.remote_dir` | no | `/tmp/megaplan-cloud` | Remote directory used for synced Docker build context and `.env`. |
| `ssh.container` | no | `megaplan-cloud-agent` | Remote container name and image tag. |

## Toolchains

Without `toolchains:`, the image is Python/Node only. Add built-in aliases or a custom install snippet:

```yaml
toolchains:
  - rust
  - go
  - name: custom
    install: |
      RUN curl -fsSL https://example.com/tool/install.sh | bash
```

## Wrapper Workflows

### `python -m arnold.pipelines.megaplan cloud bootstrap <idea-file>`

`cloud bootstrap` uploads a local idea file to `<repo.workspace>/idea.txt`, then runs:

```bash
python -m arnold.pipelines.megaplan init --project-dir <workspace> --idea-file <workspace>/idea.txt --auto-start --robustness <level>
```

`--plan-name` is optional. If omitted, cloud does **not** pass `--name`; core megaplan chooses the default slug from the idea text.

### `python -m arnold.pipelines.megaplan cloud chain <spec> [--idea-dir <dir>]`


--- FILE: arnold_pipelines/megaplan/cloud/auth.py (1,280p) ---
"""Cloud auth seeding helpers."""

from __future__ import annotations

import base64
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Callable, Any

from arnold_pipelines.megaplan.cloud.spec import CloudSpec


_CODEX_SOURCE = Path(".codex/auth.json")
_HERMES_SOURCE = Path(".hermes/auth.json")


@dataclass(frozen=True)
class OAuthSeed:
    label: str
    local_relative: Path
    persistent_dest: str
    root_dest: str


OAUTH_SEEDS = (
    OAuthSeed(
        label="codex",
        local_relative=_CODEX_SOURCE,
        persistent_dest="/workspace/.creds/codex-auth.json",
        root_dest="/root/.codex/auth.json",
    ),
    OAuthSeed(
        label="hermes",
        local_relative=_HERMES_SOURCE,
        persistent_dest="/workspace/.creds/hermes-auth.json",
        root_dest="/root/.hermes/auth.json",
    ),
)


def _remote_seed_command(*, payload_b64: str, persistent_dest: str, root_dest: str) -> str:
    persistent = PurePosixPath(persistent_dest)
    root = PurePosixPath(root_dest)
    persistent_tmp = persistent.with_name(f".{persistent.name}.tmp.$$")
    root_tmp = root.with_name(f".{root.name}.tmp.$$")
    return " ".join(
        [
            "umask 077;",
            f"mkdir -p {shlex.quote(str(persistent.parent))} {shlex.quote(str(root.parent))};",
            f"AUTH_B64={shlex.quote(payload_b64)};",
            f"tmp={shlex.quote(str(persistent_tmp))};",
            'printf %s "$AUTH_B64" | base64 -d > "$tmp" &&',
            f"mv \"$tmp\" {shlex.quote(str(persistent))} &&",
            f"chmod 600 {shlex.quote(str(persistent))} &&",
            f"tmp={shlex.quote(str(root_tmp))};",
            'printf %s "$AUTH_B64" | base64 -d > "$tmp" &&',
            f"mv \"$tmp\" {shlex.quote(str(root))} &&",
            f"chmod 600 {shlex.quote(str(root))};",
            "unset AUTH_B64",
        ]
    )


def seed_codex_oauth(
    spec: CloudSpec,
    provider: Any,
    *,
    home: Path | None = None,
    writer: Callable[[str], object] | None = None,
) -> dict[str, list[dict[str, str]]]:
    """Best-effort seed of local ChatGPT Codex OAuth into the cloud box.

    The seed is written both to the persistent volume under ``/workspace/.creds``
    and to the current root home so an already-running box can use it
    immediately. Entrypoint boot copies the persistent files back into ``/root``
    after restarts.
    """
    write = writer or sys.stderr.write
    events: list[dict[str, str]] = []
    if spec.megaplan.codex_auth == "apikey":
        message = "cloud codex OAuth seed: skipped because megaplan.codex_auth=apikey\n"
        write(message)
        return {"events": [{"label": "all", "status": "skipped", "reason": "codex_auth=apikey"}]}

    root = home or Path.home()
    for seed in OAUTH_SEEDS:
        local_path = root / seed.local_relative
        if not local_path.exists():
            message = f"cloud codex OAuth seed: local {local_path} absent; skipping {seed.label}\n"
            write(message)
            events.append({"label": seed.label, "status": "skipped", "reason": "absent"})
            continue
        payload_b64 = base64.b64encode(local_path.read_bytes()).decode("ascii")
        command = _remote_seed_command(
            payload_b64=payload_b64,
            persistent_dest=seed.persistent_dest,
            root_dest=seed.root_dest,
        )
        try:
            result: subprocess.CompletedProcess[str] = provider.ssh_exec(command)
        except Exception as exc:  # pragma: no cover - defensive best-effort path
            write(f"cloud codex OAuth seed: {seed.label} seed failed: {exc}\n")
            events.append({"label": seed.label, "status": "failed", "reason": str(exc)})
            continue
        if result.returncode == 0:
            write(
                f"cloud codex OAuth seed: seeded {seed.label} auth to {seed.persistent_dest} "
                f"and {seed.root_dest}\n"
            )
            events.append({"label": seed.label, "status": "seeded"})
            continue
        reason = (result.stderr or result.stdout or f"exit {result.returncode}").strip()
        write(f"cloud codex OAuth seed: {seed.label} seed failed: {reason}\n")
        events.append({"label": seed.label, "status": "failed", "reason": reason})
    return {"events": events}

--- FILE: arnold_pipelines/megaplan/cloud/providers/ssh.py (1,220p) ---
from __future__ import annotations

import base64
import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

from arnold_pipelines.megaplan.cloud.spec import CloudSpec, SshSpec
from arnold_pipelines.megaplan.types import CliError

from .base import Provider, _logs_follow, _missing_cli_error, _write_redacted_output


INSTALL_LINK = "Install: https://www.openssh.com/"


class SshProvider(Provider):
    def __init__(self, spec: CloudSpec) -> None:
        self._spec = spec
        self._ssh = spec.ssh or SshSpec(host="localhost")
        self._ssh_binary = shutil.which("ssh")
        self._scp_binary = shutil.which("scp")
        self._rsync_binary = shutil.which("rsync")
        if self._ssh_binary is None:
            _missing_cli_error("ssh", INSTALL_LINK.removeprefix("Install: "))
        if self._scp_binary is None and self._rsync_binary is None:
            _missing_cli_error("scp/rsync", INSTALL_LINK.removeprefix("Install: "))

    def _target(self) -> str:
        if self._ssh.user:
            return f"{self._ssh.user}@{self._ssh.host}"
        return self._ssh.host

    def _ssh_transport_argv(self) -> list[str]:
        argv = [self._ssh_binary or "ssh", "-p", str(self._ssh.port)]
        if self._ssh.identity_file:
            argv.extend(["-i", self._ssh.identity_file])
        return argv

    def _run(
        self,
        argv: list[str],
        *,
        capture_output: bool = True,
        input: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        try:
            kwargs: dict[str, object] = {
                "capture_output": capture_output,
                "text": True,
                "check": False,
            }
            if input is not None:
                kwargs["input"] = input
            result = subprocess.run(argv, **kwargs)
        except FileNotFoundError as exc:
            raise CliError("provider_failed", str(exc)) from exc
        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            raise CliError("provider_failed", stderr or f"Command failed: {' '.join(argv)}")
        return result

    def _remote_run(
        self,
        command: str,
        *,
        capture_output: bool = True,
        input: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        return self._run(
            [*self._ssh_transport_argv(), self._target(), command],
            capture_output=capture_output,
            input=input,
        )

    def _sync_deploy_dir(self, deploy_dir: Path) -> None:
        remote_dir = shlex.quote(self._ssh.remote_dir)
        if self._rsync_binary is not None:
            self._remote_run(f"mkdir -p {remote_dir}")
            self._run(
                [
                    self._rsync_binary,
                    "-az",
                    "-e",
                    shlex.join(self._ssh_transport_argv()),
                    f"{deploy_dir}/",
                    f"{self._target()}:{remote_dir}/",
                ]
            )
            return
        sys.stderr.write("WARN: rsync unavailable; falling back to scp -r\n")
        self._remote_run(f"rm -rf {remote_dir} && mkdir -p {remote_dir}")
        self._run(
            [
                self._scp_binary or "scp",
                "-r",
                "-P",
                str(self._ssh.port),
                *(["-i", self._ssh.identity_file] if self._ssh.identity_file else []),
                f"{deploy_dir}/.",
                f"{self._target()}:{remote_dir}",
            ]
        )

    def build(self, deploy_dir: Path) -> int:
        self._sync_deploy_dir(deploy_dir)
        self._remote_run(
            f"docker build -t {shlex.quote(self._ssh.container)} {shlex.quote(self._ssh.remote_dir)}"
        )
        return 0

    def deploy(self, deploy_dir: Path, *, secrets: dict[str, str]) -> int:
        del deploy_dir
        env_path = f"{self._ssh.remote_dir}/.env"
        env_lines = [f"PORT={self._spec.resources.port}"]
        env_lines.extend(f"{name}={value}" for name, value in secrets.items())
        self._remote_run(f"cat > {shlex.quote(env_path)}", input="\n".join(env_lines) + "\n")
        self._remote_run(
            f"docker rm -f {shlex.quote(self._ssh.container)} >/dev/null 2>&1 || true"
        )
        self._remote_run(
            " ".join(
                [
                    "docker run -d",
                    f"--name {shlex.quote(self._ssh.container)}",
                    "--restart unless-stopped",
                    f"--env-file {shlex.quote(env_path)}",
                    f"-p {self._spec.resources.port}:{self._spec.resources.port}",
                    shlex.quote(self._ssh.container),
                ]
            )
        )
        return 0

    def ssh_exec(self, command: str) -> subprocess.CompletedProcess[str]:
        return self._remote_run(
            f"docker exec {shlex.quote(self._ssh.container)} bash -lc {shlex.quote(command)}"
        )

    def upload_file(self, src: Path, dest: str) -> None:
        payload = base64.b64encode(src.read_bytes()).decode("ascii")
        parent = Path(dest).parent.as_posix()
        inner = f"mkdir -p {shlex.quote(parent)} && base64 -d > {shlex.quote(dest)}"
        self._remote_run(
            f"docker exec -i {shlex.quote(self._ssh.container)} bash -lc {shlex.quote(inner)}",
            input=payload,
        )

    def read_remote_file(self, path: str) -> str:
        result = self._remote_run(
            f"docker exec {shlex.quote(self._ssh.container)} bash -lc {shlex.quote(f'cat {shlex.quote(path)}')}"
        )
        return result.stdout

    def attach(self) -> int:
        self._remote_run(
            f"docker exec -it {shlex.quote(self._ssh.container)} tmux attach -t agent",
            capture_output=False,
        )
        return 0

    def logs(self, *, follow: bool = True) -> int:
        argv = f"docker logs {'-f ' if follow else '--tail 200 '}{shlex.quote(self._ssh.container)}"
        if follow:
            return _logs_follow(
                [*self._ssh_transport_argv(), self._target(), argv.strip()],
                secret_names=self._spec.secrets,
                env=os.environ,
            )
        result = self._remote_run(argv.strip())
        _write_redacted_output(result, secret_names=self._spec.secrets, env=os.environ)
        return 0

    def status_payload(self, *, plan: str | None, workspace: str) -> dict:
        command = f"cd {shlex.quote(workspace)} && arnold status"
        if plan is not None:
            command += f" --plan {shlex.quote(plan)}"
        result = self.ssh_exec(command)
        payload = json.loads(result.stdout)
        if not isinstance(payload, dict):
            raise CliError("provider_failed", "arnold status did not return a JSON object")
        return payload

    def down(self) -> int:
        self._remote_run(f"docker stop {shlex.quote(self._ssh.container)}")
        return 0

    def destroy(self, *, volume: str | None = None) -> int:
        del volume
        self._remote_run(
            f"docker rm -f {shlex.quote(self._ssh.container)} >/dev/null 2>&1 || true && rm -rf {shlex.quote(self._ssh.remote_dir)}"
        )
        return 0

--- FILE: arnold_pipelines/megaplan/cloud/providers/railway.py (1,220p) ---
"""Railway-backed cloud provider implementation."""

from __future__ import annotations

import base64
import json
import os
import shlex
import shutil
import subprocess
from pathlib import Path

from arnold_pipelines.megaplan.cloud.providers.base import (
    DeployReport,
    DeployStepReport,
    Provider,
    _logs_follow,
    _missing_cli_error,
    _write_redacted_output,
)
from arnold_pipelines.megaplan.cloud.spec import CloudSpec, RailwaySpec
from arnold_pipelines.megaplan.types import CliError


INSTALL_LINK = "Install: https://docs.railway.app/develop/cli"


class RailwayProvider(Provider):
    """Thin wrapper around the Railway CLI for sprint-1 cloud flows."""

    supports_session = True

    def __init__(self, spec: CloudSpec) -> None:
        self._spec = spec
        self._railway = spec.railway or RailwaySpec()
        self._workspace = spec.repo.workspace
        self._volume = spec.resources.volume
        self._binary = shutil.which("railway")
        if self._binary is None:
            _missing_cli_error("railway", INSTALL_LINK.removeprefix("Install: "))

    @property
    def image_tag(self) -> str:
        return f"megaplan-cloud-{self._railway.service}"

    def _run(
        self,
        argv: list[str],
        *,
        cwd: Path | None = None,
        capture_output: bool = True,
        input: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        try:
            kwargs: dict[str, object] = {
                "cwd": cwd,
                "capture_output": capture_output,
                "text": True,
                "encoding": "utf-8",
                "errors": "replace",
                "check": False,
            }
            if input is not None:
                kwargs["input"] = input
            result = subprocess.run(
                argv,
                **kwargs,
            )
        except FileNotFoundError as exc:
            raise CliError("provider_failed", str(exc)) from exc
        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            raise CliError("provider_failed", stderr or f"Command failed: {' '.join(argv)}")
        return result

    def _railway_cmd(self, *args: str) -> list[str]:
        command = [self._binary or "railway", *args]
        if not args:
            return command
        if args[0] == "link":
            if self._railway.environment:
                return [*command, "--environment", self._railway.environment]
            return command
        if self._railway.environment and args[:2] == ("service", "status"):
            return [
                *command[:3],
                "--environment",
                self._railway.environment,
                *command[3:],
            ]
        scoped: list[str] = []
        if self._railway.environment and args[0] in {
            "down",
            "logs",
            "ssh",
            "up",
            "variables",
            "volume",
        }:
            scoped.extend(["--environment", self._railway.environment])
        return [*command[:2], *scoped, *command[2:]]

    def build(self, deploy_dir: Path) -> int:
        self._run(["docker", "build", "-t", self.image_tag, str(deploy_dir)])
        return 0

    def deploy(self, deploy_dir: Path, *, secrets: dict[str, str]) -> DeployReport:
        missing = [name for name in self._spec.secrets if not secrets.get(name)]
        if missing:
            raise CliError("missing_secrets", f"Missing required secrets: {', '.join(missing)}")

        steps: list[DeployStepReport] = []
        if self._railway.project:
            link_result = self._run(
                self._railway_cmd("link", "--project", self._railway.project),
                cwd=deploy_dir,
            )
            steps.append(
                _step_from_result(
                    "railway link",
                    link_result,
                    detail=f"linked project {self._railway.project}",
                )
            )
            status_result = self._ensure_configured_service(deploy_dir)
            steps.append(
                _step_from_result(
                    "verify Railway service",
                    status_result,
                    detail=f"service {self._railway.service} is configured",
                )
            )

        variable_stdout: list[str] = []
        variable_stderr: list[str] = []
        for name in self._spec.secrets:
            value = secrets[name]
            result = self._run(
                self._railway_cmd(
                    "variables",
                    "--service",
                    self._railway.service,
                    "--set",
                    f"{name}={value}",
                ),
                cwd=deploy_dir,
            )
            variable_stdout.append(result.stdout or "")
            variable_stderr.append(result.stderr or "")
        steps.append(
            DeployStepReport(
                name="set Railway service variables",
                status="ok",
                detail=f"set {len(self._spec.secrets)} service var(s)",
                stdout="".join(variable_stdout),
                stderr="".join(variable_stderr),
                metadata={"count": len(self._spec.secrets)},
            )
        )

        up_result = self._run(
            self._railway_cmd(
                "up",
                "--service",
                self._railway.service,
                "--detach",
                "--ci",
            ),
            cwd=deploy_dir,
        )
        up_classification = _classify_railway_up(up_result)
        up_detail = "ran railway up --detach --ci"
        if up_classification == "not_triggered":
            up_detail = "railway reported no image rebuild"
        elif not (up_result.stdout or up_result.stderr):
            up_detail = "ran railway up --detach --ci; provider returned no stdout/stderr"
        steps.append(
            _step_from_result(
                "railway up",
                up_result,
                detail=up_detail,
                metadata={"image_rebuild": up_classification},
            )
        )

        no_op = up_classification == "not_triggered" and not self._spec.secrets
        if no_op:
            verdict = "deploy: no-op (nothing changed)"
        elif up_classification == "not_triggered":
            verdict = "deploy: vars updated, no image rebuild"
        else:
            verdict = f"deploy: triggered Railway build/deploy for service {self._railway.service}"
        warnings = []
        if up_classification == "triggered" and not (up_result.stdout or up_result.stderr):
            warnings.append(
                "railway up returned no stdout/stderr; verify the Railway deployment logs for build outcome"
            )
        return DeployReport(
            success=True,
            provider="railway",
            service=self._railway.service,
            deploy_dir=str(deploy_dir),
            steps=steps,
            image_rebuild=up_classification,
            no_op=no_op,
            vars_updated=len(self._spec.secrets),
            logs={
                "command": "arnold cloud logs --no-follow",
                "service": self._railway.service,
                "provider": "railway",
            },
            verdict=verdict,
            warnings=warnings,
            exit_code=0,
        )

    def _ensure_configured_service(self, deploy_dir: Path) -> subprocess.CompletedProcess[str]:
        result = self._run(
            self._railway_cmd("service", "status", "--all", "--json"),
            cwd=deploy_dir,

--- FILE: arnold_pipelines/megaplan/cloud/template.py (1,280p) ---
"""Cloud deployment template rendering and staging."""

from __future__ import annotations

import shlex
import stat
from importlib import resources
from pathlib import Path, PurePosixPath
from string import Template

from arnold_pipelines.megaplan.cloud.spec import CloudSpec, RepoSpec, ToolchainSpec
from arnold_pipelines.megaplan.profiles import DEFAULT_AGENT_ROUTING, effective_premium_vendor
from arnold_pipelines.megaplan.types import (
    format_agent_spec,
    is_premium_placeholder_spec,
    resolve_premium_placeholder_spec,
)


PLACEHOLDERS = (
    "REPO_URL",
    "REPO_BRANCH",
    "WORKSPACE_PATH",
    "CODEX_MODEL",
    "CODEX_REASONING",
    "CODEX_EMAIL",
    "MEGAPLAN_REF",
    "MEGAPLAN_REPO",
    "MEGAPLAN_INSTALL_SPEC_OVERRIDE",
    "CODEX_AUTH_METHOD",
    "CODEX_AUTH_CONFIG_BLOCK",
    "ROBUSTNESS",
    "MODE",
    "IDEA_FILE",
    "CHAIN_SPEC",
    "AUTO_PLAN_NAME",
    "AGENT_ROUTING_BLOCK",
    "CLAUDE_AUTH_BLOCK",
    "ENSURE_REPO_BLOCK",
    "RUNNER_LAUNCH_BLOCK",
)

_TOOLCHAIN_RECIPES = {
    "rust": """# Toolchain: rust
RUN curl https://sh.rustup.rs -sSf | sh -s -- -y
ENV PATH=/root/.cargo/bin:${PATH}""",
    "go": """# Toolchain: go
RUN curl -fsSL https://go.dev/dl/go1.22.5.linux-amd64.tar.gz | tar -C /usr/local -xz
ENV PATH=/usr/local/go/bin:${PATH}""",
    "java": """# Toolchain: java
RUN apt-get update && apt-get install -y --no-install-recommends openjdk-17-jdk \
    && rm -rf /var/lib/apt/lists/*
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64 \
    PATH=${JAVA_HOME}/bin:${PATH}""",
}

_AUTO_RUNNER = Template(
    """if [ ! -f "$IDEA_FILE" ]; then
  echo 'WARN: idea file missing, dropping to idle'
  tmux new-session -d -s agent -c ${WORKSPACE_PATH} "bash -l"
else
  tmux new-session -d -s agent -c ${WORKSPACE_PATH} "bash -lc ${AUTO_COMMAND}"
fi"""
)

_CHAIN_RUNNER = Template(
    """if [ ! -f "$CHAIN_SPEC" ]; then
  echo 'WARN: chain spec missing, dropping to idle'
  tmux new-session -d -s agent -c ${WORKSPACE_PATH} "bash -l"
else
  tmux new-session -d -s agent -c ${WORKSPACE_PATH} "bash -lc ${CHAIN_COMMAND}"
fi"""
)

_IDLE_RUNNER = Template("""tmux new-session -d -s agent -c ${WORKSPACE_PATH} "bash -l" """)


def _entrypoint_template() -> Template:
    text = resources.files("arnold_pipelines.megaplan.cloud.templates").joinpath("entrypoint.sh.tmpl").read_text(encoding="utf-8")
    return Template(text)


def _render_resource_template(name: str, values: dict[str, str]) -> str:
    text = resources.files("arnold_pipelines.megaplan.cloud.templates").joinpath(name).read_text(encoding="utf-8")
    return Template(text).safe_substitute(values)


def _dockerfile_template() -> Template:
    text = resources.files("arnold_pipelines.megaplan.cloud.templates").joinpath("Dockerfile").read_text(encoding="utf-8")
    return Template(text)


def _quoted(script: str) -> str:
    return shlex.quote(script.strip())


def render_ensure_repo_command(repo: RepoSpec) -> str:
    """Render the fixed clone-if-missing command used by cloud entrypoints."""
    workspace = PurePosixPath(repo.workspace)
    parent = str(workspace.parent)
    git_dir = str(workspace / ".git")
    return " && ".join(
        [
            f"mkdir -p {shlex.quote(parent)}",
            (
                f"if [ ! -d {shlex.quote(git_dir)} ]; then "
                f"git clone --branch {shlex.quote(repo.branch)} "
                f"{shlex.quote(repo.url)} {shlex.quote(repo.workspace)}; "
                "else true; fi"
            ),
        ]
    )


def render_ensure_repos_block(spec: CloudSpec) -> str:
    """Clone primary + every extra repo if missing, in declared order.

    Each repo lives at its own absolute workspace path so a multi-repo or
    multi-tenant volume can hold them as siblings on independent branches.
    """
    blocks = [render_ensure_repo_command(spec.repo)]
    for extra in spec.extra_repos:
        blocks.append(render_ensure_repo_command(extra))
    return "\n".join(blocks)


def _auto_command(spec: CloudSpec) -> str:
    assert spec.auto is not None
    plan_dir = f"{spec.repo.workspace}/.megaplan/plans/{spec.auto.plan_name}"
    script = f"""
set -euo pipefail
PLAN_DIR={shlex.quote(plan_dir)}
if [[ ! -d "$PLAN_DIR" ]]; then
  IDEA="$(cat "$IDEA_FILE")"
  arnold init --project-dir {shlex.quote(spec.repo.workspace)} --name {shlex.quote(spec.auto.plan_name)} --auto-approve --robustness {shlex.quote(spec.auto.robustness)} "$IDEA"
fi
exec arnold-supervise {shlex.quote(f"auto-{spec.auto.plan_name}")} arnold auto --plan {shlex.quote(spec.auto.plan_name)}
"""
    return _quoted(script)


def _chain_command(spec: CloudSpec) -> str:
    assert spec.chain is not None
    script = f"""
set -euo pipefail
exec arnold-supervise chain arnold-chain {shlex.quote(spec.chain.spec)}
"""
    return _quoted(script)


def _runner_block(spec: CloudSpec) -> str:
    values = {"WORKSPACE_PATH": shlex.quote(spec.repo.workspace)}
    if spec.mode == "auto":
        return _AUTO_RUNNER.safe_substitute(
            values | {"AUTO_COMMAND": _auto_command(spec)}
        )
    if spec.mode == "chain":
        return _CHAIN_RUNNER.safe_substitute(
            values | {"CHAIN_COMMAND": _chain_command(spec)}
        )
    return _IDLE_RUNNER.safe_substitute(values)


def _agent_routing_block(spec: CloudSpec) -> str:
    default_agent = spec.agents.get("default")
    selected_vendor = (
        default_agent
        if default_agent in {"claude", "codex"}
        else effective_premium_vendor()
    )
    routing = {
        step: spec.agents.get(step, default_agent or fallback)
        for step, fallback in DEFAULT_AGENT_ROUTING.items()
    }
    return "\n".join(
        "arnold config set agents."
        f"{step} "
        f"{format_agent_spec(resolve_premium_placeholder_spec(agent, selected_vendor)) if is_premium_placeholder_spec(agent) else agent} "
        ">/dev/null 2>&1 || true"
        for step, agent in routing.items()
    )


def _claude_auth_block() -> str:
    # Three auth modes, in priority order:
    #
    # 1. CLAUDE_CODE_REFRESH_TOKEN (preferred — uses Max/Pro subscription, fully
    #    programmatic): install a `claude` shim at /usr/local/bin/claude that
    #    refreshes the OAuth access token on every invocation, exports it as
    #    ANTHROPIC_API_KEY, then exec's the real binary. The refresh token
    #    rotates per use and is persisted to the volume.
    #
    # 2. ANTHROPIC_API_KEY (legacy / metered API): claude --bare reads it
    #    directly; nothing to install. claude setup-token is NOT attempted
    #    because it requires interactive browser OAuth.
    #
    # 3. Neither: claude will fail at first call. Warn loudly.
    #
    # See megaplan-cloud skill for full design rationale.
    return r"""# ── Claude auth: refresh-token shim takes precedence ─────────────────
CLAUDE_CREDS_DIR=/workspace/.claude-creds
mkdir -p "$CLAUDE_CREDS_DIR"
chmod 700 "$CLAUDE_CREDS_DIR"

if [[ -n "${CLAUDE_CODE_REFRESH_TOKEN:-}" ]]; then
  # Seed the on-volume refresh token from the env on first boot (or if missing).
  if [[ ! -s "$CLAUDE_CREDS_DIR/refresh_token" ]]; then
    printf '%s' "$CLAUDE_CODE_REFRESH_TOKEN" > "$CLAUDE_CREDS_DIR/refresh_token"
    chmod 600 "$CLAUDE_CREDS_DIR/refresh_token"
  fi

  REAL_CLAUDE=$(command -v claude || true)
  if [[ -z "$REAL_CLAUDE" ]]; then
    echo "WARN: claude binary not on PATH; skipping refresh-token shim install"
  else
    # Move the real binary aside so we can shadow it (idempotent across reboots).
    if [[ ! -x /usr/local/bin/claude.real ]]; then
      cp "$REAL_CLAUDE" /usr/local/bin/claude.real
      chmod +x /usr/local/bin/claude.real
    fi

    # Refresh helper (usable standalone, and as `apiKeyHelper` via --settings).
    cat > /usr/local/bin/claude-key-helper <<'HELPER_EOF'
#!/usr/bin/env bash
# Refresh the Claude Code OAuth access token if missing/expiring, then print it
# to stdout. Refresh token rotates per use and is persisted to the volume.
set -euo pipefail
DIR=/workspace/.claude-creds
mkdir -p "$DIR"
NOW=$(date +%s)
EXP=$(cat "$DIR/expires_at" 2>/dev/null || echo 0)
if [[ ! -s "$DIR/access_token" ]] || [[ "$NOW" -ge $((EXP - 300)) ]]; then
  RT=$(cat "$DIR/refresh_token" 2>/dev/null || true)
  if [[ -z "$RT" ]]; then
    echo "claude-key-helper: no refresh token at $DIR/refresh_token" >&2
    exit 1
  fi
  CID=${CLAUDE_CODE_OAUTH_CLIENT_ID:-9d1c250a-e61b-44d9-88ed-5944d1962f5e}
  URL=${CLAUDE_CODE_OAUTH_TOKEN_URL:-https://api.anthropic.com/v1/oauth/token}
  RESP=$(curl -sS --max-time 15 -X POST "$URL" \
    -H "Content-Type: application/json" \
    -d "{\"grant_type\":\"refresh_token\",\"refresh_token\":\"$RT\",\"client_id\":\"$CID\"}")
  AT=$(echo "$RESP" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("access_token",""))' 2>/dev/null)
  EXPIRES_IN=$(echo "$RESP" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("expires_in",0))' 2>/dev/null)
  NEW_RT=$(echo "$RESP" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("refresh_token",""))' 2>/dev/null)
  if [[ -z "$AT" ]]; then
    echo "claude-key-helper: refresh failed: $RESP" >&2
    exit 1
  fi
  printf '%s' "$AT" > "$DIR/access_token"
  echo $((NOW + EXPIRES_IN)) > "$DIR/expires_at"
  [[ -n "$NEW_RT" ]] && printf '%s' "$NEW_RT" > "$DIR/refresh_token"
  chmod 600 "$DIR/access_token" "$DIR/refresh_token" "$DIR/expires_at"
fi
cat "$DIR/access_token"
HELPER_EOF
    chmod +x /usr/local/bin/claude-key-helper

    # Claude shim: refresh on entry, export, exec real binary.
    cat > /usr/local/bin/claude <<'SHIM_EOF'
#!/usr/bin/env bash
AT=$(/usr/local/bin/claude-key-helper) || {
  echo "claude shim: refresh failed; falling back to ANTHROPIC_API_KEY (may be expired)" >&2
  exec /usr/local/bin/claude.real "$@"
}
export ANTHROPIC_API_KEY="$AT"
exec /usr/local/bin/claude.real "$@"
SHIM_EOF
    chmod +x /usr/local/bin/claude

    # Prime the cache so the first phase call doesn't pay refresh latency.
    if /usr/local/bin/claude-key-helper >/dev/null 2>&1; then
      echo "Claude auth: refresh-token shim active (cached access token ready)"
    else
      echo "WARN: claude shim installed but priming refresh FAILED — see /var/log/entrypoint.log"
    fi
  fi
elif [[ -n "${ANTHROPIC_API_KEY:-}" ]]; then
  echo "Claude auth: using ANTHROPIC_API_KEY (legacy / metered). For Max-sub usage, set CLAUDE_CODE_REFRESH_TOKEN."
else

--- FILE: arnold_pipelines/megaplan/cloud/templates/entrypoint.sh.tmpl (1,280p) ---
#!/usr/bin/env bash
set -euo pipefail

LOG=/var/log/entrypoint.log
exec > >(tee -a "$$LOG") 2>&1

echo "=== $$(date -Iseconds) entrypoint starting ==="

mkdir -p /workspace /root/.ssh /root/.config/megaplan /root/.codex /root/.hermes /workspace/.creds
chmod 700 /root/.ssh
chmod 700 /root/.codex /root/.hermes /workspace/.creds

REPO_URL="$${REPO_URL:-${REPO_URL}}"
REPO_BRANCH="$${REPO_BRANCH:-${REPO_BRANCH}}"
WORKSPACE_PATH="${WORKSPACE_PATH}"
MODE="${MODE}"
IDEA_FILE="${IDEA_FILE}"
CHAIN_SPEC="${CHAIN_SPEC}"
AUTO_PLAN_NAME="${AUTO_PLAN_NAME}"
CODEX_AUTH_METHOD="${CODEX_AUTH_METHOD}"
export MEGAPLAN_TRUSTED_CONTAINER=1

# Git identity
git config --global user.email "$${GIT_EMAIL:-${CODEX_EMAIL}}"
git config --global user.name "$${GIT_NAME:-Codex Agent}"
git config --global init.defaultBranch main
git config --global pull.rebase false
git config --global --add safe.directory "$$WORKSPACE_PATH"

# GitHub credential helper if token present
if [[ -n "$${GITHUB_TOKEN:-}" ]]; then
  echo "GITHUB_TOKEN present — configuring git credentials"
  git config --global credential.helper store
  cat > /root/.git-credentials <<EOF
https://x-access-token:$${GITHUB_TOKEN}@github.com
EOF
  chmod 600 /root/.git-credentials
fi

# Clone repo if missing (volume may already have it from a prior boot)
${ENSURE_REPO_BLOCK}

# Codex OAuth seed from persistent volume. /root is ephemeral; /workspace persists.
if [[ "$$CODEX_AUTH_METHOD" == "chatgpt" ]]; then
  if [[ -s /workspace/.creds/codex-auth.json ]]; then
    install -m 600 /workspace/.creds/codex-auth.json /root/.codex/auth.json
    echo "Codex auth: seeded ChatGPT OAuth credentials from persistent volume"
  else
    echo "Codex auth: ChatGPT OAuth selected; no persisted /workspace/.creds/codex-auth.json seed found"
  fi
  if [[ -s /workspace/.creds/hermes-auth.json ]]; then
    install -m 600 /workspace/.creds/hermes-auth.json /root/.hermes/auth.json
    echo "Hermes auth: seeded OpenAI Codex OAuth credentials from persistent volume"
  fi
fi

# Codex auth from env, only for explicit API-key billing opt-out.
if [[ "$$CODEX_AUTH_METHOD" == "apikey" ]] && [[ -n "$${OPENAI_API_KEY:-}" ]] && [[ ! -f /root/.codex/auth.json ]]; then
  echo "Authenticating codex with OPENAI_API_KEY"
  printf '%s' "$$OPENAI_API_KEY" | codex login --with-api-key 2>&1 | tail -3 || true
fi

${CLAUDE_AUTH_BLOCK}

# Codex model + reasoning config — always overwrite on boot so new tiers propagate.
# sandbox_mode = "danger-full-access" stays on because the container is the sandbox.
cat > /root/.codex/config.toml <<EOF
model = "${CODEX_MODEL}"
model_reasoning_effort = "${CODEX_REASONING}"
sandbox_mode = "danger-full-access"
approval_policy = "never"
${CODEX_AUTH_CONFIG_BLOCK}
EOF
echo "Codex model: ${CODEX_MODEL}, reasoning: ${CODEX_REASONING}, auth: $$CODEX_AUTH_METHOD, sandbox: danger-full-access (container-sandboxed)"

# Megaplan install: always re-pull on boot so entrypoint restarts pick up the
# requested ref without rebuilding the base image. The refresh helper is also
# invoked by `arnold cloud chain` before each run.
#
# MEGAPLAN_INSTALL_SPEC – runtime pip install override, verbatim. Git specs get
#   @MEGAPLAN_REF appended.
# MEGAPLAN_INSTALL_SPEC_OVERRIDE – rendered cloud.yaml megaplan.install_spec.
# MEGAPLAN_REPO – rendered cloud.yaml megaplan.repo source URL.
# MEGAPLAN_REF – git ref (branch/tag/commit) used for git installs.
MEGAPLAN_REF="$${MEGAPLAN_REF:-${MEGAPLAN_REF}}"
MEGAPLAN_REPO="$${MEGAPLAN_REPO:-${MEGAPLAN_REPO}}"
MEGAPLAN_INSTALL_SPEC_OVERRIDE="$${MEGAPLAN_INSTALL_SPEC_OVERRIDE:-${MEGAPLAN_INSTALL_SPEC_OVERRIDE}}"

mp_install_megaplan() {
  local explicit_spec="$${MEGAPLAN_INSTALL_SPEC:-$${MEGAPLAN_INSTALL_SPEC_OVERRIDE:-}}"
  if [[ -n "$$explicit_spec" ]]; then
    if [[ "$$explicit_spec" == *git+* ]] && [[ -n "$$MEGAPLAN_REF" ]]; then
      echo "Installing/upgrading arnold from explicit git spec at ref $$MEGAPLAN_REF"
      pip install --upgrade --force-reinstall --no-cache-dir "$$explicit_spec@$$MEGAPLAN_REF" 2>&1 | tail -3
    else
      echo "Installing/upgrading arnold from explicit spec"
      pip install --upgrade --force-reinstall --no-cache-dir "$$explicit_spec" 2>&1 | tail -3
    fi
    return
  fi

  if [[ -n "$$MEGAPLAN_REPO" ]]; then
    local repo="$$MEGAPLAN_REPO"
    if [[ "$$repo" == https://github.com/* ]] && [[ "$$repo" != https://*@github.com/* ]] && [[ -n "$${GITHUB_TOKEN:-}" ]]; then
      repo="https://x-access-token:$${GITHUB_TOKEN}@github.com/$${repo#https://github.com/}"
    fi
    local spec="arnold[agent] @ git+$$repo"
    echo "Installing/upgrading arnold from repo at ref $$MEGAPLAN_REF"
    pip install --upgrade --force-reinstall --no-cache-dir "$$spec@$$MEGAPLAN_REF" 2>&1 | tail -3
    return
  fi

  if [[ -n "$$MEGAPLAN_REF" ]]; then
    echo "MEGAPLAN_REF=$$MEGAPLAN_REF ignored because no git source is configured — set megaplan.repo (or a git+ megaplan.install_spec) in cloud.yaml to install from source at this ref."
  fi
  echo "Installing/upgrading arnold: arnold[agent]"
  pip install --upgrade --force-reinstall --no-cache-dir "arnold[agent]" 2>&1 | tail -3
}

{
  echo '#!/usr/bin/env bash'
  echo 'set -euo pipefail'
  printf 'MEGAPLAN_REF=$${MEGAPLAN_REF:-%q}\n' "$$MEGAPLAN_REF"
  printf 'MEGAPLAN_REPO=$${MEGAPLAN_REPO:-%q}\n' "$$MEGAPLAN_REPO"
  printf 'MEGAPLAN_INSTALL_SPEC_OVERRIDE=$${MEGAPLAN_INSTALL_SPEC_OVERRIDE:-%q}\n' "$$MEGAPLAN_INSTALL_SPEC_OVERRIDE"
  declare -f mp_install_megaplan
  echo 'mp_install_megaplan "$$@"'
} > /usr/local/bin/mp-refresh-megaplan
chmod +x /usr/local/bin/mp-refresh-megaplan

mp_install_megaplan

echo "Configuring arnold agent routing and execution defaults"
${AGENT_ROUTING_BLOCK}
arnold config set execution.auto_approve true >/dev/null 2>&1 || true
arnold config set execution.robustness "${ROBUSTNESS}" >/dev/null 2>&1 || true

echo "Runner mode: $$MODE"

# Launch heartbeat in its own tmux session.
if ! tmux has-session -t heartbeat 2>/dev/null; then
  tmux new-session -d -s heartbeat -c /workspace "bash -lc '/usr/local/bin/arnold-heartbeat'"
  echo "heartbeat watchdog running in tmux session 'heartbeat'"
fi

# Tiny health server so Railway keeps container alive
python3 /usr/local/bin/healthserver.py &
HEALTH_PID=$$!
echo "healthserver.py running as pid $$HEALTH_PID"

# Ensure tmux session 'agent' exists. The renderer injects the mode-specific
# launch block here so auto/chain can warn-and-drop-to-idle on missing inputs.
if ! tmux has-session -t agent 2>/dev/null; then
${RUNNER_LAUNCH_BLOCK}
fi
echo "tmux 'agent' session ready — attach: railway ssh --session agent"

echo "=== entrypoint idle ==="
wait "$$HEALTH_PID"
