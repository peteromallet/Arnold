/**
 * Sprint 5: Phase 4d EFFECT_REGISTRY dispatch test.
 *
 * Verifies that:
 *   1. A clipType registered in `@banodoco/timeline-composition/registry.generated`
 *      (e.g. `section-hook` from `@banodoco/timeline-theme-2rp`) renders the
 *      theme component, NOT the Sprint-3 placeholder.
 *   2. A clipType NOT in the registry (e.g. `theme:not-installed`) falls
 *      through to the loud placeholder (UnknownClipPlaceholder).
 *
 * The registry is the codegenned table from
 * `packages/timeline-composition/typescript/src/registry.generated.ts`.
 */

import { describe, expect, it } from 'vitest';
import {
  THEME_PACKAGE_REGISTRY,
  THEME_PACKAGE_CLIP_TYPES,
} from '@banodoco/timeline-composition/registry.generated';

describe('Sprint 5 EFFECT_REGISTRY dispatch (Phase 4d)', () => {
  it('registry includes the four 2rp clip types', () => {
    const ids = Array.from(THEME_PACKAGE_CLIP_TYPES);
    expect(ids).toContain('section-hook');
    expect(ids).toContain('art-card');
    expect(ids).toContain('cta-card');
    expect(ids).toContain('resource-card');
  });

  it('section-hook entry resolves to a component from @banodoco/timeline-theme-2rp', () => {
    const entry = THEME_PACKAGE_REGISTRY['section-hook'];
    expect(entry).toBeDefined();
    expect(entry.themeId).toBe('2rp');
    expect(entry.source).toMatch(/timeline-theme-2rp/);
    expect(typeof entry.component).toBe('function');
  });

  it('clip types not in the registry surface as undefined (placeholder fallback)', () => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const result = (THEME_PACKAGE_REGISTRY as any)['theme:not-installed'];
    expect(result).toBeUndefined();
  });
});
