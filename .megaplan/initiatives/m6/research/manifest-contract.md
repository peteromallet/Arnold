# M6 Pipeline Manifest Contract

M6 discovery reads pipeline identity from module-level constants without
importing the module. The manifest reader parses Python with `ast.parse` and
extracts literal assignments with `ast.literal_eval`; rejected manifests return a
catalogued `Disposition` reason and must not fall through to `exec_module`.

Required constants:

- `description`: human-readable pipeline summary.
- `name`: CLI-visible pipeline name.
- `default_profile`: profile name or `None`.
- `supported_modes`: tuple/list of mode strings.
- `driver`: literal driver descriptor for the runtime substrate.
- `entrypoint`: callable symbol name, normally `build_pipeline`.
- `arnold_api_version`: semver `major.minor`, currently accepted in `[1.0, 2.0)`.
- `capabilities`: tuple/list of capability strings.

Required shape:

- A top-level callable matching `entrypoint` must be present.
- A sibling `SKILL.md` must exist. Package pipelines use
  `<package>/SKILL.md`; sibling-file pipelines use
  `<parent>/<hyphenated-cli-name>/SKILL.md`, falling back to
  `<parent>/SKILL.md` for simple single-file packages.
- Non-literal manifest values are rejected rather than imported.
- Malformed Python, missing required fields, missing `entrypoint`, missing
  `SKILL.md`, and out-of-range `arnold_api_version` are loud rejections.

Execution discipline:

- `scan_python_pipelines()` is the non-raising catalog API. It reports every
  path as `discovered`, `rejected`, or `skipped`.
- With `MEGAPLAN_M6_MANIFEST_DISCOVERY=1`, discovered builders are deferred.
  The registry may list metadata without importing pipeline code.
- `PipelineRegistry.get()` is the trust gate. In-tree and blessed paths may
  execute; out-of-tree quarantined paths return `None` with a warning unless
  explicitly promoted.
- Out-of-tree pipeline metadata carries deterministic tenant/quota fields so
  untrusted packages cannot consume the parent run budget without reservation.
