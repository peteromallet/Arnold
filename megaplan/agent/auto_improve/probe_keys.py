"""Pre-flight API key probing for auto-improve workers."""

from __future__ import annotations

import argparse
import json
import re
import socket
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal
import urllib.error
import urllib.request


Status = Literal["alive", "exhausted", "invalid", "unreachable"]
ZHIPU_ENDPOINT = "https://api.z.ai/api/coding/paas/v4/chat/completions"
RESET_AT_PATTERN = re.compile(r"reset at ([0-9T :\-\.]+)")
DETAIL_LIMIT = 120
TABLE_DETAIL_LIMIT = 60


@dataclass(frozen=True)
class KeyStatus:
    key: str
    provider: str
    status: Status
    detail: str
    reset_at: str | None
    masked_key: str


def _require_provider(provider: str) -> None:
    if provider != "zhipu":
        raise NotImplementedError(f"Provider '{provider}' is not implemented")


def _mask_key(key: str) -> str:
    return f"{key[:8]}...{key[-4:]}"


def _short_detail(text: str, *, key: str) -> str:
    cleaned = re.sub(r"\s+", " ", (text or "").strip())
    if not cleaned:
        return "no detail"
    cleaned = cleaned.replace(key, "[redacted]")
    return cleaned[:DETAIL_LIMIT]


def _load_api_keys_json(path: Path) -> list[str]:
    if not path.exists():
        return []

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"Expected a JSON list in {path}")

    keys: list[str] = []
    for entry in payload:
        if isinstance(entry, str) and entry:
            keys.append(entry)
        elif isinstance(entry, dict):
            value = entry.get("key")
            if isinstance(value, str) and value:
                keys.append(value)
    return keys


def _load_env_map(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    env_map: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.strip()
        value = value.strip()
        if not name:
            continue
        if value and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        env_map[name] = value
    return env_map


def load_candidate_keys(provider: str = "zhipu") -> list[str]:
    _require_provider(provider)

    seen: set[str] = set()
    ordered: list[str] = []

    for key in _load_api_keys_json(Path(__file__).resolve().parent / "api_keys.json"):
        if key not in seen:
            seen.add(key)
            ordered.append(key)

    env_map = _load_env_map(Path.home() / ".hermes" / ".env")
    env_names = ["ZHIPU_API_KEY", *[f"ZHIPU_API_KEY_{index}" for index in range(1, 17)]]
    for name in env_names:
        key = env_map.get(name, "").strip()
        if key and key not in seen:
            seen.add(key)
            ordered.append(key)

    return ordered


def probe_key(key: str, *, provider: str = "zhipu", timeout: float = 5.0) -> KeyStatus:
    _require_provider(provider)

    payload = json.dumps(
        {
            "model": "glm-5.1",
            "messages": [{"role": "user", "content": "hi"}],
            "max_tokens": 1,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        ZHIPU_ENDPOINT,
        data=payload,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            detail = _short_detail(f"HTTP {getattr(response, 'status', 200)}", key=key)
            return KeyStatus(
                key=key,
                provider=provider,
                status="alive",
                detail=detail,
                reset_at=None,
                masked_key=_mask_key(key),
            )
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        reset_at_match = RESET_AT_PATTERN.search(body)
        reset_at = reset_at_match.group(1) if reset_at_match else None
        detail = _short_detail(body or f"HTTP {exc.code} {exc.reason}", key=key)
        if exc.code == 429:
            status: Status = "exhausted"
        elif exc.code in {401, 403}:
            status = "invalid"
        else:
            status = "unreachable"
        return KeyStatus(
            key=key,
            provider=provider,
            status=status,
            detail=detail,
            reset_at=reset_at,
            masked_key=_mask_key(key),
        )
    except socket.timeout:
        detail = _short_detail("socket timeout", key=key)
    except urllib.error.URLError as exc:
        detail = _short_detail(f"url error: {exc.reason}", key=key)
    except Exception as exc:  # pragma: no cover - defensive classification
        detail = _short_detail(f"{type(exc).__name__}: {exc}", key=key)
    return KeyStatus(
        key=key,
        provider=provider,
        status="unreachable",
        detail=detail,
        reset_at=None,
        masked_key=_mask_key(key),
    )


def probe_keys(
    keys: list[str], *, provider: str = "zhipu", concurrency: int = 8, timeout: float = 5.0
) -> list[KeyStatus]:
    _require_provider(provider)
    if not keys:
        return []

    results: list[KeyStatus | None] = [None] * len(keys)
    max_workers = max(1, min(concurrency, len(keys)))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_index = {
            executor.submit(probe_key, key, provider=provider, timeout=timeout): index
            for index, key in enumerate(keys)
        }
        for future in as_completed(future_to_index):
            results[future_to_index[future]] = future.result()
    return [result for result in results if result is not None]


def probe_all_keys(provider: str = "zhipu", *, concurrency: int = 8, timeout: float = 5.0) -> list[KeyStatus]:
    return probe_keys(
        load_candidate_keys(provider=provider),
        provider=provider,
        concurrency=concurrency,
        timeout=timeout,
    )


def alive_keys(results: list[KeyStatus]) -> list[str]:
    return [result.key for result in results if result.status == "alive"]


def format_status_table(results: list[KeyStatus], *, assignments: dict[str, str] | None = None) -> str:
    assignments = assignments or {}
    headers = ("key", "worker", "status", "detail", "reset_at")
    rows: list[tuple[str, str, str, str, str]] = []
    for result in results:
        status_text = ("✓" if result.status == "alive" else "✗") + f" {result.status}"
        detail = result.detail[:TABLE_DETAIL_LIMIT]
        rows.append(
            (
                result.masked_key,
                assignments.get(result.key, "-"),
                status_text,
                detail,
                result.reset_at or "-",
            )
        )

    widths = [len(header) for header in headers]
    for row in rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(cell))

    lines = [
        "  ".join(header.ljust(widths[index]) for index, header in enumerate(headers)),
        "  ".join("-" * width for width in widths),
    ]
    lines.extend("  ".join(cell.ljust(widths[index]) for index, cell in enumerate(row)) for row in rows)
    table = "\n".join(lines)
    for result in results:
        assert result.key not in table
    return table


def _public_status(result: KeyStatus) -> dict[str, str | None]:
    payload = asdict(result)
    payload["key"] = result.masked_key
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Probe configured API keys.")
    parser.add_argument("--provider", default="zhipu")
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--json", action="store_true", dest="json_output")
    args = parser.parse_args(argv)

    results = probe_all_keys(provider=args.provider, concurrency=args.concurrency, timeout=args.timeout)
    if args.json_output:
        print(json.dumps([_public_status(result) for result in results], indent=2))
    else:
        print(format_status_table(results))
    return 0 if alive_keys(results) else 1


if __name__ == "__main__":
    sys.exit(main())
