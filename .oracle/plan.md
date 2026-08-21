## Final revised tasklist

1. **Preserve and prove R1** — retain the packaged `arnold` named agent and existing omp dispatch path.  
   *Acceptance:* installed package exposes `arnold`; `agent list` and `agent run arnold` succeed from repo root; no alternate runtime or dispatcher is added.

2. **Add only authorized installer overrides** — implement `install-omp-agent <template> --name <n> --description <d>` using packaged resources. Validate `^[A-Za-z0-9._-]+$`, excluding `.` and `..`.  
   *Acceptance:* filename/frontmatter name and description change while prompt bytes remain unchanged; writes are atomic and non-overwriting; unsafe names and unknown templates fail cleanly.

3. **Repair and enforce exact prompt parity** — reflow `agentbox/agents/arnold.md` from nine wrapped lines to one physical body line equal to `AgentBoxOperatorProfile.system_prompt()`, followed by exactly one LF and no blank separator after frontmatter. Mirror omp’s CRLF normalization, first-`\n---` delimiter, and `.trim()` parsing rule.  
   *Acceptance:* raw file body equals `system_prompt().encode() + b"\n"`; trimmed parsed body equals `system_prompt().encode()` without whitespace normalization; semantic edits require both surfaces plus `AGENTBOX_OPERATOR_PROMPT_VERSION` bump.

4. **Create one minimal profile-selection seam** — make `ResidentConfig.profile` a validated non-empty string, remove argparse choices, preserve built-in names/defaults, pass the resolved project root into profile loading, and reject unknown simple names.  
   *Acceptance:* CLI and environment values behave identically; invalid values produce concise `CliError` text/JSON rather than argparse/Pydantic tracebacks; built-in behavior remains unchanged.

5. **Implement deterministic, contained external loading** — support repo-relative `path.py:Class` as trusted project code. Reject absolute paths and any `..` component; apply `root.resolve(strict=True)`, `candidate.resolve(strict=True)`, and `candidate.relative_to(root)`. Use a safe stem plus SHA-256 of `root + NUL + relpath` for module identity. Guard `sys.modules` mutation and `exec_module` with an `RLock`; evict before every load and after failure.  
   *Acceptance:* the generated profile imports and constructs; symlink escapes, missing targets/classes, import failures, wrong subclasses, and incompatible constructors fail specifically; repeated and concurrent loads cannot observe stale or cross-repo modules. Documentation states imports are trusted and unsandboxed.

6. **Make dry-run validate the selected profile** — construct its dependencies and instantiate the profile before returning, while skipping token requirements, launch attestation, Discord runner/service construction, and network activity.  
   *Acceptance:* generated profiles genuinely instantiate during dry-run; import and constructor defects surface there; dry-run remains network-free.

7. **Close the inherited runtime contract** — provide `AgentBoxOperatorProfile` an injected/default `CloudCliBackend` compatible with inherited `cloud_resume`; preserve per-instance tool registries and existing store/config/authorization injection.  
   *Acceptance:* a fake backend proves `cloud_resume` works; generated subclasses retain the unchanged Discord tool catalog.

8. **[XHARD] Add one honest standalone attestation adapter** — this is in scope because R3 promises an operable standalone launcher and no existing supported provisioning path exists. Add a single `resident attest` operation, not parallel seed/attest machinery. Require a strictly resolved repo root plus explicit expected Git HEAD; compare against live HEAD; reuse canonical vector collection, schema/digest validation, atomic content-addressed storage, and receipt conventions. Represent standalone authority explicitly and domain-separate it from cloud/chain authority—never fabricate cloud markers, manifests, supervisor evidence, or allow a cloud launch to downgrade to standalone evidence. Persist seed and receipt beneath root-custodied operational state and output the validated seed path/sha for the launcher.  
   *Acceptance:* valid standalone evidence passes `require_configured_runtime_launch("resident", create=True)` and produces process attestation; wrong root/HEAD, altered vectors, stale or edited seed, and custody-mode mismatch fail closed; existing chain-start seed provisioning and validation remain byte-for-byte behaviorally unchanged.

