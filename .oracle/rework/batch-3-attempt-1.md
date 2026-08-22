# Batch 3 Rework — Attempt 1

## 1. CLI profile validation bypass

**Finding + evidence:** Blocking. `arnold_pipelines/megaplan/resident/cli.py:703-710` tests `if profile:` and uses `model_copy(update=updates)`. Consequently, `--profile ""` is ignored and whitespace bypasses the validator, unlike environment input covered at `tests/agentbox/test_resident_profile.py:646-662`.

**Criterion + North Star:** T4 and Batch 3’s identical CLI/environment behavior with concise `CliError` rejection; R3. Principle: **One runtime, one seam**.

**Required outcome + scope:** In `_resident_config`, apply the override when `profile is not None`, then rebuild with `ResidentConfig.model_validate({**config.model_dump(), **updates})`. Preserve `ValidationError` mapping to JSON `invalid_args`. Add CLI parity regressions for empty and whitespace profiles. Scope: resident CLI and focused tests only.

**Classification:** normal. This is a localized validation-boundary correction without architectural or security redesign.

**Selected model:** `codex:gpt-5.6-luna`.

**Acceptance + exact validation:** CLI and environment values `""` and `"   "` return `invalid_args`, never default silently, and emit no traceback; valid built-ins remain unchanged.

```bash
python -m pytest tests/agentbox/test_resident_profile.py -q -k invalid_profile
```

## 2. Resolution exceptions escape `CliError`

**Finding + evidence:** Blocking. `resident/cli.py:1228-1248` catches only `FileNotFoundError`/`OSError` around both `resolve(strict=True)` calls. Symlink loops can raise `RuntimeError`; embedded NULs can raise `ValueError`, producing tracebacks.

**Criterion + North Star:** T5 strict resolved-root containment and specific failures; Batch 3’s precise-rejection checkpoint; R3. Principle: **One runtime, one seam**.

**Required outcome + scope:** Catch `RuntimeError` and `ValueError` around root and candidate resolution, mapping them to the existing resolution/containment `CliError` codes. Add root/candidate regressions for both exception types, asserting exact JSON codes and no traceback. Do not alter containment, locking, module identity, or imports.

**Classification:** normal. This is bounded exception normalization, not a trust-boundary redesign.

**Selected model:** `codex:gpt-5.6-luna`.

**Acceptance + exact validation:**

```bash
python -m pytest tests/agentbox/test_resident_profile.py -q -k 'resolution or symlink or containment'
python -m pytest tests/agentbox/test_cli.py tests/agentbox/test_resident_profile.py -q
```
tokens used
44,353
# Batch 3 Rework — Attempt 1

## 1. CLI profile validation bypass

**Finding + evidence:** Blocking. `arnold_pipelines/megaplan/resident/cli.py:703-710` tests `if profile:` and uses `model_copy(update=updates)`. Consequently, `--profile ""` is ignored and whitespace bypasses the validator, unlike environment input covered at `tests/agentbox/test_resident_profile.py:646-662`.

**Criterion + North Star:** T4 and Batch 3’s identical CLI/environment behavior with concise `CliError` rejection; R3. Principle: **One runtime, one seam**.

**Required outcome + scope:** In `_resident_config`, apply the override when `profile is not None`, then rebuild with `ResidentConfig.model_validate({**config.model_dump(), **updates})`. Preserve `ValidationError` mapping to JSON `invalid_args`. Add CLI parity regressions for empty and whitespace profiles. Scope: resident CLI and focused tests only.

**Classification:** normal. This is a localized validation-boundary correction without architectural or security redesign.

**Selected model:** `codex:gpt-5.6-luna`.

**Acceptance + exact validation:** CLI and environment values `""` and `"   "` return `invalid_args`, never default silently, and emit no traceback; valid built-ins remain unchanged.

```bash
python -m pytest tests/agentbox/test_resident_profile.py -q -k invalid_profile
```

## 2. Resolution exceptions escape `CliError`

**Finding + evidence:** Blocking. `resident/cli.py:1228-1248` catches only `FileNotFoundError`/`OSError` around both `resolve(strict=True)` calls. Symlink loops can raise `RuntimeError`; embedded NULs can raise `ValueError`, producing tracebacks.

**Criterion + North Star:** T5 strict resolved-root containment and specific failures; Batch 3’s precise-rejection checkpoint; R3. Principle: **One runtime, one seam**.

**Required outcome + scope:** Catch `RuntimeError` and `ValueError` around root and candidate resolution, mapping them to the existing resolution/containment `CliError` codes. Add root/candidate regressions for both exception types, asserting exact JSON codes and no traceback. Do not alter containment, locking, module identity, or imports.

**Classification:** normal. This is bounded exception normalization, not a trust-boundary redesign.

**Selected model:** `codex:gpt-5.6-luna`.

**Acceptance + exact validation:**

```bash
python -m pytest tests/agentbox/test_resident_profile.py -q -k 'resolution or symlink or containment'
python -m pytest tests/agentbox/test_cli.py tests/agentbox/test_resident_profile.py -q
```
