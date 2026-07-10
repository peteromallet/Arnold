#!/usr/bin/env bash
set -euo pipefail

INDEX_TS="${SHANNON_INDEX_TS:-/root/.nvm/versions/node/v20.20.2/lib/node_modules/@dexh/shannon/index.ts}"
PY_SHANNON="${MEGAPLAN_SHANNON_WORKER:-}"

if [[ ! -f "$INDEX_TS" ]]; then
  echo "cannot find Shannon index.ts at $INDEX_TS" >&2
  exit 1
fi

if [[ -z "$PY_SHANNON" ]]; then
  PY_SHANNON="$(
    PYENV_VERSION="${PYENV_VERSION:-3.11.11}" python - <<'PY'
from pathlib import Path
import megaplan.shannon_worker

print(Path(megaplan.shannon_worker.__file__).resolve())
PY
  )"
fi

PYENV_VERSION="${PYENV_VERSION:-3.11.11}" python - "$INDEX_TS" "$PY_SHANNON" <<'PY'
from pathlib import Path
import sys

index_ts = Path(sys.argv[1])
py_shannon = Path(sys.argv[2])

text = index_ts.read_text(encoding="utf-8")
text = text.replace(
    '  addBoolean(args, "--dangerously-skip-permissions", parsed.dangerouslySkipPermissions);\n',
    '  // Patched for root cloud runner: Claude Code rejects dangerous bypass flags under root.\n',
)
text = text.replace(
    '  addBoolean(args, "--allow-dangerously-skip-permissions", parsed.allowDangerouslySkipPermissions);\n',
    "",
)
text = text.replace(
    '  addString(args, "--permission-mode", parsed.permissionMode);\n',
    '  const permissionMode = parsed.permissionMode === "bypassPermissions" ? "dontAsk" : parsed.permissionMode;\n'
    '  addString(args, "--permission-mode", permissionMode);\n',
)
text = text.replace(
    '  addString(args, "--session-id", parsed.sessionId);\n',
    '  // Patched for Claude Code v2.1.x: --session-id is not accepted by claude.\n',
)
text = text.replace(
'''      "claude",
      ...options.claudeArgs,
      prompt,
''',
'''      "claude",
      ...options.claudeArgs,
''',
)
text = text.replace(
    "    let launchedWithPrompt = true;\n",
    "    // Patched for Claude Code v2.1.x: send the first prompt through tmux after launch.\n"
    "    let launchedWithPrompt = false;\n",
)
index_ts.write_text(text, encoding="utf-8")

py_text = py_shannon.read_text(encoding="utf-8")
helper = '''def _parse_json_object_from_text(text: str) -> dict[str, Any] | None:
    """Extract a JSON object from model text that may include prose."""
    stripped = text.strip()
    if not stripped:
        return None

    candidates = [stripped]
    for match in re.finditer(r"```(?:json)?\\s*\\n(.*?)\\n```", stripped, re.DOTALL):
        candidates.append(match.group(1).strip())

    decoder = json.JSONDecoder()
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, dict):
            return parsed

        for index, char in enumerate(candidate):
            if char != "{":
                continue
            try:
                parsed, _end = decoder.raw_decode(candidate[index:])
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed
    return None


'''
if "def _parse_json_object_from_text" not in py_text:
    marker = "def _parse_shannon_output(raw: str) -> tuple[dict[str, Any], dict[str, Any]]:\n"
    if marker not in py_text:
        raise SystemExit("cannot patch megaplan.shannon_worker: parse function marker not found")
    py_text = py_text.replace(marker, helper + marker, 1)

py_text = py_text.replace(
'''                try:
                    result_val = json.loads(result_val)
                except json.JSONDecodeError as exc:
                    raise CliError(
                        "parse_error",
                        f"Shannon result payload was not valid JSON: {exc}",
                        extra={"raw_output": raw},
                    ) from exc
''',
'''                parsed_result = _parse_json_object_from_text(result_val)
                if parsed_result is None:
                    raise CliError(
                        "parse_error",
                        "Shannon result payload did not contain a JSON object",
                        extra={"raw_output": raw},
                    )
                result_val = parsed_result
''',
)
py_text = py_text.replace(
'''                try:
                    result_val = json.loads(result_val)
                except json.JSONDecodeError:
                    continue
''',
'''                result_val = _parse_json_object_from_text(result_val)
                if result_val is None:
                    continue
''',
)
py_text = py_text.replace(
'''                        try:
                            parsed = json.loads(text)
                            if isinstance(parsed, dict):
                                return inner, parsed
                        except json.JSONDecodeError:
                            pass
''',
'''                        parsed = _parse_json_object_from_text(text)
                        if isinstance(parsed, dict):
                            return inner, parsed
''',
)
py_text = py_text.replace(
'''                try:
                    parsed = json.loads(content)
                    if isinstance(parsed, dict):
                        return inner, parsed
                except json.JSONDecodeError:
                    pass
''',
'''                parsed = _parse_json_object_from_text(content)
                if isinstance(parsed, dict):
                    return inner, parsed
''',
)
py_shannon.write_text(py_text, encoding="utf-8")

patched_index = index_ts.read_text(encoding="utf-8")
required_index = [
    'parsed.permissionMode === "bypassPermissions" ? "dontAsk"',
    "Patched for root cloud runner",
    "Patched for Claude Code v2.1.x",
    "send the first prompt through tmux after launch",
]
missing = [item for item in required_index if item not in patched_index]
if missing:
    raise SystemExit(f"Shannon patch verification failed; missing: {missing}")
for forbidden in [
    'addBoolean(args, "--dangerously-skip-permissions"',
    'addBoolean(args, "--allow-dangerously-skip-permissions"',
    'addString(args, "--session-id", parsed.sessionId)',
]:
    if forbidden in patched_index:
        raise SystemExit(f"Shannon patch verification failed; still contains {forbidden}")

patched_py = py_shannon.read_text(encoding="utf-8")
required_py = [
    "def _parse_json_object_from_text",
    "Shannon result payload did not contain a JSON object",
    "_parse_json_object_from_text(result_val)",
]
missing = [item for item in required_py if item not in patched_py]
if missing:
    raise SystemExit(f"megaplan.shannon_worker patch verification failed; missing: {missing}")
PY

PYENV_VERSION="${PYENV_VERSION:-3.11.11}" python -m py_compile "$PY_SHANNON"
echo "Shannon unattended-root patch verified at $INDEX_TS and $PY_SHANNON"