9. **Generate exactly five readable scaffold files** — `.omp/agents/<name>.md`, `.agentbox/resident_profile.py`, `.agentbox/resident.env.example`, `.agentbox/run-resident`, and `.agentbox/<name>-resident.service`. Pre-render and preflight all destinations; launcher is executable.  
   *Acceptance:* generation creates exactly five scaffold artifacts; collisions change nothing; in-process publication failure removes only files created by that invocation; generated profile reads the project agent body and inherits Discord tools.

10. **Wire startup without weakening custody** — launcher changes to exact repo root, loads the real env file, selects the external profile, sets repo-local store state, invokes `resident attest` for the exact HEAD, exports its returned seed path, then execs resident startup. Runtime-generated seed/receipt files are operational state, not additional scaffold templates.  
   *Acceptance:* mocked live startup provisions and validates standalone attestation, creates process attestation, constructs the profile, and reaches service startup without network; missing/invalid evidence fails clearly; no waiver variable or counterfeit JSON works.

11. **Package, test, document, and evidence** — ship templates in wheel/sdist and test generation from a clean install. Cover project-agent shadowing, exact root behavior, raw parity, containment, deterministic import isolation/concurrency, cloud backend, dry-run, standalone attestation, cloud downgrade rejection, and chain-path regression.  
   *Acceptance:* targeted and affected suites pass; docs are sufficient to install, customize, attest, dry-run, and operate a second-repo resident; every R1–R3 criterion maps to evidence.

## Residual open questions

- Before implementing task 8, freeze the exact discriminator proving a launch is standalone and ensuring cloud/chain environments reject standalone authority. If existing custody primitives cannot express that without weakening production validation, stop and escalate rather than broaden or counterfeit the contract.
- Confirm the repo-owned state directory and permissions for immutable content-addressed seeds and receipts; reuse an existing convention if one exists.

## North Star check

This advances one omp runtime through one constrained profile seam and an unavoidable, fail-closed standalone custody adapter. It explicitly rejects runtime re-architecture, magic scaffolding, flag soup, compatibility renames, omp changes, Discord tool mutation, prompt normalization, attestation bypass/counterfeiting, unrelated purge work, and `main` mutation.
tokens used
42,738
## Final revised tasklist

1. **Preserve and prove R1** — retain the packaged `arnold` named agent and existing omp dispatch path.  
   *Acceptance:* installed package exposes `arnold`; `agent list` and `agent run arnold` succeed from repo root; no alternate runtime or dispatcher is added.

2. **Add only authorized installer overrides** — implement `install-omp-agent <template> --name <n> --description <d>` using packaged resources. Validate `^[A-Za-z0-9._-]+$`, excluding `.` and `..`.  
   *Acceptance:* filename/frontmatter name and description change while prompt bytes remain unchanged; writes are atomic and non-overwriting; unsafe names and unknown templates fail cleanly.

3. **Repair and enforce exact prompt parity** — reflow `agentbox/agents/arnold.md` from nine wrapped lines to one physical body line equal to `AgentBoxOperatorProfile.system_prompt()`, followed by exactly one LF and no blank separator after frontmatter. Mirror omp’s CRLF normalization, first-`\n---` delimiter, and `.trim()` parsing rule.  
   *Acceptance:* raw file body equals `system_prompt().encode() + b"\n"`; trimmed parsed body equals `system_prompt().encode()` without whitespace normalization; semantic edits require both surfaces plus `AGENTBOX_OPERATOR_PROMPT_VERSION` bump.

4. **Create one minimal profile-selection seam** — make `ResidentConfig.profile` a validated non-empty string, remove argparse choices, preserve built-in names/defaults, pass the resolved project root into profile loading, and reject unknown simple names.  
   *Acceptance:* CLI and environment values behave identically; invalid values produce concise `CliError` text/JSON rather than argparse/Pydantic tracebacks; built-in behavior remains unchanged.

5. **Implement deterministic, contained external loading** — support repo-relative `path.py:Class` as trusted project code. Reject absolute paths and any `..` component; apply `root.resolve(strict=True)`, `candidate.resolve(strict=True)`, and `candidate.relative_to(root)`. Use a safe stem plus SHA-256 of `root + NUL + relpath` for module identity. Guard `sys.modules` mutation and `exec_module` with an `RLock`; evict before every load and after failure.  
   *Acceptance:* the generated profile imports and constructs; symlink escapes, missing targets/classes, import failures, wrong subclasses, and incompatible constructors fail specifically; repeated and concurrent loads cannot observe stale or cross-repo modules. Documentation states imports are trusted and unsandboxed.

