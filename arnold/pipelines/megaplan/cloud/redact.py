from __future__ import annotations

import re
from collections.abc import Iterator


REDACTION = "***REDACTED***"
TOKEN_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]+\b"),
    re.compile(r"\bghp_[A-Za-z0-9]+\b"),
    re.compile(r"\bxoxb-[A-Za-z0-9-]+\b"),
)


def _literal_values(secret_names: list[str] | tuple[str, ...], env: dict[str, str] | None) -> list[str]:
    if env is None:
        return []
    values: list[str] = []
    for name in secret_names:
        value = env.get(name, "")
        if len(value) >= 8:
            values.append(value)
    return sorted(set(values), key=len, reverse=True)


def redact(
    text: str,
    secret_names: list[str] | tuple[str, ...],
    env: dict[str, str] | None = None,
) -> str:
    redacted = text

    if secret_names:
        names = "|".join(re.escape(name) for name in secret_names)
        assignment = re.compile(rf"\b(?P<name>{names})(?P<sep>\s*[:=]\s*)(?P<value>[^\s\"']+)")
        redacted = assignment.sub(rf"\g<name>\g<sep>{REDACTION}", redacted)

    for value in _literal_values(secret_names, env):
        redacted = redacted.replace(value, REDACTION)

    for pattern in TOKEN_PATTERNS:
        redacted = pattern.sub(REDACTION, redacted)

    return redacted


def stream_redact(
    proc,
    secret_names: list[str] | tuple[str, ...],
    env: dict[str, str] | None = None,
) -> Iterator[str]:
    stream = getattr(proc, "stdout", None)
    if stream is None:
        return

    while True:
        chunk = stream.readline()
        if chunk == "":
            break
        yield redact(chunk, secret_names, env=env)

    tail = stream.read()
    if tail:
        yield redact(tail, secret_names, env=env)
