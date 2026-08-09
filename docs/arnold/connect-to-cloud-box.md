# Connecting a new machine to the Megaplan Cloud box

How to get a second computer (using your ChatGPT/Codex account) onto the
Megaplan Cloud worker — both an interactive shell and the `megaplan cloud`
"drive it from this laptop" path.

This is the short guide. The full reference is
`arnold_pipelines/megaplan/skills/megaplan-cloud/SKILL.md` and `docs/cloud.md`.

## TL;DR

You need three things on the new machine:

1. **An SSH key the box trusts** (to get onto the box at all).
2. **A checkout of this repo** (for `megaplan cloud`, or just to read `cloud.yaml`).
3. **A ChatGPT/Codex account** (to authorize codex on the box — billed to your
   subscription, not a metered API key).

The box: `root@159.69.51.216:22` (Hetzner), container `megaplan-cloud-agent`,
workspace volume `/workspace`.

---

## Part 1 — SSH onto the box

The box authenticates by **SSH key only** (root login, port 22). There is no
password. So the new machine needs a private key whose public half is in the
box's `/root/.ssh/authorized_keys`.

### Method A — reuse the existing key (fastest)

If you're fine with one key shared across machines, copy the Mac's private key
to the new machine:

```bash
# on the Mac (or wherever ~/.ssh/id_ed25519 lives)
# transfer id_ed25519 to the new machine's ~/.ssh/ (e.g. via 1Password, a USB
# stick, or scp to a machine you already trust) — never email/git it.
chmod 600 ~/.ssh/id_ed25519
```

Then on the new machine:

```bash
ssh root@159.69.51.216         # should drop you straight in
```

Downside: one key in two places. If one machine is lost, rotate the key
everywhere.

### Method B — add a new key for the new machine (recommended)

Generate a fresh keypair on the new machine and authorize it on the box. Do the
authorization from a machine that already has access (e.g. the Mac):

```bash
# 1. on the NEW machine
ssh-keygen -t ed25519 -C "arnold-cloud@<new-machine>"   # leave passphrase set
cat ~/.ssh/id_ed25519.pub                               # copy this

# 2. on a machine that ALREADY has box access (e.g. the Mac)
ssh root@159.69.51.216
# inside the box:
nano /root/.ssh/authorized_keys      # paste the new pubkey on its own line
exit
```

Now the new machine connects with its own key:

```bash
# on the NEW machine
ssh root@159.69.51.216
```

### Optional: an ssh config alias

There's no alias today (the `runpod` alias in `~/.ssh/config` points at a stale
box — don't use it). Add one on the new machine:

```
# ~/.ssh/config
Host megaplan-cloud
    HostName 159.69.51.216
    User root
    Port 22
    IdentityFile ~/.ssh/id_ed25519
    StrictHostKeyChecking accept-new
```

Then `ssh megaplan-cloud`.

### Get into the container

The megaplan worker runs inside Docker. From the box (or directly):

```bash
ssh root@159.69.51.216 'docker exec -it megaplan-cloud-agent bash'
```

You're now root inside `/workspace`.

---

## Part 2 — Authorize Codex on the box (ChatGPT account)

The cloud worker runs Codex (GPT-5.x) phases via the `codex exec` CLI, and you
want them billed to your **ChatGPT subscription** — not a metered API key.
`megaplan.codex_auth: chatgpt` (the default in `cloud.yaml`) forces the
subscription path.

### Why a fresh `device-auth` login, not copying a token

You *can* copy `~/.codex/auth.json` from a logged-in laptop onto the box (the
`cloud deploy` / `cloud chain` seed step does this automatically). **Don't do
that for a long-lived box.** Codex OAuth uses a refresh token, and the same
refresh token can't be used by your laptop *and* the box at the same time — one
session will invalidate the other ("the Mac token cycles out"). The fix that
sticks is to give the **box its own session**.

### Steps — give the box its own Codex session

From a machine with box access, get a shell inside the container and run the
device login:

```bash
ssh root@159.69.51.216 'docker exec -it megaplan-cloud-agent bash'

# inside the container:
codex login              # opens a device-code flow; follow the URL + enter the code
                         # (flag may be `codex login --device-auth` depending on version;
                         # run `codex login --help` to confirm)
cat ~/.codex/auth.json   # confirm it has "auth_mode": "chatgpt" (or similar) — not apikey
```

### Make it survive container restarts (important)

`/root` inside the container is **ephemeral** — a restart wipes `~/.codex/auth.json`.
The entrypoint re-seeds from the persistent volume path on every boot, so copy
your fresh login there:

```bash
# still inside the container:
install -m 600 ~/.codex/auth.json /workspace/.creds/codex-auth.json
```

Now `docker restart megaplan-cloud-agent` (or a host reboot) will reinstall it
automatically (see `entrypoint.sh.tmpl:52-57`).

### Verify it's really on the subscription backend

