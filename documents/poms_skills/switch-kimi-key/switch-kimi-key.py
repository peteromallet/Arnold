#!/usr/bin/env python3
"""Switch Kimi Code CLI between managed OAuth/plan mode and API-key modes.

Modes:
  managed  - Kimi Code OAuth/plan provider (api.kimi.com/coding/v1)
  api-key  - Direct Kimi Code API key (api.kimi.com/coding/v1)
  platform - Moonshot Open Platform API key (api.moonshot.ai/v1 or .cn/v1)
"""

import argparse
import datetime
import os
import re
import shutil
import subprocess
import sys


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
    host = "api.moonshot.ai" if region == "ai" else "api.moonshot.cn"
    return f'''[models."moonshot/kimi-k2.7-code"]
provider = "moonshot"
model = "kimi-k2.7-code"
max_context_size = 262144
capabilities = [ "thinking", "always_thinking", "image_in", "video_in", "tool_use" ]
display_name = "K2.7 Code"
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


def _replace_section(text, header_pattern, new_block):
    """Replace a top-level TOML section and any sub-tables under it."""
    pattern = (
        f"^({header_pattern})"
        r'.*?'
        r'(?=^\[(?!\1\.)[^\]]+\]|\Z)'
    )
    flags = re.MULTILINE | re.DOTALL
    if not re.search(pattern, text, flags):
        return text, False
    return re.sub(pattern, new_block, text, count=1, flags=flags), True


def _set_default_model(text, model):
    return re.sub(
        r'^default_model\s*=\s*".*?"',
        f'default_model = "{model}"',
        text,
        count=1,
        flags=re.MULTILINE,
    )


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


def rewrite_config(text, mode, key=None, region="ai"):
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
    else:
        raise ValueError(f"Unknown mode: {mode}")

    # Remove any existing provider/model/services sections so we can rewrite cleanly.
    text = _remove_section(text, r'providers\."managed:kimi-code"')
    text = _remove_section(text, r'providers\.moonshot')
    text = _remove_section(text, r'models\."kimi-code/kimi-for-coding"')
    text = _remove_section(text, r'models\."moonshot/kimi-k2\.7-code"')
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


def main():
    parser = argparse.ArgumentParser(description="Switch Kimi Code CLI provider mode")
    parser.add_argument(
        "mode",
        choices=["managed", "api-key", "platform"],
        help="Provider mode",
    )
    parser.add_argument(
        "key",
        nargs="?",
        help=(
            "API key (api-key/platform mode). "
            "If omitted, reads from KIMI_SWITCH_API_KEY env var or stdin."
        ),
    )
    parser.add_argument(
        "--region",
        choices=["ai", "cn"],
        default="ai",
        help="Moonshot Open Platform region (platform mode only). Default: ai",
    )
    args = parser.parse_args()

    if args.mode in ("api-key", "platform"):
        args.key = read_key(args)
        if not args.key:
            parser.error("API key is required for api-key/platform mode")

    path = config_path()
    if not os.path.exists(path):
        raise SystemExit(f"Config not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        original = f.read()

    try:
        new_text = rewrite_config(
            original, args.mode, key=args.key, region=args.region
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
