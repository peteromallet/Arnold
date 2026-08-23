#!/usr/bin/env python3
"""T7.4 evidence-bound historical-OOM exception comparator.

The existing J4 structural-volatility comparator remains authoritative and is
always run before this helper considers the one JUDG-OOM exception.  This file
is intentionally standalone so it can be frozen under a content-addressed run
path without importing mutable project code.
"""

import argparse
import copy
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

from typing import Any, NoReturn

RULE_RECEIPT_SHA256 = "ccbd2e8f3669b1ff7371ff0fbdeca074eca523fafb548d4bab884305d2af9289"
RULE_RECEIPT_NAME = "mrc-ed48627a7fda489e96a16d449d3067b942b42eef99bf1196.stdout"
RUN_ID = "t74-20260823T040812Z-3347570"
CONTAINER_ID = "45404872d432f0cd6a7d148a4b8b31096f033a0048f4dc328094a080402c33e2"
STARTED_AT = "2026-08-17T14:31:15.428579551Z"
DEATHS = (
    ("2026-08-23 05:03:25", "snapshot_attempt_050325_exit_137"),
    ("2026-08-23 05:18:01", "snapshot_attempt_051801_exit_137"),
)
PRIOR_HELPER_SHA256 = {
    "t74-j4-normalize-v2.py": "61436679398bea42a4ac9d2071ff308554314cf5a88994840ed7711a50b5f9a6",
    "t74-sva-compare-v2.py": "a4d3cac51c8a4c92caba082ba826d0d0cedc8c59abfa68d4cd8a6e5778cf67d3",
    "t74-sva-fixtures.py": "cd039a7eec160fdefb236470e9bc645a6f32c6375abf3c480b18d18c4c58261d",
}
COMMON_EVIDENCE = {
    "preserved_host_oom_records",
    "snapshot_attempt_050325_exit_137",
    "snapshot_attempt_051801_exit_137",
    "s8_snapshot_oom_diagnosis",
    "s8fix_oomkilled_evidence",
    "streaming_helper",
    "streaming_differential_equality_proof",
    "streaming_bounded_rss_proof",
    "s8_memory_events",
    "s8_host_kernel_oom_log",
}
S13_EVIDENCE = {"s13_memory_events", "s13_host_kernel_oom_log"}
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")

RULE_TEXT = """**T7.4 documented OOM-history exception**

For T7.4 S8 and S13 comparisons only, retain the existing J4 structural-volatility rule unchanged except for the following evidence-bound exception:

1. Run the existing comparator first. The exception is eligible only when its sole remaining difference is:
   - canonical T0.0: `State.OOMKilled=false`; and
   - immediate pre-canary and post-rollback: `State.OOMKilled=true`.
   Every other inspect field must satisfy the existing exact comparison, including all other members of `State`.
2. The `true` value must be bound to the current container epoch: the exact container ID and `StartedAt=2026-08-17T14:31:15.428579551Z`. The exception expires on any restart, recreation, container-ID change, or `StartedAt` change.
3. The accepted history is exactly the two T7.4 snapshot-helper deaths at host times `2026-08-23 05:03:25` and `2026-08-23 05:18:01`. Acceptance requires digest-bound references to:
   - the preserved host OOM records;
   - both `exit=137` snapshot-attempt artifacts;
   - `S8-snapshot-oom-diagnosis.md`;
   - `s8fix-oomkilled-evidence.txt`; and
   - the frozen streaming-helper digest and its differential-equality and bounded-RSS proofs.
4. Before resumed S8, capture an OOM occurrence fence for the target container cgroup:
   - the cgroup identity/path;
   - its `memory.events` `oom_kill` counter; and
   - the corresponding host-kernel OOM-log cursor or digest.
   The counter and kernel evidence must reconcile with exactly the two documented deaths. Missing, unreadable, inconsistent, or additional evidence fails closed.
5. At S13, require the same container epoch and an unchanged `oom_kill` counter, with no later target-cgroup OOM record. If target attribution is unavailable, any new host Memory-cgroup OOM after the S8 fence fails closed. A counter increment fails even though Docker’s already-true Boolean cannot change again.
6. Pre-to-post comparison remains exact: both sides must retain `State.OOMKilled=true`. `pre=false/post=true`, `pre=true/post=false`, any other `State` difference, or any additional protected-state difference fails.
7. Do not delete, normalize, or replace `State.OOMKilled` in raw or canonicalized evidence. A successful comparison must emit a distinct `accepted_historical_exception` record containing the rule receipt, evidence digests, container epoch, and S8/S13 OOM-fence values.
8. This exception does not authorize future OOM events and is not reusable for another container epoch, another run, or another cause. Any `State.OOMKilled=true` that cannot satisfy every condition above fails.
9. Preserve all earlier helpers, outputs, failed comparisons, and OOM artifacts byte-for-byte. Implement this rule under new content-addressed helper and output paths."""


