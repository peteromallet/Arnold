---
name: pipeline-template
description: "Pipeline Template — Authoring Quickstart"
---

# Pipeline Template — Authoring Quickstart

Use this template to bootstrap a new Arnold pipeline package.

## Step 1: Copy the template

```bash
cp -r arnold/pipelines/_template arnold/pipelines/<your-pipeline-name>
```

The destination directory must **not** have a leading underscore (``_``-
prefixed directories are invisible to pipeline discovery — see
``arnold/pipelines/megaplan/_pipeline/registry.py:904``).

## Step 2: Rename and configure

Edit ``arnold/pipelines/<your-pipeline-name>/__init__.py``:

| Field | Action |
|---|---|
| ``name`` | Set to your pipeline's CLI-visible name (e.g. ``"my-verifier"``). |
| ``description`` | Write a meaningful one-liner. |
| ``driver`` | Choose ``"in_process"`` or a tuple like ``("my_driver",)``. |
| ``capabilities`` | Replace ``("skeleton",)`` with real capability labels. |
| ``arnold_api_version`` | Keep ``"1.0"`` unless targeting a newer SDK. |

## Step 3: Set the entrypoint

The default entrypoint is the bare name ``"build_pipeline"`` (resolved
from the package's top-level namespace).  If you prefer the colon form:

```python
entrypoint = "arnold.pipelines.<your-pipeline-name>:build_pipeline"
```

Both formats are valid — see ``docs/arnold/package-authoring-contract.md``.

## Step 4: Replace the skeleton

Open ``arnold/pipelines/<your-pipeline-name>/pipelines.py`` and replace
the stub re-export with real pipeline construction logic using
:class:`arnold.pipeline.builder.PipelineBuilder`.

Then update ``__init__.py``'s ``build_pipeline()`` to call your real
builder instead of ``build_skeleton_pipeline``.

## Step 5: Validate

```bash
arnold pipelines check <your-pipeline-name>
```

The check runs the runtime validator (``validate_package_module``) which:
- Verifies all required fields are present and well-typed.
- Resolves the entrypoint and calls ``build_pipeline()``.
- Passes the resulting graph through ``arnold.pipeline.validator.validate``.
- Reports missing recommended fields as informational advisories.

Fix any ``error:`` diagnostics before publishing.

## Recommended fields

Add these when your pipeline matures:

- ``default_profile`` — default profile name (may be ``None``).
- ``supported_modes`` — tuple of mode strings (e.g. ``("code", "doc")``).
- ``hooks`` — module-level ``ExecutorHooks`` subclass or instance.
- ``resume`` — module-level resume driver.
- ``build_continuation_pipeline`` — nullary callable returning a
  continuation ``Pipeline`` for resuming suspended runs.

These are **not** required by the runtime validator, but their absence
is reported as informational, and the static manifest reader requires
``default_profile`` and ``supported_modes``.
