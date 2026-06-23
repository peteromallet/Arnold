#!/usr/bin/env python3
"""Switch coding-agent provider configuration for Kimi Code CLI and Claude Code.

Supports switching between native managed/API-key providers and third-party
providers (Moonshot Open Platform, Zhipu GLM-5.2) where the target tool allows.

Targets:
  kimi   - Kimi Code CLI (~/.kimi-code/config.toml)
  claude - Claude Code (~/.claude/settings.json)

Modes per target:
  kimi:   managed, api-key, platform, glm
  claude: managed, api-key, kimi, glm
"""

import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------


def kimi_config_path():
    home = os.environ.get("KIMI_CODE_HOME")
    if home:
        return Path(home) / "config.toml"
    return Path.home() / ".kimi-code" / "config.toml"


def claude_settings_path():
    home = os.environ.get("CLAUDE_CODE_HOME")
    if home:
        return Path(home) / "settings.json"
    return Path.home() / ".claude" / "settings.json"


# ---------------------------------------------------------------------------
# Key resolution
# ---------------------------------------------------------------------------


def load_env_key(env_path, env_vars):
    """Read the first matching key from a .env file.

    Mirrors a minimal KEY=value parser: skip blanks/comments, strip quotes.
    """
    env_path = Path(env_path).expanduser()
    if not env_path.exists():
        return None
    try:
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip("'").strip('"')
            if key in env_vars and value:
                return value
    except OSError:
        return None
    return None


def load_all_env_keys(env_path, env_vars):
    """Return all non-empty (var_name, key) matches from a .env file in order.

    Mirrors a minimal KEY=value parser: skip blanks/comments, strip quotes.
    """
    env_path = Path(env_path).expanduser()
    found = []
    if not env_path.exists():
        return found
    try:
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip("'").strip('"')
            if key in env_vars and value:
                found.append((key, value))
    except OSError:
        pass
    return found


def load_glm_keys_from_json(path):
    """Read GLM keys from a JSON file like Hermes auto_improve/api_keys.json.

    Expected shape: [{"key": "...", "base_url": "..."}, ...]
    Returns a list of (label, key) tuples.
    """
    path = Path(path).expanduser()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            found = []
            for i, entry in enumerate(data, 1):
                if isinstance(entry, dict) and entry.get("key"):
                    found.append((f"{path.name}[{i}]", entry["key"]))
            return found
    except (OSError, json.JSONDecodeError):
        pass
    return []


def test_glm_key(key, base_url):
    """Test a GLM key by calling the OpenAI-compatible /models endpoint.

    Returns (ok, reason) tuple. ok=True means the key is accepted and has
    not hit a hard quota/auth failure at the models endpoint.
    """
    import urllib.request
    import urllib.error
    import json

    url = base_url.rstrip("/") + "/models"
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {key}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read()
            try:
                data = json.loads(body)
                if data.get("object") == "list" and data.get("data"):
                    return True, "ok"
            except json.JSONDecodeError:
                pass
            return True, f"http {resp.status}"
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")[:200]
        return False, f"http {exc.code}: {body}"
    except urllib.error.URLError as exc:
        return False, f"network error: {exc.reason}"
    except Exception as exc:
        return False, f"error: {exc}"


