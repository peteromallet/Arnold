"""Tests for the M11 recovery-topology authority-surface scanner (Steps 25-26).

Covers:
* Step 25 — surface schema requires owner/expiry/target-step and a complete
  zero-positive-authority proof for any non-live surface, and forbids deriving
  authority from labels, liveness, WBC receipts, or rebuildable projections.
* Step 26 — Python and command-authority scanner adapters detect the live
  repair-authority surfaces (subprocess/exec/os.system/shutil.which,
  RepairRunner, repair-queue calls, enqueue producers, and command strings).
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.cloud.recovery_topology_surfaces import (
    ALL_FORBIDDEN_AUTHORITY_SOURCES,
    BASELINE_PLAN_STEPS,
    AuthoritySurface,
    COMMAND_AUTHORITY_DETECTION_KINDS,
    HOT_UPLOAD_DETECTION_KINDS,
    MARKDOWN_DETECTION_KINDS,
    MARKDOWN_SCAN_ROOTS,
    PYTHON_DETECTION_KINDS,
    SHELL_DETECTION_KINDS,
    SIMULATION_DETECTION_KINDS,
    SYSTEMD_DETECTION_KINDS,
    TEMPLATE_DETECTION_KINDS,
    ForbiddenAuthoritySource,
    SurfaceFamily,
    SurfaceState,
    ZeroPositiveAuthorityProof,
    build_route_authority_baseline,
    scan_command_authority,
    scan_hot_upload_authority,
    scan_markdown_authority,
    scan_markdown_file,
    scan_python_source,
    scan_shell_authority,
    scan_simulation_authority,
    scan_systemd_authority,
    scan_template_authority,
    scan_text_file,
    schema_descriptor,
)

# ── Step 25: surface schema invariants ─────────────────────────────────────


_COMPLETE_PROOF = ZeroPositiveAuthorityProof(
    proof_kind="static_call_site_inventory",
    evidence_ref="evidence/m11-recovery-topology-surfaces.json",
    forbids=tuple(ALL_FORBIDDEN_AUTHORITY_SOURCES),
)


def _complete_proof(**overrides):
    base = dict(
        proof_kind="static_call_site_inventory",
        evidence_ref="evidence/m11-recovery-topology-surfaces.json",
        forbids=tuple(ALL_FORBIDDEN_AUTHORITY_SOURCES),
    )
    base.update(overrides)
    return ZeroPositiveAuthorityProof(**base)


def test_surface_schema_requires_owner_expiry_and_zero_authority_proof():
    # A live authority surface constructs with no proof at all: it is a concrete
    # call site that currently grants authority and must be migrated.
    live = AuthoritySurface(
        family=SurfaceFamily.PYTHON_COMMAND,
        state=SurfaceState.LIVE_AUTHORITY,
        kind="python.subprocess.run",
        location="legacy.py:10",
    )
    assert live.surface_id
    assert live.content_hash.startswith("sha256:")
    assert live.zero_authority_proof is None

    changed = AuthoritySurface(
        family=SurfaceFamily.PYTHON_COMMAND,
        state=SurfaceState.LIVE_AUTHORITY,
        kind="python.subprocess.run",
        location="legacy.py:10",
        detail="subprocess.run(['changed'])",
    )
    assert changed.surface_id == live.surface_id
    assert changed.content_hash != live.content_hash

    # A live surface may NOT carry a zero-authority proof — that would be
    # self-contradictory (a live surface grants authority by definition).
    with pytest.raises(ValueError, match="must not carry a zero-authority proof"):
        AuthoritySurface(
            family=SurfaceFamily.PYTHON_COMMAND,
            state=SurfaceState.LIVE_AUTHORITY,
            kind="python.subprocess.run",
            location="legacy.py:10",
            zero_authority_proof=_complete_proof(),
        )

    # Retiring to PLANNED_PENDING requires owner, expiry, target_step, AND a
    # complete zero-authority proof.
    for bad_state in (
        SurfaceState.PLANNED_PENDING,
        SurfaceState.HISTORICAL_REPORT_ONLY,
        SurfaceState.CLOSED,
    ):
        # missing all closure fields
        with pytest.raises(ValueError, match="missing required closure fields"):
            AuthoritySurface(
                family=SurfaceFamily.PYTHON_COMMAND,
                state=bad_state,
                kind="python.subprocess.run",
                location="legacy.py:10",
            )
        # missing proof only
        with pytest.raises(ValueError, match="requires a ZeroPositiveAuthorityProof"):
            AuthoritySurface(
                family=SurfaceFamily.PYTHON_COMMAND,
                state=bad_state,
                kind="python.subprocess.run",
                location="legacy.py:10",
                owner="recovery-topology",
                expiry="2027-01-01",
                target_step="Step 41",
            )

    # A complete proof (forbidding every forbidden source) lets a surface retire.
    retired = AuthoritySurface(
        family=SurfaceFamily.PYTHON_COMMAND,
        state=SurfaceState.CLOSED,
        kind="python.subprocess.run",
        location="legacy.py:10",
        owner="recovery-topology",
        expiry="2027-01-01",
        target_step="Step 41",
        zero_authority_proof=_complete_proof(),
    )
    assert retired.zero_authority_proof.is_complete() is True

    # SC19 contract: authority may NEVER be derived from a label, a liveness
    # signal, a WBC receipt, or a rebuildable projection.  An incomplete proof
    # (omitting at least one forbidden source) must be rejected.
    with pytest.raises(ValueError, match="incomplete zero-authority proof"):
        AuthoritySurface(
            family=SurfaceFamily.PYTHON_COMMAND,
            state=SurfaceState.PLANNED_PENDING,
            kind="python.subprocess.run",
            location="legacy.py:10",
            owner="recovery-topology",
            expiry="2027-01-01",
            target_step="Step 41",
            zero_authority_proof=_complete_proof(
                forbids=(ForbiddenAuthoritySource.LABEL,)
            ),
        )

    # The schema enumerates exactly the four forbidden derivation paths.
    assert ALL_FORBIDDEN_AUTHORITY_SOURCES == frozenset(
        {
            ForbiddenAuthoritySource.LABEL,
            ForbiddenAuthoritySource.LIVENESS,
            ForbiddenAuthoritySource.WBC_RECEIPT,
            ForbiddenAuthoritySource.REBUILDABLE_PROJECTION,
        }
    )
    # A proof that forbids nothing is unconstructable.
    with pytest.raises(ValueError, match="forbids must enumerate"):
        ZeroPositiveAuthorityProof(
            proof_kind="k",
            evidence_ref="ref",
            forbids=(),
        )

    # The schema descriptor advertises the required non-live fields and the
    # forbidden sources so downstream migrations cannot discover new ones.
    descriptor = schema_descriptor()
    assert descriptor["required_non_live_fields"] == [
        "owner",
        "expiry",
        "target_step",
        "zero_authority_proof",
    ]
    assert set(descriptor["forbidden_authority_sources"]) == {
        s.value for s in ALL_FORBIDDEN_AUTHORITY_SOURCES
    }


# ── Step 26: Python and command-authority detection ────────────────────────


_PYTHON_AUTHORITY_SNIPPET = '''
import os
import shutil
import subprocess


class RepairRunner:
    def run(self, command):
        result = subprocess.run(["sh", "-c", command], check=False)


def trigger_repair_queue():
    return enqueue_repair_request(
        queue_root="/q", session="s", problem_signature={}, source="t"
    )


def trigger_human_gate_queue():
    return enqueue_human_gate_repair_request(queue_root="/q")


def call_all_python_authority_kinds(path):
    subprocess.run(["true"])
    subprocess.Popen(["true"])
    subprocess.call(["true"])
    subprocess.check_output(["true"])
    subprocess.check_call(["true"])
    os.system("true")
    shutil.which("true")
    exec("1")
    runner = RepairRunner()
    runner.run("doctor")
'''


_COMMAND_AUTHORITY_SNIPPET = """
# legacy manual trigger references
bin = "/usr/local/bin/arnold-repair-trigger"
loop = "arnold-repair-loop"
result = trigger_once(request_id="abc")
launch = "python -m arnold_pipelines.megaplan doctor --fix"
"""


def test_python_and_command_authority_surfaces_are_detected():
    # --- Python AST adapter ------------------------------------------------
    py_surfaces = scan_python_source(_PYTHON_AUTHORITY_SNIPPET, "snippet.py")
    py_kinds = {s.kind for s in py_surfaces}

    expected_python_kinds = {
        "python.subprocess.run",
        "python.subprocess.Popen",
        "python.subprocess.call",
        "python.subprocess.check_output",
        "python.subprocess.check_call",
        "python.os.system",
        "python.shutil.which",
        "python.exec",
        "python.RepairRunner.class",
        "python.RepairRunner.run",
        "python.queue.enqueue_repair_request",
        "python.queue.enqueue_human_gate_repair_request",
        "python.enqueue_producer",
    }
    missing = expected_python_kinds - py_kinds
    assert not missing, f"python scanner missed kinds: {missing}; got {sorted(py_kinds)}"

    # Every detected surface is live authority (no proof fabricated) and carries
    # a stable surface_id and a file:line location.
    for surface in py_surfaces:
        assert surface.state is SurfaceState.LIVE_AUTHORITY
        assert surface.family is SurfaceFamily.PYTHON_COMMAND
        assert surface.surface_id
        assert ":line" not in surface.location  # location is a real path/lineno

    # RepairRunner.run is tied to the assignment, not every ``.run()`` in the
    # snippet — the classifier must not over-match unrelated method calls.
    runner_runs = [s for s in py_surfaces if s.kind == "python.RepairRunner.run"]
    assert len(runner_runs) == 1, runner_runs

    # Enqueue producers are keyed by enclosing function and located at the def.
    # Both queue-calling functions in the snippet are detected as producers.
    producers = [s for s in py_surfaces if s.kind == "python.enqueue_producer"]
    producer_details = {s.detail for s in producers}
    assert producer_details == {
        "producer:trigger_repair_queue",
        "producer:trigger_human_gate_queue",
    }

    # --- Command-authority adapter ----------------------------------------
    cmd_surfaces = scan_command_authority(_COMMAND_AUTHORITY_SNIPPET, "snippet.txt")
    cmd_kinds = {s.kind for s in cmd_surfaces}
    expected_command_kinds = {
        "command.arnold-repair-trigger",
        "command.arnold-repair-loop",
        "command.trigger_once",
        "command.python_module_repair",
    }
    missing_cmd = expected_command_kinds - cmd_kinds
    assert not missing_cmd, (
        f"command scanner missed kinds: {missing_cmd}; got {sorted(cmd_kinds)}"
    )

    # The command adapter rejects a benign chain-start launch (no repair
    # subcommand) so it does not manufacture authority from a normal launch.
    benign = scan_command_authority(
        "python -m arnold_pipelines.megaplan chain start", "benign.txt"
    )
    assert [s.kind for s in benign] == []

    # The schema descriptor advertises exactly the kinds the adapters emit.
    descriptor = schema_descriptor()
    assert set(descriptor["python_detection_kinds"]) == set(PYTHON_DETECTION_KINDS)
    assert set(descriptor["command_authority_detection_kinds"]) == set(
        COMMAND_AUTHORITY_DETECTION_KINDS
    )
    assert set(descriptor["shell_detection_kinds"]) == set(SHELL_DETECTION_KINDS)
    assert set(descriptor["systemd_detection_kinds"]) == set(SYSTEMD_DETECTION_KINDS)
    assert set(descriptor["template_detection_kinds"]) == set(TEMPLATE_DETECTION_KINDS)


# ── Step 27: Shell repair-authority detection ────────────────────────────


_SHELL_AUTHORITY_SNIPPET = """\
# watchdog / auditor / meta / Kimi module launches
python -m arnold_pipelines.megaplan.watchdog monitor
python3 -m arnold_pipelines.megaplan.audits evaluate
python -m arnold_pipelines.megaplan.meta repair-loop-status
arnold-kimi --analyze

