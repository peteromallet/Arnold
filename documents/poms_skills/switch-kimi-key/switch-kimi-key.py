#!/usr/bin/env python3
"""Switch Kimi Code CLI between managed OAuth/plan mode and API-key mode."""

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


def replace_provider_block(text, new_block):
    # Match the managed:kimi-code provider block and its sub-tables,
    # stopping at the next top-level table that is not a sub-table of this provider.
    pattern = (
        r'^\[providers\."managed:kimi-code"\]'
        r'.*?'
        r'(?=^\[(?!providers\."managed:kimi-code"\.)[^\]]+\]|\Z)'
    )
    flags = re.MULTILINE | re.DOTALL
    if not re.search(pattern, text, flags):
        raise SystemExit('Could not find [providers."managed:kimi-code"] block in config')
    return re.sub(pattern, new_block, text, count=1, flags=flags)


def main():
    parser = argparse.ArgumentParser(description="Switch Kimi Code CLI provider mode")
    parser.add_argument("mode", choices=["managed", "api-key"], help="Provider mode")
    parser.add_argument(
        "key",
        nargs="?",
        help=(
            "API key (api-key mode). "
            "If omitted, reads from KIMI_SWITCH_API_KEY env var or stdin."
        ),
    )
    args = parser.parse_args()

    if args.mode == "api-key" and not args.key:
        args.key = os.environ.get("KIMI_SWITCH_API_KEY")
    if args.mode == "api-key" and not args.key:
        if not sys.stdin.isatty():
            args.key = sys.stdin.read().strip()
    if args.mode == "api-key" and not args.key:
        parser.error("API key is required for api-key mode")

    path = config_path()
    if not os.path.exists(path):
        raise SystemExit(f"Config not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        original = f.read()

    new_block = MANAGED_BLOCK if args.mode == "managed" else api_key_block(args.key)
    new_text = replace_provider_block(original, new_block)

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
