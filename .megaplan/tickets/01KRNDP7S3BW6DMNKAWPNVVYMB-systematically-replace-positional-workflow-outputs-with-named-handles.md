---
id: 01KRNDP7S3BW6DMNKAWPNVVYMB
title: Systematically replace positional workflow outputs with named handles
status: open
source: human
tags:
- workflow-porting
- developer-experience
- validation
- tech-debt
codebase_id: null
created_at: '2026-05-15T08:57:43.972038+00:00'
last_edited_at: '2026-05-15T08:57:43.972038+00:00'
epics: []
---

Problem

Pure-Python ready templates still contain positional handle calls such as `guider.out(0)`, `concat.out(0)`, `sampled.out(1)`, and test assertions against raw node ids. This makes imported workflows feel like transliterated JSON rather than authored Python, and it hides meaning that Comfy schemas often already know through `RETURN_NAMES`, output labels, or stable node semantics. The immediate example is `ready_templates/video/ltx2_3_lightricks_first_last_parity.py`, where the LTX guide outputs were named but the sampler/latent/audio/video spine still uses numeric outputs.

Why this matters

The numbering issue is not cosmetic. Positional outputs make workflow review and parity work slower, make regressions easier when a node output order changes, and encourage raw JSON/node-id patching instead of understandable workflow code. For every workflow, the Python source should communicate the dataflow: `sampled.out("denoised_output")`, `concat.out("latent")`, `checkpoint.out("vae")`, etc. Numeric `.out(n)` should be reserved for genuinely unnamed or unknown outputs and should be visible as a validation warning.

Right level of fix

Do not solve this one template at a time only. Fix it at the VibeComfy workflow import/emitter/doctor layer so every workflow benefits:

1. Schema ingestion should preserve output names from Comfy node metadata whenever available (`RETURN_NAMES`, output display names, or equivalent object-info data).
2. The Python emitter should emit `_outputs=(...)` for imported nodes with known names and should generate named `.out("...")` references instead of `.out(0)` when a handle name is available.
3. The ready-template doctor should report avoidable positional outputs in pure-Python templates, distinguishing:
   - allowed: unknown node schema or intentionally positional legacy compatibility;
   - warning/error: node has known output names but the template uses numeric output access.
4. The converter should provide a repair mode or suggested patch mapping for existing templates, so onboarding/forking workflows can move from JSON-like output slots to readable Python without manual archaeology.
5. The skill/README workflow-onboarding docs should make this the default path: import -> enrich with schema -> emit named Python -> run doctor -> only accept positional outputs when justified.

Acceptance criteria

- Existing LTX first/last parity template uses named outputs across the sampler/latent/audio/video spine where names are known.
- The converter/emitter can produce named-output Python from a workflow plus schema provider.
- A repository-level validation command can find avoidable numeric `.out(n)` calls across `ready_templates/`.
- The validation output is actionable: it names the file, node variable/class/id, numeric slot, and suggested output name.
- Documentation explains why named outputs matter and how agents/developers should run the import/repair/check loop for new, forked, and existing workflows.

Non-goals

- Do not invent unstable names for outputs when schema data is genuinely unavailable. In those cases the tool should leave `.out(n)` and make the uncertainty explicit.
- Do not force one workflow architecture. This is about making dataflow handles readable and validated, not constraining how workflows are authored.