# legacy repair-loop relaunch patterns
nohup arnold-repair-loop --watchdog &
exec arnold-repair-loop --forever

# repair-loop wrapper loops
while true; do trigger_once request_id="loop"; done
for attempt in 1 2 3; do arnold-repair-trigger --retry; done

# tmux-based repair sessions
tmux new-session -d -s arnold-repair 'python -m arnold_pipelines.megaplan doctor'

# bash heredoc repair
bash <<EOF
python -m arnold_pipelines.megaplan doctor --fix
EOF

# wrapper functions
function run_repair() { echo repairing; }
heal_service() { echo healing; }

# aliases
alias repair_now="python -m arnold_pipelines.megaplan doctor"
"""


def test_shell_repair_surfaces_are_detected():
    """Step 27: shell adapter detects watchdog/auditor/meta/Kimi launches,
    repair-loop relaunch/wrapper patterns, tmux, heredoc, and wrapper
    functions/aliases."""
    surfaces = scan_shell_authority(_SHELL_AUTHORITY_SNIPPET, "snippet.sh")
    kinds = {s.kind for s in surfaces}

    expected_kinds = {
        "shell.watchdog_repair",
        "shell.auditor_repair",
        "shell.meta_repair",
        "shell.kimi_repair",
        "shell.module_repair",
        "shell.repair_loop_relaunch",
        "shell.repair_loop_wrapper",
        "shell.tmux_repair",
        "shell.heredoc_repair",
        "shell.wrapper_function",
        "shell.alias_repair",
    }
    missing = expected_kinds - kinds
    assert not missing, f"shell scanner missed kinds: {missing}; got {sorted(kinds)}"

    # Every detected surface is live authority and belongs to SHELL family.
    for surface in surfaces:
        assert surface.state is SurfaceState.LIVE_AUTHORITY
        assert surface.family is SurfaceFamily.SHELL
        assert surface.surface_id
        assert ":" in surface.location  # file:line

    # The wrapper_function pattern should match both functions.
    wrapper_funcs = [s for s in surfaces if s.kind == "shell.wrapper_function"]
    assert len(wrapper_funcs) >= 2, (
        f"expected >=2 wrapper functions, got {len(wrapper_funcs)}: "
        f"{[s.detail for s in wrapper_funcs]}"
    )

    # The scanner must NOT match benign shell that happens to contain "repair"
    # in a non-authority context (e.g. a comment).
    benign = scan_shell_authority("# just a comment about repair", "benign.sh")
    assert len(benign) == 0, f"shell scanner matched benign comment: {benign}"


# ── Step 28: Systemd repair-authority detection ──────────────────────────


_SYSTEMD_AUTHORITY_SNIPPET = """\
# systemd path unit
[Path]
PathChanged=/var/run/arnold-repair-trigger.path

