# M6: Credentials And Preflight

Overall plan difficulty: 5/5; selected profile: partnered-5; because credential leakage, false-positive auth, or bad redaction can cause security and operational failures that tests may not catch.

## Outcome

Add Arnold credential manifest/sync/preflight primitives and an AgentBox host backend so operations can verify required GitHub, Codex, Claude, Discord, and provider credentials before expensive work starts.

## Scope

In:

- define Arnold credential manifest/spec model;
- implement AgentBox host backend for `creds push`, `creds list`, `creds test`, and `creds push guide`;
- copy only named credentials to strict remote paths;
- support Codex OAuth and Claude token patterns using existing cloud credential code where possible;
- add GitHub and Discord health checks;
- add launch-time credential gate for `megaplan_chain`;
- add redaction for logs and Discord output;
- record source/destination/status/last-tested metadata without values.

Out:

- full encrypted-at-rest backend unless trivial behind the same interface;
- credential rotation automation;
- copying arbitrary `.env` files;
- multi-user secret ownership.

## Locked Decisions

- Arnold owns credential manifest, redaction, health check, audit, and consumer contracts.
- AgentBox owns host file paths and push transport.
- Sync only named credentials.
- Never dump the local environment.
- SSH keys are access credentials and are separate from runtime secrets.

## Open Questions

- Exact manifest location.
- Whether age/pass/1Password integration should be stubbed behind an interface.
- Exact credential classes required for each operation kind.

## Constraints

- Never print secret values.
- Audit every secret test/injection.
- Failed preflight blocks launch and returns the exact fix command.
- Logs and Discord output must redact known secret patterns.

## Done Criteria

- Credential tests pass/fail deterministically in local/fake environments.
- Missing or stale credentials block Discord chain launch.
- `creds list` shows names/status only.
- Codex/Claude/GitHub/Discord checks have clear error messages.
- Redaction tests cover representative tokens and auth file paths.

## Touchpoints

- `cloud/auth.py`
- cloud templates/secrets handling
- Arnold credential model
- AgentBox host provider
- runner env injection
- resident Discord output path

## Anti-Scope

- No broad `.env` copying.
- No secret values in events/logs.
- No mandatory external password manager for v0.
