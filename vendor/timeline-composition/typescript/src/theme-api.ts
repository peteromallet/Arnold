/**
 * Stable public theme API (Sprint 4 surface; Sprint 5 physically lifted).
 *
 * Sprint 4 introduced this re-export to give theme components a stable import
 * sub-path (`@banodoco/timeline-composition/theme-api`) instead of deep
 * relative paths. Sprint 5 physically moved the source modules into this
 * package; the re-export shape is unchanged so theme packages migrated under
 * Sprint 4 keep compiling without churn.
 */

// effects-types — type surface for EffectProps, AnimationReferenceList,
// transition types, animation kinds, etc.
export type {
  EffectProps,
  EffectComponent,
  AnimationPhase,
  AnimationKind,
  AnimationEasing,
  AnimationReferenceObject,
  AnimationReference,
  AnimationReferenceList,
  AnimationSlots,
  AnimationMeta,
  BaseAnimationProps,
  WrapperAnimationProps,
  HookAnimationResult,
  HookAnimationProps,
  WrapperAnimationComponent,
  HookAnimationComponent,
  AnimationComponent,
  TransitionReferenceObject,
  TransitionReference,
  TransitionProps,
  TransitionComponentResult,
  TransitionComponent,
} from "./effects-types";

// lib/animations — runtime helpers that compose animation references for
// effect components. composeAnimations is the primary one used by
// themed-effect components.
export {
  composeAnimations,
  normalizeAnimationReferences,
  resolveAnimationReferences,
} from "./lib/animations";
export type {
  NormalizedAnimationReference,
  ResolvedAnimation,
  ComposeAnimationsInput,
} from "./lib/animations";

// ThemeContext — useTheme hook + types theme components use to read
// resolved theme values at render time.
export {
  ThemeProvider,
  useTheme,
  DEFAULT_THEME,
} from "./ThemeContext";
export type { Theme, RuntimeTheme } from "./ThemeContext";