def resolve_key(args, env_vars, purpose, test_fn=None, extra_candidates=None):
    """Resolve an API key from argv, KIMI_SWITCH_API_KEY env var, stdin, .env, or extras.

    If test_fn is provided and multiple candidate keys are found, cycle through
    them and return the first one that passes test_fn(key).
    """
    key = args.key
    source = "argument"
    if not key:
        key = os.environ.get("KIMI_SWITCH_API_KEY")
        if key:
            source = "KIMI_SWITCH_API_KEY"
    if not key and not sys.stdin.isatty():
        key = sys.stdin.read().strip()
        if key:
            source = "stdin"

    env_path = Path(args.env_file).expanduser()
    env_vars_list = [v.strip() for v in env_vars.split(",") if v.strip()]

    if not key:
        # Gather all candidate keys so we can cycle through them if requested.
        candidates = []
        for var in env_vars_list:
            val = os.environ.get(var)
            if val:
                candidates.append((var, val))
        candidates.extend(load_all_env_keys(env_path, env_vars_list))
        if extra_candidates:
            candidates.extend(extra_candidates)
        # Deduplicate while preserving order.
        seen = set()
        unique = []
        for var, val in candidates:
            if val not in seen:
                seen.add(val)
                unique.append((var, val))
        candidates = unique

        if not candidates:
            raise SystemExit(
                f"error: {purpose} API key is required. Pass it as an argument, "
                "set KIMI_SWITCH_API_KEY, or ensure one of "
                f"{env_vars_list} is set in {env_path}."
            )

        if test_fn is None or len(candidates) == 1:
            var, key = candidates[0]
            if var.startswith("api_keys.json"):
                source = f"{var}"
            else:
                source = f"{var} from {env_path}"
        else:
            print(f"Testing {len(candidates)} candidate {purpose} keys...", file=sys.stderr)
            for var, candidate in candidates:
                ok, reason = test_fn(candidate)
                print(f"  {var}: {reason}", file=sys.stderr)
                if ok:
                    key = candidate
                    if var.startswith("api_keys.json"):
                        source = f"{var}"
                    else:
                        source = f"{var} from {env_path}"
                    break
            if not key:
                raise SystemExit(
                    f"error: none of the candidate {purpose} keys worked. "
                    f"Checked: {[v for v, _ in candidates]}"
                )

    if test_fn is not None and source != "argument":
        ok, reason = test_fn(key)
        if not ok:
            raise SystemExit(
                f"error: the resolved {purpose} key failed validation: {reason}"
            )

    print(f"Using {purpose} key from {source}", file=sys.stderr)
    return key


# ---------------------------------------------------------------------------
# Kimi Code CLI config helpers
# ---------------------------------------------------------------------------


def kimi_provider_managed():
    return '''[providers."managed:kimi-code"]
type = "kimi"
api_key = ""
base_url = "https://api.kimi.com/coding/v1"

[providers."managed:kimi-code".oauth]
storage = "file"
key = "oauth/kimi-code"

'''


def kimi_provider_api_key(key):
    return f'''[providers."managed:kimi-code"]
type = "kimi"
api_key = {key!r}
base_url = "https://api.kimi.com/coding/v1"

'''


def kimi_provider_platform(key, region="ai"):
    host = "api.moonshot.ai" if region == "ai" else "api.moonshot.cn"
    return f'''[providers.moonshot]
type = "kimi"
api_key = {key!r}
base_url = "https://{host}/v1"

'''


def kimi_provider_glm(key, base_url):
    return f'''[providers.glm]
type = "openai"
api_key = {key!r}
base_url = "{base_url}"

'''


MODEL_KIMI = '''[models."kimi-code/kimi-for-coding"]
provider = "managed:kimi-code"
model = "kimi-for-coding"
max_context_size = 262144
capabilities = [ "thinking", "always_thinking", "image_in", "video_in", "tool_use" ]
display_name = "K2.7 Code"
'''


def kimi_model_platform(region="ai"):
    return '''[models."moonshot/kimi-k2.7-code"]
provider = "moonshot"
model = "kimi-k2.7-code"
max_context_size = 262144
capabilities = [ "thinking", "always_thinking", "image_in", "video_in", "tool_use" ]
display_name = "K2.7 Code"
'''


MODEL_GLM = '''[models."glm/glm-5.2"]
provider = "glm"
model = "glm-5.2"
max_context_size = 1000000
capabilities = [ "thinking", "tool_use" ]
display_name = "GLM-5.2"
'''


