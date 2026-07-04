# M2 Security Broker — Threat Model

## Scope

This threat model covers credential exposure risks addressed by the M2 Security Broker
milestone. It does **not** cover fleet-level sandboxing, DB-backed durable approval storage,
or full non-LLM credential brokering, which are deferred to later milestones (M4–M6).

## Assets

| Asset | Sensitivity | Exposure Paths |
|-------|-------------|----------------|
| Git PAT / push credentials | **Critical** | Environment variables, MCP subprocess env, agent tool invocations, logs |
| LLM API keys (OpenAI, Anthropic, DeepSeek, etc.) | **Critical** | `env_loader.py`, `KeyPool.acquire()`, `auxiliary_client.py`, provider client init |
| OAuth refresh tokens (Nous Portal, Codex, Anthropic OAuth) | **Critical** | `~/.hermes/auth.json`, token storage on disk |
| GitHub read-only tokens (skills hub) | **High** | `skills_hub.py` `GitHubAuth`, env vars (`GITHUB_TOKEN`, `GH_TOKEN`), `gh` CLI |
| MCP server credentials (PATs, API keys in config) | **High** | `config.yaml` `mcp_servers.*.env`, subprocess environment |
| Non-LLM tool credentials (ElevenLabs, FAL.ai, Firecrawl, Groq) | **Medium** | Environment variables, tool module init |
| Terminal SSH keys / `gh` keychain | **Medium** | `terminal_tool.py` subprocess, agent-initiated shell commands |

## Threat Actors

| Actor | Capability | Motivation |
|-------|-----------|------------|
| **Compromised agent prompt** | Can invoke any registered tool, including terminal | Exfiltrate credentials via tool outputs, logs, or side-channels |
| **Malicious skill bundle** | Code executed during skill installation/scanning | Access env vars, filesystem, or network from agent process |
| **MCP server exploit** | Malicious or compromised MCP server | Extract credentials from subprocess environment or request payloads |
| **Log/audit consumer** | Reads agent logs, audit NDJSON, or broker responses | Extract raw credentials from unsanitized output |
| **Insider/operator error** | Accidental `env` dump, `cat .env`, `print(os.environ)` | Expose credentials in terminal output or shared logs |

## Attack Vectors

### AV1: Agent-initiated credential exfiltration via terminal
- **Description**: An agent prompt instructs the terminal tool to run `env`, `cat ~/.hermes/.env`,
  `gh auth token`, or `cat ~/.hermes/auth.json`.
- **M2 Coverage**: **Uncovered (deferred)**. Terminal/SSH/`gh` bypasses are documented as
  residual risk. Mitigation requires fleet-level sandboxing (M5–M6) that restricts agent
  subprocess access to credential-bearing files and environment variables.
- **Residual Risk**: **High**. An agent with terminal access can read any file or env var
  that the agent process uid can access.
- **Mitigation (future)**: Worker sandboxing, seccomp filters, mount namespace isolation.

### AV2: Credential exposure via broker response or audit log
- **Description**: The broker returns raw credentials in `ActionResult` fields, or audit
  NDJSON records contain unsanitized PATs/API keys.
- **M2 Coverage**: **Covered**. `ActionResult` sanitizes `summary` and `metadata` on
  construction via `redact_text()` and `redact_mapping()`. Audit records inherit
  redaction from the action result.
- **Residual Risk**: **Low**. The redaction pipeline uses regex-based scrubbing and
  sensitive-key masking. Token patterns (`sk-*`, `ghp_*`, `github_pat_*`, `Bearer *`)
  are matched before serialization.

### AV3: Git push to protected branch bypassing broker
- **Description**: Agent constructs a `git push origin main` command via the terminal tool
  using a PAT injected from the environment, bypassing the broker entirely.
- **M2 Coverage**: **Partially covered**. The broker denies `git_push` to protected branches
  when routed through `SecurityPolicy.evaluate()`. However, terminal-based `git push` with
  SSH keys or `gh` keychain is an **uncovered bypass** for M2.
- **Residual Risk**: **Medium**. Git push via terminal is not intercepted. True protection
  requires broker-as-sidecar intercepting all git operations at the transport layer (M5–M6).

### AV4: LLM API key exposure through provider client
- **Description**: `KeyPool.acquire()` returns a raw API key string. If this key is logged,
  included in error messages, or reflected in agent-visible provider client output, it is
  exposed.
- **M2 Coverage**: **Covered** for API-key providers. The broker proxies LLM requests so
  raw keys never reach the agent process. `resolve_provider_client()` returns a broker-backed
  client in production mode.
