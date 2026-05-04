/**
 * Theme-api sub-path smoke test (Sprint 4).
 *
 * Imports from `@banodoco/timeline-composition/theme-api` as a downstream
 * theme-component would. The point is to verify the package's `exports`
 * map resolves the sub-path to the in-tree re-export module. This file is
 * type-checked via `scripts/ci-timeline-composition.sh`; we don't run it
 * via `node --test` because the ThemeContext / animations modules pull in
 * React + Remotion which the package's standalone build does not link.
 */

import {
  composeAnimations,
  useTheme,
  type EffectProps,
  type AnimationReferenceList,
  type RuntimeTheme,
} from "@banodoco/timeline-composition/theme-api";

// Compile-time assertions (no runtime call) — these only have to type-check.
type _EffectPropsCheck = EffectProps<{ kicker?: string }>;
type _AnimationListCheck = AnimationReferenceList;
type _RuntimeThemeCheck = RuntimeTheme;
const _composeAnimationsRef: typeof composeAnimations = composeAnimations;
const _useThemeRef: typeof useTheme = useTheme;

void _composeAnimationsRef;
void _useThemeRef;
declare const _e: _EffectPropsCheck;
declare const _a: _AnimationListCheck;
declare const _r: _RuntimeThemeCheck;
void _e;
void _a;
void _r;
