#!/usr/bin/env python3
"""Send an admin DM via the Arnold Discord bot.

Usage: discord_admin_notify.py "message text"
Env: DISCORD_BOT_TOKEN, DISCORD_DM_USER_ID (both present in /workspace/.cloud-hot-env
on the agentbox). Safe to re-run; failures exit nonzero with a short reason.
"""
import json
import os
import sys
import urllib.request
import urllib.error

BASE = "https://discord.com/api/v10"


def _api(token: str, path: str, payload: dict | None = None) -> dict:
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={
            "Authorization": f"Bot {token}",
            "Content-Type": "application/json",
        },
        method="POST" if payload is not None else "GET",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def main() -> int:
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        print("usage: discord_admin_notify.py MESSAGE", file=sys.stderr)
        return 2
    token = (os.environ.get("DISCORD_BOT_TOKEN") or "").strip()
    user = (os.environ.get("DISCORD_DM_USER_ID") or "").strip()
    fallback_channel = (
        os.environ.get("DISCORD_ADMIN_CHANNEL_ID") or ""
    ).strip()
    msg = sys.argv[1][:1900]
    if not token:
        print("error: DISCORD_BOT_TOKEN not set", file=sys.stderr)
        return 3
    # Prefer a DM; Discord 403s DM-channel creation when the admin's privacy
    # settings block it or no mutual guild exists — then fall back to posting
    # in the configured guild text channel with an @admin mention.
    try:
        dm = _api(token, "/users/@me/channels", {"recipient_id": user})
        _api(token, f"/channels/{dm['id']}/messages", {"content": msg})
        print(f"delivered admin DM ({len(msg)} chars) -> user {user}")
        return 0
    except urllib.error.HTTPError as exc:
        if exc.code != 403 or not fallback_channel:
            raise
    _api(token, f"/channels/{fallback_channel}/messages",
         {"content": f"<@{user}> {msg}"})
    print(f"DM forbidden; delivered fallback channel message ({len(msg)} chars)"
          f" -> channel {fallback_channel}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