def kimi_services_managed():
    return '''[services.moonshot_search]
base_url = "https://api.kimi.com/coding/v1/search"
api_key = ""

[services.moonshot_search.oauth]
storage = "file"
key = "oauth/kimi-code"

[services.moonshot_fetch]
base_url = "https://api.kimi.com/coding/v1/fetch"
api_key = ""

[services.moonshot_fetch.oauth]
storage = "file"
key = "oauth/kimi-code"
'''


def kimi_services_api_key(key):
    return f'''[services.moonshot_search]
base_url = "https://api.kimi.com/coding/v1/search"
api_key = {key!r}

[services.moonshot_fetch]
base_url = "https://api.kimi.com/coding/v1/fetch"
api_key = {key!r}
'''


def kimi_services_platform(region="ai"):
    host = "api.moonshot.ai" if region == "ai" else "api.moonshot.cn"
    return f'''[services.moonshot_search]
base_url = "https://{host}/v1/search"
api_key = ""

[services.moonshot_fetch]
base_url = "https://{host}/v1/fetch"
api_key = ""
'''


def kimi_services_glm(base_url):
    search_url = base_url.rstrip("/") + "/search"
    fetch_url = base_url.rstrip("/") + "/fetch"
    return f'''[services.moonshot_search]
base_url = "{search_url}"
api_key = ""

[services.moonshot_fetch]
base_url = "{fetch_url}"
api_key = ""
'''


def _remove_kimi_section(text, header_pattern):
    """Remove a top-level TOML section and any sub-tables under it."""
    pattern = (
        r'^\[('
        + header_pattern
        + r')\]'
        r'.*?'
        r'(?=^\[(?!\1\.)[^\]]+\]|\Z)'
    )
    flags = re.MULTILINE | re.DOTALL
    return re.sub(pattern, '', text, count=1, flags=flags)


def _kimi_set_default_model(text, model):
    return re.sub(
        r'^default_model\s*=\s*".*?"',
        f'default_model = "{model}"',
        text,
        count=1,
        flags=re.MULTILINE,
    )


def rewrite_kimi_config(text, mode, key=None, region="ai", glm_base_url=None):
    if mode == "managed":
        provider_block = kimi_provider_managed()
        model_block = MODEL_KIMI
        services_block = kimi_services_managed()
        default_model = "kimi-code/kimi-for-coding"
    elif mode == "api-key":
        provider_block = kimi_provider_api_key(key)
        model_block = MODEL_KIMI
        services_block = kimi_services_api_key(key)
        default_model = "kimi-code/kimi-for-coding"
    elif mode == "platform":
        provider_block = kimi_provider_platform(key, region)
        model_block = kimi_model_platform(region)
        services_block = kimi_services_platform(region).replace('api_key = ""', f'api_key = {key!r}')
        default_model = "moonshot/kimi-k2.7-code"
    elif mode == "glm":
        provider_block = kimi_provider_glm(key, glm_base_url)
        model_block = MODEL_GLM
        services_block = kimi_services_glm(glm_base_url).replace('api_key = ""', f'api_key = {key!r}')
        default_model = "glm/glm-5.2"
    else:
        raise ValueError(f"Unknown Kimi mode: {mode}")

    text = _remove_kimi_section(text, r'providers\."managed:kimi-code"')
    text = _remove_kimi_section(text, r'providers\.moonshot')
    text = _remove_kimi_section(text, r'providers\.glm')
    text = _remove_kimi_section(text, r'models\."kimi-code/kimi-for-coding"')
    text = _remove_kimi_section(text, r'models\."moonshot/kimi-k2\.7-code"')
    text = _remove_kimi_section(text, r'models\."glm/glm-5\.2"')
    text = _remove_kimi_section(text, r'services\.moonshot_search')
    text = _remove_kimi_section(text, r'services\.moonshot_fetch')

    text = text.rstrip() + "\n\n" + provider_block + model_block + "\n" + services_block + "\n"
    text = _kimi_set_default_model(text, default_model)
    return text


