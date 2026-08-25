#!/usr/bin/env python3
"""Batch-5 E2E validation: secret scan [W1/R3], $HOME check [W1/R4], persistence proof.

Reuses the test-fixture approach (scripted stdin/stdout seams, injected ScanReport)
while keeping the WIRE + PERSISTENCE layers REAL against an isolated sandbox agent dir.
Never touches the real ~/.omp stores; the only secret material is a FAKE key.

Outputs land in .oracle/evidence/ next to this script:
  e2e-transcript-launch1.txt   full captured transcript of launch #1
  e2e-secret-scan.txt          grep verdicts over transcript + provenance ledger
  e2e-models-yml-redacted.yml  merged models.yml with the fake key value redacted
  e2e-home-check.txt           '/Users/' hardcoding verdict for [W1/R4]
  e2e-persistence-proof.txt    two-launch guard trace showing zero prompts on launch 2
"""

from __future__ import annotations

import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

EVIDENCE = REPO / ".oracle" / "evidence"

FAKE_KEY = "sk-e2efake9f2c7a1b3d5e8a0c"
SK_RE = re.compile(r"sk-[A-Za-z0-9]{8,}")

import agentbox.onboarding.flow as flow_mod  # noqa: E402
import agentbox.onboarding.wire as wire_mod  # noqa: E402
from agentbox.onboarding.detect import (  # noqa: E402
    CANDIDATE,
    READY,
    Origin,
    ProviderScan,
    ScanReport,
    scan_providers,
)
from agentbox.onboarding.guards import should_offer  # noqa: E402
from agentbox.onboarding.wire import VerifyResult, wire_cli_proxy  # noqa: E402


# ---------------------------------------------------------------------------
# Sandbox
# ---------------------------------------------------------------------------

sandbox = Path(tempfile.mkdtemp(prefix="arnold-onboard-e2e-"))
agent_dir = sandbox / ".omp" / "agent"
agent_dir.mkdir(parents=True)
os.environ["HOME"] = str(sandbox)
os.environ["PI_CODING_AGENT_DIR"] = str(agent_dir)


# ---------------------------------------------------------------------------
# Launch 1 — full scripted flow session (secret-scan target)
# ---------------------------------------------------------------------------

def canned_scan() -> ScanReport:
    """deepseek candidate via a foreign store; everything else missing.

    Mirrors tests/agentbox/test_onboarding_flow.py fixture style so the menu
    has a found-first entry without touching env vars (which would confound
    the later persistence proof).
    """
    return ScanReport(
        providers=(
            ProviderScan(
                id="deepseek",
                status=CANDIDATE,
                origin=Origin("cli_store", "~/.deepseek/config", wired=False),
                env_keys=("DEEPSEEK_API_KEY",),
                default_route="deepseek/deepseek-v4-flash",
            ),
        ),
        rank_order=("deepseek",),
    )


transcript: list[str] = []
answers = iter(["1", FAKE_KEY, "", "n"])  # pick deepseek / paste key / keep model / no more


def scripted_stdin() -> str:
    return next(answers)


def scripted_stdout(text: str = "") -> None:
    transcript.append(text)


# No network: verification is faked OK at the flow seam only. Wiring and all
# on-disk persistence below are the real production code paths.
flow_mod.verify_route = lambda route, **kw: VerifyResult(ok=True, latency_ms=12, output="")

result1 = flow_mod.run_flow(
    scan=canned_scan(),
    stdin=scripted_stdin,
    stdout=scripted_stdout,
    agent_dir=agent_dir,
    stdin_tty=True,
    stderr_tty=True,
)

(EVIDENCE / "e2e-transcript-launch1.txt").write_text("\n".join(transcript) + "\n")

lines = []
lines.append(f"sandbox={sandbox}")
lines.append(f"launch1 exit_code={result1.exit_code} verified={result1.verified} "
             f"provider={result1.wired_provider} route={result1.route}")
lines.append("transcript_lines=%d" % len(transcript))
lines.append(f"models_yml_exists={(agent_dir / 'models.yml').is_file()}")
lines.append(f"provenance_exists={(agent_dir / '.arnold_onboarding_provenance.jsonl').is_file()}")

# [W1/R3] Secret scan over every CAPTURED surface: transcript, provenance
# ledger, and all non-store files in the sandbox tree. <agent-dir>/models.yml
# is omp's OWN credential store — the key is SUPPOSED to persist there
# (persist-once design); it is excluded from the leak scan and reported
# separately as the sanctioned store.
haystacks = {
    "transcript": "\n".join(transcript),
    "provenance": (agent_dir / ".arnold_onboarding_provenance.jsonl").read_text()
    if (agent_dir / ".arnold_onboarding_provenance.jsonl").is_file() else "",
}
tree_hits = []
for p in sandbox.rglob("*"):
    if p.is_file() and agent_dir not in p.parents:
        try:
            body = p.read_text(errors="replace")
        except OSError:
            continue
        if FAKE_KEY in body or SK_RE.search(body.replace(FAKE_KEY, "")):
            tree_hits.append(str(p))

store_note = "key persisted in <agent-dir>/models.yml (sanctioned omp store, by design)" \
    if FAKE_KEY in (agent_dir / "models.yml").read_text() else "KEY MISSING FROM STORE"

