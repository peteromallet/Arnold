/**
 * @publicContract
 * SDK public-import boundary test.
 *
 * Proves that the stable @reigh/editor-sdk alias resolves to the public
 * contract re-exported from src/sdk/index.ts and that the real vendored
 * @banodoco/timeline-schema package is consumable without relying on
 * editor-internal deep imports or the Vitest shim.
 */

import { describe, expect, it } from 'vitest';

// ── Public SDK alias boundary ────────────────────────────────────────────────
// These imports must resolve through the @reigh/editor-sdk alias (wired in
// vitest.config.ts → src/sdk) and re-export the stable public contract from
// src/tools/video-editor/index.ts.  No deep @/tools/video-editor/… paths.
import {
  BUILTIN_CLIP_TYPES,
  getStableConfigSignature,
  TimelineVersionConflictError,
} from '@reigh/editor-sdk';

// ── Real vendored timeline-schema boundary ───────────────────────────────────
// Import the actual vendored package dist (not the Vitest shim) so this test
// proves the canonical @banodoco/timeline-schema artifact is consumable.
// Path is relative from src/sdk/__tests__/ to vendor/timeline-schema.
import {
  TimelineConfig,
  resolveTheme,
  deepMergeTheme,
} from '../../../vendor/timeline-schema/typescript/dist/src/index.js';

describe('SDK public-import boundary (@reigh/editor-sdk)', () => {
  it('exports BUILTIN_CLIP_TYPES as a non-empty array', () => {
    expect(Array.isArray(BUILTIN_CLIP_TYPES)).toBe(true);
    expect(BUILTIN_CLIP_TYPES.length).toBeGreaterThan(0);
  });

  it('exports getStableConfigSignature as a function', () => {
    expect(typeof getStableConfigSignature).toBe('function');
  });

  it('exports TimelineVersionConflictError as an Error class', () => {
    const err = new TimelineVersionConflictError('test', 1, 2);
    expect(err).toBeInstanceOf(Error);
    expect(err.name).toBe('TimelineVersionConflictError');
    expect(err.message).toContain('test');
  });
});

describe('Real vendored timeline-schema boundary', () => {
  it('resolves TimelineConfig zod schema from vendored dist', () => {
    // TimelineConfig is a zod schema object with .parse and .safeParse
    expect(typeof TimelineConfig.parse).toBe('function');
    expect(typeof TimelineConfig.safeParse).toBe('function');
  });

  it('parses a minimal valid TimelineConfig', () => {
    const result = TimelineConfig.safeParse({ clips: [] });
    expect(result.success).toBe(true);
  });

  it('rejects invalid TimelineConfig', () => {
    const result = TimelineConfig.safeParse({ clips: 'not-an-array' });
    expect(result.success).toBe(false);
  });

  it('exports resolveTheme as a function', () => {
    expect(typeof resolveTheme).toBe('function');
  });

  it('exports deepMergeTheme as a function', () => {
    expect(typeof deepMergeTheme).toBe('function');
  });

  it('resolveTheme returns a merged theme object', () => {
    const registry = {
      'test-theme': {
        id: 'test-theme',
        visual: { canvas: { width: 1920, height: 1080 } },
      },
    };
    const result = resolveTheme({ theme: 'test-theme' }, registry);
    expect(result).toBeDefined();
    expect(typeof result).toBe('object');
  });
});
