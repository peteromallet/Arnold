# ComfyUI Version Compatibility Support

## Overview

VibeComfy targets a specific pinned ComfyUI commit (HiddenSwitch) for all
default development, CI, and production use. Cross-version compatibility
testing — verifying that ported workflows remain correct across multiple
ComfyUI versions — is **Sprint 4 scope** and is **not enabled by default**.

## Target Channels

Four ComfyUI channels are tracked for compatibility testing:

| Channel | Identifier | Description |
|---|---|---|
| **Current** | `hiddenswitch-pinned` | The currently pinned Hiddenswitch commit. This is the active development target and the version used in all default CI. |
| **Previous** | `previous-release` | One previous release pin. Backward compatibility baseline — guards against regressions in older but still widely used ComfyUI versions. |
| **Ahead** | `ahead-candidate` | One ahead candidate commit. Forward compatibility smoke test — provides early warning of upcoming breaking changes. |
| **Upstream HEAD** | `upstream-main-head` | Upstream ComfyUI main HEAD. Bleeding edge check — informs Sprint planning for version upgrades. |

## Current State (Sprint 3)

- **Marker defined**: All compatibility tests use the `comfy_version_compat`
  pytest marker, registered in `pyproject.toml`.
- **Skipped by default**: All tests are decorated with `@pytest.mark.skipif`
  and will not execute unless explicitly opted in.
- **Offline collection**: `python -m pytest -m comfy_version_compat --collect-only`
  works without network access or ComfyUI installation.
- **Default CI unaffected**: The standard `ci.yml` workflow excludes these tests
  via `-m 'not gpu'` (which also excludes `comfy_version_compat` — only `gpu`
  tests are explicitly filtered).

## Opt-In Instructions (Local Testing)

To run cross-version compatibility tests locally:

```bash
# Set the environment variable
export COMFY_VERSION_COMPAT=1

# Run the compatibility tests
python -m pytest -m comfy_version_compat -v
```

To run a specific channel in Sprint 4 (when implemented):

```bash
# Per-channel markers will be added in Sprint 4
python -m pytest -m "comfy_version_compat and hiddenswitch_pinned" -v
```

## Sprint 4 Roadmap

In Sprint 4, the following will be implemented:

1. **Per-channel ComfyUI installation**: Automated fetching and setup of each
   channel's ComfyUI commit in isolated environments.
2. **Cross-version execution**: Full `port_convert_workflow` validation suite
   run against all four channels.
3. **Result comparison**: Diff-based comparison of outputs across channels to
   detect regressions or improvements.
4. **CI integration**: Optional matrix workflow for on-demand cross-version
   testing (not part of default PR CI).

## Related Files

- `tests/test_comfy_version_compat.py` — Marker-only collection tests
- `.github/workflows/ci.yml` — Default CI (excludes compat tests)
- `pyproject.toml` — Marker registration
