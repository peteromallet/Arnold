#!/usr/bin/env python3
"""Switch Kimi Code CLI between provider modes.

Modes:
  managed  - Kimi Code OAuth/plan provider (api.kimi.com/coding/v1)
  api-key  - Direct Kimi Code API key (api.kimi.com/coding/v1)
  platform - Moonshot Open Platform API key (api.moonshot.ai/v1 or .cn/v1)
  glm      - Zhipu GLM-5.2 via OpenAI-compatible endpoint
"""

import argparse
import datetime
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


def config_path():
    home = os.environ.get("KIMI_CODE_HOME")
    if home:
        return os.path.join(home, "config.toml")
    return os.path.join(os.path.expanduser("~"), ".kimi-code", "config.toml")


MANAGED_BLOCK = '''[providers."managed:kimi-code"]
type = "kimi"
api_key = ""
base_url = "https://api.kimi.com/coding/v1"

[providers."managed:kimi-code".oauth]
storage = "file"
key = "oauth/kimi-code"

'''


def api_key_block(key):
    return f'''[providers."managed:kimi-code"]
type = "kimi"
api_key = {key!r}
base_url = "https://api.kimi.com/coding/v1"

'''


def platform_block(key, region="ai"):
    host = "api.moonshot.ai" if region == "ai" else "api.moonshot.cn"
    return f'''[providers.moonshot]
type = "kimi"
api_key = {key!r}
base_url = "https://{host}/v1"

'''


MODEL_MANAGED = '''[models."kimi-code/kimi-for-coding"]
provider = "managed:kimi-code"
model = "kimi-for-coding"
max_context_size = 262144
capabilities = [ "thinking", "always_thinking", "image_in", "video_in", "tool_use" ]
display_name = "K2.7 Code"
'''


def model_platform(region="ai"):
    return f'''[models."moonshot/kimi-k2.7-code"]
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


def glm_block(key, base_url):
    return f'''[providers.glm]
type = "openai"
api_key = {key!r}
base_url = "{base_url}"

'''


def services_managed():
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


def services_platform(region="ai"):
    host = "api.moonshot.ai" if region == "ai" else "api.moonshot.cn"
    return f'''[services.moonshot_search]
base_url = "https://{host}/v1/search"
api_key = ""

[services.moonshot_fetch]
base_url = "https://{host}/v1/fetch"
api_key = ""
'''


def services_glm(base_url):
    # GLM does not expose the same search/fetch services as Kimi. Leave them
    # configured against the GLM base URL so any service calls at least have
    # a provider, even if they may not be supported by GLM.
    search_url = base_url.rstrip("/") + "/search"
    fetch_url = base_url.rstrip("/") + "/fetch"
    return f'''[services.moonshot_search]
base_url = "{search_url}"
api_key = ""