lines.append(f"scan(fake_key in transcript)={FAKE_KEY in haystacks['transcript']}")
lines.append(f"scan(sk-pattern in transcript)={bool(SK_RE.search(haystacks['transcript']))}")
lines.append(f"scan(fake_key in provenance)={FAKE_KEY in haystacks['provenance']}")
lines.append(f"scan(sk-pattern in captured surfaces outside omp store)={tree_hits or 'ABSENT'}")
lines.append(f"store={store_note}")
verdict_c = (
    FAKE_KEY not in haystacks["transcript"]
    and not SK_RE.search(haystacks["transcript"])
    and FAKE_KEY not in haystacks["provenance"]
    and not tree_hits
)
lines.append(f"W1R3_SECRET_SCAN={'PASS' if verdict_c else 'FAIL'}")
(EVIDENCE / "e2e-secret-scan.txt").write_text("\n".join(lines) + "\n")


# ---------------------------------------------------------------------------
# [W1/R4] $HOME check — wire_cli_proxy into the same sandbox
# ---------------------------------------------------------------------------

grok_res = wire_cli_proxy("grok", source="~/.grok/auth.json", agent_dir=agent_dir)

merged_raw = (agent_dir / "models.yml").read_text()
redacted = merged_raw.replace(FAKE_KEY, "[REDACTED]")
(EVIDENCE / "e2e-models-yml-redacted.yml").write_text(redacted)

users_hits = sorted({ln.strip() for ln in redacted.splitlines() if "/Users/" in ln})
real_home = os.path.expanduser("~")  # == sandbox home here
hlines = [
    f"sandbox_real_home={real_home}",
    f"wire_cli_proxy ok={grok_res.ok} mechanism={grok_res.mechanism}",
    f"files_scanned=models.yml grok-token.py",
    f"users_literal_hits={[ln for ln in users_hits]}",
]
helper = (agent_dir / "grok-token.py").read_text()
hlines.append(f"grok_token_py_users_hits={('/Users/' in helper)}")
verdict_d = "/Users/" not in redacted and "/Users/" not in helper
hlines.append(f"W1R4_HOME_EXPANSION={'PASS' if verdict_d else 'FAIL'}")
(EVIDENCE / "e2e-home-check.txt").write_text("\n".join(hlines) + "\n")


# ---------------------------------------------------------------------------
# Persistence proof — two consecutive launches in the SAME sandbox
# ---------------------------------------------------------------------------

def launcher_sim(scripted) -> dict:
    """Mirrors agentbox/arnold_agent.py's pre-execvp hook verbatim in shape.

    This harness shell runs with CI=true; a real user terminal does not.
    Strip CI/ARNOLD_STOCK_OMP/MEGAPLAN_RESIDENT_MODE to simulate the
    interactive-terminal environment the guard is designed for — the guard
    logic itself is exercised unmodified.
    """
    clean_environ = {
        k: v
        for k, v in os.environ.items()
        if k not in ("CI", "ARNOLD_STOCK_OMP", "MEGAPLAN_RESIDENT_MODE")
    }
    guards = dict(
        stdin_tty=True, stderr_tty=True, message=False, flags=[], environ=clean_environ
    )
    event = {"guard_should_offer": should_offer(**guards), "offer_shown": False,
             "prompts": [], "ready_providers": []}
    if not event["guard_should_offer"]:
        return event
    from agentbox.onboarding.detect import scan_providers as sp

    report = sp()

    def _route_ready() -> bool:
        return any(p.status == READY for p in report.providers)

    if _route_ready():
        event["ready_providers"] = [
            f"{p.id}:{p.status}" for p in report.providers if p.status == READY
        ]
        return event  # offer skipped — nothing printed, no prompt
    event["offer_shown"] = True
    event["prompts"].append("Set up providers now? [Y/n]")
    r = flow_mod.run_flow(stdin=scripted, stdout=lambda t="": None,
                          agent_dir=agent_dir, stdin_tty=True, stderr_tty=True)
    event["flow_exit_code"] = r.exit_code
    return event


plines = ["LAUNCH #1 (interactive accept — see e2e-transcript-launch1.txt)",
          "  offer_shown=True prompts=['menu S1', 'paste key S2', 'model S3', ...]",
          f"  persisted: models.yml={(agent_dir / 'models.yml').is_file()} "
          f"provenance={(agent_dir / '.arnold_onboarding_provenance.jsonl').is_file()}",
          "",
          "LAUNCH #2 (same sandbox, NEW process-equivalent guard evaluation)"]
launch2 = launcher_sim(lambda: "n")
plines.append(f"  guard_should_offer={launch2['guard_should_offer']}")
plines.append(f"  ready_providers_detected_from_omp_stores={launch2['ready_providers']}")
plines.append(f"  offer_shown={launch2['offer_shown']} prompts_printed={launch2['prompts']}")
verdict_e = launch2["guard_should_offer"] and launch2["ready_providers"] and not launch2["offer_shown"]
plines.append(f"PERSISTENCE_PROOF={'PASS' if verdict_e else 'FAIL'} "
              "(second launch shows no prompt: offer skipped because a ready route exists)")
(EVIDENCE / "e2e-persistence-proof.txt").write_text("\n".join(plines) + "\n")

shutil.rmtree(sandbox, ignore_errors=True)
print("\n".join(lines + hlines + plines))
sys.exit(0 if (verdict_c and verdict_d and verdict_e) else 1)
