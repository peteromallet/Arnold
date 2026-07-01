from __future__ import annotations

import os
import re
from collections.abc import Iterable, Iterator, Mapping
from copy import deepcopy
from typing import Any


REDACTION = "***REDACTED***"
_DISABLE_VALUES = {"0", "false", "no", "off"}
_SECRET_FLAG_NAMES = (
    "api-key",
    "apikey",
    "access-token",
    "auth-token",
    "bearer",
    "key",
    "password",
    "passwd",
    "refresh-token",
    "secret",
    "token",
)
_SECRET_ENV_NAME_FRAGMENT = (
    r"(?:API(?:_?KEY)?|TOKEN|SECRET|PASSWORD|PASSWD|PASS|AUTH|CREDENTIALS?)"
)
_TOKEN_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(?<![A-Za-z0-9_-])sk-[A-Za-z0-9_-]{10,}(?![A-Za-z0-9_-])"), REDACTION),
    (re.compile(r"(?<![A-Za-z0-9_-])gh[pousr]_[A-Za-z0-9]{10,}(?![A-Za-z0-9_-])"), REDACTION),
    (re.compile(r"(?<![A-Za-z0-9_-])github_pat_[A-Za-z0-9_]{10,}(?![A-Za-z0-9_-])"), REDACTION),
    (re.compile(r"(?<![A-Za-z0-9_-])xox[baprs]-[A-Za-z0-9-]{10,}(?![A-Za-z0-9_-])"), REDACTION),
    (re.compile(r"(?<![A-Za-z0-9_-])AKIA[A-Z0-9]{16}(?![A-Za-z0-9_-])"), REDACTION),
    (re.compile(r"(?<![A-Za-z0-9_-])SG\.[A-Za-z0-9_-]{10,}(?![A-Za-z0-9_-])"), REDACTION),
    (re.compile(r"(?<![A-Za-z0-9_-])hf_[A-Za-z0-9]{10,}(?![A-Za-z0-9_-])"), REDACTION),
    (
        re.compile(r"M[A-Za-z0-9_-]{18,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{20,}"),
        REDACTION,
    ),
)
_AUTH_HEADER_RE = re.compile(
    r"(?P<prefix>\bAuthorization\s*:\s*(?:Bearer|Token|Basic)\s+)(?P<value>\S+)",
    re.IGNORECASE,
)
_GENERIC_BEARER_RE = re.compile(r"(?P<prefix>\bBearer\s+)(?P<value>[A-Za-z0-9_~+/=\-.]{8,})")
_JSON_SECRET_FIELD_RE = re.compile(
    r'(?P<prefix>"(?:api_?[Kk]ey|token|secret|password|access_token|refresh_token|auth_token|bearer)"\s*:\s*")'
    r'(?P<value>[^"]+)(")',
    re.IGNORECASE,
)
_ENV_ASSIGN_RE = re.compile(
    rf"(?P<name>\b(?:export\s+)?[A-Z0-9_]*{_SECRET_ENV_NAME_FRAGMENT}[A-Z0-9_]*\b)"
    r"(?P<sep>\s*=\s*)(?P<quote>['\"]?)(?P<value>[^\s'\"]+)(?P=quote)",
    re.IGNORECASE,
)
_URL_TOKEN_RE = re.compile(
    r"(?P<prefix>(?:https?|wss?)://[^\s?#]+(?:\?[^#\s]*)?"
    r"(?:[?&](?:access_token|auth_token|token|api[_-]?key|key|sig)=))"
    r"(?P<value>[^&#\s]+)",
    re.IGNORECASE,
)
_DB_CONNSTR_RE = re.compile(
    r"(?P<prefix>(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis|amqp|mariadb|sqlserver)://"
    r"[^:/@\s]+:)(?P<value>[^@/\s]+)(?P<suffix>@)",
    re.IGNORECASE,
)
_PRIVATE_KEY_RE = re.compile(
    r"-----BEGIN(?: [A-Z0-9]+)? PRIVATE KEY-----[\s\S]*?-----END(?: [A-Z0-9]+)? PRIVATE KEY-----"
)
_TELEGRAM_RE = re.compile(r"(?P<prefix>bot)?(?P<id>\d{8,}):(?P<value>[-A-Za-z0-9_]{30,})")
_COMMAND_FLAG_INLINE_RE = re.compile(
    rf"(?P<flag>--?(?:{'|'.join(re.escape(flag) for flag in _SECRET_FLAG_NAMES)}))"
    r"(?P<sep>=)(?P<value>[^\s'\"]+)",
    re.IGNORECASE,
)
_COMMAND_FLAG_ARG_RE = re.compile(
    rf"(?P<flag>--?(?:{'|'.join(re.escape(flag) for flag in _SECRET_FLAG_NAMES)}))"
    r"(?P<sep>\s+)(?P<quote>['\"]?)(?P<value>[^\s'\"]+)(?P=quote)",
    re.IGNORECASE,
)


def redaction_enabled(env: Mapping[str, str] | None = None) -> bool:
    source = env if env is not None else os.environ
    return str(source.get("ARNOLD_REDACTION_ENABLED", "1")).strip().lower() not in _DISABLE_VALUES