- **Residual Risk**: **Low** for covered providers. OAuth/refresh-token providers
  (Nous, Codex, Anthropic OAuth) are deferred to M5–M6.

### AV5: Skills hub token exfiltration
- **Description**: `skills_hub.py` `GitHubAuth` resolves tokens from `GITHUB_TOKEN`/`GH_TOKEN`
  env vars or `gh auth token` subprocess. A compromised skill or prompt could extract
  this token.
- **M2 Coverage**: **Uncovered (deferred)**. `skills_hub.py` GitHubAuth is classified as
  non-production uncovered. The GitHub token used for skill fetching is a read-only
  API access token, not a push-class mutation credential.
- **Residual Risk**: **Low–Medium**. Read-only GitHub tokens have limited blast radius,
  but token theft could enable private repo enumeration.

### AV6: MCP server credential injection
- **Description**: MCP server configs in `~/.hermes/config.yaml` include `GITHUB_PERSONAL_ACCESS_TOKEN`
  or `Authorization: Bearer sk-...` headers. These are passed to subprocess environments.
- **M2 Coverage**: **Uncovered (deferred)**. MCP subprocess credentials are not brokered.
  The agent process reads config.yaml and passes env to MCP subprocesses directly.
- **Residual Risk**: **Medium**. A compromised MCP server or prompt-injected MCP tool call
  can expose subprocess credentials.

### AV7: Non-LLM tool credential leakage
- **Description**: ElevenLabs (`ELEVENLABS_API_KEY`), FAL.ai (`FAL_KEY`), Firecrawl
  (`FIRECRAWL_API_KEY`), Groq (`GROQ_API_KEY`), and other non-LLM tool credentials
  are read from environment variables at tool invocation time.
- **M2 Coverage**: **Uncovered (deferred)**. Non-LLM tool credentials are classified
  as documented-uncovered for M2.
- **Residual Risk**: **Medium**. These credentials are in the agent process environment
  and could be exfiltrated via any of the attack vectors above.

## Trust Boundaries

```
┌─────────────────────────────────────────────────────────┐
│  Agent Process (untrusted for credential storage)       │
│  ┌─────────────┐  ┌──────────┐  ┌───────────────────┐  │
│  │ Terminal    │  │ Skills   │  │ Non-LLM Tools     │  │
│  │ (SSH/gh)    │  │ Hub      │  │ (TTS,Img,Search)  │  │
│  └──────┬──────┘  └────┬─────┘  └────────┬──────────┘  │
│         │              │                 │              │
│         ▼              ▼                 ▼              │
│  ┌──────────────────────────────────────────────────┐   │
│  │        Environment / Config / Keychain           │   │
│  │  (PATs, API keys, OAuth tokens — RAW ACCESS)    │   │
│  └──────────────────────┬───────────────────────────┘   │
│                         │                               │
│  ┌──────────────────────┼───────────────────────────┐   │
│  │   MCP Subprocesses   │   Provider Clients        │   │
│  │   (raw env injection)│   (raw KeyPool keys)      │   │
│  └──────────────────────┴───────────────────────────┘   │
└─────────────────────────┬───────────────────────────────┘
                          │
        ─ ─ ─ ─ ─ Broker Boundary ─ ─ ─ ─ ─
                          │
┌─────────────────────────▼───────────────────────────────┐
│  Broker Process (trusted for credential storage)        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ Git Policy   │  │ LLM Proxy    │  │ Redaction    │  │
│  │ (push-class) │  │ (API-key)    │  │ Pipeline     │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
│                                                         │
│  ┌──────────────────────────────────────────────────┐   │
│  │        Credential Vault (broker-owned)           │   │
│  │  (Git PATs, LLM API keys — NEVER in agent proc) │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

## Risk Acceptance

The following risks are **explicitly accepted** for M2 and deferred to later milestones:

1. **Terminal/SSH/`gh` bypasses** → M5–M6 fleet sandboxing
2. **OAuth/refresh-token providers** → M5–M6 provider credential brokering
3. **`skills_hub.py` GitHubAuth** → M5–M6 (read-only, low blast radius)
4. **MCP subprocess credentials** → M5–M6 (requires broker-as-sidecar transport layer)
5. **Non-LLM tool credentials** → M5–M6 full credential brokering
6. **DB-backed durable approval storage** → M4

Each deferred path is recorded in `coverage_matrix.py` with its residual risk classification.
