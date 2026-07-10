from __future__ import annotations

import difflib
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal


RepairMode = Literal["mechanical", "semantic"]


@dataclass(frozen=True, slots=True)
class RepairFinding:
    code: str
    severity: str
    message: str
    line: int | None = None
    evidence: dict[str, object] = field(default_factory=dict)

    def to_json(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class RepairEdit:
    kind: str
    line: int
    original: str
    replacement: str
    rationale: str

    def to_json(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class RepairPacket:
    path: str
    marker: str
    mode: RepairMode
    findings: list[RepairFinding]
    edits: list[RepairEdit]
    diff: str

    def to_json(self) -> dict[str, object]:
        return {
            "path": self.path,
            "marker": self.marker,
            "mode": self.mode,
            "findings": [item.to_json() for item in self.findings],
            "edits": [item.to_json() for item in self.edits],
            "diff": self.diff,
        }


@dataclass(frozen=True, slots=True)
class RepairResult:
    path: str
    marker: str
    mode: RepairMode
    dry_run: bool
    written: bool
    review_packet: str | None
    findings: list[RepairFinding]
    edits: list[RepairEdit]
    diff: str

    def to_json(self) -> dict[str, object]:
        return {
            "path": self.path,
            "marker": self.marker,
            "mode": self.mode,
            "dry_run": self.dry_run,
            "written": self.written,
            "review_packet": self.review_packet,
            "findings": [item.to_json() for item in self.findings],
            "edits": [item.to_json() for item in self.edits],
            "diff": self.diff,
        }


_OUT_RE = re.compile(r"\.out\(\s*(\d+)\s*\)")


def repair_manual_template(
    path: str | Path,
    *,
    mode: RepairMode,
    dry_run: bool = True,
    write: bool = False,
    review_out: str | Path | None = None,
) -> RepairResult:
    template_path = Path(path)
    source = template_path.read_text(encoding="utf-8")
    marker = _marker(source)
    findings: list[RepairFinding] = []
    edits: list[RepairEdit] = []
    replacement = source

    if marker == "generated" and write:
        raise ValueError("port repair refuses to write generated templates; promote to manual first")

    if mode == "mechanical":
        findings.extend(_positional_output_findings(source))
        # Sprint 7 only allows mechanical rewrites with unambiguous local
        # evidence. This conservative pass records review evidence but does not
        # guess named output aliases from integer slots.
    else:
        findings.extend(_semantic_findings(source))

    diff = "".join(
        difflib.unified_diff(
            source.splitlines(keepends=True),
            replacement.splitlines(keepends=True),
            fromfile=str(template_path),
            tofile=f"{template_path} (repaired)",
        )
    )
    written = False
    if write and not dry_run and replacement != source:
        template_path.write_text(replacement, encoding="utf-8")
        written = True

    packet_path: str | None = None
    if review_out is not None:
        packet_dir = Path(review_out)
        packet_dir.mkdir(parents=True, exist_ok=True)
        packet_path_obj = packet_dir / f"{template_path.stem}.{mode}.review.json"
        packet = RepairPacket(
            path=str(template_path),
            marker=marker,
            mode=mode,
            findings=findings,
            edits=edits,
            diff=diff,
        )
        packet_path_obj.write_text(json.dumps(packet.to_json(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        packet_path = str(packet_path_obj)

    return RepairResult(
        path=str(template_path),
        marker=marker,
        mode=mode,
        dry_run=dry_run,
        written=written,
        review_packet=packet_path,
        findings=findings,
        edits=edits,
        diff=diff,
    )


def _marker(source: str) -> str:
    for raw in source.splitlines()[:5]:
        line = raw.strip()
        if line.startswith("# vibecomfy: manual"):
            return "manual"
        if line.startswith("# vibecomfy: generated"):
            return "generated"
    return "unknown"


def _positional_output_findings(source: str) -> list[RepairFinding]:
    findings: list[RepairFinding] = []
    for lineno, line in enumerate(source.splitlines(), start=1):
        slots = _OUT_RE.findall(line)
        for slot in slots:
            findings.append(
                RepairFinding(
                    code="positional_output_review_required",
                    severity="info",
                    message="Positional output handle kept until local output-name evidence is available.",
                    line=lineno,
                    evidence={"slot": int(slot), "line": line.strip()},
                )
            )
    return findings


def _semantic_findings(source: str) -> list[RepairFinding]:
    findings: list[RepairFinding] = []
    if "bind_output(" not in source:
        findings.append(
            RepairFinding(
                code="semantic_output_contract_missing",
                severity="warning",
                message="Template has no semantic bind_output descriptor.",
            )
        )
    if "register_input(" not in source and "bind_input(" not in source:
        findings.append(
            RepairFinding(
                code="semantic_public_input_missing",
                severity="warning",
                message="Template has no explicit public input descriptors.",
            )
        )
    return findings


__all__ = [
    "RepairEdit",
    "RepairFinding",
    "RepairMode",
    "RepairPacket",
    "RepairResult",
    "repair_manual_template",
]