def fail(message: str) -> NoReturn:
    raise SystemExit(f"t74-oom-exception-compare: FAIL: {message}")


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=False)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        fail(f"cannot read {path}: {exc}")
    return digest.hexdigest()


def require_object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        fail(f"{label} must be a JSON object")
    return value


def require_exact_keys(value: dict[str, Any], required: set[str] | dict[str, Any], label: str) -> None:
    actual = set(value)
    if actual != set(required):
        fail(
            f"{label} keys differ: missing={sorted(set(required) - actual)} "
            f"unexpected={sorted(actual - set(required))}"
        )


def load_json(path: Path, label: str) -> Any:
    try:
        with path.open(encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        fail(f"cannot load {label} {path}: {exc}")


def run_existing_comparator(comparator: Path, left: Path, right: Path) -> dict[str, Any]:
    try:
        process = subprocess.run(
            [sys.executable, str(comparator), str(left), str(right)],
            capture_output=True,
            check=False,
        )
    except OSError as exc:
        fail(f"cannot run existing comparator first: {exc}")
    return {
        "exit_code": process.returncode,
        "stdout": process.stdout,
        "stderr": process.stderr,
        "stdout_sha256": sha256_bytes(process.stdout),
        "stderr_sha256": sha256_bytes(process.stderr),
    }


def comparator_normal_form(document: Any, label: str) -> tuple[dict[str, Any], Counter[str]]:
    document = require_object(document, label)
    if "ExecIDs" in document:
        fail(f"{label} still contains ExecIDs; existing stage-A contract not met")
    if "Mounts" not in document or not isinstance(document["Mounts"], list):
        fail(f"{label}.Mounts is missing or is not an array")
    serialized = []
    for index, mount in enumerate(document["Mounts"]):
        if not isinstance(mount, dict):
            fail(f"{label}.Mounts[{index}] is not an object")
        serialized.append(canonical_json(mount))
    normalized = copy.deepcopy(document)
    normalized["Mounts"] = sorted(normalized["Mounts"], key=canonical_json)
    return normalized, Counter(serialized)


def require_sole_oom_delta(canonical: Any, candidate: Any, candidate_label: str) -> None:
    canonical_form, canonical_mounts = comparator_normal_form(canonical, "canonical")
    candidate_form, candidate_mounts = comparator_normal_form(candidate, candidate_label)
    if canonical_mounts != candidate_mounts:
        fail("existing comparator difference is not solely State.OOMKilled: Mounts differ")
    canonical_state = require_object(canonical_form.get("State"), "canonical.State")
    candidate_state = require_object(candidate_form.get("State"), f"{candidate_label}.State")
    if "OOMKilled" not in canonical_state or "OOMKilled" not in candidate_state:
        fail("State.OOMKilled must remain present on both sides")
    if canonical_state["OOMKilled"] is not False:
        fail("canonical T0.0 State.OOMKilled must be the Boolean false")
    if candidate_state["OOMKilled"] is not True:
        fail(f"{candidate_label} State.OOMKilled must be the Boolean true")
    candidate_state["OOMKilled"] = False
    if canonical_json(canonical_form) != canonical_json(candidate_form):
        fail("existing comparator has a protected difference in addition to State.OOMKilled")


def require_epoch(document: Any, label: str, expected_oom: bool) -> None:
    document = require_object(document, label)
    state = require_object(document.get("State"), f"{label}.State")
    if document.get("Id") != CONTAINER_ID:
        fail(f"{label} is not the authorized container ID")
    if state.get("StartedAt") != STARTED_AT:
        fail(f"{label} is not the authorized StartedAt epoch")
    if state.get("OOMKilled") is not expected_oom:
        fail(f"{label}.State.OOMKilled is not {str(expected_oom).lower()}")


def validate_digest_record(record: Any, label: str, expected_sha256: str | None = None) -> tuple[Path, str]:
    record = require_object(record, label)
    require_exact_keys(record, {"path", "sha256"}, label)
    path_value = record.get("path")
    claimed = record.get("sha256")
    if not isinstance(path_value, str) or not path_value:
        fail(f"{label}.path must be non-empty")
    if not isinstance(claimed, str) or SHA256_RE.fullmatch(claimed) is None:
        fail(f"{label}.sha256 must be a lowercase SHA-256 digest")
    path = Path(path_value).expanduser().resolve(strict=False)
    actual = sha256_file(path)
    if actual != claimed:
        fail(f"{label} digest mismatch: claimed={claimed} actual={actual}")
    if expected_sha256 is not None and actual != expected_sha256:
        fail(f"{label} is not the frozen artifact: expected={expected_sha256} actual={actual}")
    return path, actual


def read_required_bytes(path: Path, label: str) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        fail(f"cannot read {label} {path}: {exc}")


def require_markers(path: Path, label: str, markers: list[str]) -> None:
    payload = read_required_bytes(path, label)
    for marker in markers:
        encoded = marker.encode("utf-8")
        if payload.count(encoded) != 1:
            fail(f"{label} must contain exactly one occurrence of {marker!r}")


def require_present_markers(path: Path, label: str, markers: list[str]) -> None:
    payload = read_required_bytes(path, label)
    for marker in markers:
        if marker.encode("utf-8") not in payload:
            fail(f"{label} does not contain required marker {marker!r}")


def memory_events_oom_kill(path: Path, label: str) -> int:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        fail(f"cannot read {label} {path}: {exc}")
    values = []
    for line in lines:
        fields = line.split()
        if len(fields) == 2 and fields[0] == "oom_kill":
            try:
                values.append(int(fields[1]))
            except ValueError:
                fail(f"{label} oom_kill value is not an integer")
    if len(values) != 1 or values[0] < 0:
        fail(f"{label} must contain exactly one non-negative oom_kill counter")
    return values[0]


def validate_prior_helpers(attestation, comparator):
    records = require_object(attestation.get("prior_helpers"), "attestation.prior_helpers")
    require_exact_keys(records, PRIOR_HELPER_SHA256, "attestation.prior_helpers")
    resolved = {}
    for name, expected in PRIOR_HELPER_SHA256.items():
        path, digest = validate_digest_record(records[name], f"prior_helpers.{name}", expected)
        if path.name != name:
            fail(f"prior_helpers.{name} path does not preserve the helper name")
        resolved[name] = {"path": str(path), "sha256": digest}
    if Path(resolved["t74-sva-compare-v2.py"]["path"]) != comparator:
        fail("--existing-comparator is not the frozen t74-sva-compare-v2.py")
    return resolved


def validate_evidence(attestation, phase):
    records = require_object(attestation.get("evidence"), "attestation.evidence")
    required = COMMON_EVIDENCE | (S13_EVIDENCE if phase == "S13" else set())
    require_exact_keys(records, required, "attestation.evidence")
    resolved = {}
    for name in sorted(required):
        path, digest = validate_digest_record(records[name], f"evidence.{name}")
        resolved[name] = {"path": str(path), "sha256": digest}

    death_markers = [timestamp for timestamp, _ in DEATHS]
    require_markers(
        Path(resolved["preserved_host_oom_records"]["path"]),
        "preserved host OOM records",
        death_markers,
    )
    require_markers(
        Path(resolved["s8fix_oomkilled_evidence"]["path"]),
        "s8fix-oomkilled-evidence.txt",
        death_markers + [STARTED_AT, '"OOMKilled": true'],
    )
    require_present_markers(
        Path(resolved["s8_snapshot_oom_diagnosis"]["path"]),
        "S8-snapshot-oom-diagnosis.md",
        ["Memory cgroup out of memory", "exit code **137**"],
    )
    for _, evidence_key in DEATHS:
        exit_payload = read_required_bytes(Path(resolved[evidence_key]["path"]), evidence_key)
        if exit_payload.strip() != b"137":
            fail(f"{evidence_key} must contain only exit code 137")
    return resolved


def validate_deaths(attestation):
    expected = [
        {"host_time": timestamp, "exit_code": 137, "evidence": evidence_key}
        for timestamp, evidence_key in DEATHS
    ]
    if attestation.get("deaths") != expected:
        fail("attestation.deaths is not the exact ordered pair of documented exit=137 deaths")


def validate_s8_fence(attestation, evidence):
    fence = require_object(attestation.get("s8_fence"), "attestation.s8_fence")
    keys = {
        "cgroup_identity",
        "cgroup_path",
        "oom_kill_counter",
        "memory_events_evidence",
        "host_kernel_oom_log_evidence",
        "host_kernel_oom_log_cursor",
        "host_kernel_oom_log_sha256",
    }
    require_exact_keys(fence, keys, "attestation.s8_fence")
    identity = fence.get("cgroup_identity")
    cgroup_path = fence.get("cgroup_path")
    if not isinstance(identity, str) or not identity:
        fail("s8_fence.cgroup_identity must be non-empty")
    if not isinstance(cgroup_path, str) or not cgroup_path.startswith("/"):
        fail("s8_fence.cgroup_path must be an absolute cgroup path")
    if CONTAINER_ID not in f"{identity} {cgroup_path}":
        fail("S8 cgroup identity/path is not bound to the authorized container ID")
    if fence.get("memory_events_evidence") != "s8_memory_events":
        fail("S8 fence is not bound to the s8_memory_events digest")
    if fence.get("host_kernel_oom_log_evidence") != "s8_host_kernel_oom_log":
        fail("S8 fence is not bound to the s8_host_kernel_oom_log digest")
    host_digest = evidence["s8_host_kernel_oom_log"]["sha256"]
    cursor = fence.get("host_kernel_oom_log_cursor")
    if not isinstance(cursor, str):
        fail("s8_fence.host_kernel_oom_log_cursor must be a string")
    if fence.get("host_kernel_oom_log_sha256") != host_digest:
        fail("S8 host-kernel OOM-log digest does not match its evidence record")
    observed_counter = memory_events_oom_kill(
        Path(evidence["s8_memory_events"]["path"]), "S8 memory.events"
    )
    if fence.get("oom_kill_counter") != 2 or observed_counter != 2:
        fail("S8 oom_kill counter must reconcile with exactly the two documented deaths")
    require_markers(
        Path(evidence["s8_host_kernel_oom_log"]["path"]),
        "S8 host-kernel OOM log",
        [timestamp for timestamp, _ in DEATHS],
    )
    return copy.deepcopy(fence)


def validate_s13_fence(attestation, evidence, s8_fence):
    fence = require_object(attestation.get("s13_fence"), "attestation.s13_fence")
    keys = {
        "cgroup_identity",
        "cgroup_path",
        "oom_kill_counter",
        "memory_events_evidence",
        "host_kernel_oom_log_evidence",
        "host_kernel_oom_log_cursor",
        "host_kernel_oom_log_sha256",
        "target_attribution_available",
        "later_target_cgroup_oom_records",
        "new_host_memory_cgroup_oom_records_after_s8",
    }
    require_exact_keys(fence, keys, "attestation.s13_fence")
    if fence.get("cgroup_identity") != s8_fence["cgroup_identity"]:
        fail("S13 cgroup identity differs from the S8 fence")
    if fence.get("cgroup_path") != s8_fence["cgroup_path"]:
        fail("S13 cgroup path differs from the S8 fence")
    if fence.get("memory_events_evidence") != "s13_memory_events":
        fail("S13 fence is not bound to the s13_memory_events digest")
    if fence.get("host_kernel_oom_log_evidence") != "s13_host_kernel_oom_log":
        fail("S13 fence is not bound to the s13_host_kernel_oom_log digest")
    host_digest = evidence["s13_host_kernel_oom_log"]["sha256"]
    if fence.get("host_kernel_oom_log_sha256") != host_digest:
        fail("S13 host-kernel OOM-log digest does not match its evidence record")
    if not isinstance(fence.get("host_kernel_oom_log_cursor"), str):
        fail("s13_fence.host_kernel_oom_log_cursor must be a string")
    observed_counter = memory_events_oom_kill(
        Path(evidence["s13_memory_events"]["path"]), "S13 memory.events"
    )
    if (
        fence.get("oom_kill_counter") != s8_fence["oom_kill_counter"]
        or observed_counter != s8_fence["oom_kill_counter"]
    ):
        fail("S13 oom_kill counter changed after the S8 fence")
    attribution = fence.get("target_attribution_available")
    if not isinstance(attribution, bool):
        fail("s13_fence.target_attribution_available must be Boolean")
    later_target = fence.get("later_target_cgroup_oom_records")
    later_host = fence.get("new_host_memory_cgroup_oom_records_after_s8")
    if not isinstance(later_target, list) or later_target:
        fail("a later target-cgroup OOM record is present or unreadable")
    if not isinstance(later_host, list):
        fail("new host Memory-cgroup OOM records must be an array")
    if not attribution and later_host:
        fail("target attribution is unavailable and a new host Memory-cgroup OOM exists")
    return copy.deepcopy(fence)


def validate_attestation(attestation, phase, comparator):
    attestation = require_object(attestation, "attestation")
    keys = {
        "schema",
        "run_id",
        "rule_receipt",
        "prior_helpers",
        "evidence",
        "container_epoch",
        "deaths",
        "s8_fence",
    }
    if phase == "S13":
        keys.add("s13_fence")
    require_exact_keys(attestation, keys, "attestation")
    if attestation.get("schema") != "arnold.t7.4.oom_history_attestation.v1":
        fail("attestation schema is not arnold.t7.4.oom_history_attestation.v1")
    if attestation.get("run_id") != RUN_ID:
        fail("historical exception is not reusable for another run")
    rule_path, rule_digest = validate_digest_record(
        attestation.get("rule_receipt"), "attestation.rule_receipt", RULE_RECEIPT_SHA256
    )
    if rule_path.name != RULE_RECEIPT_NAME:
        fail("rule receipt path does not name the frozen JUDG-OOM receipt")
    prior_helpers = validate_prior_helpers(attestation, comparator)
    evidence = validate_evidence(attestation, phase)
    epoch = require_object(attestation.get("container_epoch"), "attestation.container_epoch")
    require_exact_keys(epoch, {"container_id", "started_at"}, "attestation.container_epoch")
    if epoch != {"container_id": CONTAINER_ID, "started_at": STARTED_AT}:
        fail("attested container epoch is not the one authorized by JUDG-OOM")
    validate_deaths(attestation)
    s8_fence = validate_s8_fence(attestation, evidence)
    s13_fence = None
    if phase == "S13":
        s13_fence = validate_s13_fence(attestation, evidence, s8_fence)
    return {
        "rule_receipt": {"path": str(rule_path), "sha256": rule_digest},
        "prior_helpers": prior_helpers,
        "evidence": evidence,
        "container_epoch": copy.deepcopy(epoch),
        "s8_fence": s8_fence,
        "s13_fence": s13_fence,
    }


def helper_digest_and_address():
    helper_path = Path(__file__).resolve(strict=True)
    digest = sha256_file(helper_path)
    expected_parent = f"t74-oom-exception-{digest}"
    if helper_path.parent.name != expected_parent:
        fail(
            "helper is not running from its content-addressed path: "
            f"expected parent {expected_parent!r}"
        )
    return helper_path, digest


def write_record(path, record):
    payload = (json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError:
        fail(f"refusing to overwrite output {path}")
    except OSError as exc:
        fail(f"cannot write output {path}: {exc}")


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", required=True, choices=("S8", "S13"))
    parser.add_argument("--existing-comparator", required=True, type=Path)
    parser.add_argument("--canonical", required=True, type=Path)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--pre", type=Path)
    parser.add_argument("--attestation", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.phase == "S13" and args.pre is None:
        parser.error("--pre is required for S13")
    if args.phase == "S8" and args.pre is not None:
        parser.error("--pre is only valid for S13")
    return args


def main():
    args = parse_args()
    comparator = args.existing_comparator.expanduser().resolve(strict=False)
    canonical_path = args.canonical.expanduser().resolve(strict=False)
    candidate_path = args.candidate.expanduser().resolve(strict=False)
    output_path = args.output.expanduser().resolve(strict=False)
    helper_path, helper_digest = helper_digest_and_address()

    # JUDG-OOM clause 1: this launch is deliberately the first comparison act.
    first = run_existing_comparator(comparator, canonical_path, candidate_path)
    if first["exit_code"] == 0:
        write_record(
            output_path,
            {
                "schema": "arnold.t7.4.comparison_result.v1",
                "record_type": "exact_comparison",
                "phase": args.phase,
                "helper": {"path": str(helper_path), "sha256": helper_digest},
                "existing_comparator": {
                    "path": str(comparator),
                    "exit_code": 0,
                    "stdout_sha256": first["stdout_sha256"],
                    "stderr_sha256": first["stderr_sha256"],
                },
            },
        )
        print("T74-OOM-COMPARE OK exact_comparison")
        return

    canonical = load_json(canonical_path, "canonical record")
    candidate = load_json(candidate_path, "candidate record")
    candidate_label = "immediate-pre-canary" if args.phase == "S8" else "post-rollback"
    require_sole_oom_delta(canonical, candidate, candidate_label)
    require_epoch(canonical, "canonical", False)
    require_epoch(candidate, candidate_label, True)

    attestation_path = args.attestation.expanduser().resolve(strict=False)
    validated = validate_attestation(
        load_json(attestation_path, "OOM-history attestation"), phase=args.phase, comparator=comparator
    )

    pre_path = None
    pre_to_post = None
    if args.phase == "S13":
        pre_path = args.pre.expanduser().resolve(strict=False)
        pre = load_json(pre_path, "immediate pre-canary record")
        require_epoch(pre, "immediate-pre-canary", True)
        pre_to_post = run_existing_comparator(comparator, pre_path, candidate_path)
        if pre_to_post["exit_code"] != 0:
            fail("pre-to-post existing-comparator check is not exact")

    input_digests = {
        "canonical": {"path": str(canonical_path), "sha256": sha256_file(canonical_path)},
        "candidate": {"path": str(candidate_path), "sha256": sha256_file(candidate_path)},
    }
    if pre_path is not None:
        input_digests["pre"] = {"path": str(pre_path), "sha256": sha256_file(pre_path)}
    record = {
        "schema": "arnold.t7.4.accepted_historical_exception.v1",
        "record_type": "accepted_historical_exception",
        "phase": args.phase,
        "run_id": RUN_ID,
        "rule_receipt": validated["rule_receipt"],
        "helper": {"path": str(helper_path), "sha256": helper_digest},
        "existing_comparator": {
            "path": str(comparator),
            "sha256": validated["prior_helpers"]["t74-sva-compare-v2.py"]["sha256"],
            "first_exit_code": first["exit_code"],
            "first_stdout_sha256": first["stdout_sha256"],
            "first_stderr_sha256": first["stderr_sha256"],
        },
        "inputs": input_digests,
        "evidence_digests": {
            name: item["sha256"] for name, item in sorted(validated["evidence"].items())
        },
        "container_epoch": validated["container_epoch"],
        "s8_oom_fence": validated["s8_fence"],
        "s13_oom_fence": validated["s13_fence"],
    }
    if pre_to_post is not None:
        record["pre_to_post_comparator"] = {
            "exit_code": pre_to_post["exit_code"],
            "stdout_sha256": pre_to_post["stdout_sha256"],
            "stderr_sha256": pre_to_post["stderr_sha256"],
        }
    write_record(output_path, record)
    print("T74-OOM-COMPARE OK accepted_historical_exception")


if __name__ == "__main__":
    main()