def _literal_values(
    secret_names: list[str] | tuple[str, ...],
    env: Mapping[str, str] | None,
) -> list[str]:
    if env is None:
        return []
    values: list[str] = []
    for name in secret_names:
        value = env.get(name, "")
        if len(value) >= 8:
            values.append(value)
    return sorted(set(values), key=len, reverse=True)


def _secret_name_assignment_pattern(secret_names: list[str] | tuple[str, ...]) -> re.Pattern[str] | None:
    if not secret_names:
        return None
    names = "|".join(re.escape(name) for name in sorted(set(secret_names), key=len, reverse=True))
    return re.compile(
        rf"(?P<name>\b(?:export\s+)?(?:{names})\b)(?P<sep>\s*[:=]\s*)(?P<quote>['\"]?)(?P<value>[^\s'\"]+)(?P=quote)"
    )


def _redact_text_patterns(text: str, secret_names: list[str] | tuple[str, ...], env: Mapping[str, str] | None) -> str:
    redacted = text
    assignment_pattern = _secret_name_assignment_pattern(secret_names)
    if assignment_pattern is not None:
        redacted = assignment_pattern.sub(
            lambda match: f"{match.group('name')}{match.group('sep')}{match.group('quote')}{REDACTION}{match.group('quote')}",
            redacted,
        )

    redacted = _ENV_ASSIGN_RE.sub(
        lambda match: f"{match.group('name')}{match.group('sep')}{match.group('quote')}{REDACTION}{match.group('quote')}",
        redacted,
    )
    redacted = _COMMAND_FLAG_INLINE_RE.sub(
        lambda match: f"{match.group('flag')}{match.group('sep')}{REDACTION}",
        redacted,
    )
    redacted = _COMMAND_FLAG_ARG_RE.sub(
        lambda match: f"{match.group('flag')}{match.group('sep')}{match.group('quote')}{REDACTION}{match.group('quote')}",
        redacted,
    )
    redacted = _AUTH_HEADER_RE.sub(
        lambda match: f"{match.group('prefix')}{REDACTION}",
        redacted,
    )
    redacted = _GENERIC_BEARER_RE.sub(
        lambda match: f"{match.group('prefix')}{REDACTION}",
        redacted,
    )
    redacted = _JSON_SECRET_FIELD_RE.sub(
        lambda match: f"{match.group('prefix')}{REDACTION}\"",
        redacted,
    )
    redacted = _URL_TOKEN_RE.sub(
        lambda match: f"{match.group('prefix')}{REDACTION}",
        redacted,
    )
    redacted = _DB_CONNSTR_RE.sub(
        lambda match: f"{match.group('prefix')}{REDACTION}{match.group('suffix')}",
        redacted,
    )
    redacted = _PRIVATE_KEY_RE.sub(REDACTION, redacted)
    redacted = _TELEGRAM_RE.sub(
        lambda match: f"{match.group('prefix') or ''}{match.group('id')}:{REDACTION}",
        redacted,
    )

    for value in _literal_values(secret_names, env):
        redacted = redacted.replace(value, REDACTION)

    for pattern, replacement in _TOKEN_PATTERNS:
        redacted = pattern.sub(replacement, redacted)

    return redacted


def redact_text(
    text: str,
    secret_names: list[str] | tuple[str, ...] = (),
    env: Mapping[str, str] | None = None,
) -> str:
    if text is None or not isinstance(text, str):
        return text
    if not text or not redaction_enabled(env):
        return text
    return _redact_text_patterns(text, secret_names, env)


def redact_payload(
    value: Any,
    secret_names: list[str] | tuple[str, ...] = (),
    env: Mapping[str, str] | None = None,
) -> Any:
    if not redaction_enabled(env):
        return deepcopy(value)
    if isinstance(value, str):
        return redact_text(value, secret_names, env=env)
    if isinstance(value, dict):
        return {key: redact_payload(item, secret_names, env=env) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_payload(item, secret_names, env=env) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_payload(item, secret_names, env=env) for item in value)
    return deepcopy(value)


def redact(
    text: str,
    secret_names: list[str] | tuple[str, ...],
    env: Mapping[str, str] | None = None,
) -> str:
    return redact_text(text, secret_names, env=env)


def _iter_chunks(source: Any) -> Iterator[str]:
    stream = getattr(source, "stdout", None)
    if stream is not None:
        while True:
            chunk = stream.readline()
            if chunk == "":
                break
            yield chunk
        tail = stream.read()
        if tail:
            yield tail
        return

    if isinstance(source, Iterable) and not isinstance(source, (str, bytes)):
        for chunk in source:
            yield chunk


def stream_redact(
    proc: Any,
    secret_names: list[str] | tuple[str, ...],
    env: Mapping[str, str] | None = None,
) -> Iterator[str]:
    for chunk in _iter_chunks(proc):
        yield redact_text(chunk, secret_names, env=env)


__all__ = [
    "REDACTION",
    "redact",
    "redact_payload",
    "redact_text",
    "redaction_enabled",
    "stream_redact",
]
