#!/usr/bin/env python3
"""Four-stage status-trigger babysitter orchestrator.

The watchdog's status trigger (``MEGAPLAN_SUPERFIXER_ONLY=1``) launches this
orchestrator directly (see ``arnold_pipelines/megaplan/cloud/wrappers/
arnold-babysitter``).  It turns superfixer-debug Phases 1-5 into CODE — a
prompt handed to a single agent is a known failure mode, so every stage is a
typed, receipted step:

    Stage 1  Sol (codex:gpt-5.6-sol, read-only) scopes the evidence pack
             into bounded DeepSeek V4 Flash investigator questions.
    Stage 2  One Flash investigator per Sol question, fanned out in-process
             through skills/subagent-launcher/fan.py.
    Stage 3  Sol adjudicates the swarm into a validated, content-addressed
             arnold.superfixer.recovery_handoff.v1 envelope (JSON + Markdown).
    Stage 4  The implementer executes only the canonical immediate repair
             (Horizon A) in the approved editable runtime, then the
             orchestrator proves the canonical chain milestone/cursor moved.

Every stage writes a receipt under the run root and fails closed: a missing
codex/fan binary, a non-zero stage rc, or an unparsable handoff stops the run
with a typed receipt — it never silently falls through to a weaker route.

Env overrides (all optional):
    ARNOLD_BABYSITTER_CODEX_BIN         codex executable (default "codex")
    ARNOLD_BABYSITTER_FAN_BIN           path to skills/subagent-launcher/fan.py
    ARNOLD_BABYSITTER_SOL_MODEL         Sol model (default "gpt-5.6-sol")
    ARNOLD_BABYSITTER_MODEL             Flash swarm model (default "deepseek:deepseek-v4-flash")
    ARNOLD_BABYSITTER_WORKERS           fan.py --max-workers (default 5)
    ARNOLD_BABYSITTER_MAX_TOKENS        fan.py --max-tokens (default 65536)
    ARNOLD_BABYSITTER_TASK_TIMEOUT      fan.py --task-timeout (default 1800)
    ARNOLD_BABYSITTER_CODEX_TIMEOUT     per-codex-call timeout seconds (default 1800)
    ARNOLD_BABYSITTER_IMPLEMENTER_MODEL implementer model (defaults to --model)
    ARNOLD_BABYSITTER_DRY_SOL           "1" => stage 1/3 use the prompt as output (tests)
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

RECOVERY_HANDOFF_SCHEMA = "arnold.superfixer.recovery_handoff.v1"
STAGE_RECEIPT_SCHEMA = "arnold.superfixer.stage_receipt.v1"
FINAL_RECEIPT_SCHEMA = "arnold.superfixer.babysitter_receipt.v1"

_REPO_ROOT = Path(__file__).resolve().parents[4]


def _utcnow_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _eprint(message: str) -> None:
    print(message, file=sys.stderr)
    sys.stderr.flush()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _stage_receipt(
    stage: str,
    *,
    status: str,
    run_id: str,
    session: str,
    detail: str = "",
    artifacts: dict[str, str] | None = None,
) -> dict[str, Any]:
    return {
        "schema": STAGE_RECEIPT_SCHEMA,
        "stage": stage,
        "status": status,
        "run_id": run_id,
        "session": session,
        "detail": detail,
        "artifacts": artifacts or {},
        "recorded_at": _utcnow_iso(),
    }


def _extract_json(text: str) -> dict[str, Any]:
    """Tolerantly extract the first balanced JSON object from *text*."""
    text = text.strip()
    try:
        payload = json.loads(text)
        if isinstance(payload, dict):
            return payload
    except (ValueError, TypeError):
        pass
    start = text.find("{")
    while start != -1:
        depth = 0
        for index in range(start, len(text)):
            char = text[index]
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start : index + 1]
                    try:
                        payload = json.loads(candidate)
                    except (ValueError, TypeError):
                        break
                    if isinstance(payload, dict):
                        return payload
                    break
        start = text.find("{", start + 1)
    raise ValueError("no JSON object found in model output")


def _default_fan_bin() -> Path:
    return _REPO_ROOT / "arnold_pipelines" / "megaplan" / "skills" / "subagent-launcher" / "fan.py"


def _run_codex(
    *,
    prompt: str,
    out_path: Path,
    codex_bin: str,
    sol_model: str,
    timeout: int,
    env: dict[str, str],
) -> None:
    cmd = [
        codex_bin,
        "exec",
        "--skip-git-repo-check",
        "--sandbox",
        "read-only",
        "-c",
        f"model={sol_model}",
        "-c",
        "model_reasoning_effort=high",
        "--output-last-message",
        str(out_path),
        "-",
    ]
    proc = subprocess.run(
        cmd,
        input=prompt,
        text=True,
        capture_output=True,
        env=env,
        timeout=timeout,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"codex stage failed rc={proc.returncode} stderr={proc.stderr[-2000:]}"
        )
    if not out_path.is_file() or not out_path.read_text(encoding="utf-8", errors="replace").strip():
        raise RuntimeError("codex stage produced no output message")


# ── Stage 1 — Sol scopes the swarm ───────────────────────────────────────────


def stage1_sol_scope(
    *,
    evidence_pack: str,
    run_dir: Path,
    run_id: str,
    session: str,
    codex_bin: str,
    sol_model: str,
    codex_timeout: int,
    env: dict[str, str],
) -> list[str]:
    prompt = (
        "You are Sol (gpt-5.6-sol), scoping stage 1 of an evidence-first epic "
        "babysitting recovery.  Read the evidence pack and produce the bounded "
        "questions that a DeepSeek V4 Flash read-only swarm must investigate.\n\n"
        "Respond with ONLY a JSON object of the form "
        '{"questions": ["<question 1>", "<question 2>", ...]} — 3 to 8 questions, '
        "each self-contained, naming the exact artifacts/decisions it informs.\n\n"
        "EVIDENCE PACK:\n" + evidence_pack
    )
    sol1_path = run_dir / "stage1-sol-scope.txt"
    if os.environ.get("ARNOLD_BABYSITTER_DRY_SOL") == "1":
        _write_text(sol1_path, json.dumps({"questions": ["dry-run question"]}))
    else:
        _run_codex(
            prompt=prompt,
            out_path=sol1_path,
            codex_bin=codex_bin,
            sol_model=sol_model,
            timeout=codex_timeout,
            env=env,
        )
        _eprint(f"[babysitter] stage1 sol scope written {sol1_path}")
    payload = _extract_json(sol1_path.read_text(encoding="utf-8", errors="replace"))
    questions = payload.get("questions")
    if not isinstance(questions, list) or not all(
        isinstance(item, str) and item.strip() for item in questions
    ):
        raise RuntimeError("Sol stage 1 produced no usable questions")
    _write_json(
        run_dir / "stage1.json",
        {
            "schema": "arnold.superfixer.sol_scope.v1",
            "run_id": run_id,
            "session": session,
            "question_count": len(questions),
            "questions": [str(item) for item in questions],
            "sol_text_path": str(sol1_path),
            "recorded_at": _utcnow_iso(),
        },
    )
    return [str(item) for item in questions]


# ── Stage 2 — DeepSeek V4 Flash swarm ────────────────────────────────────────


def stage2_flash_swarm(
    *,
    questions: list[str],
    run_dir: Path,
    run_id: str,
    session: str,
    workspace: str,
    fan_bin: Path,
    model: str,
    workers: int,
    max_tokens: int,
    task_timeout: int,
    env: dict[str, str],
) -> Path:
    briefs_dir = run_dir / "stage2-briefs"
    briefs_dir.mkdir(parents=True, exist_ok=True)
    for index, question in enumerate(questions, start=1):
        _write_text(
            briefs_dir / f"q{index:02d}.md",
            f"# Swarm investigator {index}\n\n"
            f"Session: {session}\nRun id: {run_id}\n\n"
            "You are a bounded, READ-ONLY DeepSeek V4 Flash evidence worker. "
            "Answer the assigned question with exact artifacts, paths, and "
            "file-grounded findings.  Label evidence, inference, and unknowns "
            "separately.  Do not propose architecture or self-authorize a "
            "repair.\n\nQuestion:\n" + question,
        )
    swarm_dir = run_dir / "stage2-swarm"
    cmd = [
        sys.executable,
        str(fan_bin),
        "--briefs-dir",
        str(briefs_dir),
        "--output-dir",
        str(swarm_dir),
        "--max-workers",
        str(workers),
        "--model",
        model,
        "--toolsets",
        "file,web",
        "--max-tokens",
        str(max_tokens),
        "--task-timeout",
        str(task_timeout),
        "--project-dir",
        workspace,
    ]
    _eprint(f"[babysitter] stage2 swarm fan.py briefs={len(questions)}")
    proc = subprocess.run(cmd, text=True, capture_output=True, env=env, check=False)
    if proc.returncode != 0:
        raise RuntimeError(
            f"stage2 swarm fan.py failed rc={proc.returncode} stderr={proc.stderr[-2000:]}"
        )
    report = swarm_dir / "_report.json"
    if not report.is_file():
        raise RuntimeError("stage2 swarm produced no _report.json")
    _write_json(
        run_dir / "stage2.json",
        {
            "schema": "arnold.superfixer.swarm_index.v1",
            "run_id": run_id,
            "session": session,
            "investigators": len(questions),
            "model": model,
            "report_path": str(report),
            "recorded_at": _utcnow_iso(),
        },
    )
    return report


# ── Stage 3 — Sol adjudicates into recovery_handoff.v1 ───────────────────────


def _content_address(payload: dict[str, Any]) -> str:
    unsigned = {key: value for key, value in payload.items() if key != "handoff_id"}
    canonical = json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(canonical).hexdigest()


def _validate_handoff(payload: dict[str, Any]) -> dict[str, Any]:
    if str(payload.get("schema") or "") != RECOVERY_HANDOFF_SCHEMA:
        raise RuntimeError("recovery_handoff.v1 schema mismatch")
    target = payload.get("target")
    if not isinstance(target, dict) or not str(target.get("session") or "").strip():
        raise RuntimeError("recovery_handoff.v1 missing target.session")
    for tier in ("tier1", "tier2"):
        if not isinstance(payload.get(tier), dict) or not str(
            (payload.get(tier) or {}).get("action") or ""
        ).strip():
            raise RuntimeError(f"recovery_handoff.v1 missing {tier}.action")
    payload = dict(payload)
    payload["handoff_id"] = _content_address(payload)
    return payload


def stage3_sol_adjudicate(
    *,
    evidence_pack: str,
    sol1_text: str,
    swarm_report: Path,
    run_dir: Path,
    run_id: str,
    session: str,
    codex_bin: str,
    sol_model: str,
    codex_timeout: int,
    env: dict[str, str],
) -> dict[str, Any]:
    try:
        swarm_index = json.loads(swarm_report.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        swarm_index = {"report_path": str(swarm_report)}
    prompt = (
        "You are Sol (gpt-5.6-sol), stage 3 of an evidence-first epic "
        "babysitting recovery.  Adjudicate the original evidence, your stage-1 "
        "scope, and the DeepSeek V4 Flash swarm reports, then emit the recovery "
        "handoff envelope.\n\n"
        "Respond with ONLY a JSON object matching this contract:\n"
        '{"schema": "arnold.superfixer.recovery_handoff.v1", '
        '"target": {"session": "...", "plan": "...", "occurrence": "..."}, '
        '"evidence": {"pack": "...", "sol_stage1": "...", "swarm_index": "...", '
        '"sol_stage2": "..."}, '
        '"root_cause": "adjudicated root cause", '
        '"tier1": {"action": "shortest safe path to durable movement (agent-actionable now)"}, '
        '"tier2": {"action": "deepest complete solution for the failure category"}, '
        '"confidence": "high|medium|low", '
        '"flash_overrides": ["..."], '
        '"evidence_paths": ["..."]}' + "\n\n"
        "EVIDENCE PACK:\n" + evidence_pack
        + "\n\nSOL STAGE 1 SCOPE:\n"
        + sol1_text
        + "\n\nSWARM INDEX:\n"
        + json.dumps(swarm_index, indent=2, sort_keys=True)
    )
    sol2_path = run_dir / "stage3-sol-adjudication.txt"
    if os.environ.get("ARNOLD_BABYSITTER_DRY_SOL") == "1":
        _write_text(
            sol2_path,
            json.dumps(
                {
                    "schema": RECOVERY_HANDOFF_SCHEMA,
                    "target": {"session": session, "plan": "", "occurrence": ""},
                    "evidence": {
                        "pack": "evidence-pack.json",
                        "sol_stage1": "stage1-sol-scope.txt",
                        "swarm_index": "stage2-swarm/_report.json",
                        "sol_stage2": "stage3-sol-adjudication.txt",
                    },
                    "root_cause": "dry-run",
                    "tier1": {"action": "no-op (dry-run)"},
                    "tier2": {"action": "no-op (dry-run)"},
                    "confidence": "low",
                    "flash_overrides": [],
                    "evidence_paths": [],
                }
            ),
        )
    else:
        _run_codex(
            prompt=prompt,
            out_path=sol2_path,
            codex_bin=codex_bin,
            sol_model=sol_model,
            timeout=codex_timeout,
            env=env,
        )
        _eprint(f"[babysitter] stage3 sol adjudication written {sol2_path}")
    handoff = _validate_handoff(
        _extract_json(sol2_path.read_text(encoding="utf-8", errors="replace"))
    )
    handoff_path = run_dir / "stage3-recovery_handoff.v1.json"
    _write_json(handoff_path, handoff)
    handoff_md = run_dir / "stage3-handoff.md"
    _write_text(
        handoff_md,
        "# Recovery handoff v1\n\n"
        f"handoff_id: {handoff['handoff_id']}\n\n"
        "```json\n"
        + json.dumps(handoff, indent=2, sort_keys=True)
        + "\n```\n",
    )
    _write_json(
        run_dir / "stage3.json",
        {
            "schema": "arnold.superfixer.sol_adjudication.v1",
            "run_id": run_id,
            "session": session,
            "handoff_id": handoff["handoff_id"],
            "handoff_path": str(handoff_path),
            "handoff_md_path": str(handoff_md),
            "recorded_at": _utcnow_iso(),
        },
    )
    return handoff


# ── Stage 4 — implement Horizon A and prove movement ─────────────────────────


def _chain_movement_evidence(workspace: Path, plan: str) -> dict[str, Any]:
    evidence: dict[str, Any] = {"workspace": str(workspace), "plan": plan}
    chains_root = workspace / ".megaplan" / "plans" / ".chains"
    if chains_root.is_dir():
        indices = []
        for path in sorted(chains_root.glob("chain-*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                continue
            indices.append(
                {
                    "path": str(path),
                    "current_milestone_index": payload.get("current_milestone_index"),
                    "last_state": payload.get("last_state"),
                    "current_plan_name": payload.get("current_plan_name"),
                }
            )
        evidence["chains"] = indices
    if plan:
        plan_dir = workspace / ".megaplan" / "plans" / plan
        # Content-addressed plan state: the canonical cursor for a standalone
        # local plan (run_kind=plan) is its own state.json, not a chain file.
        state_path = plan_dir / "state.json"
        if state_path.is_file():
            try:
                raw = state_path.read_bytes()
                evidence["plan_state_sha256"] = (
                    "sha256:" + hashlib.sha256(raw).hexdigest()
                )
                payload = json.loads(raw.decode("utf-8"))
                evidence["plan_current_state"] = payload.get("current_state")
                resume_cursor = payload.get("resume_cursor")
                if isinstance(resume_cursor, dict):
                    evidence["plan_resume_cursor"] = resume_cursor
            except (ValueError, OSError):
                pass
        # The plan's real event journal: events.ndjson plus the .events.seq
        # sidecar the EventWriter maintains under fcntl.flock.
        events_ndjson = plan_dir / "events.ndjson"
        if events_ndjson.is_file():
            try:
                evidence["plan_events_lines"] = sum(
                    1
                    for _ in events_ndjson.open(
                        "r", encoding="utf-8", errors="replace"
                    )
                )
            except OSError:
                pass
        events_seq = plan_dir / ".events.seq"
        if events_seq.is_file():
            try:
                evidence["plan_events_seq"] = int(
                    events_seq.read_text(encoding="utf-8").strip() or "0"
                )
            except (ValueError, OSError):
                pass
        # The incident ledger is the watchdog's real event journal for the
        # session; its sequence must also advance with any terminal event.
        ledger = workspace / ".megaplan" / "incident-ledger"
        ledger_jsonl = ledger / "events.jsonl"
        if ledger_jsonl.is_file():
            try:
                evidence["incident_ledger_lines"] = sum(
                    1
                    for _ in ledger_jsonl.open(
                        "r", encoding="utf-8", errors="replace"
                    )
                )
            except OSError:
                pass
        ledger_seq = ledger / ".events.seq"
        if ledger_seq.is_file():
            try:
                evidence["incident_ledger_seq"] = int(
                    ledger_seq.read_text(encoding="utf-8").strip() or "0"
                )
            except (ValueError, OSError):
                pass
    return evidence


def _advance_key(evidence: dict[str, Any]) -> tuple:
    """Run-kind-aware movement key for the Stage 4 proof.

    Chain runs advance via the chain milestone indices; standalone local
    plans (run_kind=plan) advance via the content-addressed plan state and
    the real event journals (plan events.ndjson/.events.seq and the
    incident ledger events.jsonl/.events.seq).  All components are
    monotonic, so a durable delta in any of them is legitimate movement.
    """
    chains = []
    for chain in evidence.get("chains") or []:
        index = chain.get("current_milestone_index")
        if isinstance(index, int):
            chains.append((index, str(chain.get("last_state") or "")))
    return (
        sorted(chains),
        int(evidence.get("plan_events_seq") or 0),
        int(evidence.get("plan_events_lines") or 0),
        int(evidence.get("incident_ledger_seq") or 0),
        int(evidence.get("incident_ledger_lines") or 0),
        str(evidence.get("plan_state_sha256") or ""),
    )


def stage4_implement(
    *,
    handoff: dict[str, Any],
    run_dir: Path,
    run_id: str,
    session: str,
    plan: str,
    workspace: str,
    fan_bin: Path,
    model: str,
    workers: int,
    max_tokens: int,
    task_timeout: int,
    env: dict[str, str],
) -> dict[str, Any]:
    before = _chain_movement_evidence(Path(workspace), plan)
    briefs_dir = run_dir / "stage4-briefs"
    briefs_dir.mkdir(parents=True, exist_ok=True)
    _write_text(
        briefs_dir / "implementer.md",
        "# Horizon A implementer\n\n"
        f"Session: {session}\nRun id: {run_id}\n\n"
        "You are the DeepSeek implementer executing ONLY the canonical "
        "immediate repair from the content-addressed recovery handoff below. "
        "Load and validate the handoff envelope; make the smallest source-level "
        "repair in the approved editable runtime; run the focused regression; "
        "inspect the real result; and iterate (bounded, with an evidence delta "
        "after every failed attempt) until the preserved occurrence advances. "
        "Escalate back to Sol after three distinct verified fix attempts. "
        "agent_actionable: false is reserved for a genuinely external gate. "
        "Never weaken a guard, fabricate output, or accept a PID/commit/self-"
        "report as recovery.  Prove the canonical milestone/cursor moved.\n\n"
        "RECOVERY HANDOFF (validate + consume):\n"
        + json.dumps(handoff, indent=2, sort_keys=True)
        + "\n\nHandoff file: "
        + str(run_dir / "stage3-recovery_handoff.v1.json"),
    )
    out_dir = run_dir / "stage4-implementer"
    cmd = [
        sys.executable,
        str(fan_bin),
        str(briefs_dir / "implementer.md"),
        "--output-dir",
        str(out_dir),
        "--max-workers",
        str(workers),
        "--model",
        model,
        "--toolsets",
        "file,web,terminal",
        "--max-tokens",
        str(max_tokens),
        "--task-timeout",
        str(task_timeout),
        "--project-dir",
        workspace,
    ]
    _eprint(f"[babysitter] stage4 implementer launched")
    proc = subprocess.run(cmd, text=True, capture_output=True, env=env, check=False)
    if proc.returncode != 0:
        raise RuntimeError(
            f"stage4 implementer failed rc={proc.returncode} stderr={proc.stderr[-2000:]}"
        )
    after = _chain_movement_evidence(Path(workspace), plan)

    before_key, after_key = _advance_key(before), _advance_key(after)
    proven = after_key > before_key
    proof = {
        "schema": "arnold.superfixer.stage4_proof.v1",
        "run_id": run_id,
        "session": session,
        "movement_proven": proven,
        "before": before,
        "after": after,
        "implementer_report_path": str(out_dir / "_report.json"),
        "recorded_at": _utcnow_iso(),
    }
    _write_json(run_dir / "stage4-proof.json", proof)
    return proof


# ── Orchestration ────────────────────────────────────────────────────────────


def _build_evidence_pack(
    *,
    goal_file: Path,
    session: str,
    workspace: str,
    plan: str,
    run_kind: str,
    occurrence: str,
    remote_spec: str,
) -> str:
    goal_text = ""
    try:
        goal_text = goal_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        pass
    return (
        f"SESSION: {session}\nWORKSPACE: {workspace}\nPLAN: {plan}\n"
        f"RUN_KIND: {run_kind}\nOCCURRENCE: {occurrence}\nREMOTE_SPEC: {remote_spec}\n\n"
        "GOAL (rendered by the watchdog):\n" + goal_text
    )


def run_orchestrator(
    *,
    goal_file: Path,
    session: str,
    workspace: str,
    plan: str,
    run_kind: str,
    occurrence: str,
    remote_spec: str,
    run_id: str,
    run_root: Path,
    mode: str,
) -> int:
    env = dict(os.environ)
    repo_root = str(_REPO_ROOT)
    env["PYTHONPATH"] = repo_root + (":" + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    codex_bin = os.environ.get("ARNOLD_BABYSITTER_CODEX_BIN", "codex")
    sol_model = os.environ.get("ARNOLD_BABYSITTER_SOL_MODEL", "gpt-5.6-sol")
    fan_bin = Path(
        os.environ.get("ARNOLD_BABYSITTER_FAN_BIN") or _default_fan_bin()
    ).resolve()
    model = os.environ.get("ARNOLD_BABYSITTER_MODEL", "deepseek:deepseek-v4-flash")
    implementer_model = os.environ.get("ARNOLD_BABYSITTER_IMPLEMENTER_MODEL", model)
    workers = int(os.environ.get("ARNOLD_BABYSITTER_WORKERS", "5"))
    max_tokens = int(os.environ.get("ARNOLD_BABYSITTER_MAX_TOKENS", "65536"))
    task_timeout = int(os.environ.get("ARNOLD_BABYSITTER_TASK_TIMEOUT", "1800"))
    codex_timeout = int(os.environ.get("ARNOLD_BABYSITTER_CODEX_TIMEOUT", "1800"))

    _write_json(
        run_root / "started.json",
        {
            "schema": "arnold.superfixer.started.v1",
            "run_id": run_id,
            "session": session,
            "plan": plan,
            "mode": mode,
            "goal_file": str(goal_file),
            "started_at": _utcnow_iso(),
        },
    )
    evidence_pack = _build_evidence_pack(
        goal_file=goal_file,
        session=session,
        workspace=workspace,
        plan=plan,
        run_kind=run_kind,
        occurrence=occurrence,
        remote_spec=remote_spec,
    )
    _write_text(run_root / "evidence-pack.txt", evidence_pack)

    try:
        questions = stage1_sol_scope(
            evidence_pack=evidence_pack,
            run_dir=run_root,
            run_id=run_id,
            session=session,
            codex_bin=codex_bin,
            sol_model=sol_model,
            codex_timeout=codex_timeout,
            env=env,
        )
        _write_json(
            run_root / "stage1.receipt.json",
            _stage_receipt("stage1_sol_scope", status="ok", run_id=run_id, session=session),
        )
        swarm_report = stage2_flash_swarm(
            questions=questions,
            run_dir=run_root,
            run_id=run_id,
            session=session,
            workspace=workspace,
            fan_bin=fan_bin,
            model=model,
            workers=workers,
            max_tokens=max_tokens,
            task_timeout=task_timeout,
            env=env,
        )
        _write_json(
            run_root / "stage2.receipt.json",
            _stage_receipt("stage2_flash_swarm", status="ok", run_id=run_id, session=session),
        )
        handoff = stage3_sol_adjudicate(
            evidence_pack=evidence_pack,
            sol1_text=(run_root / "stage1-sol-scope.txt").read_text(
                encoding="utf-8", errors="replace"
            ),
            swarm_report=swarm_report,
            run_dir=run_root,
            run_id=run_id,
            session=session,
            codex_bin=codex_bin,
            sol_model=sol_model,
            codex_timeout=codex_timeout,
            env=env,
        )
        _write_json(
            run_root / "stage3.receipt.json",
            _stage_receipt("stage3_sol_adjudicate", status="ok", run_id=run_id, session=session),
        )
        proof = stage4_implement(
            handoff=handoff,
            run_dir=run_root,
            run_id=run_id,
            session=session,
            plan=plan,
            workspace=workspace,
            fan_bin=fan_bin,
            model=implementer_model,
            workers=workers,
            max_tokens=max_tokens,
            task_timeout=task_timeout,
            env=env,
        )
        final = {
            "schema": FINAL_RECEIPT_SCHEMA,
            "run_id": run_id,
            "session": session,
            "plan": plan,
            "mode": mode,
            "status": "movement_proven" if proof.get("movement_proven") else "movement_unproven",
            "handoff_id": handoff.get("handoff_id", ""),
            "stages": ["stage1_sol_scope", "stage2_flash_swarm", "stage3_sol_adjudicate", "stage4_implement"],
            "recorded_at": _utcnow_iso(),
        }
        _write_json(run_root / "final-receipt.json", final)
        _eprint(f"[babysitter] run {run_id} complete status={final['status']}")
        return 0
    except Exception as exc:  # noqa: BLE001 - the babysitter fails closed with a typed receipt
        _write_json(
            run_root / "final-receipt.json",
            {
                "schema": FINAL_RECEIPT_SCHEMA,
                "run_id": run_id,
                "session": session,
                "plan": plan,
                "mode": mode,
                "status": "failed",
                "error": str(exc),
                "stages": [],
                "recorded_at": _utcnow_iso(),
            },
        )
        _eprint(f"[babysitter] run {run_id} failed: {exc}")
        return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--goal-file", required=True)
    parser.add_argument("--session", required=True)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--plan", default="")
    parser.add_argument("--run-kind", default="")
    parser.add_argument("--occurrence", default="")
    parser.add_argument("--remote-spec", default="")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--mode", default="superfixer", choices=("superfixer", "layered", "off"))
    args = parser.parse_args(argv)
    return run_orchestrator(
        goal_file=Path(args.goal_file),
        session=args.session,
        workspace=args.workspace,
        plan=args.plan,
        run_kind=args.run_kind,
        occurrence=args.occurrence,
        remote_spec=args.remote_spec,
        run_id=args.run_id,
        run_root=Path(args.run_root),
        mode=args.mode,
    )


if __name__ == "__main__":
    raise SystemExit(main())