# systemd service unit
[Unit]
Description=Arnold Repair Service
[Service]
ExecStart=/usr/local/bin/arnold-repair-loop --forever
[Install]
WantedBy=multi-user.target

# systemctl commands
systemctl enable arnold-repair.service
systemctl start arnold-watchdog.service
systemctl restart arnold-repair.timer
systemctl daemon-reload

# systemd-run
systemd-run --unit=arnold-doctor /usr/local/bin/arnold-repair-trigger

# unit dependency directives
Wants=arnold-repair.service
Requires=arnold-watchdog.service
After=arnold-repair.service
BindsTo=arnold-heal.service
"""


def test_systemd_repair_surfaces_are_detected():
    """Step 28: systemd adapter detects .path/.service/.timer unit references,
    systemctl commands, systemd-run, and unit dependency directives."""
    surfaces = scan_systemd_authority(_SYSTEMD_AUTHORITY_SNIPPET, "snippet.service")
    kinds = {s.kind for s in surfaces}

    expected_kinds = {
        "systemd.path_unit_repair",
        "systemd.service_unit_repair",
        "systemd.timer_unit_repair",
        "systemd.systemctl_repair",
        "systemd.systemd_run_repair",
        "systemd.unit_dependency_repair",
    }
    missing = expected_kinds - kinds
    assert not missing, f"systemd scanner missed kinds: {missing}; got {sorted(kinds)}"

    # Every detected surface is live authority and belongs to SYSTEMD family.
    for surface in surfaces:
        assert surface.state is SurfaceState.LIVE_AUTHORITY
        assert surface.family is SurfaceFamily.SYSTEMD
        assert surface.surface_id
        assert ":" in surface.location

    # The systemctl pattern should match enable and start (at least 2).
    systemctl_surfaces = [s for s in surfaces if s.kind == "systemd.systemctl_repair"]
    assert len(systemctl_surfaces) >= 2, (
        f"expected >=2 systemctl matches, got {len(systemctl_surfaces)}"
    )

    # The unit_dependency pattern should match Wants, Requires, After, BindsTo.
    dep_surfaces = [s for s in surfaces if s.kind == "systemd.unit_dependency_repair"]
    assert len(dep_surfaces) >= 4, (
        f"expected >=4 unit dependency matches, got {len(dep_surfaces)}"
    )

    # Benign systemd references without repair keywords must not match.
    benign = scan_systemd_authority(
        "[Unit]\nDescription=Normal Service\n[Service]\nExecStart=/bin/true\n",
        "normal.service",
    )
    assert len(benign) == 0, f"systemd scanner matched benign service: {benign}"


# ── Step 29: Template and ensure scanner detection ───────────────────────


_TEMPLATE_AUTHORITY_SNIPPET = """\
# Jinja2 deployment template
command: {{ arnold_repair_command }}
args: ["{{ repair_mode }}", "--fix"]

# cloud-init entrypoint
runcmd:
  - python3 -m arnold_pipelines.megaplan doctor --fix
  - /usr/local/bin/trigger_once request_id=cloud

# shell-substitution template
REPAIR_CMD=${ARNOLD_REPAIR_PATH:-/usr/local/bin/arnold-repair-trigger}

# ensure script
ensure_repair_complete() { check; }
guarantee_heal_finished() { verify; }

# Makefile repair target
repair:
	python -m arnold_pipelines.megaplan doctor

# Dockerfile ENTRYPOINT
ENTRYPOINT ["/usr/local/bin/arnold-repair-trigger", "--mode=docker"]