[services.moonshot_fetch]
base_url = "{fetch_url}"
api_key = ""
'''


def _remove_section(text, header_pattern):
    """Remove a top-level TOML section and any sub-tables under it.

    header_pattern is the inner table name regex, e.g.
    r'providers\\."managed:kimi-code"'.
    """
    pattern = (
        r'^\[('
        + header_pattern
        + r')\]'
        r'.*?'
        r'(?=^\[(?!\1\.)[^\]]+\]|\Z)'
    )
    flags = re.MULTILINE | re.DOTALL
    return re.sub(pattern, '', text, count=1, flags=flags)


def _set_default_model(text, model):
    return re.sub(
        r'^default_model\s*=\s*".*?"',
        f'default_model = "{model}"',
        text,
        count=1,
        flags=re.MULTILINE,
    )


def load_env_key(env_path, env_vars):
    """Read the first matching key from a .env file.

    Mirrors the minimal parser in _load_hermes_env: KEY=value, optional quotes,
    skip comments and blank lines.
    """
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


def rewrite_config(text, mode, key=None, region="ai", glm_base_url=None):
    if mode == "managed":
        provider_block = MANAGED_BLOCK
        model_block = MODEL_MANAGED
        services_block = services_managed()
        default_model = "kimi-code/kimi-for-coding"
    elif mode == "api-key":
        provider_block = api_key_block(key)
        model_block = MODEL_MANAGED
        services_block = services_managed().replace('api_key = ""', f'api_key = {key!r}')
        default_model = "kimi-code/kimi-for-coding"
    elif mode == "platform":
        provider_block = platform_block(key, region)
        model_block = model_platform(region)
        services_block = services_platform(region).replace('api_key = ""', f'api_key = {key!r}')
        default_model = "moonshot/kimi-k2.7-code"
    elif mode == "glm":
        provider_block = glm_block(key, glm_base_url)
        model_block = MODEL_GLM
        services_block = services_glm(glm_base_url).replace('api_key = ""', f'api_key = {key!r}')
        default_model = "glm/glm-5.2"
    else:
        raise ValueError(f"Unknown mode: {mode}")

    # Remove any existing provider/model/services sections so we can rewrite cleanly.
    text = _remove_section(text, r'providers\."managed:kimi-code"')
    text = _remove_section(text, r'providers\.moonshot')
    text = _remove_section(text, r'providers\.glm')
    text = _remove_section(text, r'models\."kimi-code/kimi-for-coding"')
    text = _remove_section(text, r'models\."moonshot/kimi-k2\.7-code"')
    text = _remove_section(text, r'models\."glm/glm-5\.2"')
    text = _remove_section(text, r'services\.moonshot_search')
    text = _remove_section(text, r'services\.moonshot_fetch')

    # Append the new blocks.
    text = text.rstrip() + "\n\n" + provider_block + model_block + "\n" + services_block + "\n"

    # Update default_model.
    text = _set_default_model(text, default_model)

    return text


def read_key(args):
    key = args.key
    if not key:
        key = os.environ.get("KIMI_SWITCH_API_KEY")
    if not key and not sys.stdin.isatty():
        key = sys.stdin.read().strip()
    return key


def resolve_glm_key(args):
    """Find a GLM API key from argv, env var, or a .env file.

    Returns the key, or None if no key was found.
    """
    key = read_key(args)
    if key:
        return key

    env_path = Path(args.env_file).expanduser()
    env_vars = [v.strip() for v in args.env_var.split(",") if v.strip()]
    return load_env_key(env_path, env_vars)


def main():
    parser = argparse.ArgumentParser(description="Switch Kimi Code CLI provider mode")
    parser.add_argument(
        "mode",
        choices=["managed", "api-key", "platform", "glm"],
        help="Provider mode",
    )
    parser.add_argument(
        "key",
        nargs="?",
        help=(
            "API key (api-key/platform/glm mode). "
            "If omitted, reads from KIMI_SWITCH_API_KEY env var, stdin, or a .env file."
        ),
    )
    parser.add_argument(
        "--region",
        choices=["ai", "cn"],
        default="ai",
        help="Moonshot Open Platform region (platform mode only). Default: ai",
    )
    parser.add_argument(
        "--env-file",
        default="~/Documents/megaplan/.env",
        help="Path to a .env file to read the GLM key from (glm mode). Default: ~/Documents/megaplan/.env",
    )
    parser.add_argument(
        "--env-var",
        default="ZHIPU_API_KEY,GLM_API_KEY,BIGMODEL_API_KEY",
        help="Comma-separated env var names to look for in --env-file (glm mode).",
    )
    parser.add_argument(
        "--glm-base-url",
        default="https://open.bigmodel.cn/api/paas/v4",
        help="GLM OpenAI-compatible base URL (glm mode). Default: https://open.bigmodel.cn/api/paas/v4",
    )
    args = parser.parse_args()

    if args.mode in ("api-key", "platform"):
        args.key = read_key(args)
        if not args.key:
            parser.error("API key is required for api-key/platform mode")
    elif args.mode == "glm":
        args.key = resolve_glm_key(args)
        if not args.key:
            env_path = Path(args.env_file).expanduser()
            env_vars = [v.strip() for v in args.env_var.split(",") if v.strip()]
            parser.error(
                "GLM API key is required. Pass it as an argument, set KIMI_SWITCH_API_KEY, "
                f"or ensure one of {env_vars} is set in {env_path}."
            )

    path = config_path()
    if not os.path.exists(path):
        raise SystemExit(f"Config not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        original = f.read()

    try:
        new_text = rewrite_config(
            original,
            args.mode,
            key=args.key,
            region=args.region,
            glm_base_url=args.glm_base_url,
        )
    except Exception as exc:
        print(f"error: could not rewrite config: {exc}", file=sys.stderr)
        sys.exit(1)

    candidate = path + ".candidate"
    with open(candidate, "w", encoding="utf-8") as f:
        f.write(new_text)

    result = subprocess.run(
        ["kimi", "doctor", "config", candidate],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print("Validation failed:", file=sys.stderr)
        print(result.stdout, file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        os.remove(candidate)
        sys.exit(1)

    backup = f"{path}.{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}.bak"
    shutil.copy2(path, backup)
    shutil.move(candidate, path)

    print(f"Switched to {args.mode} mode.")
    print(f"Backup: {backup}")
    print("Run /reload in the Kimi Code TUI to apply the change.")


if __name__ == "__main__":
    main()
