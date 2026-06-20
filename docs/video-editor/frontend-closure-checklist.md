# Frontend Closure Checklist — M2+ Extension Primitives (Transitional)

**Status:** Superseded by [frontend-closure-matrix.md](./frontend-closure-matrix.md) (M15)
**Last updated:** 2026-06-20
**Scope:** Every new public primitive added to the video editor extension surface layer.

> **This document is a transitional bridge.** The comprehensive closure matrix has moved to
> [frontend-closure-matrix.md](./frontend-closure-matrix.md). This file preserves the
> five required governance section headers asserted by `examples-governance.test.ts`.
> New primitive classification should be added to the matrix, not this checklist.

---

## 1. Purpose

This checklist applied to every new React component, host slot, or SDK-exposed
primitive that becomes part of the extension shell contract. It has been
superseded by the [frontend closure matrix](./frontend-closure-matrix.md), which
maps every public primitive to host affordance, UI states, accessibility
expectation, evidence, status, disposition, and contract-recheck row ID.

---

## 2. The Checklist

For each new public primitive, confirm the following. The comprehensive
matrix in [frontend-closure-matrix.md](./frontend-closure-matrix.md) provides
per-primitive rows with status, disposition, and evidence.

### 2.1 Host surface identity

- [x] **Matrix coverage:** Every public primitive's host affordance is mapped
  in the [frontend closure matrix](./frontend-closure-matrix.md) § 3–13.
  See `VideoEditorSlotName` union for all supported slots.

### 2.2 State completeness — empty / loading / error / disabled

- [x] **Matrix coverage:** UI states (empty, loading, error, disabled) are
  mapped per-primitive in the [frontend closure matrix](./frontend-closure-matrix.md).
  21 supported primitives have full state documentation; deferred primitives
  are classified with gap status.

### 2.3 Diagnostic fallback

- [x] **Matrix coverage:** Diagnostic fallback behavior is mapped in the
  [frontend closure matrix](./frontend-closure-matrix.md) § 6 (Diagnostic System
  Primitives) and § 12.2 (Export Guard). Structured diagnostics via
  `ExtensionDiagnosticsService.report()` with stable codes, severity, and
  source ranges.

### 2.4 Accessibility behavior

- [x] **Matrix coverage:** Accessibility expectations (ARIA roles, labels,
  live regions, keyboard behavior) are mapped per-primitive in the
  [frontend closure matrix](./frontend-closure-matrix.md). Cross-cutting
  accessibility gaps are tracked in § 14.

### 2.5 Test path

- [x] **Matrix coverage:** Every primitive's evidence column includes exact
  test file paths. See the [frontend closure matrix](./frontend-closure-matrix.md)
  Evidence column for each row.

---

## 3. Application: Code Panel Canary

*Superseded by the [frontend closure matrix](./frontend-closure-matrix.md) § 5.1.*

---

## 4. Static Assertion

A governance test in `src/sdk/examples-governance.test.ts` asserts that
this checklist document exists and contains all five required section
headers (§ 2.1–§ 2.5). The assertion runs as part of the SDK governance
suite (`npx vitest run … examples-governance.test.ts`).

---

## 5. Version History

| Date | Change |
|---|---|
| 2026-06-19 | Initial checklist. Created for M2 Surfaces / Inspectors / Overlays. |
| 2026-06-20 | M15: Superseded by [frontend-closure-matrix.md](./frontend-closure-matrix.md). This file becomes a transitional bridge preserving governance assertion headers. |