# ---------------------------------------------------------------------------
# Claude Code settings helpers
# ---------------------------------------------------------------------------


def read_claude_settings(path):
    if not path.exists():
        return {"env": {}}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"error: could not parse {path}: {exc}")


def write_claude_settings(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def rewrite_claude_settings(data, mode, key=None):
    env = data.setdefault("env", {})

    # Clear any previous provider overrides we manage.
    for k in ("ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_MODEL"):
        env.pop(k, None)
    env.pop("ANTHROPIC_API_KEY", None)

    if mode == "managed":
        # Native Anthropic managed login; no env vars needed.
        pass
    elif mode == "api-key":
        env["ANTHROPIC_API_KEY"] = key
    elif mode == "kimi":
        env["ANTHROPIC_BASE_URL"] = "https://api.kimi.com/coding/"
        env["ANTHROPIC_AUTH_TOKEN"] = key
        env["ANTHROPIC_MODEL"] = "kimi-for-coding"
    elif mode == "glm":
        env["ANTHROPIC_BASE_URL"] = "https://open.bigmodel.cn/api/anthropic"
        env["ANTHROPIC_AUTH_TOKEN"] = key
        env["ANTHROPIC_MODEL"] = "glm-5.2"
    else:
        raise ValueError(f"Unknown Claude mode: {mode}")

    # Clean up empty env dict.
    if not env:
        data.pop("env", None)

    return data


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_kimi(candidate_path):
    result = subprocess.run(
        ["kimi", "doctor", "config", str(candidate_path)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print("Validation failed:", file=sys.stderr)
        print(result.stdout, file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        return False
    return True


def validate_claude(candidate_path):
    # Claude Code has no public config validator; just check JSON is valid.
    try:
        with open(candidate_path, "r", encoding="utf-8") as f:
            json.load(f)
        return True
    except json.JSONDecodeError as exc:
        print(f"Validation failed: invalid JSON: {exc}", file=sys.stderr)
        return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Switch coding-agent provider configuration"
    )
    parser.add_argument(
        "--target",
        choices=["kimi", "claude"],
        default="kimi",
        help="Which coding agent to configure. Default: kimi",
    )
    parser.add_argument(
        "mode",
        help="Provider mode",
    )
    parser.add_argument(
        "key",
        nargs="?",
        help="API key. If omitted, reads from KIMI_SWITCH_API_KEY, stdin, or a .env file.",
    )
    parser.add_argument(
        "--region",
        choices=["ai", "cn"],
        default="ai",
        help="Moonshot Open Platform region (kimi platform mode). Default: ai",
    )
    parser.add_argument(
        "--env-file",
        default="~/.hermes/.env",
        help="Path to a .env file to read the key from. Default: ~/.hermes/.env",
    )
    parser.add_argument(
        "--env-var",
        default=None,
        help="Comma-separated env var names to look for in --env-file.",
    )
    parser.add_argument(
        "--glm-base-url",
        default="https://open.bigmodel.cn/api/coding/paas/v4",
        help="GLM OpenAI-compatible base URL (kimi glm mode). Default: https://open.bigmodel.cn/api/coding/paas/v4",
    )
    parser.add_argument(
        "--glm-keys-file",
        default="~/Documents/hermes-agent/auto_improve/api_keys.json",
        help="JSON file with GLM keys ([{\"key\": \"...\", \"base_url\": \"...\"}]). "
             "Default: ~/Documents/hermes-agent/auto_improve/api_keys.json",
    )
    args = parser.parse_args()

    # Validate mode against target.
    kimi_modes = {"managed", "api-key", "platform", "glm"}
    claude_modes = {"managed", "api-key", "kimi", "glm"}
    valid_modes = kimi_modes if args.target == "kimi" else claude_modes
    if args.mode not in valid_modes:
        parser.error(
            f"mode {args.mode!r} is not valid for target {args.target!r}. "
            f"Valid modes: {', '.join(sorted(valid_modes))}"
        )

    # Resolve key when needed.
    test_fn = None
    extra_candidates = None
    if args.mode in ("api-key", "platform", "kimi", "glm"):
        if args.target == "kimi" and args.mode == "platform":
            env_vars = args.env_var or "MOONSHOT_API_KEY,KIMI_API_KEY"
            purpose = "Moonshot Open Platform"
        elif args.mode == "glm":
            env_vars = args.env_var or "GLM_API_KEY,ZAI_API_KEY,Z_AI_API_KEY,ZHIPU_API_KEY,ZHIPU_API_KEY_2,BIGMODEL_API_KEY"
            purpose = "GLM"
            # Test keys against the OpenAI-compatible /models endpoint.  For Kimi
            # we use the selected GLM base URL; for Claude we validate the same
            # key against the standard China endpoint since Claude uses the
            # Anthropic-compatible base URL.
            if args.target == "kimi":
                test_url = args.glm_base_url
            else:
                test_url = "https://open.bigmodel.cn/api/paas/v4"
            test_fn = lambda k: test_glm_key(k, test_url)
            extra_candidates = load_glm_keys_from_json(args.glm_keys_file)
        elif args.target == "claude" and args.mode == "kimi":
            env_vars = args.env_var or "KIMI_API_KEY,KIMICODE_API_KEY"
            purpose = "Kimi Code"
        elif args.target == "kimi" and args.mode == "api-key":
            env_vars = args.env_var or "KIMI_API_KEY,KIMICODE_API_KEY"
            purpose = "Kimi Code"
        elif args.target == "claude" and args.mode == "api-key":
            env_vars = args.env_var or "ANTHROPIC_API_KEY"
            purpose = "Anthropic"
        else:
            env_vars = args.env_var or ""
            purpose = "API"
        args.key = resolve_key(args, env_vars, purpose, test_fn=test_fn, extra_candidates=extra_candidates)

    if args.target == "kimi":
        path = kimi_config_path()
        if not path.exists():
            raise SystemExit(f"Config not found: {path}")

        with open(path, "r", encoding="utf-8") as f:
            original = f.read()

        try:
            new_text = rewrite_kimi_config(
                original,
                args.mode,
                key=args.key,
                region=args.region,
                glm_base_url=args.glm_base_url,
            )
        except Exception as exc:
            print(f"error: could not rewrite config: {exc}", file=sys.stderr)
            sys.exit(1)

        candidate = path.with_suffix(path.suffix + ".candidate")
        with open(candidate, "w", encoding="utf-8") as f:
            f.write(new_text)

        if not validate_kimi(candidate):
            os.remove(candidate)
            sys.exit(1)

        backup = path.parent / f"config.toml.{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}.bak"
        shutil.copy2(path, backup)
        shutil.move(candidate, path)

        print(f"Switched Kimi Code CLI to {args.mode} mode.")
        print(f"Backup: {backup}")

    else:  # claude
        path = claude_settings_path()
        data = read_claude_settings(path)
        original_text = json.dumps(data, indent=2) + "\n" if path.exists() else ""

        try:
            new_data = rewrite_claude_settings(data, args.mode, key=args.key)
        except Exception as exc:
            print(f"error: could not rewrite settings: {exc}", file=sys.stderr)
            sys.exit(1)

        candidate = path.with_suffix(path.suffix + ".candidate")
        write_claude_settings(candidate, new_data)

        if not validate_claude(candidate):
            os.remove(candidate)
            sys.exit(1)

        if path.exists():
            backup = path.parent / f"settings.json.{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}.bak"
            shutil.copy2(path, backup)
        else:
            backup = None
        shutil.move(candidate, path)

        print(f"Switched Claude Code to {args.mode} mode.")
        if backup:
            print(f"Backup: {backup}")

    print("Run /reload in the agent TUI to apply the change.")


if __name__ == "__main__":
    main()