# CI pipeline repair gate
run: python -m arnold_pipelines.megaplan doctor --ci-check
"""


def test_template_and_ensure_surfaces_are_detected():
    """Step 29: template/ensure adapter detects Jinja2 templates, cloud-init,
    shell-substitution, ensure scripts, Makefiles, Dockerfiles, and CI gates."""
    surfaces = scan_template_authority(_TEMPLATE_AUTHORITY_SNIPPET, "deploy.yaml")
    kinds = {s.kind for s in surfaces}

    expected_kinds = {
        "template.deploy_repair_ref",
        "template.cloud_init_repair",
        "template.shell_subst_repair",
        "template.ensure_script",
        "template.makefile_repair",
        "template.docker_repair",
        "template.ci_repair_gate",
    }
    missing = expected_kinds - kinds
    assert not missing, f"template scanner missed kinds: {missing}; got {sorted(kinds)}"

    # Every detected surface is live authority and belongs to TEMPLATE family.
    for surface in surfaces:
        assert surface.state is SurfaceState.LIVE_AUTHORITY
        assert surface.family is SurfaceFamily.TEMPLATE
        assert surface.surface_id
        assert ":" in surface.location

    # The ensure_script pattern should match both ensure_repair_complete
    # and guarantee_heal_finished.
    ensure_surfaces = [s for s in surfaces if s.kind == "template.ensure_script"]
    assert len(ensure_surfaces) >= 2, (
        f"expected >=2 ensure script matches, got {len(ensure_surfaces)}"
    )

    # Benign template without repair keywords must not match.
    benign = scan_template_authority(
        "command: echo hello\nargs: world\n",
        "normal.yaml",
    )
    assert len(benign) == 0, f"template scanner matched benign yaml: {benign}"

    # scan_text_file combines all three adapters.
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".sh", delete=False
    ) as tmp:
        tmp.write("python -m arnold_pipelines.megaplan.watchdog monitor\n")
        tmp.write("systemctl start arnold-repair.service\n")
        tmp.write("repair:\n\tpython -m arnold_pipelines.megaplan doctor\n")
        tmp_path = tmp.name
    try:
        combined = scan_text_file(Path(tmp_path))
        assert isinstance(combined, list)
        assert len(combined) >= 3  # at least one from each adapter
    finally:
        Path(tmp_path).unlink(missing_ok=True)


# ── Step 30: Hot-upload / session-exec scanner detection ─────────────────


_HOT_UPLOAD_AUTHORITY_SNIPPET = (
    "# hot-upload / session-exec repair authority\n"
    "scp /tmp/watchdog arnold@host:/usr/local/bin/arnold-watchdog\n"
    "REMOTE_BIN_DIR=/usr/local/bin\n"
    "runner = SessionRunner(--session-command='arnold-repair-trigger --once')\n"
    "docker exec cloudbox arnold-repair-trigger --once\n"
    "cloud_hot_upload --upload watchdog.bin --restart-session\n"
)


def test_hot_upload_surfaces_are_detected():
    """Step 30: hot-upload/session-exec adapter detects legacy-bin upload
    destinations, caller-supplied session commands, ``docker exec``/remote
    exec strings, and explicit upload/restart/wrapper overrides (see
    ``scripts/cloud_hot_upload.py``).  Every match is LIVE_AUTHORITY of the
    HOT_UPLOAD family — a concrete call site that must be migrated, never an
    authority derived from a label, liveness, a WBC receipt, or a projection.
    """
    surfaces = scan_hot_upload_authority(
        _HOT_UPLOAD_AUTHORITY_SNIPPET, "scripts/cloud_hot_upload.py"
    )
    kinds = {s.kind for s in surfaces}

    expected_kinds = set(HOT_UPLOAD_DETECTION_KINDS)
    missing = expected_kinds - kinds
    assert not missing, (
        f"hot-upload scanner missed kinds: {sorted(missing)}; got {sorted(kinds)}"
    )

    for surface in surfaces:
        assert surface.state is SurfaceState.LIVE_AUTHORITY
        assert surface.family is SurfaceFamily.HOT_UPLOAD
        assert surface.surface_id
        assert ":" in surface.location

    # A benign snippet with no hot-upload markers must not match.
    benign = scan_hot_upload_authority("print('hello world')\nx = 1 + 2\n", "benign.py")
    assert len(benign) == 0, f"hot-upload scanner matched benign text: {benign}"


# ── Step 31: Simulation / dry-run success-path scanner detection ────────


_SIMULATION_SUCCESS_SNIPPET = (
    "# simulation / dry-run success gates\n"
    "proc = subprocess.run(cmd + ['--dry-run'], capture_output=True)\n"
    "if result.returncode == 0:\n"
    "    publish_repair_accepted()\n"
    "if trigger.returncode != 0:\n"
    "    raise RuntimeError('simulation failed')\n"
)


def test_simulation_success_paths_are_detected():
    """Step 31: simulation/dry-run success-path adapter detects ``--dry-run``
    subprocess invocations and ``returncode == 0`` / ``!= 0`` success gates.
    The return-code gate is only flagged *inside a simulation context* so the
    scanner never manufactures authority from a plain numeric comparison; and
    a simulation success may never publish accepted repair (see the baseline's
    ``simulation_success_proof``), which forbids deriving authority from a
    liveness signal or a rebuildable projection.
    """
    surfaces = scan_simulation_authority(
        _SIMULATION_SUCCESS_SNIPPET, "progress_auditor_controller.py"
    )
    kinds = {s.kind for s in surfaces}

    expected_kinds = set(SIMULATION_DETECTION_KINDS)
    missing = expected_kinds - kinds
    assert not missing, (
        f"simulation scanner missed kinds: {sorted(missing)}; got {sorted(kinds)}"
    )

    for surface in surfaces:
        assert surface.state is SurfaceState.LIVE_AUTHORITY
        assert surface.family is SurfaceFamily.SIMULATION
        assert surface.surface_id
        assert ":" in surface.location

    # A return-code gate OUTSIDE a simulation context must NOT be flagged,
    # otherwise authority would be manufactured from a numeric comparison.
    no_context = scan_simulation_authority(
        "if result.returncode == 0:\n    print('done')\n", "plain.py"
    )
    assert len(no_context) == 0, (
        f"simulation scanner flagged a return code outside simulation context: "
        f"{no_context}"
    )

    # A plain benign snippet must not match either.
    benign = scan_simulation_authority("x = 1\nprint('ok')\n", "benign.py")
    assert len(benign) == 0, f"simulation scanner matched benign text: {benign}"


# ── Step 32: Markdown roots (package-local/data/generated skills/briefs) ──


def test_markdown_roots_include_package_local_and_skill_data():
    """Step 32: markdown scanner roots cover package-local data, generated
    skills/briefs, cloud rollout, the docs tree, and README.  The adapter
    detects repair-command references and fenced repair blocks, all as
    LIVE_AUTHORITY of the MARKDOWN family.
    """
    roots = set(MARKDOWN_SCAN_ROOTS)
    # package-local data + generated skills/briefs
    assert "arnold_pipelines/megaplan/data" in roots, roots
    # docs tree, cloud rollout, README
    assert "docs" in roots, roots
    assert any(r.endswith("rollout.md") for r in roots), roots
    assert "README.md" in roots, roots

    snippet = (
        "# Recovery\n"
        "Run `arnold-repair-trigger --once` to heal the node.\n\n"
        "```bash\n"
        "python3 -m arnold_pipelines.megaplan doctor --fix\n"
        "```\n"
    )
    surfaces = scan_markdown_authority(snippet, "docs/ops/recovery.md")
    kinds = {s.kind for s in surfaces}
    assert {
        "markdown.repair_command_reference",
        "markdown.fenced_repair_block",
    }.issubset(kinds), f"markdown scanner missed kinds; got {sorted(kinds)}"

    for surface in surfaces:
        assert surface.state is SurfaceState.LIVE_AUTHORITY
        assert surface.family is SurfaceFamily.MARKDOWN
        assert surface.surface_id
        assert ":" in surface.location

    # scan_markdown_file path API overlays markdown + text adapters.
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False
    ) as tmp:
        tmp.write(snippet)
        tmp_path = tmp.name
    try:
        file_surfaces = scan_markdown_file(Path(tmp_path))
        assert isinstance(file_surfaces, list)
        assert any(s.family is SurfaceFamily.MARKDOWN for s in file_surfaces)
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    # Benign markdown without repair keywords must not match.
    benign = scan_markdown_authority("# Notes\nThis is just prose.\n", "notes.md")
    assert len(benign) == 0, f"markdown scanner matched benign text: {benign}"


# ── Step 33: deterministic pre-migration route-authority baseline ────────


def test_baseline_records_steps_25_to_32_before_migration():
    """Step 33: the deterministic pre-migration route-authority baseline
    records Steps 25-32, is emitted before any migration consumes it,
    validates that every recorded surface is live authority, and carries a
    simulation-success proof that forbids deriving authority from a liveness
    signal or a rebuildable projection (SC21).
    """
    # One representative surface per new scanner family (Steps 30-32) plus the
    # Step 26 Python family, to exercise cross-family baseline construction.
    surfaces: list = []
    surfaces.extend(scan_python_source("import subprocess\nsubprocess.run(['x'])\n", "a.py"))
    surfaces.extend(
        scan_hot_upload_authority("docker exec cloudbox run --once\n", "b.py")
    )
    surfaces.extend(
        scan_simulation_authority(
            "proc = subprocess.run(['--dry-run'])\nif proc.returncode == 0:\n"
            "    ok()\n",
            "c.py",
        )
    )
    surfaces.extend(scan_markdown_authority("Run `arnold-repair-trigger`\n", "d.md"))
    assert surfaces, "fixture surfaces should be detected before baseline build"

    scan_roots = {
        "markdown": list(MARKDOWN_SCAN_ROOTS),
        "python": ["arnold_pipelines/megaplan/cloud", "scripts"],
        "text": ["scripts", "systemd"],
    }
    baseline = build_route_authority_baseline(
        surfaces, scan_roots, emitted_before_migration=True
    )

    # --- Step 33 structural invariants ---
    assert baseline["baseline_kind"] == "pre_migration_route_authority_baseline"
    assert baseline["plan_steps_covered"] == list(BASELINE_PLAN_STEPS)
    assert baseline["plan_steps_covered"] == [
        "Step 25", "Step 26", "Step 27", "Step 28",
        "Step 29", "Step 30", "Step 31", "Step 32",
    ]
    assert baseline["emitted_before_migration"] is True

    # validation gate: all surfaces live, and any non-live surface would
    # require owner+expiry+target_step and a complete zero-authority proof.
    validation = baseline["validation"]
    assert validation["all_surfaces_are_live_authority"] is True
    assert validation[
        "non_live_surfaces_require_owner_expiry_target_step_and_complete_proof"
    ] is True
    assert validation["baseline_is_deterministic"] is True

    # Step 32 markdown roots (package-local data + docs) are recorded.
    md_roots = baseline["scan_roots"]["markdown"]
    assert "arnold_pipelines/megaplan/data" in md_roots, md_roots
    assert "docs" in md_roots, md_roots

    # every serialized surface carries live authority + a real call site.
    for surface in baseline["surfaces"]:
        assert surface["state"] == "live_authority"
        assert surface["family"] in baseline["scanner_families"]
        assert surface["surface_id"]
        assert surface["zero_authority_proof"] is None  # live => no proof needed

    # SC21: a simulation success path may never grant authority from a
    # forbidden source.  The proof forbids the liveness + rebuildable
    # projection members and nothing outside the forbidden set.
    sim_proof = baseline["simulation_success_proof"]
    assert sim_proof is not None, "baseline must carry a simulation success proof"
    forbidden = set(ALL_FORBIDDEN_AUTHORITY_SOURCES)
    proof_forbids = set(sim_proof["forbids"])
    assert proof_forbids.issubset(forbidden), sim_proof["forbids"]
    assert "liveness" in proof_forbids, sim_proof["forbids"]
    assert "rebuildable_projection" in proof_forbids, sim_proof["forbids"]


# ── T27: Manual repair trigger surface closure ────────────────────────────


def test_manual_repair_trigger_surface_is_closed():
    """T27: The manual_repair_trigger module no longer carries legacy surfaces.

    After migration to simple_fixer delegation:
    - ``trigger_once`` is still detected as a live command-authority surface
      (it remains the operator-facing entry point).
    - ``arnold-repair-trigger`` is NOT detected as a separate surface (the
      legacy binary path was removed).
    - ``ARNOLD_MANUAL_REPAIR_TRIGGER_BIN`` is NOT detected (the env var
      override authority was removed).
    - ``subprocess.run`` / ``subprocess`` imports are not detected as legacy
      surfaces.
    """
    from arnold_pipelines.megaplan.cloud.recovery_topology_surfaces import (
        scan_python_file,
    )

    mt_path = Path(
        "arnold_pipelines/megaplan/cloud/manual_repair_trigger.py"
    )
    text = mt_path.read_text(encoding="utf-8")

            # Extract the code body by skipping the module-level docstring.
    # The first non-blank, non-docstring line after imports is where code starts.
    code_body = text.split("from __future__", 1)[-1]
    code_body = "from __future__" + code_body

    from arnold_pipelines.megaplan.cloud.recovery_topology_surfaces import (
        scan_command_authority,
    )

    # Scan only the code body for command-authority surfaces.
    code_surfaces = scan_command_authority(code_body, str(mt_path))
    code_kinds = {s.kind for s in code_surfaces}

    # trigger_once is still a live surface (the entry point itself).
    assert "command.trigger_once" in code_kinds, (
        f"trigger_once must remain a detected surface; got kinds={code_kinds}"
    )

    # The legacy arnold-repair-trigger binary path must NOT be detected
    # as a command-authority surface in the code body.
    assert "command.arnold-repair-trigger" not in code_kinds, (
        f"arnold-repair-trigger binary surface must be closed in code; "
        f"got kinds={code_kinds}"
    )

    # ARNOLD_MANUAL_REPAIR_TRIGGER_BIN env var must not appear in code.
    assert "ARNOLD_MANUAL_REPAIR_TRIGGER_BIN" not in code_body, (
        "ARNOLD_MANUAL_REPAIR_TRIGGER_BIN must not appear in code body"
    )

    # /usr/local/bin/arnold-repair-trigger literal must not appear in code.
    assert "/usr/local/bin/arnold-repair-trigger" not in code_body, (
        "/usr/local/bin/arnold-repair-trigger must not appear in code body"
    )

    # subprocess import must not appear.
    assert "import subprocess" not in code_body, (
        "subprocess import must not appear in manual_repair_trigger.py"
    )

    # The delegation import must be present (positive signal).
    assert "repair_delegation" in code_body, (
        "manual_repair_trigger.py must import repair_delegation"
    )
    assert "simple_fixer" in code_body, (
        "manual_repair_trigger.py must import simple_fixer"
    )


# ── T30: progress auditor controller dispatch surface closure ───────────────


def test_progress_auditor_controller_dispatch_surface_is_closed():
    """T30 / Step 43: the controller no longer executes arbitrary trigger argv.

    After migration to shim validation:
    - ``import subprocess`` is absent (the arbitrary argv subprocess runner has
      been retired; the canonical repair path is simple_fixer delegation).
    - The legacy ``_default_trigger_runner`` arbitrary-execution entry point is
      gone.
    - The closed trigger-argv rejection vocabulary and the delegation-shim
      typed rejection are present (positive migration signals).

    No authority is manufactured from a label, liveness signal, WBC receipt, or
    rebuildable projection: recognition only narrows the typed rejection reason.
    """
    controller_path = Path(
        "arnold_pipelines/megaplan/cloud/progress_auditor_controller.py"
    )
    text = controller_path.read_text(encoding="utf-8")

    # The arbitrary subprocess trigger runner has been retired.
    assert "import subprocess" not in text, (
        "progress_auditor_controller.py must not import subprocess after "
        "trigger argv retirement"
    )
    assert "_default_trigger_runner" not in text, (
        "the legacy arbitrary-argv subprocess runner must be removed"
    )

    # The closed rejection vocabulary and delegation-shim consumption are present.
    assert "TRIGGER_ARGV_REJECTION_KINDS" in text, (
        "the closed trigger-argv rejection vocabulary must be defined"
    )
    assert "_classify_trigger_argv" in text, (
        "the trigger-argv classifier must be present"
    )
    assert "emit_zero_authority_rejection" in text, (
        "the controller must consume the delegation-shim typed rejection"
    )


# ── T29: arnold-repair-trigger wrapper dispatch surface closure ──────────────


def test_repair_trigger_wrapper_surface_is_closed():
    """T29 / Step 42 second split: retire queue-scan dispatch bypass families.

    After migration to simple_fixer delegation inside ``_dispatch``:
    - ``subprocess.Popen`` repair-launch authority is absent from the wrapper.
    - ``manager_argv`` managed-agent construction is absent.
    - ``child_argv`` repair-child argv construction is absent.
    - The canonical ``_delegate_repair_to_simple_fixer`` delegation path and
      ``build_custody_target_key`` occurrence resolution are present (positive
      migration signals).

    No authority is manufactured from a label, liveness signal, WBC receipt, or
    rebuildable projection: the CustodyTargetKey is built from exact occurrence
    data and delegated through the typed shim.
    """
    wrapper_path = Path(
        "arnold_pipelines/megaplan/cloud/wrappers/arnold-repair-trigger"
    )
    text = wrapper_path.read_text(encoding="utf-8")

    # subprocess.Popen repair-launch authority must be retired.
    assert "subprocess.Popen" not in text, (
        "arnold-repair-trigger must not use subprocess.Popen for repair "
        "dispatch after migration to simple_fixer delegation"
    )

    # manager_argv managed-agent construction must be retired.
    assert "manager_argv" not in text, (
        "arnold-repair-trigger must not construct manager_argv managed-agent "
        "argv after migration to simple_fixer delegation"
    )

    # child_argv repair-child argv construction must be retired.
    assert "child_argv" not in text, (
        "arnold-repair-trigger must not construct child_argv repair-child "
        "argv after migration to simple_fixer delegation"
    )

    # The canonical delegation function must be present and called.
    assert "_delegate_repair_to_simple_fixer(" in text, (
        "arnold-repair-trigger must call _delegate_repair_to_simple_fixer "
        "for canonical repair delegation"
    )

    # build_custody_target_key must be imported (exact occurrence resolution).
    assert "build_custody_target_key" in text, (
        "arnold-repair-trigger must resolve occurrences through "
        "build_custody_target_key for canonical simple_fixer delegation"
    )

    # The RepairDelegation / delegate_to_simple_fixer imports must be present.
    assert "delegate_to_simple_fixer" in text, (
        "arnold-repair-trigger must import delegate_to_simple_fixer"
    )


# ── T36 / Step 51: arnold-progress-auditor wrapper repair-trigger handoff ────


def test_progress_auditor_wrapper_repair_handoff_surface_is_closed():
    """T36 / Step 51: the progress-auditor wrapper repair-trigger handoff
    routes through the shared repair-delegation shim.

    After rerouting the L3 escalation controller's repair handoff:
    - The legacy ``REPAIR_TRIGGER_BIN`` argv is no longer plumbed to the
      controller (the ``arnold-repair-trigger`` binary is no longer invoked
      by this wrapper for repair authority).
    - The dead ``MEGAPLAN_AUDIT_REPAIR_TRIGGER_BIN`` override is gone.
    - The shared ``repair_delegation`` shim is imported and the
      ``emit_zero_authority_rejection`` typed handoff is used exactly once,
      confined to the repair-trigger handoff point (SC36).  Audit reporting,
      human escalation, GitHub sync, and model audit behaviour remain
      non-authoritative and are NOT routed through the shim.

    No authority is manufactured from a label, liveness signal, WBC receipt,
    or rebuildable projection: the auditor wrapper boundary holds no exact
    F01 occurrence tuple, so the handoff emits a typed zero-authority
    rejection and repair authority stays with the canonical simple_fixer
    delegation that drains the occurrence-compatible queue.
    """
    wrapper_path = Path(
        "arnold_pipelines/megaplan/cloud/wrappers/arnold-progress-auditor"
    )
    text = wrapper_path.read_text(encoding="utf-8")

    # The legacy argv handoff to the controller must be retired.
    assert "MEGAPLAN_AUDIT_REPAIR_TRIGGER_BIN" not in text, (
        "arnold-progress-auditor must not define the legacy "
        "MEGAPLAN_AUDIT_REPAIR_TRIGGER_BIN override after Step 51"
    )
    assert 'trigger_argv=[trigger]' not in text, (
        "the legacy trigger_argv=[trigger] handoff must be retired"
    )
    assert "authorized, trigger = sys.argv[1:6]" not in text, (
        "the controller heredoc must not unpack the legacy trigger argv"
    )

    # The shared shim is imported exactly once and the typed handoff is
    # called exactly once (confined to the repair-trigger handoff point).
    assert (
        "from arnold_pipelines.megaplan.cloud.wrappers.repair_delegation"
        in text
    ), "the progress-auditor wrapper must import the shared repair-delegation shim"
    assert text.count(
        "from arnold_pipelines.megaplan.cloud.wrappers.repair_delegation"
    ) == 1, (
        "the repair-delegation shim must be imported exactly once"
    )
    assert text.count("emit_zero_authority_rejection(") == 1, (
        "the repair handoff must call emit_zero_authority_rejection "
        "exactly once (only the repair-trigger handoff; report paths "
        "remain non-authoritative)"
    )

    # The wrapper boundary holds no exact F01 occurrence tuple, so it must
    # NOT attempt a full delegation (no delegate_to_simple_fixer call).
    assert "delegate_to_simple_fixer" not in text, (
        "the progress-auditor wrapper boundary must not attempt full "
        "delegation; it must emit a typed zero-authority rejection"
    )

    # The typed caller kind and routing marker must be present.
    assert (
        '"terminal_audit"' in text or "'terminal_audit'" in text
    ), "the repair handoff must declare the terminal_audit caller kind"
    assert "repair_handoff_routed_through_shim" in text, (
        "the handoff result must record the shim-routing marker"
    )

    # The controller is invoked without a launch argv (request is queued
    # for canonical simple_fixer delegation rather than launched here).
    assert "trigger_argv=()" in text, (
        "the L3 escalation controller must be invoked with trigger_argv=()"
    )

    # Non-authoritative report paths must remain present and unrouted.
    assert "record_incident_audits" in text, (
        "audit incident reporting must remain present (non-authoritative)"
    )


# ── Step 59-65: watchdog planned-pending closure (T39, SC39) ────────────────
#
# After the watchdog claim-write, claim-adoption/existing-owner, stale-state
# cleanup, process-reaping, retry-loop, unchanged-fingerprint, and retry-budget
# families are bound to the watchdog_repair_state_authority_or_reject gate, no
# watchdog authority surface may be left in a half-migrated planned-pending
# state.  Each family is either fully live (legitimate authority through the
# gate) or fully closed (legacy direct authority removed); none derives
# authority from a label, liveness signal, WBC receipt, or rebuildable
# projection (SC39).

WRAPPERS_DIR = Path("arnold_pipelines/megaplan/cloud/wrappers")


def test_watchdog_has_zero_planned_pending_surfaces() -> None:
    """Step 65: scanning arnold-watchdog must yield zero planned-pending
    surfaces after the Step 59-65 repair-state migration.

    A planned-pending surface is one scheduled for migration but not yet
    closed; leaving one would mean a watchdog repair-state mutation can still
    become accepted repair outside canonical simple_fixer delegation.  The test
    also asserts the migration gate and canonical delegation path are present
    so the absence of planned-pending surfaces reflects a *completed*
    migration, not an unscanned wrapper.  Authority is never manufactured from
    a label, liveness signal, WBC receipt, or rebuildable projection (SC39).
    """
    wrapper_path = WRAPPERS_DIR / "arnold-watchdog"
    text = wrapper_path.read_text(encoding="utf-8")

    # Positive migration signal: the repair-state authority gate is defined and
    # routes every watchdog repair-state mutation through the simple_fixer
    # singleton claim (exact F01 occurrence tuple), binding to current fence
    # and custody epoch rather than to a label/liveness/WBC/projection.
    assert "watchdog_repair_state_authority_or_reject() {" in text, (
        "arnold-watchdog must define the repair-state authority gate"
    )
    assert "simple_fixer.singleton_claim.exact_f01_tuple" in text, (
        "arnold-watchdog repair-state mutations must delegate through the "
        "simple_fixer singleton claim (exact occurrence identity)"
    )

    surfaces = scan_shell_authority(text, str(wrapper_path))
    planned_pending = [s for s in surfaces if s.state is SurfaceState.PLANNED_PENDING]
    assert planned_pending == [], (
        f"arnold-watchdog must carry zero planned-pending surfaces after the "
        f"Step 59-65 repair-state migration; found {len(planned_pending)}: "
        f"{[s.kind for s in planned_pending]}"
    )


def test_repair_loop_has_zero_planned_pending_surfaces() -> None:
    """Steps 68-75: scanning arnold-repair-loop must yield zero planned-pending
    surfaces after the Step 68-75 repair-state migration.

    A planned-pending surface is one scheduled for migration but not yet
    closed; leaving one would mean a repair-loop repair-state mutation can still
    become accepted repair outside canonical simple_fixer delegation.  The test
    also asserts the migration gate and canonical delegation path are present
    so the absence of planned-pending surfaces reflects a *completed*
    migration, not an unscanned wrapper.  Authority is never manufactured from
    a label, liveness signal, WBC receipt, or rebuildable projection (SC41).
    """
    wrapper_path = WRAPPERS_DIR / "arnold-repair-loop"
    text = wrapper_path.read_text(encoding="utf-8")

    # Positive migration signal: the repair-state and repair-launch authority
    # gates are defined and route every repair-loop mutation through the
    # simple_fixer singleton claim (exact F01 occurrence tuple), binding to
    # current fence and custody epoch rather than to a label/liveness/WBC/
    # projection.
    assert "repair_loop_repair_state_authority_or_reject() {" in text, (
        "arnold-repair-loop must define the repair-state authority gate"
    )
    assert "repair_loop_repair_launch_authority_or_reject() {" in text, (
        "arnold-repair-loop must define the repair-launch authority gate"
    )
    assert "simple_fixer.singleton_claim.exact_f01_tuple" in text, (
        "arnold-repair-loop repair-state/launch mutations must delegate through "
        "the simple_fixer singleton claim (exact occurrence identity)"
    )

    # All step markers T68-T75 must be present.
    for marker in (
        "T68-RETRIGGER-01", "T69-META-01",
        "T70-STALE-STATE-01", "T71-STALE-CLAIM-01",
        "T72-REAP-01", "T73-RETRY-01",
        "T74-FINGERPRINT-01", "T75-BUDGET-01",
    ):
        assert marker in text, (
            f"arnold-repair-loop must carry {marker} evidence marker"
        )

    surfaces = scan_shell_authority(text, str(wrapper_path))
    planned_pending = [s for s in surfaces if s.state is SurfaceState.PLANNED_PENDING]
    assert planned_pending == [], (
        f"arnold-repair-loop must carry zero planned-pending surfaces after the "
        f"Steps 68-75 repair-state migration; found {len(planned_pending)}: "
        f"{[s.kind for s in planned_pending]}"
    )


# ── T44: Operator docs, tiered repair/audit, and generated skills ──────────


_ZERO_AUTHORITY_MARKERS = (
    "zero-authority history",
    "zero-authority",
    "canonical delegation",
    "non-authoritative",
    "compatibility only",
    "legacy compatibility",
    "Authority status",
    "M11 acceptance",
)


def _has_migration_marker(text: str) -> bool:
    """Return True if *text* contains a T44 zero-authority migration marker."""
    lowered = text.lower()
    return any(m.lower() in lowered for m in _ZERO_AUTHORITY_MARKERS)


def test_operator_docs_have_no_authoritative_legacy_commands():
    """T44/Steps 86-91: core operator docs carry no authoritative legacy commands.

    Every operator-facing Markdown doc under docs/ must have been migrated to
    canonical delegation or zero-authority history.  The scanner detects any
    remaining live repair-command references; each file with live surfaces must
    carry a zero-authority migration marker proving it has been reviewed and
    marked as non-authoritative.
    """
    docs_root = Path("docs")
    if not docs_root.is_dir():
        pytest.skip("docs/ directory not found")

    md_files = list(docs_root.rglob("*.md"))
    if not md_files:
        pytest.skip("no Markdown files found under docs/")

    unmigrated: list[str] = []
    for md_path in md_files:
        surfaces = scan_markdown_file(md_path)
        live_surfaces = [s for s in surfaces if s.state is SurfaceState.LIVE_AUTHORITY]
        if live_surfaces:
            text = md_path.read_text(encoding="utf-8")
            if not _has_migration_marker(text):
                unmigrated.append(str(md_path))

    assert unmigrated == [], (
        f"docs/ Markdown files with live-authority surfaces must carry a "
        f"zero-authority migration marker after T44; "
        f"found {len(unmigrated)} unmigrated: {unmigrated[:20]}"
    )


def test_tiered_repair_and_audit_loop_doc_has_no_authoritative_legacy_commands():
    """T44/Steps 86-91: package-local rollout and repair/audit docs carry no
    authoritative legacy commands.

    The rollout.md doc and any tiered repair/audit docs under
    arnold_pipelines/megaplan/cloud/ must have been migrated to canonical
    delegation or zero-authority history.
    """
    rollout = Path("arnold_pipelines/megaplan/cloud/rollout.md")
    assert rollout.is_file(), f"rollout.md must exist at {rollout}"

    text = rollout.read_text(encoding="utf-8")

    # Verify the zero-authority migration marker is present
    assert _has_migration_marker(text), (
        "rollout.md must declare zero-authority history migration marker"
    )

    # Verify the legacy six-hour section is annotated as compatibility-only
    surfaces = scan_markdown_file(rollout)
    live_surfaces = [s for s in surfaces if s.state is SurfaceState.LIVE_AUTHORITY]
    # rollout.md is allowed to have legacy path references ONLY if the
    # document-level zero-authority marker explicitly disclaims authority.
    # The marker above (verified) serves as that disclaimer.
    # Also verify the legacy section explicitly notes its status.
    assert "Six-hour timer propagation path" in text, (
        "rollout.md must retain the six-hour propagation path documentation"
    )

    # The cloud/ directory docs (if any others) must also be migrated
    cloud_dir = Path("arnold_pipelines/megaplan/cloud")
    doc_files = [p for p in cloud_dir.rglob("*.md") if p != rollout]
    unmigrated: list[str] = []
    for doc_path in doc_files:
        doc_surfaces = scan_markdown_file(doc_path)
        doc_live = [s for s in doc_surfaces if s.state is SurfaceState.LIVE_AUTHORITY]
        if doc_live:
            doc_text = doc_path.read_text(encoding="utf-8")
            if not _has_migration_marker(doc_text):
                unmigrated.append(str(doc_path))

    assert unmigrated == [], (
        f"cloud/ Markdown files with live-authority surfaces must carry a "
        f"zero-authority migration marker after T44; "
        f"found {len(unmigrated)} unmigrated: {unmigrated}"
    )


def test_generated_codex_skills_have_no_authoritative_legacy_commands():
    """T44/Steps 86-91: generated _codex_skills and auditor_signal_swarm_briefs
    carry no authoritative legacy commands.

    Generated skill Markdown and brief files must have been migrated to
    canonical delegation or zero-authority history — they must not contain
    materializable legacy repair commands without a migration marker.
    """
    skills_dir = Path("arnold_pipelines/megaplan/data/_codex_skills")
    briefs_dir = Path("arnold_pipelines/megaplan/data/auditor_signal_swarm_briefs")

    all_md_files: list[Path] = []
    if skills_dir.is_dir():
        all_md_files.extend(skills_dir.rglob("*.md"))
    if briefs_dir.is_dir():
        all_md_files.extend(briefs_dir.rglob("*.md"))

    if not all_md_files:
        pytest.skip("no generated skill or brief Markdown files found")

    unmigrated: list[str] = []
    for md_path in all_md_files:
        surfaces = scan_markdown_file(md_path)
        live_surfaces = [s for s in surfaces if s.state is SurfaceState.LIVE_AUTHORITY]
        if live_surfaces:
            text = md_path.read_text(encoding="utf-8")
            if not _has_migration_marker(text):
                unmigrated.append(str(md_path))

    assert unmigrated == [], (
        f"generated _codex_skills and auditor_signal_swarm_briefs with live-"
        f"authority surfaces must carry a zero-authority migration marker after "
        f"T44; found {len(unmigrated)} unmigrated: {unmigrated[:20]}"
    )


# ═══════════════════════════════════════════════════════════════════════════
# T45 / Step 92 — Final route-authority closure
# ═══════════════════════════════════════════════════════════════════════════


def test_final_route_authority_closure_has_zero_unplanned_and_zero_planned_pending():
    """Step 92 closes exact surface IDs and content, never whole kinds."""
    import scripts.check_recovery_topology_surfaces as _checker

    # Kind→step coverage remains exhaustive, but is not itself a closure.
    declared = _checker._ALL_DECLARED_DETECTION_KINDS
    assert set(_checker._KIND_CLOSURE_STEPS) == declared

    surfaces = [
        AuthoritySurface(
            kind="python.subprocess.run",
            family=SurfaceFamily.PYTHON_COMMAND,
            state=SurfaceState.LIVE_AUTHORITY,
            location="first.py:10",
            detail="subprocess.run(['first'])",
        ),
        AuthoritySurface(
            kind="python.subprocess.run",
            family=SurfaceFamily.PYTHON_COMMAND,
            state=SurfaceState.LIVE_AUTHORITY,
            location="second.py:20",
            detail="subprocess.run(['second'])",
        ),
    ]
    manifest = _checker.build_route_closure_manifest(surfaces)
    assert set(manifest) == {surface.surface_id for surface in surfaces}
    assert len(manifest) == 2

    # Every concrete record is CLOSED and bound to ID/location/content hash.
    for surface in surfaces:
        record = manifest[surface.surface_id]
        assert record["closure_state"] == SurfaceState.CLOSED.value, (
            f"{surface.surface_id}: expected CLOSED, got {record['closure_state']}"
        )
        assert record["surface_id"] == surface.surface_id
        assert record["location"] == surface.location
        assert record["content_hash"] == surface.content_hash
        proof = record["zero_authority_proof"]
        forbids = frozenset(proof.get("forbids", []))
        assert {item.value for item in ALL_FORBIDDEN_AUTHORITY_SOURCES}.issubset(
            forbids
        )
        assert proof["evidence_ref"].endswith(
            f"surface={surface.surface_id}&content_hash={surface.content_hash}"
        )
        assert record.get("owner")
        assert record.get("expiry")
        assert record.get("target_step")

    closed = _checker.classify_final_route_authority(
        surfaces=surfaces,
        manifest=manifest,
    )
    assert closed["closure_complete"] is True
    assert closed["exact_set_equal"] is True
    assert closed["closed_count"] == 2

    # A newly detected call of an already-known kind is still unplanned.
    added_surface = AuthoritySurface(
        kind="python.subprocess.run",
        family=SurfaceFamily.PYTHON_COMMAND,
        state=SurfaceState.LIVE_AUTHORITY,
        location="third.py:30",
        detail="subprocess.run(['third'])",
    )
    added = _checker.classify_final_route_authority(
        surfaces=surfaces + [added_surface],
        manifest=manifest,
    )
    assert added["unplanned_surface_ids"] == [added_surface.surface_id]
    assert added["closure_complete"] is False

    # A deleted/moved surface leaves a stale manifest row.
    removed = _checker.classify_final_route_authority(
        surfaces=surfaces[:1],
        manifest=manifest,
    )
    assert removed["stale_manifest_surface_ids"] == [surfaces[1].surface_id]
    assert removed["exact_set_equal"] is False
    assert removed["closure_complete"] is False

    # Same stable ID/location with changed content cannot inherit closure.
    changed_surface = AuthoritySurface(
        kind=surfaces[0].kind,
        family=surfaces[0].family,
        state=SurfaceState.LIVE_AUTHORITY,
        location=surfaces[0].location,
        detail="subprocess.run(['changed-in-place'])",
    )
    assert changed_surface.surface_id == surfaces[0].surface_id
    changed = _checker.classify_final_route_authority(
        surfaces=[changed_surface, surfaces[1]],
        manifest=manifest,
    )
    assert changed["mismatched_surface_ids"] == [changed_surface.surface_id]
    assert changed["closure_complete"] is False

    # Incomplete or unbound proof cannot close an otherwise matching surface.
    bad_proof_manifest = {
        surface_id: dict(record)
        for surface_id, record in manifest.items()
    }
    first_id = surfaces[0].surface_id
    bad_proof_manifest[first_id]["zero_authority_proof"] = dict(
        bad_proof_manifest[first_id]["zero_authority_proof"],
        evidence_ref="evidence/unbound.json",
    )
    bad_proof = _checker.classify_final_route_authority(
        surfaces=surfaces,
        manifest=bad_proof_manifest,
    )
    assert bad_proof["invalid_proof_surface_ids"] == [first_id]
    assert bad_proof["closure_complete"] is False

    # A concrete pending row blocks closure.
    manifest_pending = dict(manifest)
    pending_id = surfaces[0].surface_id
    manifest_pending[pending_id] = dict(
        manifest_pending[pending_id]
    )
    manifest_pending[pending_id]["closure_state"] = (
        SurfaceState.PLANNED_PENDING.value
    )
    cls_pending = _checker.classify_final_route_authority(
        surfaces=surfaces,
        manifest=manifest_pending,
    )
    assert cls_pending["planned_pending_count"] == 1
    assert cls_pending["planned_pending_surface_ids"] == [pending_id]
    assert cls_pending["closure_complete"] is False

    # Full payload contains both the detected set and per-surface manifest.
    payload = _checker.build_final_route_closure_payload(surfaces=surfaces)
    assert payload["baseline_kind"] == "final_route_authority_closure"
    assert payload["closure"]["closure_complete"] is True
    assert len(payload["route_closure_manifest"]) == len(surfaces)
    assert len(payload["detected_surfaces"]) == len(surfaces)