A stray `OPENAI_API_KEY` silently routes codex to metered billing. Confirm:

```bash
RUST_LOG=debug codex exec --sandbox read-only --skip-git-repo-check "ok" 2>&1 \
  | grep -iE 'chatgpt.com/backend-api/codex|api.openai.com'
```

You want `chatgpt.com/backend-api/codex`, **not** `api.openai.com`. If you see
the latter, ensure `/root/.codex/config.toml` has
`preferred_auth_method = "chatgpt"` and that `OPENAI_API_KEY` isn't overriding
it (it shouldn't, given the config, but a dead key there causes
`Quota exceeded` errors).

### Alternative: a Codex Access Token (no refresh contention)

If you're on ChatGPT Business/Enterprise, mint a **Codex Access Token**
(7/30/60/90-day) and set it as `CODEX_ACCESS_TOKEN` on the box. This avoids the
refresh-token-sharing problem entirely and is the cleanest multi-machine setup.

---

## Part 3 — (Optional) Drive the box from the new laptop

If "connect to it" means *run `megaplan cloud` from this new laptop and have it
launch chains on the existing box*, you don't need codex on the laptop at all —
the laptop just SSHes the box and the box does the model calls.

On the new machine:

```bash
git clone https://github.com/peteromallet/Arnold.git && cd Arnold
# editable install so tooling sees live code:
pip install -e .

# confirm you can reach the box over SSH (Part 1), then observe:
megaplan cloud status --all --cloud-yaml .megaplan/initiatives/<initiative>/cloud.yaml

# get an interactive view of a running chain:
megaplan cloud attach   --cloud-yaml .megaplan/initiatives/<initiative>/cloud.yaml
megaplan cloud logs     --cloud-yaml .megaplan/initiatives/<initiative>/cloud.yaml
megaplan cloud exec     --cloud-yaml .megaplan/initiatives/<initiative>/cloud.yaml 'docker ps'
```

You only need worker secrets (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`,
`DEEPSEEK_API_KEY`, etc.) in the **laptop's** env if a `cloud.yaml` lists them
under `secrets:`. Your `cloud.yaml`s have `secrets: []`, which means *values are
already set on the box* and the laptop needs none of them. Keep it that way.

For the full launch flow (`initiative new` → `cloud preflight` → `cloud chain`),
follow `arnold_pipelines/megaplan/skills/megaplan-cloud/SKILL.md`.

---

## Privacy: what's actually secret vs. exposed

Honest audit of each piece:

| Asset | Where it lives | In git? | Verdict |
|---|---|---|---|
| API keys (`.env`: OpenRouter, DeepSeek, etc.) | repo root `.env` | **No** — gitignored (`.gitignore:42-45`) | ✅ Private |
| SSH private key (`id_ed25519`) | `~/.ssh/` on your machine(s) only | No | ✅ Private |
| Codex `auth.json` / OAuth refresh token | `~/.codex/auth.json` (laptop) + `/workspace/.creds/` (box) | No | ✅ Private (don't commit) |
| Box IP `159.69.51.216` + `root` + port `22` | every `cloud.yaml` | **Yes** — and the repo is **PUBLIC** | ⚠️ Exposed |

**The one real exposure:** the repo is public, so the box's IP, root username,
and SSH port are world-readable in every `cloud.yaml`. That's not a credential
leak (no password or key is committed — `cloud.yaml` only has `host`/`user`/
`port`), but it does paint a target on SSH port 22 for scanners. Since auth is
key-only, knowing the IP alone won't get anyone in. Still, harden it:

- Add a **Hetzner Cloud Firewall** (or host `ufw`) that allows TCP/22 only from
  your known IPs, **or**
- move SSH off port 22, **or**
- install `fail2ban` for brute-force protection.

No other secret is reachable from the public repo. The things you'd actually
worry about (keys, tokens) are all gitignored or live only on the machines.

---

## Gotchas

- **`runpod` ssh alias is stale.** It points at `213.173.102.176:12592`. Use
  `159.69.51.216` directly, or the `megaplan-cloud` alias from Part 1.
- **Don't copy the Mac's `auth.json` to the box as the primary auth.** It shares
  a refresh token and one side cycles out. Use the box's own `codex login`
  (Part 2), or a `CODEX_ACCESS_TOKEN`.
- **A codex login inside the container is wiped on restart** unless you also
  `install -m 600 ~/.codex/auth.json /workspace/.creds/codex-auth.json`.
- **`OPENAI_API_KEY` on the box hijacks codex onto metered billing** even when
  you intend the subscription — that's the usual cause of
  `Quota exceeded. Check your plan and billing details.` The `chatgpt` auth
  config overrides it; just don't be surprised if a stale key is set.
- **`secrets: []` is deliberate.** Listing secrets in `cloud.yaml` makes
  `cloud deploy` push your local env values (possibly empty) and overwrite what's
  on the box. Leave it empty; the box already has its secrets.
