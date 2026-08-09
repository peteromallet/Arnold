# M2: Parity And Delete

## Outcome

Supported Megaplan behavior and the clean-break deletion are landed on `main` in commit `1052ef091a`. The legacy `arnold/pipelines/megaplan` implementation root is absent, not merely reduced to a stub, and this brief now records post-hoc parity verification plus remaining closeout gates. No permanent shims remain.

## Scope

In:

- Canonical CLI smoke for the registered `init` and `status` subparsers, the real run-phase verb `execute`, and supported subcommands. `run` and `config` are not registered on the canonical path: `parse_args(['run'])` and `parse_args(['config'])` exit `SystemExit 2`, and there is no `config` subcommand.
- Chain compatibility: load/save state, chain start/status/resume, remote sync snippets, PR helper flows, and cloud/supervisor one-liners.
- Resume/status compatibility for existing `.megaplan/plans` and `.megaplan/briefs` state.
- Worker compatibility: Codex, Hermes, Shannon, process env, and engine-write isolation gates.
- Discovery/package compatibility: every migrated Megaplan pipeline row points at shipped canonical modules and builder targets resolve in editable and wheel installs.
- Docs/skills/generated assets sweep so humans and agents use `python -m arnold_pipelines.megaplan`. Follow up on the stale `run`/`config` references still advertised at `docs/pipelines.md:120` and `docs/configuration.md:9`.
- Installed-wheel smoke tests proving `arnold/pipelines/megaplan` is absent and all supported canonical entrypoints work.
- Verify the remaining legacy-file, temporary-shim, stale-doc, generated-asset, root `SKILL.md`, `_codex_skills` symlink, `__pycache__`, and deleted-path-reference surfaces. Scope the deletion claim to the absent `arnold/pipelines/megaplan` root; the parent `arnold/pipelines/` legitimately retains `_authoring.py` and `evidence_pack/`.

Out:

- No permanent shims.
- No broad compatibility package.
- No last-minute behavior rewrites unrelated to deletion.
- Do not reintroduce previously rejected dirty changes such as local host turn-cap behavior.

## Done Criteria

- `[Verified on current main]` Canonical `init` and `status` subparsers are registered and smoke-tested; the run-phase verb is `execute`; `run` and `config` are not registered (`parse_args(['run'])` and `parse_args(['config'])` exit `SystemExit 2`), and there is no `config` subcommand.
- `[Post-hoc verification required]` Chain, resume/status, worker, discovery, docs, editable-install, and wheel-install gates remain required proof surfaces. Current evidence verifies the five canonical builder rows statically, but installed-wheel/editable smoke still must be run before final closeout.
- `[Verified on current main, 1052ef091a]` `arnold/pipelines/megaplan` is absent. This is the stronger clean-break result, not an accepted migration-error stub.
- `[Verified on current main]` The legacy `arnold_pipelines.megaplan._pipeline.registry` namespace is deleted. This is distinct from the canonical non-empty `arnold_pipelines/megaplan/pipeline_ids.json`, which retains five keep rows.
- `[Verified on current main]` Source/test/doc/skill scans show no unapproved legacy path usage through `arnold/conformance/checks.py` and `arnold/conformance/legacy_reference_allowlist.json`; all 134 allowlist entries are live and `stale=[]`.
- `[OPEN]` `git status --porcelain` still has symlink/type churn: eight bundled skill symlinks under `arnold_pipelines/megaplan/skills/` were rewritten from relative to absolute targets. Restore them to relative targets with `git checkout` before treating this gate as clean; that code-side fix is outside this documentation edit.
- `[OPEN follow-up]` Correct the stale `run`/`config` advertisements in `docs/pipelines.md:120` and `docs/configuration.md:9`.
- `[OPEN follow-up]` Review `skills/subagent-launcher/SKILL.md:73`, which still names the deleted `arnold.pipelines.megaplan.agent` path; correct it to the canonical path or past tense and recategorize its allowlist entry.
