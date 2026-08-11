> **Authority status (T44):** Zero-authority — the commands below are illustrative operator guidance; all live authority runs through canonical delegation (megaplan CLI / managed-agent seam). This document is not an authoritative execution surface.

# Letting another user run a Codex agent on your Megaplan Cloud box

Scenario: **a teammate is accessing your existing box** (`root@159.69.51.216`,
container `megaplan-cloud-agent`, workspace `/workspace`). Not spinning up a new
instance — they're joining yours.

The short version: **the only thing the new user has to give you is their SSH
public key.** Everything the worker needs is already provisioned on the box, and
once they're on, they use *your* codex session, *your* GitHub token, and *your*
trusted-container flag.

Companion: `docs/arnold/connect-to-cloud-box.md` (SSH + codex-login basics),
`arnold_pipelines/megaplan/skills/megaplan-cloud/SKILL.md` (full reference).

## What the new user needs vs. what's already on your box

| Need | Already on the box? | Does the new user bring anything? |
|---|---|---|
| **SSH access** (the gate) | Your key is in `authorized_keys` | ✅ **Their SSH public key** — the one thing they must provide. You add it. |
| Codex / ChatGPT session | ✅ box has a `codex` session at `/root/.codex/auth.json` | No — their `codex exec` calls bill to **your** ChatGPT subscription. |
| GitHub token | ✅ `GITHUB_TOKEN` is set in the box env | No — their commits/pushes attribute to **your** GitHub account. |
| Trusted-container flag | ✅ `MEGAPLAN_TRUSTED_CONTAINER=1` | No. |
| Other model keys (Anthropic, DeepSeek, …) | ✅ whatever you've set | No. |

So: **they bring an SSH pubkey; you bring everything else (by sharing the box).**

## Steps

### You (the owner) — add them, once
1. Get their public key (`id_ed25519.pub` / `id_rsa.pub`).
2. Append it to the box's root authorized_keys:
   ```bash
   ssh root@159.69.51.216
   nano /root/.ssh/authorized_keys     # paste their pubkey on its own line
   ```

### Them — get a key, send it, then connect

**1. Check for an existing key** (skip to step 3 if they already have one):
```bash
ls ~/.ssh/id_ed25519.pub ~/.ssh/id_rsa.pub 2>/dev/null
```

**2. Generate a keypair** (only if step 1 printed nothing):
```bash
ssh-keygen -t ed25519 -C "their-email@example.com"
# press Enter to accept the default path; set a passphrase (recommended)
```
`ssh-keygen` ships with macOS, Linux, and Windows 10+ (OpenSSH). On Windows use
Git Bash, WSL, or PowerShell.

**3. Send the owner their PUBLIC key:**
```bash
cat ~/.ssh/id_ed25519.pub
```
Copy the entire line (starts with `ssh-ed25519 …`) and send it to the owner.
**Send only the `.pub` file — never the private key** (`~/.ssh/id_ed25519`, no
`.pub`). Anyone with the private key has full access; the public key is safe to
share in chat/email.

→ The owner adds it to the box (see above). ←

**4. Connect** (once the owner confirms it's added):
```bash
ssh root@159.69.51.216
```
- First connect prompts to verify the host fingerprint — type `yes`.
- If it asks for a **password**, the key isn't authorized yet (or ssh is using the
  wrong local key) — ping the owner / check step 3.
- It should drop you straight into a root shell with no password.

Optional `~/.ssh/config` alias so they don't type the IP:
```
# ~/.ssh/config
Host megaplan-cloud
    HostName 159.69.51.216
    User root
    IdentityFile ~/.ssh/id_ed25519
    StrictHostKeyChecking accept-new
```
Then `ssh megaplan-cloud`.

**5. Into the worker container:**
```bash
docker exec -it megaplan-cloud-agent bash
```

**6. Sanity-check that codex + the chain respond:**
```bash
megaplan cloud status --all --cloud-yaml /workspace/<initiative>/Arnold/.megaplan/initiatives/<initiative>/cloud.yaml
```
They launch/observe chains with the normal `megaplan cloud …` commands.

## Important: what "shared box" really means

Everyone SSHes in as **`root`** — there's no per-user OS account. So:

- **Shared billing & identity.** Their codex calls bill your ChatGPT subscription
  and their git pushes go out under your GitHub token. That's usually fine for a
  trusted collaborator — just know it's happening. If you want them to self-bill
  or commit as themselves, that needs extra setup (see below); the default is
  they ride yours.
- **Don't let them re-login codex.** A second `codex login` on the box would
  **overwrite** the shared `/root/.codex/auth.json` and knock *your* session out
  (refresh tokens can't be shared). If they need their own codex identity, use a
  separate workspace with its own env (below) — not a second login on shared root.
- **Root = full trust.** Once on, they can read every secret on the box (your
  tokens, keys, the resident env). Only add someone you'd trust with all of it.
  Least-privilege (separate non-root user, restricted sudo) is a bigger change and
  out of scope here.

## Running concurrently without collisions
The box can host multiple chains at once, but two mutating chains in the **same**
checkout collide. Give the new user their own:
- **workspace path** (`/workspace/<their-name>/<repo>/`), and
- **`chain_session:`** (tmux session name) in their `cloud.<chain>.yaml`.

Keep `merge_policy: auto` + `driver.auto_approve: true` for unattended cloud epics.

## If you *do* want them to bring their own credentials
(Optional — only if shared billing/identity isn't acceptable.)
- **Their own ChatGPT billing:** have them mint a **Codex Access Token**
  (`CODEX_ACCESS_TOKEN`, ChatGPT Business/Enterprise, 7/30/60/90-day) and set it
  in *their* workspace's env — not by re-logging-in codex on shared root.
- **Their own GitHub identity:** set their own `GITHUB_TOKEN` in their workspace's
  env before launch (box-level token is the fallback).
- Cleanest long-term: a separate OS user per person — but that's a real refactor.

## Verify codex is on the subscription (not metered) — anyone can check
```bash
RUST_LOG=debug codex exec --sandbox read-only --skip-git-repo-check "ok" 2>&1 \
  | grep -iE 'chatgpt.com/backend-api/codex|api.openai.com'
```
Want `chatgpt.com/backend-api/codex`, not `api.openai.com`.