6. **Make dry-run validate the selected profile** — construct its dependencies and instantiate the profile before returning, while skipping token requirements, launch attestation, Discord runner/service construction, and network activity.  
   *Acceptance:* generated profiles genuinely instantiate during dry-run; import and constructor defects surface there; dry-run remains network-free.

7. **Close the inherited runtime contract** — provide `AgentBoxOperatorProfile` an injected/default `CloudCliBackend` compatible with inherited `cloud_resume`; preserve per-instance tool registries and existing store/config/authorization injection.  
   *Acceptance:* a fake backend proves `cloud_resume` works; generated subclasses retain the unchanged Discord tool catalog.

8. **[XHARD] Add one honest standalone attestation adapter** — this is in scope because R3 promises an operable standalone launcher and no existing supported provisioning path exists. Add a single `resident attest` operation, not parallel seed/attest machinery. Require a strictly resolved repo root plus explicit expected Git HEAD; compare against live HEAD; reuse canonical vector collection, schema/digest validation, atomic content-addressed storage, and receipt conventions. Represent standalone authority explicitly and domain-separate it from cloud/chain authority—never fabricate cloud markers, manifests, supervisor evidence, or allow a cloud launch to downgrade to standalone evidence. Persist seed and receipt beneath root-custodied operational state and output the validated seed path/sha for the launcher.  
   *Acceptance:* valid standalone evidence passes `require_configured_runtime_launch("resident", create=True)` and produces process attestation; wrong root/HEAD, altered vectors, stale or edited seed, and custody-mode mismatch fail closed; existing chain-start seed provisioning and validation remain byte-for-byte behaviorally unchanged.

9. **Generate exactly five readable scaffold files** — `.omp/agents/<name>.md`, `.agentbox/resident_profile.py`, `.agentbox/resident.env.example`, `.agentbox/run-resident`, and `.agentbox/<name>-resident.service`. Pre-render and preflight all destinations; launcher is executable.  
   *Acceptance:* generation creates exactly five scaffold artifacts; collisions change nothing; in-process publication failure removes only files created by that invocation; generated profile reads the project agent body and inherits Discord tools.

10. **Wire startup without weakening custody** — launcher changes to exact repo root, loads the real env file, selects the external profile, sets repo-local store state, invokes `resident attest` for the exact HEAD, exports its returned seed path, then execs resident startup. Runtime-generated seed/receipt files are operational state, not additional scaffold templates.  
   *Acceptance:* mocked live startup provisions and validates standalone attestation, creates process attestation, constructs the profile, and reaches service startup without network; missing/invalid evidence fails clearly; no waiver variable or counterfeit JSON works.

11. **Package, test, document, and evidence** — ship templates in wheel/sdist and test generation from a clean install. Cover project-agent shadowing, exact root behavior, raw parity, containment, deterministic import isolation/concurrency, cloud backend, dry-run, standalone attestation, cloud downgrade rejection, and chain-path regression.  
   *Acceptance:* targeted and affected suites pass; docs are sufficient to install, customize, attest, dry-run, and operate a second-repo resident; every R1–R3 criterion maps to evidence.

## Residual open questions

- Before implementing task 8, freeze the exact discriminator proving a launch is standalone and ensuring cloud/chain environments reject standalone authority. If existing custody primitives cannot express that without weakening production validation, stop and escalate rather than broaden or counterfeit the contract.
- Confirm the repo-owned state directory and permissions for immutable content-addressed seeds and receipts; reuse an existing convention if one exists.

## North Star check

This advances one omp runtime through one constrained profile seam and an unavoidable, fail-closed standalone custody adapter. It explicitly rejects runtime re-architecture, magic scaffolding, flag soup, compatibility renames, omp changes, Discord tool mutation, prompt normalization, attestation bypass/counterfeiting, unrelated purge work, and `main` mutation.
