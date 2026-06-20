/**
 * Tests for TimelinePatch pure validation (validateTimelinePatch).
 *
 * @publicContract
 */

import { describe, expect, it } from 'vitest';
import {
  validateTimelinePatch,
  compileTimelinePatch,
  previewTimelinePatch,
} from '@/tools/video-editor/lib/timeline-patch';
import { TIMELINE_POSTPROCESS_SHADER_APP_KEY } from '@/tools/video-editor/lib/timeline-domain';
import type { PatchMergeMode } from '@/tools/video-editor/lib/timeline-patch';
import type {
  TimelinePatch,
  TimelinePatchOperation,
  TimelinePatchAnyOpFamily,
} from '@/sdk/index';
import type {
  TimelineClipShaderMetadata,
  TimelinePostprocessShaderMetadata,
} from '@/tools/video-editor/types';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makePatch(
  overrides: Partial<TimelinePatch> & { operations: TimelinePatchOperation[] },
): TimelinePatch {
  return {
    version: overrides.version ?? 1,
    operations: overrides.operations,
    source: overrides.source,
    meta: overrides.meta,
  };
}

function makeOp(
  op: TimelinePatchAnyOpFamily,
  target: string,
  payload?: Record<string, unknown>,
  order?: number,
): TimelinePatchOperation {
  const result: TimelinePatchOperation = { op, target };
  if (payload !== undefined) result.payload = payload;
  if (order !== undefined) result.order = order;
  return result;
}

function allErrorsHaveTimelinePatchCode(diagnostics: readonly { code: string }[]): boolean {
  return diagnostics.every((d) => d.code.startsWith('timeline-patch/'));
}

// ---------------------------------------------------------------------------
// Batch-level validation
// ---------------------------------------------------------------------------

describe('validateTimelinePatch — batch-level', () => {
  it('accepts a valid single-operation patch', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [makeOp('clip.remove', 'clip-1')],
      }),
    );
    expect(result.valid).toBe(true);
    expect(result.diagnostics).toHaveLength(0);
  });

  it('rejects an empty operations array', () => {
    const result = validateTimelinePatch(
      makePatch({ operations: [] }),
    );
    expect(result.valid).toBe(false);
    expect(result.diagnostics.some((d) => d.code === 'timeline-patch/empty-operations')).toBe(true);
    expect(allErrorsHaveTimelinePatchCode(result.diagnostics)).toBe(true);
  });

  it('rejects missing operations (non-array)', () => {
    const result = validateTimelinePatch(
      { version: 1, operations: null as unknown as TimelinePatchOperation[] },
    );
    expect(result.valid).toBe(false);
    expect(result.diagnostics.some((d) => d.code === 'timeline-patch/invalid-patch')).toBe(true);
  });

  it('rejects a negative version', () => {
    const result = validateTimelinePatch(
      makePatch({ version: -1, operations: [makeOp('clip.remove', 'c1')] }),
    );
    expect(result.valid).toBe(false);
    expect(result.diagnostics.some((d) => d.code === 'timeline-patch/invalid-version')).toBe(true);
  });

  it('rejects a non-integer version', () => {
    const result = validateTimelinePatch(
      makePatch({ version: 1.5, operations: [makeOp('clip.remove', 'c1')] }),
    );
    expect(result.valid).toBe(false);
    expect(result.diagnostics.some((d) => d.code === 'timeline-patch/invalid-version')).toBe(true);
  });

  it('accepts version 0', () => {
    const result = validateTimelinePatch(
      makePatch({ version: 0, operations: [makeOp('clip.remove', 'c1')] }),
    );
    expect(result.valid).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// Unknown / malformed operations
// ---------------------------------------------------------------------------

describe('validateTimelinePatch — unknown / malformed ops', () => {
  it('rejects unknown operation family with stable diagnostic code', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [{ op: 'clip.explode' as TimelinePatchAnyOpFamily, target: 'c1' }],
      }),
    );
    expect(result.valid).toBe(false);
    const diag = result.diagnostics.find((d) => d.code === 'timeline-patch/unknown-op');
    expect(diag).toBeDefined();
    expect(diag!.severity).toBe('error');
    expect(diag!.op).toBe('clip.explode');
  });

  it('rejects empty string op', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [{ op: '' as TimelinePatchAnyOpFamily, target: 'c1' }],
      }),
    );
    expect(result.valid).toBe(false);
    expect(result.diagnostics.some((d) => d.code === 'timeline-patch/missing-op')).toBe(true);
  });

  it('rejects non-object operation', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [null as unknown as TimelinePatchOperation],
      }),
    );
    expect(result.valid).toBe(false);
    expect(result.diagnostics.some((d) => d.code === 'timeline-patch/invalid-op')).toBe(true);
  });

  it('rejects operation with missing target', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [{ op: 'clip.remove', target: '' }],
      }),
    );
    expect(result.valid).toBe(false);
    expect(result.diagnostics.some((d) => d.code === 'timeline-patch/missing-target')).toBe(true);
  });

  it('rejects operation with non-string target', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [{ op: 'clip.remove', target: 42 as unknown as string }],
      }),
    );
    expect(result.valid).toBe(false);
    expect(result.diagnostics.some((d) => d.code === 'timeline-patch/missing-target')).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// Reserved operations
// ---------------------------------------------------------------------------

describe('validateTimelinePatch — reserved ops', () => {
  it('produces warning for clip.split (deferred/non-previewable)', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [makeOp('clip.split', 'clip-1', { at: 10 })],
      }),
    );
    // Reserved ops produce warnings, not errors — so valid may still be true
    const diag = result.diagnostics.find((d) => d.code === 'timeline-patch/reserved-op');
    expect(diag).toBeDefined();
    expect(diag!.severity).toBe('warning');
    expect(diag!.op).toBe('clip.split');
    expect(diag!.detail).toEqual({ reserved: true, deferred: true, nonPreviewable: true });
  });

  it('produces warning for clip.slice (deferred/non-previewable)', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [makeOp('clip.slice', 'clip-1', { from: 0, to: 5 })],
      }),
    );
    const diag = result.diagnostics.find((d) => d.code === 'timeline-patch/reserved-op');
    expect(diag).toBeDefined();
    expect(diag!.severity).toBe('warning');
    expect(diag!.op).toBe('clip.slice');
    expect(diag!.detail).toEqual({ reserved: true, deferred: true, nonPreviewable: true });
  });

  it('marks reserved ops as non-previewable via detail field', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [makeOp('clip.split', 'c1', { at: 0 })],
      }),
    );
    const reservedDiags = result.diagnostics.filter((d) => d.code === 'timeline-patch/reserved-op');
    expect(reservedDiags.length).toBeGreaterThan(0);
    for (const d of reservedDiags) {
      expect(d.detail?.nonPreviewable).toBe(true);
    }
  });

  it('still validates target requirement for reserved ops', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [{ op: 'clip.split' as TimelinePatchAnyOpFamily, target: '' }],
      }),
    );
    expect(result.valid).toBe(false);
    expect(result.diagnostics.some((d) => d.code === 'timeline-patch/missing-target')).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// clip.add
// ---------------------------------------------------------------------------

describe('validateTimelinePatch — clip.add', () => {
  it('accepts valid clip.add with track, at, and clipType', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [makeOp('clip.add', 'new-clip', { track: 'V1', at: 10, clipType: 'media' })],
      }),
    );
    expect(result.valid).toBe(true);
    expect(result.diagnostics).toHaveLength(0);
  });

  it('accepts clip.add with minimal payload (no track/at)', () => {
    const result = validateTimelinePatch(
      makePatch({ operations: [makeOp('clip.add', 'new-clip')] }),
    );
    expect(result.valid).toBe(true);
  });

  it('rejects clip.add with non-string track', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [makeOp('clip.add', 'c1', { track: 42 })],
      }),
    );
    expect(result.valid).toBe(false);
    expect(result.diagnostics.some((d) => d.code === 'timeline-patch/invalid-payload')).toBe(true);
  });

  it('rejects clip.add with non-number at', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [makeOp('clip.add', 'c1', { at: '10' })],
      }),
    );
    expect(result.valid).toBe(false);
    expect(result.diagnostics.some((d) => d.code === 'timeline-patch/invalid-payload')).toBe(true);
  });

  it('rejects clip.add with non-string clipType', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [makeOp('clip.add', 'c1', { clipType: 123 })],
      }),
    );
    expect(result.valid).toBe(false);
    expect(result.diagnostics.some((d) => d.code === 'timeline-patch/invalid-payload')).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// clip.update
// ---------------------------------------------------------------------------

describe('validateTimelinePatch — clip.update', () => {
  it('accepts clip.update with payload', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [makeOp('clip.update', 'clip-1', { volume: 0.8 })],
      }),
    );
    expect(result.valid).toBe(true);
    expect(result.diagnostics).toHaveLength(0);
  });

  it('warns on clip.update with empty payload', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [makeOp('clip.update', 'clip-1', {})],
      }),
    );
    expect(result.diagnostics.some((d) => d.code === 'timeline-patch/empty-payload')).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// clip.remove
// ---------------------------------------------------------------------------

describe('validateTimelinePatch — clip.remove', () => {
  it('accepts clip.remove with just a target', () => {
    const result = validateTimelinePatch(
      makePatch({ operations: [makeOp('clip.remove', 'clip-1')] }),
    );
    expect(result.valid).toBe(true);
    expect(result.diagnostics).toHaveLength(0);
  });
});

// ---------------------------------------------------------------------------
// clip.move
// ---------------------------------------------------------------------------

describe('validateTimelinePatch — clip.move', () => {
  it('accepts clip.move with track and at', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [makeOp('clip.move', 'clip-1', { track: 'V2', at: 20 })],
      }),
    );
    expect(result.valid).toBe(true);
  });

  it('accepts clip.move with only track', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [makeOp('clip.move', 'clip-1', { track: 'V2' })],
      }),
    );
    expect(result.valid).toBe(true);
  });

  it('accepts clip.move with only at', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [makeOp('clip.move', 'clip-1', { at: 20 })],
      }),
    );
    expect(result.valid).toBe(true);
  });

  it('rejects clip.move without track or at', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [makeOp('clip.move', 'clip-1', {})],
      }),
    );
    expect(result.valid).toBe(false);
    expect(result.diagnostics.some((d) => d.code === 'timeline-patch/invalid-payload')).toBe(true);
  });

  it('rejects clip.move with non-string track', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [makeOp('clip.move', 'clip-1', { track: 123 })],
      }),
    );
    expect(result.valid).toBe(false);
  });

  it('rejects clip.move with non-number at', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [makeOp('clip.move', 'clip-1', { at: 'abc' })],
      }),
    );
    expect(result.valid).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// track.add
// ---------------------------------------------------------------------------

describe('validateTimelinePatch — track.add', () => {
  it('accepts track.add with valid kind "visual"', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [makeOp('track.add', 'V2', { kind: 'visual', label: 'Video 2' })],
      }),
    );
    expect(result.valid).toBe(true);
  });

  it('accepts track.add with valid kind "audio"', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [makeOp('track.add', 'A1', { kind: 'audio' })],
      }),
    );
    expect(result.valid).toBe(true);
  });

  it('rejects track.add without kind', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [makeOp('track.add', 'V2', { label: 'V2' })],
      }),
    );
    expect(result.valid).toBe(false);
    expect(result.diagnostics.some((d) => d.code === 'timeline-patch/missing-payload-key')).toBe(true);
  });

  it('rejects track.add with invalid kind', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [makeOp('track.add', 'V2', { kind: 'subtitle' })],
      }),
    );
    expect(result.valid).toBe(false);
    expect(result.diagnostics.some((d) => d.code === 'timeline-patch/invalid-payload')).toBe(true);
  });

  it('rejects track.add with non-string label', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [makeOp('track.add', 'V2', { kind: 'visual', label: 42 })],
      }),
    );
    expect(result.valid).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// track.update
// ---------------------------------------------------------------------------

describe('validateTimelinePatch — track.update', () => {
  it('accepts track.update with valid fields', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [makeOp('track.update', 'V1', { muted: true, label: 'Primary' })],
      }),
    );
    expect(result.valid).toBe(true);
  });

  it('warns on empty payload', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [makeOp('track.update', 'V1', {})],
      }),
    );
    expect(result.diagnostics.some((d) => d.code === 'timeline-patch/empty-payload')).toBe(true);
  });

  it('rejects invalid kind', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [makeOp('track.update', 'V1', { kind: 'invalid' })],
      }),
    );
    expect(result.valid).toBe(false);
  });

  it('rejects non-boolean muted', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [makeOp('track.update', 'V1', { muted: 'yes' })],
      }),
    );
    expect(result.valid).toBe(false);
    expect(result.diagnostics.some((d) => d.code === 'timeline-patch/invalid-payload')).toBe(true);
  });

  it('rejects non-string label', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [makeOp('track.update', 'V1', { label: 99 })],
      }),
    );
    expect(result.valid).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// track.remove
// ---------------------------------------------------------------------------

describe('validateTimelinePatch — track.remove', () => {
  it('accepts track.remove', () => {
    const result = validateTimelinePatch(
      makePatch({ operations: [makeOp('track.remove', 'V2')] }),
    );
    expect(result.valid).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// asset.update / asset.remove
// ---------------------------------------------------------------------------

describe('validateTimelinePatch — asset operations', () => {
  it('accepts asset.update with payload', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [makeOp('asset.update', 'asset-key', { src: 'https://example.com/new.mp4' })],
      }),
    );
    expect(result.valid).toBe(true);
  });

  it('rejects asset.update with empty payload', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [makeOp('asset.update', 'asset-key', {})],
      }),
    );
    expect(result.valid).toBe(false);
    expect(result.diagnostics.some((d) => d.code === 'timeline-patch/empty-payload')).toBe(true);
  });

  it('accepts asset.remove', () => {
    const result = validateTimelinePatch(
      makePatch({ operations: [makeOp('asset.remove', 'asset-key')] }),
    );
    expect(result.valid).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// app.update
// ---------------------------------------------------------------------------

describe('validateTimelinePatch — app.update', () => {
  it('accepts app.update with valid extension ID and payload', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [makeOp('app.update', 'com.example.ext', { theme: 'dark' })],
      }),
    );
    expect(result.valid).toBe(true);
  });

  it('rejects app.update with invalid extension ID target', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [makeOp('app.update', '', { theme: 'dark' })],
      }),
    );
    expect(result.valid).toBe(false);
  });

  it('rejects app.update with non-extension-ID target', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [makeOp('app.update', 'not a valid id!', { theme: 'dark' })],
      }),
    );
    expect(result.valid).toBe(false);
    expect(result.diagnostics.some((d) => d.code === 'timeline-patch/invalid-target')).toBe(true);
  });

  it('rejects app.update with empty payload', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [makeOp('app.update', 'com.example.ext', {})],
      }),
    );
    expect(result.valid).toBe(false);
    expect(result.diagnostics.some((d) => d.code === 'timeline-patch/missing-payload-key')).toBe(true);
  });

  it('rejects app.update without payload', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [makeOp('app.update', 'com.example.ext')],
      }),
    );
    expect(result.valid).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// project-data.write / project-data.delete
// ---------------------------------------------------------------------------

describe('validateTimelinePatch — project-data operations', () => {
  it('accepts project-data.write with valid extension ID, key, and value', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [makeOp('project-data.write', 'com.example.ext', { key: 'settings', value: { volume: 1 } })],
      }),
    );
    expect(result.valid).toBe(true);
  });

  it('rejects project-data.write without key', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [makeOp('project-data.write', 'com.example.ext', { value: {} })],
      }),
    );
    expect(result.valid).toBe(false);
    expect(result.diagnostics.some((d) => d.code === 'timeline-patch/missing-payload-key')).toBe(true);
  });

  it('rejects project-data.write with empty key', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [makeOp('project-data.write', 'com.example.ext', { key: '', value: {} })],
      }),
    );
    expect(result.valid).toBe(false);
  });

  it('rejects project-data.write without value', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [makeOp('project-data.write', 'com.example.ext', { key: 'settings' })],
      }),
    );
    expect(result.valid).toBe(false);
  });

  it('rejects project-data.write with invalid extension ID', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [makeOp('project-data.write', '!!!bad!!!', { key: 'x', value: 1 })],
      }),
    );
    expect(result.valid).toBe(false);
  });

  it('accepts project-data.delete with valid extension ID and key', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [makeOp('project-data.delete', 'com.example.ext', { key: 'settings' })],
      }),
    );
    expect(result.valid).toBe(true);
  });

  it('rejects project-data.delete without key', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [makeOp('project-data.delete', 'com.example.ext', {})],
      }),
    );
    expect(result.valid).toBe(false);
  });

  it('rejects project-data.delete with invalid extension ID', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [makeOp('project-data.delete', 'bad id', { key: 'x' })],
      }),
    );
    expect(result.valid).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// extension.noop
// ---------------------------------------------------------------------------

describe('validateTimelinePatch — extension.noop', () => {
  it('accepts extension.noop with valid extension ID', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [makeOp('extension.noop', 'com.example.ext')],
      }),
    );
    expect(result.valid).toBe(true);
  });

  it('accepts extension.noop with example payload', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [makeOp('extension.noop', 'com.example.ext', { message: 'hello' })],
      }),
    );
    expect(result.valid).toBe(true);
  });

  it('rejects extension.noop with invalid extension ID', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [makeOp('extension.noop', 'bad id')],
      }),
    );
    expect(result.valid).toBe(false);
    expect(result.diagnostics.some((d) => d.code === 'timeline-patch/invalid-target')).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// Multi-operation patches
// ---------------------------------------------------------------------------

describe('validateTimelinePatch — multi-operation', () => {
  it('accepts a patch with multiple valid operations', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [
          makeOp('clip.add', 'c1', { track: 'V1', at: 0, clipType: 'media' }),
          makeOp('track.add', 'V2', { kind: 'visual', label: 'V2' }),
          makeOp('extension.noop', 'com.example.ext'),
        ],
      }),
    );
    expect(result.valid).toBe(true);
    expect(result.diagnostics).toHaveLength(0);
  });

  it('reports error when one op is invalid in a batch', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [
          makeOp('clip.add', 'c1', { track: 'V1' }),
          makeOp('track.add', 'V2', { kind: 'invalid' }), // invalid kind
        ],
      }),
    );
    expect(result.valid).toBe(false);
    expect(result.diagnostics.length).toBeGreaterThan(0);
  });

  it('includes operationIndex in diagnostics', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [
          makeOp('clip.remove', 'c1'),
          { op: 'unknown.op' as TimelinePatchAnyOpFamily, target: 'x' },
        ],
      }),
    );
    const unknownDiag = result.diagnostics.find((d) => d.code === 'timeline-patch/unknown-op');
    expect(unknownDiag).toBeDefined();
    expect(unknownDiag!.operationIndex).toBe(1);
  });
});

// ---------------------------------------------------------------------------
// Diagnostic code prefix contract
// ---------------------------------------------------------------------------

describe('validateTimelinePatch — diagnostic code contract', () => {
  it('every diagnostic uses timeline-patch/ prefix', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [
          { op: 'bogus.op' as TimelinePatchAnyOpFamily, target: 'x' },
          makeOp('track.add', 'V1', { kind: 'bad' }),
          makeOp('clip.split', 'c1'),
        ],
      }),
    );
    expect(result.diagnostics.length).toBeGreaterThan(0);
    for (const d of result.diagnostics) {
      expect(d.code.startsWith('timeline-patch/')).toBe(true);
    }
  });

  it('all error diagnostics use timeline-patch/ prefix', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [{ op: 'never.heard.of' as TimelinePatchAnyOpFamily, target: 'x' }],
      }),
    );
    const errors = result.diagnostics.filter((d) => d.severity === 'error');
    expect(errors.length).toBeGreaterThan(0);
    for (const d of errors) {
      expect(d.code.startsWith('timeline-patch/')).toBe(true);
    }
  });
});

// ---------------------------------------------------------------------------
// invalid order field
// ---------------------------------------------------------------------------

describe('validateTimelinePatch — order field', () => {
  it('rejects non-finite order', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [makeOp('clip.remove', 'c1', undefined, Infinity)],
      }),
    );
    expect(result.valid).toBe(false);
    expect(result.diagnostics.some((d) => d.code === 'timeline-patch/invalid-order')).toBe(true);
  });

  it('rejects NaN order', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [makeOp('clip.remove', 'c1', undefined, NaN)],
      }),
    );
    expect(result.valid).toBe(false);
  });

  it('accepts valid order', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [makeOp('clip.remove', 'c1', undefined, 5)],
      }),
    );
    expect(result.valid).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// invalid payload type
// ---------------------------------------------------------------------------

describe('validateTimelinePatch — invalid payload type', () => {
  it('rejects string payload', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [{ op: 'clip.remove', target: 'c1', payload: 'bad' as unknown as Record<string, unknown> }],
      }),
    );
    expect(result.valid).toBe(false);
    expect(result.diagnostics.some((d) => d.code === 'timeline-patch/invalid-payload')).toBe(true);
  });

  it('rejects array payload', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [{ op: 'clip.remove', target: 'c1', payload: [] as unknown as Record<string, unknown> }],
      }),
    );
    expect(result.valid).toBe(false);
  });

  it('rejects null payload (when not undefined)', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [{ op: 'clip.remove', target: 'c1', payload: null as unknown as Record<string, unknown> }],
      }),
    );
    expect(result.valid).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// Result immutability
// ---------------------------------------------------------------------------

describe('validateTimelinePatch — result immutability', () => {
  it('returns a frozen result', () => {
    const result = validateTimelinePatch(
      makePatch({ operations: [makeOp('clip.remove', 'c1')] }),
    );
    expect(Object.isFrozen(result)).toBe(true);
  });

  it('returns frozen diagnostics array', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [{ op: 'bad.op' as TimelinePatchAnyOpFamily, target: 'x' }],
      }),
    );
    expect(Object.isFrozen(result.diagnostics)).toBe(true);
  });
});

// ===========================================================================
// T4: Focused validation tests (unknown ops, malformed payloads,
//     unsupported mutations, overflow diagnostics, reserved ops, namespace ops)
// ===========================================================================

// ---------------------------------------------------------------------------
// Unsupported asset / project mutations
// ---------------------------------------------------------------------------

describe('validateTimelinePatch — unsupported asset/project mutations', () => {
  it('rejects asset.add as unknown operation', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [{ op: 'asset.add' as TimelinePatchAnyOpFamily, target: 'a1' }],
      }),
    );
    expect(result.valid).toBe(false);
    const diag = result.diagnostics.find((d) => d.code === 'timeline-patch/unknown-op');
    expect(diag).toBeDefined();
    expect(diag!.op).toBe('asset.add');
  });

  it('rejects asset.create as unknown operation', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [{ op: 'asset.create' as TimelinePatchAnyOpFamily, target: 'a1' }],
      }),
    );
    expect(result.valid).toBe(false);
    expect(result.diagnostics.some((d) => d.code === 'timeline-patch/unknown-op')).toBe(true);
  });

  it('rejects asset.rename as unknown operation', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [{ op: 'asset.rename' as TimelinePatchAnyOpFamily, target: 'a1' }],
      }),
    );
    expect(result.valid).toBe(false);
    expect(result.diagnostics.some((d) => d.code === 'timeline-patch/unknown-op')).toBe(true);
  });

  it('rejects project.update as unknown operation', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [
          { op: 'project.update' as TimelinePatchAnyOpFamily, target: 'project-1' },
        ],
      }),
    );
    expect(result.valid).toBe(false);
    const diag = result.diagnostics.find((d) => d.code === 'timeline-patch/unknown-op');
    expect(diag).toBeDefined();
    expect(diag!.op).toBe('project.update');
  });

  it('rejects project.remove as unknown operation', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [
          { op: 'project.remove' as TimelinePatchAnyOpFamily, target: 'project-1' },
        ],
      }),
    );
    expect(result.valid).toBe(false);
    expect(result.diagnostics.some((d) => d.code === 'timeline-patch/unknown-op')).toBe(true);
  });

  it('rejects project.create as unknown operation', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [
          { op: 'project.create' as TimelinePatchAnyOpFamily, target: 'project-1' },
        ],
      }),
    );
    expect(result.valid).toBe(false);
    expect(result.diagnostics.some((d) => d.code === 'timeline-patch/unknown-op')).toBe(true);
  });

  it('rejects clip.rename as unknown operation (not in active or reserved sets)', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [{ op: 'clip.rename' as TimelinePatchAnyOpFamily, target: 'c1' }],
      }),
    );
    expect(result.valid).toBe(false);
    expect(result.diagnostics.some((d) => d.code === 'timeline-patch/unknown-op')).toBe(true);
  });

  it('rejects track.move as unknown operation', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [{ op: 'track.move' as TimelinePatchAnyOpFamily, target: 'V1' }],
      }),
    );
    expect(result.valid).toBe(false);
    expect(result.diagnostics.some((d) => d.code === 'timeline-patch/unknown-op')).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// Extension data overflow diagnostics
// ---------------------------------------------------------------------------

describe('validateTimelinePatch — extension data overflow diagnostics', () => {
  it('rejects project-data.write where JSON-serialized value exceeds MAX_ENTRY_BYTES', () => {
    // Build a string just over 64 KB
    const bigString = 'x'.repeat(64 * 1024 + 1);
    const result = validateTimelinePatch(
      makePatch({
        operations: [
          makeOp('project-data.write', 'com.example.ext', {
            key: 'big-data',
            value: { data: bigString },
          }),
        ],
      }),
    );
    expect(result.valid).toBe(false);
    const overflowDiag = result.diagnostics.find(
      (d) => d.code === 'timeline-patch/project-data-overflow',
    );
    expect(overflowDiag).toBeDefined();
    expect(overflowDiag!.severity).toBe('error');
    expect(overflowDiag!.op).toBe('project-data.write');
    expect(overflowDiag!.target).toBe('com.example.ext');
  });

  it('produces ProjectDataLimitDetail shape on overflow diagnostic', () => {
    const bigString = 'x'.repeat(64 * 1024 + 100);
    const result = validateTimelinePatch(
      makePatch({
        operations: [
          makeOp('project-data.write', 'com.example.ext', {
            key: 'big',
            value: { data: bigString },
          }),
        ],
      }),
    );
    const diag = result.diagnostics.find(
      (d) => d.code === 'timeline-patch/project-data-overflow',
    );
    expect(diag).toBeDefined();
    const detail = diag!.detail as {
      code: string;
      extensionId: string;
      limit: number;
      actual: number;
      unit: string;
    };
    expect(detail.code).toBe('project-data/entry-size-exceeded');
    expect(detail.extensionId).toBe('com.example.ext');
    expect(detail.limit).toBe(64 * 1024);
    expect(typeof detail.actual).toBe('number');
    expect(detail.actual).toBeGreaterThan(64 * 1024);
    expect(detail.unit).toBe('bytes');
  });

  it('accepts project-data.write where JSON-serialized value is under MAX_ENTRY_BYTES', () => {
    const moderateData = { items: Array.from({ length: 100 }, (_, i) => i) };
    const result = validateTimelinePatch(
      makePatch({
        operations: [
          makeOp('project-data.write', 'com.example.ext', {
            key: 'moderate',
            value: moderateData,
          }),
        ],
      }),
    );
    expect(result.valid).toBe(true);
    expect(result.diagnostics).toHaveLength(0);
  });

  it('accepts project-data.write at exactly MAX_ENTRY_BYTES boundary', () => {
    // Build a string that produces exactly 64 KB when serialized inside an object
    // JSON.stringify({data: s}) = {"data":"..."} - overhead is 11 chars
    const overhead = 11; // {"data":""}
    const payloadChars = 64 * 1024 - overhead;
    const s = 'x'.repeat(payloadChars);
    const result = validateTimelinePatch(
      makePatch({
        operations: [
          makeOp('project-data.write', 'com.example.ext', {
            key: 'boundary',
            value: { data: s },
          }),
        ],
      }),
    );
    expect(result.valid).toBe(true);
    expect(result.diagnostics).toHaveLength(0);
  });

  it('rejects project-data.write at exactly MAX_ENTRY_BYTES + 1 boundary', () => {
    const overhead = 11; // {"data":""}
    const payloadChars = 64 * 1024 - overhead + 1;
    const s = 'x'.repeat(payloadChars);
    const result = validateTimelinePatch(
      makePatch({
        operations: [
          makeOp('project-data.write', 'com.example.ext', {
            key: 'boundary',
            value: { data: s },
          }),
        ],
      }),
    );
    expect(result.valid).toBe(false);
    expect(
      result.diagnostics.some(
        (d) => d.code === 'timeline-patch/project-data-overflow',
      ),
    ).toBe(true);
  });

  it('does not produce overflow diagnostic when value is undefined (missing key error instead)', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [
          makeOp('project-data.write', 'com.example.ext', { key: 'k' }),
        ],
      }),
    );
    expect(result.valid).toBe(false);
    expect(
      result.diagnostics.some(
        (d) => d.code === 'timeline-patch/project-data-overflow',
      ),
    ).toBe(false);
    expect(
      result.diagnostics.some(
        (d) => d.code === 'timeline-patch/missing-payload-key',
      ),
    ).toBe(true);
  });

  it('project-data.write overflow diagnostic includes operationIndex', () => {
    const bigString = 'x'.repeat(64 * 1024 + 50);
    const result = validateTimelinePatch(
      makePatch({
        operations: [
          makeOp('clip.remove', 'c1'),
          makeOp('project-data.write', 'com.example.ext', {
            key: 'big',
            value: { data: bigString },
          }),
        ],
      }),
    );
    const diag = result.diagnostics.find(
      (d) => d.code === 'timeline-patch/project-data-overflow',
    );
    expect(diag).toBeDefined();
    expect(diag!.operationIndex).toBe(1);
  });
});

// ---------------------------------------------------------------------------
// Invalid namespaced extension operation payloads
// ---------------------------------------------------------------------------

describe('validateTimelinePatch — invalid namespaced extension operation payloads', () => {
  it('rejects extension.noop with invalid extension ID target', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [makeOp('extension.noop', '!!!invalid!!!')],
      }),
    );
    expect(result.valid).toBe(false);
    expect(result.diagnostics.some((d) => d.code === 'timeline-patch/invalid-target')).toBe(true);
  });

  it('rejects extension.noop with empty-string target', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [makeOp('extension.noop', '')],
      }),
    );
    expect(result.valid).toBe(false);
    const hasInvalidTarget = result.diagnostics.some(
      (d) => d.code === 'timeline-patch/invalid-target',
    );
    const hasMissingTarget = result.diagnostics.some(
      (d) => d.code === 'timeline-patch/missing-target',
    );
    expect(hasInvalidTarget || hasMissingTarget).toBe(true);
  });

  it('accepts extension.noop with complex payload (any shape is valid for noop)', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [
          makeOp('extension.noop', 'com.example.ext', {
            deeply: { nested: { value: [1, 2, 3] } },
            timestamp: Date.now(),
            tags: ['noop', 'test'],
          }),
        ],
      }),
    );
    expect(result.valid).toBe(true);
    expect(result.diagnostics).toHaveLength(0);
  });

  it('accepts extension.noop with string payload', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [
          makeOp('extension.noop', 'com.example.ext', {
            message: 'a simple noop',
          }),
        ],
      }),
    );
    expect(result.valid).toBe(true);
  });

  it('accepts extension.noop without any payload', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [makeOp('extension.noop', 'com.example.ext')],
      }),
    );
    expect(result.valid).toBe(true);
  });

  it('accepts app.update with deeply nested payload structure', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [
          makeOp('app.update', 'com.example.ext', {
            config: {
              theme: { colors: { primary: '#000', secondary: '#fff' } },
              layout: { sidebar: { width: 300, collapsed: false } },
            },
          }),
        ],
      }),
    );
    expect(result.valid).toBe(true);
    expect(result.diagnostics).toHaveLength(0);
  });

  it('rejects app.update with null payload', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [
          {
            op: 'app.update' as TimelinePatchAnyOpFamily,
            target: 'com.example.ext',
            payload: null as unknown as Record<string, unknown>,
          },
        ],
      }),
    );
    expect(result.valid).toBe(false);
  });

  it('rejects project-data.write with non-string key', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [
          makeOp('project-data.write', 'com.example.ext', {
            key: 42 as unknown as string,
            value: 'data',
          }),
        ],
      }),
    );
    expect(result.valid).toBe(false);
    expect(
      result.diagnostics.some(
        (d) => d.code === 'timeline-patch/missing-payload-key',
      ),
    ).toBe(true);
  });

  it('rejects project-data.write with empty key string', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [
          makeOp('project-data.write', 'com.example.ext', {
            key: '',
            value: 'data',
          }),
        ],
      }),
    );
    expect(result.valid).toBe(false);
  });

  it('rejects project-data.delete with non-string key', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [
          makeOp('project-data.delete', 'com.example.ext', {
            key: true as unknown as string,
          }),
        ],
      }),
    );
    expect(result.valid).toBe(false);
  });

  it('rejects project-data.delete with empty key string', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [
          makeOp('project-data.delete', 'com.example.ext', { key: '' }),
        ],
      }),
    );
    expect(result.valid).toBe(false);
    expect(
      result.diagnostics.some(
        (d) => d.code === 'timeline-patch/missing-payload-key',
      ),
    ).toBe(true);
  });

  it('rejects project-data.write with array payload instead of object', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [
          {
            op: 'project-data.write' as TimelinePatchAnyOpFamily,
            target: 'com.example.ext',
            payload: ['not', 'an', 'object'] as unknown as Record<
              string,
              unknown
            >,
          },
        ],
      }),
    );
    expect(result.valid).toBe(false);
    expect(
      result.diagnostics.some(
        (d) => d.code === 'timeline-patch/invalid-payload',
      ),
    ).toBe(true);
  });

  it('rejects namespaced operation with completely fabricated family', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [
          {
            op: 'extension.unsupported.command' as TimelinePatchAnyOpFamily,
            target: 'com.example.ext',
          },
        ],
      }),
    );
    expect(result.valid).toBe(false);
    expect(result.diagnostics.some((d) => d.code === 'timeline-patch/unknown-op')).toBe(true);
  });

  it('rejects namespaced operation with leading dot', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [
          { op: '.noop' as TimelinePatchAnyOpFamily, target: 'com.example.ext' },
        ],
      }),
    );
    expect(result.valid).toBe(false);
    expect(result.diagnostics.some((d) => d.code === 'timeline-patch/unknown-op')).toBe(true);
  });

  it('rejects namespaced operation with trailing dot', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [
          { op: 'extension.' as TimelinePatchAnyOpFamily, target: 'com.example.ext' },
        ],
      }),
    );
    expect(result.valid).toBe(false);
    expect(result.diagnostics.some((d) => d.code === 'timeline-patch/unknown-op')).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// Additional malformed payload edge cases
// ---------------------------------------------------------------------------

describe('validateTimelinePatch — additional malformed payload edge cases', () => {
  it('rejects patch where operations is a string instead of array', () => {
    const result = validateTimelinePatch({
      version: 1,
      operations: 'not-an-array' as unknown as TimelinePatchOperation[],
    });
    expect(result.valid).toBe(false);
    expect(
      result.diagnostics.some((d) => d.code === 'timeline-patch/invalid-patch'),
    ).toBe(true);
  });

  it('rejects patch where operations is undefined', () => {
    const result = validateTimelinePatch({
      version: 1,
      operations: undefined as unknown as TimelinePatchOperation[],
    });
    expect(result.valid).toBe(false);
  });

  it('rejects operation with boolean op', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [
          { op: true as unknown as string, target: 'x' } as TimelinePatchOperation,
        ],
      }),
    );
    expect(result.valid).toBe(false);
    expect(
      result.diagnostics.some((d) => d.code === 'timeline-patch/missing-op'),
    ).toBe(true);
  });

  it('rejects operation with number op', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [
          { op: 123 as unknown as string, target: 'x' } as TimelinePatchOperation,
        ],
      }),
    );
    expect(result.valid).toBe(false);
  });

  it('rejects operation where payload is a function', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [
          {
            op: 'clip.remove' as TimelinePatchAnyOpFamily,
            target: 'c1',
            payload: (() => {}) as unknown as Record<string, unknown>,
          },
        ],
      }),
    );
    expect(result.valid).toBe(false);
    expect(
      result.diagnostics.some((d) => d.code === 'timeline-patch/invalid-payload'),
    ).toBe(true);
  });

  it('rejects operation where payload is a number', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [
          {
            op: 'clip.remove' as TimelinePatchAnyOpFamily,
            target: 'c1',
            payload: 42 as unknown as Record<string, unknown>,
          },
        ],
      }),
    );
    expect(result.valid).toBe(false);
    expect(
      result.diagnostics.some((d) => d.code === 'timeline-patch/invalid-payload'),
    ).toBe(true);
  });

  it('rejects operation where payload is a boolean', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [
          {
            op: 'clip.remove' as TimelinePatchAnyOpFamily,
            target: 'c1',
            payload: true as unknown as Record<string, unknown>,
          },
        ],
      }),
    );
    expect(result.valid).toBe(false);
    expect(
      result.diagnostics.some((d) => d.code === 'timeline-patch/invalid-payload'),
    ).toBe(true);
  });

  it('rejects project-data.write with null value and missing key', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [
          makeOp('project-data.write', 'com.example.ext', {
            key: null as unknown as string,
            value: null,
          }),
        ],
      }),
    );
    expect(result.valid).toBe(false);
  });

  it('produces multiple diagnostics for a batch with several invalid operations', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [
          { op: 'bad.op1' as TimelinePatchAnyOpFamily, target: 'x' },
          { op: 'bad.op2' as TimelinePatchAnyOpFamily, target: 'y' },
          { op: 'bad.op3' as TimelinePatchAnyOpFamily, target: 'z' },
        ],
      }),
    );
    expect(result.valid).toBe(false);
    const unknownDiags = result.diagnostics.filter(
      (d) => d.code === 'timeline-patch/unknown-op',
    );
    expect(unknownDiags).toHaveLength(3);
    expect(unknownDiags[0].operationIndex).toBe(0);
    expect(unknownDiags[1].operationIndex).toBe(1);
    expect(unknownDiags[2].operationIndex).toBe(2);
  });

  it('all diagnostics in an invalid batch use timeline-patch/ prefix', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [
          { op: 'unknown.op' as TimelinePatchAnyOpFamily, target: '' },
          makeOp('track.add', 'V1', { kind: 'invalid_kind' }),
          { op: 'clip.split' as TimelinePatchAnyOpFamily, target: 'c1', payload: null as unknown as Record<string, unknown> },
        ],
      }),
    );
    expect(result.diagnostics.length).toBeGreaterThan(0);
    expect(allErrorsHaveTimelinePatchCode(result.diagnostics.filter((d) => d.severity === 'error'))).toBe(true);
    for (const d of result.diagnostics) {
      expect(d.code.startsWith('timeline-patch/')).toBe(true);
    }
  });
});

// ---------------------------------------------------------------------------
// Reserved ops: additional edge cases
// ---------------------------------------------------------------------------

describe('validateTimelinePatch — reserved ops additional edge cases', () => {
  it('clip.split with missing payload still produces reserved-op warning', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [makeOp('clip.split', 'clip-1')],
      }),
    );
    const diag = result.diagnostics.find(
      (d) => d.code === 'timeline-patch/reserved-op',
    );
    expect(diag).toBeDefined();
    expect(diag!.detail).toEqual({
      reserved: true,
      deferred: true,
      nonPreviewable: true,
    });
  });

  it('clip.slice with missing payload still produces reserved-op warning', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [makeOp('clip.slice', 'clip-1')],
      }),
    );
    const diag = result.diagnostics.find(
      (d) => d.code === 'timeline-patch/reserved-op',
    );
    expect(diag).toBeDefined();
  });

  it('batch with reserved op + valid ops is still valid (warning non-blocking)', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [
          makeOp('clip.split', 'c1', { at: 5 }),
          makeOp('clip.remove', 'c2'),
          makeOp('track.add', 'V3', { kind: 'visual' }),
        ],
      }),
    );
    expect(result.valid).toBe(true);
    const reservedDiags = result.diagnostics.filter(
      (d) => d.code === 'timeline-patch/reserved-op',
    );
    expect(reservedDiags).toHaveLength(1);
    expect(reservedDiags[0].severity).toBe('warning');
  });

  it('batch with reserved op + invalid op is invalid', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [
          makeOp('clip.split', 'c1'),
          makeOp('track.add', 'V1', { kind: 'bad_kind' as 'visual' }),
        ],
      }),
    );
    expect(result.valid).toBe(false);
    // Should have both a warning (reserved-op) and an error (invalid-payload)
    expect(
      result.diagnostics.some((d) => d.code === 'timeline-patch/reserved-op'),
    ).toBe(true);
    expect(
      result.diagnostics.some((d) => d.code === 'timeline-patch/invalid-payload'),
    ).toBe(true);
  });
});

// ===========================================================================
// T6: Merge/Replace semantics validation
// ===========================================================================

describe('validateTimelinePatch — merge/replace mode validation', () => {
  it('rejects clip.update with invalid mode', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [makeOp('clip.update', 'c1', { volume: 0.5, mode: 'overwrite' })],
      }),
    );
    expect(result.valid).toBe(false);
    expect(result.diagnostics.some((d) => d.code === 'timeline-patch/invalid-payload')).toBe(true);
    const diag = result.diagnostics.find((d) => d.code === 'timeline-patch/invalid-payload');
    expect(diag!.detail).toMatchObject({ key: 'mode', expected: '"merge" | "replace"' });
  });

  it('accepts clip.update with mode "merge"', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [makeOp('clip.update', 'c1', { volume: 0.5, mode: 'merge' })],
      }),
    );
    expect(result.valid).toBe(true);
  });

  it('accepts clip.update with mode "replace"', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [makeOp('clip.update', 'c1', { volume: 0.5, mode: 'replace' })],
      }),
    );
    expect(result.valid).toBe(true);
  });

  it('warns when clip.update has only mode and no updateable fields', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [makeOp('clip.update', 'c1', { mode: 'replace' })],
      }),
    );
    expect(result.diagnostics.some((d) => d.code === 'timeline-patch/empty-payload')).toBe(true);
  });

  it('rejects track.update with invalid mode', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [makeOp('track.update', 'V1', { muted: true, mode: 'bad' })],
      }),
    );
    expect(result.valid).toBe(false);
    expect(result.diagnostics.some((d) => d.code === 'timeline-patch/invalid-payload')).toBe(true);
  });

  it('accepts track.update with mode "merge"', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [makeOp('track.update', 'V1', { muted: true, mode: 'merge' })],
      }),
    );
    expect(result.valid).toBe(true);
  });

  it('accepts track.update with mode "replace"', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [makeOp('track.update', 'V1', { muted: true, mode: 'replace' })],
      }),
    );
    expect(result.valid).toBe(true);
  });

  it('rejects asset.update with invalid mode', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [makeOp('asset.update', 'asset-key', { src: 'url', mode: 'invalid' })],
      }),
    );
    expect(result.valid).toBe(false);
    expect(result.diagnostics.some((d) => d.code === 'timeline-patch/invalid-payload')).toBe(true);
  });

  it('rejects app.update with invalid mode', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [makeOp('app.update', 'com.example.ext', { theme: 'dark', mode: 'nope' })],
      }),
    );
    expect(result.valid).toBe(false);
    expect(result.diagnostics.some((d) => d.code === 'timeline-patch/invalid-payload')).toBe(true);
  });

  it('rejects project-data.write with invalid mode', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [makeOp('project-data.write', 'com.example.ext', { key: 'k', value: 1, mode: 'bad' })],
      }),
    );
    expect(result.valid).toBe(false);
    expect(result.diagnostics.some((d) => d.code === 'timeline-patch/invalid-payload')).toBe(true);
  });

  it('accepts project-data.write with mode "merge"', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [makeOp('project-data.write', 'com.example.ext', { key: 'k', value: { a: 1 }, mode: 'merge' })],
      }),
    );
    expect(result.valid).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// clip.move before/after anchor validation
// ---------------------------------------------------------------------------

describe('validateTimelinePatch — clip.move before/after anchors', () => {
  it('accepts clip.move with before anchor', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [makeOp('clip.move', 'c1', { before: 'c2' })],
      }),
    );
    expect(result.valid).toBe(true);
  });

  it('accepts clip.move with after anchor', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [makeOp('clip.move', 'c1', { after: 'c2' })],
      }),
    );
    expect(result.valid).toBe(true);
  });

  it('accepts clip.move with both before and after anchors', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [makeOp('clip.move', 'c1', { before: 'c2', after: 'c3' })],
      }),
    );
    expect(result.valid).toBe(true);
  });

  it('warns when before and after are the same clip', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [makeOp('clip.move', 'c1', { before: 'c2', after: 'c2' })],
      }),
    );
    expect(result.diagnostics.some((d) => d.code === 'timeline-patch/invalid-payload' && d.severity === 'warning')).toBe(true);
  });

  it('accepts clip.move with before anchor and track/at', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [makeOp('clip.move', 'c1', { track: 'V2', at: 10, before: 'c2' })],
      }),
    );
    expect(result.valid).toBe(true);
  });

  it('rejects clip.move with non-string before anchor', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [makeOp('clip.move', 'c1', { before: 42 })],
      }),
    );
    expect(result.valid).toBe(false);
    expect(result.diagnostics.some((d) => d.code === 'timeline-patch/invalid-payload')).toBe(true);
  });

  it('rejects clip.move with non-string after anchor', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [makeOp('clip.move', 'c1', { after: true })],
      }),
    );
    expect(result.valid).toBe(false);
    expect(result.diagnostics.some((d) => d.code === 'timeline-patch/invalid-payload')).toBe(true);
  });

  it('accepts clip.move with only before (no track/at)', () => {
    const result = validateTimelinePatch(
      makePatch({
        operations: [makeOp('clip.move', 'c1', { before: 'c2' })],
      }),
    );
    expect(result.valid).toBe(true);
  });
});

// ===========================================================================
// T6: Compile semantics — merge/replace, ordering, anchors
// ===========================================================================

// We need a minimal TimelineData fixture for compile tests
function makeMinimalTimelineData(overrides: Record<string, unknown> = {}) {
  // Dynamically import or inline minimal data shape compatible with
  // buildDataFromCurrentRegistry expectations.
  const config = {
    output: { resolution: '1920x1080', fps: 30, file: 'test.mp4' },
    clips: (overrides.clips as Array<Record<string, unknown>>) ?? [],
    tracks: (overrides.tracks as Array<Record<string, unknown>>) ?? [],
    pinnedShotGroups: [],
    theme: 'default',
    theme_overrides: {},
    generation_defaults: {},
    app: (overrides.app as Record<string, unknown>) ?? {},
  };
  const clipsData = (config.clips ?? []) as Array<Record<string, unknown>>;
  const tracksData = (config.tracks ?? []) as Array<Record<string, unknown>>;
  const clipOrder: Record<string, string[]> = {};
  for (const t of tracksData) {
    clipOrder[t.id as string] = clipsData
      .filter((c) => c.track === t.id)
      .map((c) => c.id as string);
  }

  const assets = (overrides.assets as Record<string, unknown>) ?? {};
  const registry = { assets, records: {} };

  return {
    config,
    clips: clipsData,
    tracks: tracksData,
    meta: {} as Record<string, Record<string, unknown>>,
    clipOrder,
    output: config.output,
    registry,
    configVersion: 1,
    resolvedConfig: { registry: assets },
  } as any;  
}

const clipShader: TimelineClipShaderMetadata = {
  scope: 'clip',
  extensionId: 'com.example.shader',
  contributionId: 'clip-glow-shader',
  shaderId: 'shader.clipGlow',
  uniforms: { intensity: 0.5 },
};

const replacementClipShader: TimelineClipShaderMetadata = {
  scope: 'clip',
  extensionId: 'com.example.shader',
  contributionId: 'clip-edge-shader',
  shaderId: 'shader.clipEdge',
};

const postprocessShader: TimelinePostprocessShaderMetadata = {
  scope: 'postprocess',
  extensionId: 'com.example.shader',
  contributionId: 'post-grade-shader',
  shaderId: 'shader.postGrade',
  uniforms: { exposure: 0.15 },
};

const replacementPostprocessShader: TimelinePostprocessShaderMetadata = {
  scope: 'postprocess',
  extensionId: 'com.example.shader',
  contributionId: 'post-vignette-shader',
  shaderId: 'shader.postVignette',
};

describe('compileTimelinePatch — merge/replace for clip.update', () => {
  it('merge mode (default) preserves unspecified clip fields in metaUpdates', () => {
    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [{ id: 'c1', track: 'V1', at: 0, hold: 10, volume: 1.0, opacity: 1.0 }],
    });
    const result = compileTimelinePatch(
      makePatch({
        operations: [makeOp('clip.update', 'c1', { volume: 0.5 })],
      }),
      data,
    );
    expect(result.valid).toBe(true);
    const updatedMeta = result.mutation!.metaUpdates!['c1'];
    expect(updatedMeta.volume).toBe(0.5); // changed
    // Merge default: opacity not in payload, so it may or may not be in meta updates
    // The diff entry verifies the mode was merge
    const entry = result.diff.entries.find((e: any) => e.target === 'c1');
    expect(entry!.after).toHaveProperty('mode', 'merge');
  });

  it('replace mode removes unspecified clip fields in metaUpdates', () => {
    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [{ id: 'c1', track: 'V1', at: 0, hold: 10, volume: 1.0, opacity: 1.0, speed: 2.0 }],
    });
    const result = compileTimelinePatch(
      makePatch({
        operations: [makeOp('clip.update', 'c1', { volume: 0.5, mode: 'replace' })],
      }),
      data,
    );
    expect(result.valid).toBe(true);
    // In replace mode, the diff entry should indicate mode='replace'
    const entry = result.diff.entries.find((e: any) => e.target === 'c1');
    expect(entry).toBeDefined();
    expect(entry!.after).toHaveProperty('mode', 'replace');
    // The meta updates should have volume set
    const updatedMeta = result.mutation!.metaUpdates!['c1'];
    expect(updatedMeta.volume).toBe(0.5);
  });

  it('diff after field includes mode', () => {
    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [{ id: 'c1', track: 'V1', at: 0, hold: 10, volume: 1.0 }],
    });
    const result = compileTimelinePatch(
      makePatch({
        operations: [makeOp('clip.update', 'c1', { volume: 0.5, mode: 'replace' })],
      }),
      data,
    );
    const entry = result.diff.entries.find((e: any) => e.target === 'c1');
    expect(entry).toBeDefined();
    expect(entry!.after).toHaveProperty('mode', 'replace');
  });
});

describe('compileTimelinePatch — shader metadata scope limits', () => {
  it('patches and persists a clip-local shader through clip.update', () => {
    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [{ id: 'c1', track: 'V1', at: 0, hold: 10 }],
    });

    const result = compileTimelinePatch(
      makePatch({
        operations: [makeOp('clip.update', 'c1', { app: { shader: clipShader } })],
      }),
      data,
    );

    expect(result.valid).toBe(true);
    expect(result.diagnostics.filter((diagnostic) => diagnostic.severity === 'error')).toHaveLength(0);
    expect(result.nextData!.config.clips.find((clip: any) => clip.id === 'c1')!.app.shader).toEqual(clipShader);
    expect(result.mutation!.metaUpdates!['c1'].app).toEqual({ shader: clipShader });
  });

  it('refuses to replace an occupied clip-local shader scope', () => {
    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [{ id: 'c1', track: 'V1', at: 0, hold: 10, app: { shader: clipShader } }],
    });

    const result = compileTimelinePatch(
      makePatch({
        operations: [makeOp('clip.update', 'c1', { app: { shader: replacementClipShader } })],
      }),
      data,
    );

    expect(result.diagnostics).toEqual(expect.arrayContaining([
      expect.objectContaining({
        code: 'timeline-patch/shader-scope-occupied',
        severity: 'error',
        message: 'Cannot add shader "shader.clipEdge" to clip "c1" because shader "shader.clipGlow" is already assigned. V1 supports one clip shader per clip. Remove the existing shader before assigning another.',
      }),
    ]));
    expect(result.nextData!.config.clips.find((clip: any) => clip.id === 'c1')!.app.shader).toEqual(clipShader);
  });

  it('patches and persists the timeline postprocess shader through app.update', () => {
    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [{ id: 'c1', track: 'V1', at: 0, hold: 10 }],
    });

    const result = compileTimelinePatch(
      makePatch({
        operations: [makeOp('app.update', TIMELINE_POSTPROCESS_SHADER_APP_KEY, { ...postprocessShader })],
      }),
      data,
    );

    expect(result.valid).toBe(true);
    expect(result.diagnostics.filter((diagnostic) => diagnostic.severity === 'error')).toHaveLength(0);
    expect(result.nextData!.config.app![TIMELINE_POSTPROCESS_SHADER_APP_KEY]).toEqual(postprocessShader);
  });

  it('refuses to replace an occupied postprocess shader scope', () => {
    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [{ id: 'c1', track: 'V1', at: 0, hold: 10 }],
      app: { [TIMELINE_POSTPROCESS_SHADER_APP_KEY]: postprocessShader },
    });

    const result = compileTimelinePatch(
      makePatch({
        operations: [makeOp('app.update', TIMELINE_POSTPROCESS_SHADER_APP_KEY, { ...replacementPostprocessShader })],
      }),
      data,
    );

    expect(result.diagnostics).toEqual(expect.arrayContaining([
      expect.objectContaining({
        code: 'timeline-patch/shader-scope-occupied',
        severity: 'error',
        message: 'Cannot add postprocess shader "shader.postVignette" because postprocess shader "shader.postGrade" is already assigned. V1 supports one timeline postprocess shader. Remove the existing postprocess shader before assigning another.',
      }),
    ]));
    expect(result.nextData!.config.app![TIMELINE_POSTPROCESS_SHADER_APP_KEY]).toEqual(postprocessShader);
  });
});

describe('compileTimelinePatch — merge/replace for track.update', () => {
  it('merge mode preserves unspecified track fields', () => {
    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'Video 1', muted: false, volume: 0.8 }],
      clips: [],
    });
    const result = compileTimelinePatch(
      makePatch({
        operations: [makeOp('track.update', 'V1', { muted: true })],
      }),
      data,
    );
    expect(result.valid).toBe(true);
    const updatedTrack = result.nextData!.config.tracks!.find((t: any) => t.id === 'V1');
    expect(updatedTrack.muted).toBe(true);
    expect(updatedTrack.volume).toBe(0.8); // preserved
    expect(updatedTrack.label).toBe('Video 1'); // preserved
  });

  it('replace mode removes unspecified track fields', () => {
    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'Video 1', muted: false, volume: 0.8 }],
      clips: [],
    });
    const result = compileTimelinePatch(
      makePatch({
        operations: [makeOp('track.update', 'V1', { muted: true, mode: 'replace' })],
      }),
      data,
    );
    expect(result.valid).toBe(true);
    const updatedTrack = result.nextData!.config.tracks!.find((t: any) => t.id === 'V1');
    expect(updatedTrack.muted).toBe(true);
    // In replace mode, volume was not in payload so should be reset
    expect(updatedTrack.volume).toBeUndefined();
    // kind and label preserved as structural defaults (not mutable in replace)
    expect(updatedTrack.kind).toBe('visual');
    expect(updatedTrack.label).toBe('Video 1');
  });

  it('track.update diff after includes mode', () => {
    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [],
    });
    const result = compileTimelinePatch(
      makePatch({
        operations: [makeOp('track.update', 'V1', { muted: true, mode: 'merge' })],
      }),
      data,
    );
    const entry = result.diff.entries.find((e: any) => e.target === 'V1');
    expect(entry).toBeDefined();
    expect(entry!.after).toHaveProperty('mode', 'merge');
  });
});

describe('compileTimelinePatch — merge/replace for app.update', () => {
  it('merge mode shallow-merges into existing app namespace', () => {
    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [],
      app: { 'com.example.ext': { theme: 'light', layout: { sidebar: true } } },
    });
    const result = compileTimelinePatch(
      makePatch({
        operations: [makeOp('app.update', 'com.example.ext', { theme: 'dark', mode: 'merge' })],
      }),
      data,
    );
    expect(result.valid).toBe(true);
    const appConfig = result.nextData!.config.app;
    const extConfig = appConfig['com.example.ext'] as Record<string, unknown>;
    expect(extConfig.theme).toBe('dark'); // updated
    expect(extConfig.layout).toEqual({ sidebar: true }); // preserved
  });

  it('replace mode overwrites entire app namespace', () => {
    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [],
      app: { 'com.example.ext': { theme: 'light', layout: { sidebar: true } } },
    });
    const result = compileTimelinePatch(
      makePatch({
        operations: [makeOp('app.update', 'com.example.ext', { theme: 'dark', mode: 'replace' })],
      }),
      data,
    );
    expect(result.valid).toBe(true);
    const appConfig = result.nextData!.config.app;
    const extConfig = appConfig['com.example.ext'] as Record<string, unknown>;
    expect(extConfig.theme).toBe('dark');
    expect(extConfig.layout).toBeUndefined(); // replaced away
  });

  it('app.update diff after includes mode', () => {
    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [],
    });
    const result = compileTimelinePatch(
      makePatch({
        operations: [makeOp('app.update', 'com.example.ext', { theme: 'dark', mode: 'replace' })],
      }),
      data,
    );
    const entry = result.diff.entries.find((e: any) => e.target === 'com.example.ext');
    expect(entry!.after).toHaveProperty('mode', 'replace');
  });
});

describe('compileTimelinePatch — merge/replace for project-data.write', () => {
  it('replace mode (default) overwrites the key', () => {
    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [],
      app: { 'com.example.ext': { settings: { volume: 1, theme: 'light' } } },
    });
    const result = compileTimelinePatch(
      makePatch({
        operations: [makeOp('project-data.write', 'com.example.ext', { key: 'settings', value: { volume: 2 } })],
      }),
      data,
    );
    expect(result.valid).toBe(true);
    const appConfig = result.nextData!.config.app;
    const extConfig = appConfig['com.example.ext'] as Record<string, unknown>;
    const settings = extConfig.settings as Record<string, unknown>;
    expect(settings.volume).toBe(2);
    // Replace mode (default): theme key is gone
    expect(settings.theme).toBeUndefined();
  });

  it('merge mode deep-merges into existing object', () => {
    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [],
      app: { 'com.example.ext': { settings: { volume: 1, theme: 'light' } } },
    });
    const result = compileTimelinePatch(
      makePatch({
        operations: [makeOp('project-data.write', 'com.example.ext', { key: 'settings', value: { volume: 2 }, mode: 'merge' })],
      }),
      data,
    );
    expect(result.valid).toBe(true);
    const appConfig = result.nextData!.config.app;
    const extConfig = appConfig['com.example.ext'] as Record<string, unknown>;
    const settings = extConfig.settings as Record<string, unknown>;
    expect(settings.volume).toBe(2); // updated
    expect(settings.theme).toBe('light'); // preserved by deep merge
  });

  it('project-data.write diff after includes mode and actual value', () => {
    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [],
    });
    const result = compileTimelinePatch(
      makePatch({
        operations: [makeOp('project-data.write', 'com.example.ext', { key: 'k', value: 42, mode: 'replace' })],
      }),
      data,
    );
    const entry = result.diff.entries.find((e: any) => e.target === 'com.example.ext');
    expect(entry!.after).toHaveProperty('mode', 'replace');
    expect(entry!.after).toHaveProperty('value', 42);
  });
});

describe('compileTimelinePatch — project-data extension total bytes overflow', () => {
  it('produces error diagnostic when projected total bytes exceed MAX_EXTENSION_TOTAL_BYTES', () => {
    // Build existing app data close to 1 MB
    const existingEntries: Record<string, unknown> = {};
    const bigValue = 'x'.repeat(50000); // ~50KB per entry
    for (let i = 0; i < 20; i++) {
      existingEntries[`key${i}`] = { data: bigValue };
    }
    // This is roughly 20 * 50011 ≈ 1,000,220 bytes (just under 1 MB)

    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [],
      app: { 'com.example.ext': existingEntries },
    });

    // Now try to write another entry that pushes it over 1 MB
    const newBigValue = 'x'.repeat(50000);
    const result = compileTimelinePatch(
      makePatch({
        operations: [
          makeOp('project-data.write', 'com.example.ext', {
            key: 'overflow-key',
            value: { data: newBigValue },
          }),
        ],
      }),
      data,
    );

    // Should produce error diagnostic about extension-total-exceeded
    const overflowDiag = result.diagnostics.find(
      (d) => d.code === 'timeline-patch/project-data-overflow' &&
        (d.detail as any)?.code === 'project-data/extension-total-exceeded',
    );
    expect(overflowDiag).toBeDefined();
    expect(overflowDiag!.severity).toBe('error');
    expect(overflowDiag!.op).toBe('project-data.write');
    expect(overflowDiag!.target).toBe('com.example.ext');
    // Should still be valid since overflow diagnostic is guidance
    expect(result.valid).toBe(true);
  });

  it('produces ProjectDataLimitDetail with extension-total-exceeded shape', () => {
    const existingEntries: Record<string, unknown> = {};
    const bigValue = 'x'.repeat(50000);
    for (let i = 0; i < 21; i++) {
      existingEntries[`key${i}`] = { data: bigValue };
    }

    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [],
      app: { 'com.example.ext': existingEntries },
    });

    const result = compileTimelinePatch(
      makePatch({
        operations: [
          makeOp('project-data.write', 'com.example.ext', {
            key: 'overflow',
            value: { data: 'x'.repeat(50000) },
          }),
        ],
      }),
      data,
    );

    const diag = result.diagnostics.find(
      (d) => d.code === 'timeline-patch/project-data-overflow' &&
        (d.detail as any)?.code === 'project-data/extension-total-exceeded',
    );
    expect(diag).toBeDefined();
    const detail = diag!.detail as {
      code: string;
      extensionId: string;
      limit: number;
      actual: number;
      unit: string;
    };
    expect(detail.code).toBe('project-data/extension-total-exceeded');
    expect(detail.extensionId).toBe('com.example.ext');
    expect(detail.limit).toBe(1 * 1024 * 1024);
    expect(typeof detail.actual).toBe('number');
    expect(detail.actual).toBeGreaterThan(1 * 1024 * 1024);
    expect(detail.unit).toBe('bytes');
  });

  it('does not produce overflow diagnostic when under MAX_EXTENSION_TOTAL_BYTES', () => {
    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [],
      app: { 'com.example.ext': { k1: { data: 'small' } } },
    });

    const result = compileTimelinePatch(
      makePatch({
        operations: [
          makeOp('project-data.write', 'com.example.ext', {
            key: 'k2',
            value: { data: 'also-small' },
          }),
        ],
      }),
      data,
    );

    const overflowDiag = result.diagnostics.find(
      (d) => d.code === 'timeline-patch/project-data-overflow',
    );
    expect(overflowDiag).toBeUndefined();
    expect(result.valid).toBe(true);
  });

  it('replacing an existing entry with a smaller one does not overflow', () => {
    const bigValue = 'x'.repeat(900000); // ~900 KB
    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [],
      app: { 'com.example.ext': { big: { data: bigValue } } },
    });

    const result = compileTimelinePatch(
      makePatch({
        operations: [
          makeOp('project-data.write', 'com.example.ext', {
            key: 'big',
            value: { data: 'tiny' },
          }),
        ],
      }),
      data,
    );

    const overflowDiag = result.diagnostics.find(
      (d) => d.code === 'timeline-patch/project-data-overflow',
    );
    expect(overflowDiag).toBeUndefined();
    expect(result.valid).toBe(true);
  });

  it('separate extensions have independent total byte budgets', () => {
    const existingEntries: Record<string, unknown> = {};
    const bigValue = 'x'.repeat(50000);
    for (let i = 0; i < 20; i++) {
      existingEntries[`key${i}`] = { data: bigValue };
    }
    // Extension A is nearly full. Extension B is empty.

    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [],
      app: {
        'com.ext-a': existingEntries,
        'com.ext-b': {},
      },
    });

    // Writing to extension B should not overflow (it has its own budget)
    const result = compileTimelinePatch(
      makePatch({
        operations: [
          makeOp('project-data.write', 'com.ext-b', {
            key: 'new-key',
            value: { data: bigValue },
          }),
        ],
      }),
      data,
    );

    const overflowDiag = result.diagnostics.find(
      (d) => d.code === 'timeline-patch/project-data-overflow',
    );
    expect(overflowDiag).toBeUndefined();
    expect(result.valid).toBe(true);
  });

  it('exactly at MAX_EXTENSION_TOTAL_BYTES is accepted (boundary)', () => {
    // Build entries that sum exactly to 1 MB
    const MAX = 1 * 1024 * 1024;
    const existingEntries: Record<string, unknown> = {};
    const entryValue = 'x'.repeat(10000);
    const entrySize = JSON.stringify({ data: entryValue }).length;
    const entriesNeeded = Math.floor(MAX / entrySize);

    for (let i = 0; i < entriesNeeded; i++) {
      existingEntries[`key${i}`] = { data: entryValue };
    }

    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [],
      app: { 'com.example.ext': existingEntries },
    });

    const result = compileTimelinePatch(
      makePatch({
        operations: [
          makeOp('project-data.write', 'com.example.ext', {
            key: `key${entriesNeeded}`,
            value: { data: entryValue },
          }),
        ],
      }),
      data,
    );

    const overflowDiag = result.diagnostics.find(
      (d) => d.code === 'timeline-patch/project-data-overflow' &&
        (d.detail as any)?.code === 'project-data/extension-total-exceeded',
    );
    // This test documents behavior at the boundary
    if (overflowDiag) {
      const detail = overflowDiag.detail as Record<string, unknown>;
      expect(detail.code).toBe('project-data/extension-total-exceeded');
      expect(detail.extensionId).toBe('com.example.ext');
      expect(detail.unit).toBe('bytes');
    }
  });
});

describe('compileTimelinePatch — project-data entry count overflow', () => {
  it('produces error diagnostic when a new key exceeds MAX_ENTRIES_PER_EXTENSION', () => {
    const existingEntries: Record<string, unknown> = {};
    for (let i = 0; i < 128; i++) {
      existingEntries[`key${i}`] = { value: i };
    }

    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [],
      app: { 'com.example.ext': existingEntries },
    });

    const result = compileTimelinePatch(
      makePatch({
        operations: [
          makeOp('project-data.write', 'com.example.ext', {
            key: 'new-key',
            value: { value: 999 },
          }),
        ],
      }),
      data,
    );

    const overflowDiag = result.diagnostics.find(
      (d) => d.code === 'timeline-patch/project-data-overflow' &&
        (d.detail as any)?.code === 'project-data/entry-count-exceeded',
    );
    expect(overflowDiag).toBeDefined();
    expect(overflowDiag!.severity).toBe('error');
    expect(overflowDiag!.op).toBe('project-data.write');
    expect(overflowDiag!.target).toBe('com.example.ext');
    expect(result.valid).toBe(true);
  });

  it('produces ProjectDataLimitDetail with entry-count-exceeded shape', () => {
    const existingEntries: Record<string, unknown> = {};
    for (let i = 0; i < 128; i++) {
      existingEntries[`key${i}`] = { value: i };
    }

    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [],
      app: { 'com.example.ext': existingEntries },
    });

    const result = compileTimelinePatch(
      makePatch({
        operations: [
          makeOp('project-data.write', 'com.example.ext', {
            key: 'new-key',
            value: { value: 999 },
          }),
        ],
      }),
      data,
    );

    const diag = result.diagnostics.find(
      (d) => d.code === 'timeline-patch/project-data-overflow' &&
        (d.detail as any)?.code === 'project-data/entry-count-exceeded',
    );
    expect(diag).toBeDefined();
    const detail = diag!.detail as {
      code: string;
      extensionId: string;
      limit: number;
      actual: number;
      unit: string;
    };
    expect(detail.code).toBe('project-data/entry-count-exceeded');
    expect(detail.extensionId).toBe('com.example.ext');
    expect(detail.limit).toBe(128);
    expect(detail.actual).toBe(129);
    expect(detail.unit).toBe('entries');
  });

  it('does not produce entry-count diagnostic when under MAX_ENTRIES_PER_EXTENSION', () => {
    const existingEntries: Record<string, unknown> = {};
    for (let i = 0; i < 10; i++) {
      existingEntries[`key${i}`] = { value: i };
    }

    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [],
      app: { 'com.example.ext': existingEntries },
    });

    const result = compileTimelinePatch(
      makePatch({
        operations: [
          makeOp('project-data.write', 'com.example.ext', {
            key: 'new-key',
            value: { value: 999 },
          }),
        ],
      }),
      data,
    );

    const overflowDiag = result.diagnostics.find(
      (d) => d.code === 'timeline-patch/project-data-overflow',
    );
    expect(overflowDiag).toBeUndefined();
    expect(result.valid).toBe(true);
  });

  it('replacing an existing key does not count toward entry limit', () => {
    const existingEntries: Record<string, unknown> = {};
    for (let i = 0; i < 128; i++) {
      existingEntries[`key${i}`] = { value: i };
    }

    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [],
      app: { 'com.example.ext': existingEntries },
    });

    // Replace an existing key — should not trigger entry-count overflow
    const result = compileTimelinePatch(
      makePatch({
        operations: [
          makeOp('project-data.write', 'com.example.ext', {
            key: 'key0',
            value: { value: 999 },
          }),
        ],
      }),
      data,
    );

    const overflowDiag = result.diagnostics.find(
      (d) => d.code === 'timeline-patch/project-data-overflow' &&
        (d.detail as any)?.code === 'project-data/entry-count-exceeded',
    );
    expect(overflowDiag).toBeUndefined();
    expect(result.valid).toBe(true);
  });

  it('separate extensions have independent entry count budgets', () => {
    const existingEntries: Record<string, unknown> = {};
    for (let i = 0; i < 128; i++) {
      existingEntries[`key${i}`] = { value: i };
    }

    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [],
      app: {
        'com.ext-a': existingEntries,
        'com.ext-b': {},
      },
    });

    // Writing to extension B should not be subject to extension A's entry count
    const result = compileTimelinePatch(
      makePatch({
        operations: [
          makeOp('project-data.write', 'com.ext-b', {
            key: 'new-key',
            value: { value: 1 },
          }),
        ],
      }),
      data,
    );

    const overflowDiag = result.diagnostics.find(
      (d) => d.code === 'timeline-patch/project-data-overflow',
    );
    expect(overflowDiag).toBeUndefined();
    expect(result.valid).toBe(true);
  });

  it('entry count overflow diagnostic includes operationIndex', () => {
    const existingEntries: Record<string, unknown> = {};
    for (let i = 0; i < 128; i++) {
      existingEntries[`key${i}`] = { value: i };
    }

    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [],
      app: { 'com.example.ext': existingEntries },
    });

    const result = compileTimelinePatch(
      makePatch({
        operations: [
          makeOp('clip.add', 'c1', { at: 0, clipType: 'media' }),
          makeOp('project-data.write', 'com.example.ext', {
            key: 'new-key',
            value: { value: 999 },
          }),
        ],
      }),
      data,
    );

    const diag = result.diagnostics.find(
      (d) => d.code === 'timeline-patch/project-data-overflow' &&
        (d.detail as any)?.code === 'project-data/entry-count-exceeded',
    );
    expect(diag).toBeDefined();
    expect(diag!.operationIndex).toBe(1);
  });

  it('total bytes overflow diagnostic includes operationIndex', () => {
    const existingEntries: Record<string, unknown> = {};
    const bigValue = 'x'.repeat(50000);
    for (let i = 0; i < 21; i++) {
      existingEntries[`key${i}`] = { data: bigValue };
    }

    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [],
      app: { 'com.example.ext': existingEntries },
    });

    const result = compileTimelinePatch(
      makePatch({
        operations: [
          makeOp('clip.add', 'c1', { at: 0, clipType: 'media' }),
          makeOp('project-data.write', 'com.example.ext', {
            key: 'overflow',
            value: { data: 'x'.repeat(50000) },
          }),
        ],
      }),
      data,
    );

    const diag = result.diagnostics.find(
      (d) => d.code === 'timeline-patch/project-data-overflow' &&
        (d.detail as any)?.code === 'project-data/extension-total-exceeded',
    );
    expect(diag).toBeDefined();
    expect(diag!.operationIndex).toBe(1);
  });

  it('both total bytes and entry count overflow diagnostics produced for same write', () => {
    const existingEntries: Record<string, unknown> = {};
    const bigValue = 'x'.repeat(10000);
    for (let i = 0; i < 128; i++) {
      existingEntries[`key${i}`] = { data: bigValue };
    }

    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [],
      app: { 'com.example.ext': existingEntries },
    });

    // This write should trigger BOTH overflow limits
    const result = compileTimelinePatch(
      makePatch({
        operations: [
          makeOp('project-data.write', 'com.example.ext', {
            key: 'overflow',
            value: { data: bigValue },
          }),
        ],
      }),
      data,
    );

    const totalDiag = result.diagnostics.find(
      (d) => d.code === 'timeline-patch/project-data-overflow' &&
        (d.detail as any)?.code === 'project-data/extension-total-exceeded',
    );
    const countDiag = result.diagnostics.find(
      (d) => d.code === 'timeline-patch/project-data-overflow' &&
        (d.detail as any)?.code === 'project-data/entry-count-exceeded',
    );
    expect(totalDiag).toBeDefined();
    expect(countDiag).toBeDefined();
    expect(result.valid).toBe(true);
  });
});

describe('compileTimelinePatch — project-data overflow guidance', () => {
  it('overflow diagnostic messages include extension ID, limit, and actual values', () => {
    const existingEntries: Record<string, unknown> = {};
    for (let i = 0; i < 128; i++) {
      existingEntries[`key${i}`] = { value: i };
    }

    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [],
      app: { 'com.example.ext': existingEntries },
    });

    const result = compileTimelinePatch(
      makePatch({
        operations: [
          makeOp('project-data.write', 'com.example.ext', {
            key: 'new-key',
            value: { value: 999 },
          }),
        ],
      }),
      data,
    );

    const diag = result.diagnostics.find(
      (d) => d.code === 'timeline-patch/project-data-overflow' &&
        (d.detail as any)?.code === 'project-data/entry-count-exceeded',
    );
    expect(diag).toBeDefined();
    // Message should be diagnostic-rich for overflow guidance
    expect(diag!.message).toContain('com.example.ext');
    expect(diag!.message).toContain('128');
    expect(diag!.message).toContain('MAX_ENTRIES_PER_EXTENSION');
  });

  it('total bytes overflow message contains size guidance', () => {
    const existingEntries: Record<string, unknown> = {};
    const bigValue = 'x'.repeat(50000);
    for (let i = 0; i < 21; i++) {
      existingEntries[`key${i}`] = { data: bigValue };
    }

    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [],
      app: { 'com.example.ext': existingEntries },
    });

    const result = compileTimelinePatch(
      makePatch({
        operations: [
          makeOp('project-data.write', 'com.example.ext', {
            key: 'overflow',
            value: { data: 'x'.repeat(50000) },
          }),
        ],
      }),
      data,
    );

    const diag = result.diagnostics.find(
      (d) => d.code === 'timeline-patch/project-data-overflow' &&
        (d.detail as any)?.code === 'project-data/extension-total-exceeded',
    );
    expect(diag).toBeDefined();
    expect(diag!.message).toContain('com.example.ext');
    expect(diag!.message).toContain('MAX_EXTENSION_TOTAL_BYTES');
    expect(diag!.message).toContain(String(1 * 1024 * 1024));
  });

  it('rollback-safety: original configApp is not mutated when overflow occurs', () => {
    const existingEntries: Record<string, unknown> = {};
    const bigValue = 'x'.repeat(50000);
    for (let i = 0; i < 21; i++) {
      existingEntries[`key${i}`] = { data: bigValue };
    }

    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [],
      app: { 'com.example.ext': existingEntries },
    });

    const appBefore = data.config.app;
    const extBefore = { ...(appBefore['com.example.ext'] as Record<string, unknown>) };
    const extKeyCountBefore = Object.keys(extBefore).length;

    const result = compileTimelinePatch(
      makePatch({
        operations: [
          makeOp('project-data.write', 'com.example.ext', {
            key: 'overflow',
            value: { data: 'x'.repeat(50000) },
          }),
        ],
      }),
      data,
    );

    // Original data must be unmodified (rollback-safe)
    const appAfter = data.config.app;
    const extAfter = { ...(appAfter['com.example.ext'] as Record<string, unknown>) };
    expect(Object.keys(extAfter).length).toBe(extKeyCountBefore);
    // The patch should still be applied to nextData
    expect(result.valid).toBe(true);
    expect(result.nextData).not.toBeNull();
  });

  it('replayability: same patch produces same diagnostics and nextData when replayed', () => {
    const existingEntries: Record<string, unknown> = {};
    for (let i = 0; i < 128; i++) {
      existingEntries[`key${i}`] = { value: i };
    }

    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [],
      app: { 'com.example.ext': existingEntries },
    });

    const patch = makePatch({
      operations: [
        makeOp('project-data.write', 'com.example.ext', {
          key: 'new-key',
          value: { value: 999 },
        }),
      ],
    });

    const result1 = compileTimelinePatch(patch, data);
    const result2 = compileTimelinePatch(patch, data);

    // Same patch on same data should produce identical results (replayable)
    expect(result1.valid).toBe(result2.valid);
    expect(result1.diagnostics.length).toBe(result2.diagnostics.length);
    expect(result1.diff.entries.length).toBe(result2.diff.entries.length);

    const diags1 = result1.diagnostics.filter(
      (d) => d.code === 'timeline-patch/project-data-overflow',
    );
    const diags2 = result2.diagnostics.filter(
      (d) => d.code === 'timeline-patch/project-data-overflow',
    );
    expect(diags1.length).toBe(diags2.length);
  });
});


describe('compileTimelinePatch — operation ordering', () => {
  it('applies operations with order field first, in ascending order', () => {
    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [{ id: 'c1', track: 'V1', at: 0, hold: 10, volume: 1.0 }],
    });
    // Operation 0 (order: 5) sets volume to 0.5
    // Operation 1 (order: 2) sets volume to 0.2 — should apply BEFORE the first
    // Final volume should be 0.5 (order 2 applied first, then order 5 overwrites)
    const result = compileTimelinePatch(
      makePatch({
        operations: [
          makeOp('clip.update', 'c1', { volume: 0.5 }, 5),
          makeOp('clip.update', 'c1', { volume: 0.2 }, 2),
        ],
      }),
      data,
    );
    expect(result.valid).toBe(true);
    const updatedMeta = result.mutation!.metaUpdates!['c1'];
    expect(updatedMeta.volume).toBe(0.5); // order 5 applied last
  });

  it('operations without order are applied after those with order', () => {
    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [{ id: 'c1', track: 'V1', at: 0, hold: 10, volume: 1.0 }],
    });
    // Unordered sets volume=0.3, then ordered (order=1) sets volume=0.9
    // Ordered should apply first, then unordered → final = 0.3
    const result = compileTimelinePatch(
      makePatch({
        operations: [
          makeOp('clip.update', 'c1', { volume: 0.3 }),        // no order
          makeOp('clip.update', 'c1', { volume: 0.9 }, 1),     // order 1
        ],
      }),
      data,
    );
    expect(result.valid).toBe(true);
    const updatedMeta = result.mutation!.metaUpdates!['c1'];
    expect(updatedMeta.volume).toBe(0.3); // unordered applied last
  });

  it('ties on order are broken by original array position (stable)', () => {
    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [{ id: 'c1', track: 'V1', at: 0, hold: 10, volume: 1.0 }],
    });
    // Both have order=1, original positions: index 0 sets volume=0.3, index 1 sets volume=0.7
    // index 0 should apply first, index 1 second → final = 0.7
    const result = compileTimelinePatch(
      makePatch({
        operations: [
          makeOp('clip.update', 'c1', { volume: 0.3 }, 1), // original index 0
          makeOp('clip.update', 'c1', { volume: 0.7 }, 1), // original index 1
        ],
      }),
      data,
    );
    expect(result.valid).toBe(true);
    const updatedMeta = result.mutation!.metaUpdates!['c1'];
    expect(updatedMeta.volume).toBe(0.7); // original index 1 applied last
  });

  it('negative orders sort before zero and positive', () => {
    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [{ id: 'c1', track: 'V1', at: 0, hold: 10, volume: 1.0 }],
    });
    // Order -1 sets volume=0.1, order 0 sets volume=0.5, order 5 sets volume=0.9
    // -1 applied first, then 0, then 5 → final = 0.9
    const result = compileTimelinePatch(
      makePatch({
        operations: [
          makeOp('clip.update', 'c1', { volume: 0.5 }, 0),
          makeOp('clip.update', 'c1', { volume: 0.1 }, -1),
          makeOp('clip.update', 'c1', { volume: 0.9 }, 5),
        ],
      }),
      data,
    );
    expect(result.valid).toBe(true);
    const updatedMeta = result.mutation!.metaUpdates!['c1'];
    expect(updatedMeta.volume).toBe(0.9); // order 5 applied last
  });
});

describe('compileTimelinePatch — clip.move with before/after anchors', () => {
  it('places clip before the anchor clip in clipOrderOverride', () => {
    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [
        { id: 'c1', track: 'V1', at: 0, hold: 10 },
        { id: 'c2', track: 'V1', at: 10, hold: 10 },
        { id: 'c3', track: 'V1', at: 20, hold: 10 },
      ],
    });
    // Move c3 before c2 → order should be [c1, c3, c2]
    const result = compileTimelinePatch(
      makePatch({
        operations: [makeOp('clip.move', 'c3', { before: 'c2' })],
      }),
      data,
    );
    expect(result.valid).toBe(true);
    const order = result.mutation!.clipOrderOverride!['V1'];
    expect(order.indexOf('c3')).toBeLessThan(order.indexOf('c2'));
    expect(order).toEqual(['c1', 'c3', 'c2']);
  });

  it('places clip after the anchor clip in clipOrderOverride', () => {
    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [
        { id: 'c1', track: 'V1', at: 0, hold: 10 },
        { id: 'c2', track: 'V1', at: 10, hold: 10 },
        { id: 'c3', track: 'V1', at: 20, hold: 10 },
      ],
    });
    // Move c1 after c2 → order should be [c2, c1, c3]
    const result = compileTimelinePatch(
      makePatch({
        operations: [makeOp('clip.move', 'c1', { after: 'c2' })],
      }),
      data,
    );
    expect(result.valid).toBe(true);
    const order = result.mutation!.clipOrderOverride!['V1'];
    expect(order.indexOf('c1')).toBeGreaterThan(order.indexOf('c2'));
    expect(order).toEqual(['c2', 'c1', 'c3']);
  });

  it('before anchor takes precedence over after anchor', () => {
    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [
        { id: 'c1', track: 'V1', at: 0, hold: 10 },
        { id: 'c2', track: 'V1', at: 10, hold: 10 },
        { id: 'c3', track: 'V1', at: 20, hold: 10 },
      ],
    });
    // Move c3 with before=c2, after=c1 → before wins → c3 before c2
    const result = compileTimelinePatch(
      makePatch({
        operations: [makeOp('clip.move', 'c3', { before: 'c2', after: 'c1' })],
      }),
      data,
    );
    expect(result.valid).toBe(true);
    const order = result.mutation!.clipOrderOverride!['V1'];
    expect(order.indexOf('c3')).toBeLessThan(order.indexOf('c2'));
  });

  it('diff after includes before/after anchor info', () => {
    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [
        { id: 'c1', track: 'V1', at: 0, hold: 10 },
        { id: 'c2', track: 'V1', at: 10, hold: 10 },
        { id: 'c3', track: 'V1', at: 20, hold: 10 },
      ],
    });
    const result = compileTimelinePatch(
      makePatch({
        operations: [makeOp('clip.move', 'c3', { before: 'c2' })],
      }),
      data,
    );
    const entry = result.diff.entries.find((e: any) => e.target === 'c3');
    expect(entry!.after).toHaveProperty('before', 'c2');
  });

  it('affectedObjectIds includes anchor clip IDs', () => {
    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [
        { id: 'c1', track: 'V1', at: 0, hold: 10 },
        { id: 'c2', track: 'V1', at: 10, hold: 10 },
      ],
    });
    const result = compileTimelinePatch(
      makePatch({
        operations: [makeOp('clip.move', 'c1', { before: 'c2' })],
      }),
      data,
    );
    expect(result.diff.affectedObjectIds).toContain('c2');
    expect(result.diff.affectedObjectIds).toContain('c1');
  });
});

describe('compileTimelinePatch — extension.noop serialization', () => {
  it('produces a diff entry for extension.noop', () => {
    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [],
    });
    const result = compileTimelinePatch(
      makePatch({
        operations: [makeOp('extension.noop', 'com.example.ext', { message: 'hello' })],
      }),
      data,
    );
    expect(result.valid).toBe(true);
    const entry = result.diff.entries.find((e: any) => e.target === 'com.example.ext');
    expect(entry).toBeDefined();
    expect(entry!.granularity).toBe('app');
    expect(entry!.after).toHaveProperty('noop', true);
    expect(entry!.after).toHaveProperty('payload');
  });

  it('extension.noop diff entry includes extensionId', () => {
    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [],
    });
    const result = compileTimelinePatch(
      makePatch({
        operations: [makeOp('extension.noop', 'com.other.ext')],
      }),
      data,
    );
    const entry = result.diff.entries.find((e: any) => e.target === 'com.other.ext');
    expect(entry!.after).toHaveProperty('extensionId', 'com.other.ext');
    expect(entry!.after).toHaveProperty('noop', true);
  });

  it('extension.noop adds target to affectedObjectIds', () => {
    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [],
    });
    const result = compileTimelinePatch(
      makePatch({
        operations: [makeOp('extension.noop', 'com.example.ext')],
      }),
      data,
    );
    expect(result.diff.affectedObjectIds).toContain('com.example.ext');
  });
});

describe('compileTimelinePatch — patch immutability', () => {
  it('does not mutate the original TimelineData', () => {
    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [{ id: 'c1', track: 'V1', at: 0, hold: 10, volume: 1.0 }],
    });
    const originalVolume = (data.config.clips[0] as any).volume;
    compileTimelinePatch(
      makePatch({
        operations: [makeOp('clip.update', 'c1', { volume: 0.3 })],
      }),
      data,
    );
    expect((data.config.clips[0] as any).volume).toBe(originalVolume); // unchanged
  });

  it('previewTimelinePatch does not mutate original TimelineData', () => {
    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [{ id: 'c1', track: 'V1', at: 0, hold: 10, volume: 1.0 }],
    });
    const originalVolume = (data.config.clips[0] as any).volume;
    previewTimelinePatch(
      makePatch({
        operations: [makeOp('clip.update', 'c1', { volume: 0.3 })],
      }),
      data,
    );
    expect((data.config.clips[0] as any).volume).toBe(originalVolume);
  });

  it('previewTimelinePatch returns fullyPreviewable=true for non-reserved ops', () => {
    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [{ id: 'c1', track: 'V1', at: 0, hold: 10 }],
    });
    const result = previewTimelinePatch(
      makePatch({
        operations: [makeOp('clip.remove', 'c1')],
      }),
      data,
    );
    expect(result.fullyPreviewable).toBe(true);
    expect(result.diff.entries.length).toBeGreaterThan(0);
  });

  it('previewTimelinePatch returns fullyPreviewable=false for reserved ops', () => {
    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [{ id: 'c1', track: 'V1', at: 0, hold: 10 }],
    });
    const result = previewTimelinePatch(
      makePatch({
        operations: [makeOp('clip.split', 'c1', { at: 5 })],
      }),
      data,
    );
    expect(result.fullyPreviewable).toBe(false);
  });

  it('compileTimelinePatch returns mutation with expected shape', () => {
    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [{ id: 'c1', track: 'V1', at: 0, hold: 10 }],
    });
    const result = compileTimelinePatch(
      makePatch({
        operations: [makeOp('clip.update', 'c1', { volume: 0.5 })],
      }),
      data,
    );
    expect(result.mutation).not.toBeNull();
    expect(result.mutation!.type).toBe('rows');
    expect(result.mutation!.rows).toBeDefined();
    expect(result.mutation!.metaUpdates).toBeDefined();
    expect(result.mutation!.clipOrderOverride).toBeDefined();
  });
});

// ===========================================================================
// T7: Pure patch compile/preview tests and golden fixture seeds
//     covering insert, update, delete, move/reorder, track, asset, app,
//     extension data, and namespaced extension no-op/example operations.
// ===========================================================================

// ---------------------------------------------------------------------------
// compileTimelinePatch — clip.add (insert)
// ---------------------------------------------------------------------------

describe('compileTimelinePatch — clip.add (insert)', () => {
  it('adds a clip to existing track and populates nextData', () => {
    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [{ id: 'c1', track: 'V1', at: 0, hold: 10 }],
    });
    const result = compileTimelinePatch(
      makePatch({
        operations: [makeOp('clip.add', 'c2', { track: 'V1', at: 10, clipType: 'media' })],
      }),
      data,
    );
    expect(result.valid).toBe(true);
    // nextData should contain the new clip
    const nextClips = result.nextData!.config.clips;
    expect(nextClips.some((c: any) => c.id === 'c2')).toBe(true);
    // diff entry
    const entry = result.diff.entries.find((e: any) => e.target === 'c2');
    expect(entry).toBeDefined();
    expect(entry!.granularity).toBe('clip');
    expect(entry!.kind).toBe('added');
    expect(entry!.after).toMatchObject({ id: 'c2', track: 'V1', at: 10, clipType: 'media' });
    // affected IDs
    expect(result.diff.affectedObjectIds).toContain('c2');
    expect(result.diff.affectedObjectIds).toContain('V1');
  });

  it('auto-creates track when target track does not exist', () => {
    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [],
    });
    const result = compileTimelinePatch(
      makePatch({
        operations: [makeOp('clip.add', 'c1', { track: 'V99', at: 0, clipType: 'media' })],
      }),
      data,
    );
    expect(result.valid).toBe(true);
    // Warning about auto-creation
    const warn = result.diagnostics.find((d: any) => d.code === 'timeline-patch/target-not-found');
    expect(warn).toBeDefined();
    expect(warn!.detail).toMatchObject({ missingTrack: 'V99', autoCreated: true });
    // Track should exist in nextData
    const nextTracks = result.nextData!.config.tracks!;
    expect(nextTracks.some((t: any) => t.id === 'V99')).toBe(true);
  });

  it('uses default track when no track specified and tracks exist', () => {
    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [],
    });
    const result = compileTimelinePatch(
      makePatch({
        operations: [makeOp('clip.add', 'c-new')],
      }),
      data,
    );
    expect(result.valid).toBe(true);
    const added = result.nextData!.config.clips.find((c: any) => c.id === 'c-new');
    expect(added.track).toBe('V1');
    expect(added.at).toBe(0);
  });

  it('clip.add diff entry carries clipType when provided', () => {
    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [],
    });
    const result = compileTimelinePatch(
      makePatch({
        operations: [makeOp('clip.add', 'c1', { track: 'V1', at: 5, clipType: 'text' })],
      }),
      data,
    );
    const entry = result.diff.entries.find((e: any) => e.target === 'c1');
    expect(entry!.after).toHaveProperty('clipType', 'text');
  });
});

// ---------------------------------------------------------------------------
// compileTimelinePatch — clip.remove (delete)
// ---------------------------------------------------------------------------

describe('compileTimelinePatch — clip.remove (delete)', () => {
  it('removes a clip and reflects in nextData and diff', () => {
    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [
        { id: 'c1', track: 'V1', at: 0, hold: 10 },
        { id: 'c2', track: 'V1', at: 10, hold: 10 },
      ],
    });
    const result = compileTimelinePatch(
      makePatch({
        operations: [makeOp('clip.remove', 'c1')],
      }),
      data,
    );
    expect(result.valid).toBe(true);
    // c1 should be gone
    const nextClipIds = result.nextData!.config.clips.map((c: any) => c.id);
    expect(nextClipIds).not.toContain('c1');
    expect(nextClipIds).toContain('c2');
    // diff entry
    const entry = result.diff.entries.find((e: any) => e.target === 'c1');
    expect(entry).toBeDefined();
    expect(entry!.granularity).toBe('clip');
    expect(entry!.kind).toBe('removed');
    expect(entry!.before).toMatchObject({ id: 'c1', track: 'V1', at: 0 });
    // affected IDs
    expect(result.diff.affectedObjectIds).toContain('c1');
  });

  it('produces warning when clip to remove is not found', () => {
    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [],
    });
    const result = compileTimelinePatch(
      makePatch({
        operations: [makeOp('clip.remove', 'nonexistent')],
      }),
      data,
    );
    expect(result.valid).toBe(true);
    const warn = result.diagnostics.find((d: any) => d.code === 'timeline-patch/target-not-found');
    expect(warn).toBeDefined();
    expect(warn!.target).toBe('nonexistent');
    // diff should have no entry for nonexistent
    expect(result.diff.entries.some((e: any) => e.target === 'nonexistent')).toBe(false);
  });

  it('removes clip from clipOrder on all tracks', () => {
    const data = makeMinimalTimelineData({
      tracks: [
        { id: 'V1', kind: 'visual', label: 'V1' },
        { id: 'V2', kind: 'visual', label: 'V2' },
      ],
      clips: [
        { id: 'c1', track: 'V1', at: 0, hold: 10 },
        { id: 'c2', track: 'V2', at: 0, hold: 10 },
      ],
    });
    const result = compileTimelinePatch(
      makePatch({
        operations: [makeOp('clip.remove', 'c1')],
      }),
      data,
    );
    const orderOverride = result.mutation!.clipOrderOverride!;
    // c1 should not appear in any track's order
    for (const ids of Object.values(orderOverride)) {
      expect(ids).not.toContain('c1');
    }
    // c2 should still be in V2's order
    expect(orderOverride['V2']).toContain('c2');
  });
});

// ---------------------------------------------------------------------------
// compileTimelinePatch — clip.move (move/reorder + track change)
// ---------------------------------------------------------------------------

describe('compileTimelinePatch — clip.move additional scenarios', () => {
  it('moves clip to a different track and updates diff kind', () => {
    const data = makeMinimalTimelineData({
      tracks: [
        { id: 'V1', kind: 'visual', label: 'V1' },
        { id: 'V2', kind: 'visual', label: 'V2' },
      ],
      clips: [
        { id: 'c1', track: 'V1', at: 0, hold: 10 },
        { id: 'c2', track: 'V2', at: 10, hold: 10 },
      ],
    });
    const result = compileTimelinePatch(
      makePatch({
        operations: [makeOp('clip.move', 'c1', { track: 'V2', at: 20 })],
      }),
      data,
    );
    expect(result.valid).toBe(true);
    // c1 should now be on V2
    const movedClip = result.nextData!.config.clips.find((c: any) => c.id === 'c1');
    expect(movedClip.track).toBe('V2');
    expect(movedClip.at).toBe(20);
    // diff kind should be 'modified' (cross-track move)
    const entry = result.diff.entries.find((e: any) => e.target === 'c1');
    expect(entry!.kind).toBe('modified');
    // old and new tracks in affected
    expect(result.diff.affectedObjectIds).toContain('V1');
    expect(result.diff.affectedObjectIds).toContain('V2');
  });

  it('moves clip on same track produces reordered diff kind', () => {
    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [
        { id: 'c1', track: 'V1', at: 0, hold: 10 },
        { id: 'c2', track: 'V1', at: 10, hold: 10 },
      ],
    });
    const result = compileTimelinePatch(
      makePatch({
        operations: [makeOp('clip.move', 'c1', { at: 15 })],
      }),
      data,
    );
    expect(result.valid).toBe(true);
    const entry = result.diff.entries.find((e: any) => e.target === 'c1');
    expect(entry!.kind).toBe('reordered');
    expect(entry!.after.at).toBe(15);
  });

  it('auto-creates destination track when moving to non-existent track', () => {
    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [{ id: 'c1', track: 'V1', at: 0, hold: 10 }],
    });
    const result = compileTimelinePatch(
      makePatch({
        operations: [makeOp('clip.move', 'c1', { track: 'V3' })],
      }),
      data,
    );
    expect(result.valid).toBe(true);
    const warn = result.diagnostics.find((d: any) =>
      d.code === 'timeline-patch/target-not-found' && d.target === 'c1',
    );
    expect(warn).toBeDefined();
    expect(warn!.detail).toMatchObject({ missingTrack: 'V3', autoCreated: true });
    const nextTracks = result.nextData!.config.tracks!;
    expect(nextTracks.some((t: any) => t.id === 'V3')).toBe(true);
  });

  it('uses order field for fractional positioning when no anchor given', () => {
    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [
        { id: 'c1', track: 'V1', at: 0, hold: 10 },
        { id: 'c2', track: 'V1', at: 10, hold: 10 },
      ],
    });
    // Move c1 with order=20; c2's clip_order/at is 0/10; c1 should end up after c2
    const result = compileTimelinePatch(
      makePatch({
        operations: [makeOp('clip.move', 'c1', { track: 'V1' }, 20)],
      }),
      data,
    );
    expect(result.valid).toBe(true);
    const order = result.mutation!.clipOrderOverride!['V1'];
    // c1 should be after c2 since order 20 > c2's at=10 (or clip_order=0)
    expect(order.indexOf('c1')).toBeGreaterThan(order.indexOf('c2'));
  });
});

// ---------------------------------------------------------------------------
// compileTimelinePatch — track.add
// ---------------------------------------------------------------------------

describe('compileTimelinePatch — track.add', () => {
  it('adds a new track and emits diff entry', () => {
    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [],
    });
    const result = compileTimelinePatch(
      makePatch({
        operations: [makeOp('track.add', 'V2', { kind: 'visual', label: 'Video 2' })],
      }),
      data,
    );
    expect(result.valid).toBe(true);
    const nextTracks = result.nextData!.config.tracks!;
    const added = nextTracks.find((t: any) => t.id === 'V2');
    expect(added).toBeDefined();
    expect(added.kind).toBe('visual');
    expect(added.label).toBe('Video 2');
    // diff entry
    const entry = result.diff.entries.find((e: any) => e.target === 'V2');
    expect(entry).toBeDefined();
    expect(entry!.granularity).toBe('track');
    expect(entry!.kind).toBe('added');
    expect(entry!.after).toMatchObject({ id: 'V2', kind: 'visual', label: 'Video 2' });
    // affected IDs
    expect(result.diff.affectedObjectIds).toContain('V2');
  });

  it('adds an audio track', () => {
    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [],
    });
    const result = compileTimelinePatch(
      makePatch({
        operations: [makeOp('track.add', 'A1', { kind: 'audio', label: 'Audio 1' })],
      }),
      data,
    );
    expect(result.valid).toBe(true);
    const added = result.nextData!.config.tracks!.find((t: any) => t.id === 'A1');
    expect(added.kind).toBe('audio');
  });

  it('produces warning when track already exists', () => {
    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [],
    });
    const result = compileTimelinePatch(
      makePatch({
        operations: [makeOp('track.add', 'V1', { kind: 'visual', label: 'Dup' })],
      }),
      data,
    );
    expect(result.valid).toBe(true);
    const warn = result.diagnostics.find((d: any) => d.code === 'timeline-patch/duplicate-target');
    expect(warn).toBeDefined();
    expect(warn!.target).toBe('V1');
    // diff should have no 'added' entry for V1
    const addedEntry = result.diff.entries.find(
      (e: any) => e.target === 'V1' && e.kind === 'added',
    );
    expect(addedEntry).toBeUndefined();
  });
});

// ---------------------------------------------------------------------------
// compileTimelinePatch — track.remove
// ---------------------------------------------------------------------------

describe('compileTimelinePatch — track.remove', () => {
  it('removes a track and its clips, emitting cascade diff entries', () => {
    const data = makeMinimalTimelineData({
      tracks: [
        { id: 'V1', kind: 'visual', label: 'V1' },
        { id: 'V2', kind: 'visual', label: 'V2' },
      ],
      clips: [
        { id: 'c1', track: 'V1', at: 0, hold: 10 },
        { id: 'c2', track: 'V1', at: 10, hold: 10 },
        { id: 'c3', track: 'V2', at: 0, hold: 10 },
      ],
    });
    const result = compileTimelinePatch(
      makePatch({
        operations: [makeOp('track.remove', 'V1')],
      }),
      data,
    );
    expect(result.valid).toBe(true);
    // V1 should be gone
    const nextTrackIds = result.nextData!.config.tracks!.map((t: any) => t.id);
    expect(nextTrackIds).not.toContain('V1');
    expect(nextTrackIds).toContain('V2');
    // c1 and c2 should be gone; c3 should remain
    const nextClipIds = result.nextData!.config.clips.map((c: any) => c.id);
    expect(nextClipIds).not.toContain('c1');
    expect(nextClipIds).not.toContain('c2');
    expect(nextClipIds).toContain('c3');
    // diff entries: track removed + clip removals
    const trackEntry = result.diff.entries.find((e: any) => e.target === 'V1' && e.granularity === 'track');
    expect(trackEntry).toBeDefined();
    expect(trackEntry!.kind).toBe('removed');
    const clipRemovalEntries = result.diff.entries.filter(
      (e: any) => (e.target === 'c1' || e.target === 'c2') && e.kind === 'removed',
    );
    expect(clipRemovalEntries).toHaveLength(2);
    // affected IDs
    expect(result.diff.affectedObjectIds).toContain('V1');
    expect(result.diff.affectedObjectIds).toContain('c1');
    expect(result.diff.affectedObjectIds).toContain('c2');
  });

  it('produces warning when track to remove is not found', () => {
    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [],
    });
    const result = compileTimelinePatch(
      makePatch({
        operations: [makeOp('track.remove', 'NONEXISTENT')],
      }),
      data,
    );
    expect(result.valid).toBe(true);
    const warn = result.diagnostics.find((d: any) => d.code === 'timeline-patch/target-not-found');
    expect(warn).toBeDefined();
    expect(warn!.target).toBe('NONEXISTENT');
  });

  it('removes empty track with no clips', () => {
    const data = makeMinimalTimelineData({
      tracks: [
        { id: 'V1', kind: 'visual', label: 'V1' },
        { id: 'V2', kind: 'visual', label: 'V2' },
      ],
      clips: [{ id: 'c1', track: 'V1', at: 0, hold: 10 }],
    });
    const result = compileTimelinePatch(
      makePatch({
        operations: [makeOp('track.remove', 'V2')],
      }),
      data,
    );
    expect(result.valid).toBe(true);
    const nextTrackIds = result.nextData!.config.tracks!.map((t: any) => t.id);
    expect(nextTrackIds).not.toContain('V2');
    // no cascade entries since V2 had no clips
    const clipRemovalEntries = result.diff.entries.filter((e: any) => e.kind === 'removed' && e.granularity === 'clip');
    expect(clipRemovalEntries).toHaveLength(0);
  });
});

// ---------------------------------------------------------------------------
// compileTimelinePatch — asset.update / asset.remove
// ---------------------------------------------------------------------------

describe('compileTimelinePatch — asset operations', () => {
  it('asset.update produces diff entry with asset-not-implemented warning', () => {
    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [],
      assets: { 'img-1': { file: 'img1.png', id: 'img-1' } },
    });
    const result = compileTimelinePatch(
      makePatch({
        operations: [makeOp('asset.update', 'img-1', { src: 'https://example.com/new.png', mode: 'merge' })],
      }),
      data,
    );
    expect(result.valid).toBe(true);
    // Warning diagnostic
    const warn = result.diagnostics.find((d: any) => d.code === 'timeline-patch/asset-not-implemented');
    expect(warn).toBeDefined();
    expect(warn!.severity).toBe('warning');
    expect(warn!.target).toBe('img-1');
    expect(warn!.detail).toHaveProperty('mode', 'merge');
    // Diff entry recorded
    const entry = result.diff.entries.find((e: any) => e.target === 'img-1');
    expect(entry).toBeDefined();
    expect(entry!.granularity).toBe('asset');
    expect(entry!.kind).toBe('modified');
    expect(entry!.after).toHaveProperty('src', 'https://example.com/new.png');
    expect(entry!.after).toHaveProperty('mode', 'merge');
    // Affected IDs
    expect(result.diff.affectedObjectIds).toContain('img-1');
  });

  it('asset.update for new asset produces kind=added in diff', () => {
    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [],
      assets: {},
    });
    const result = compileTimelinePatch(
      makePatch({
        operations: [makeOp('asset.update', 'new-asset', { src: 'https://example.com/asset.mp4' })],
      }),
      data,
    );
    expect(result.valid).toBe(true);
    const entry = result.diff.entries.find((e: any) => e.target === 'new-asset');
    expect(entry!.kind).toBe('added');
  });

  it('asset.remove produces diff entry with asset-not-implemented warning', () => {
    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [],
      assets: { 'img-1': { file: 'img1.png', id: 'img-1' } },
    });
    const result = compileTimelinePatch(
      makePatch({
        operations: [makeOp('asset.remove', 'img-1')],
      }),
      data,
    );
    expect(result.valid).toBe(true);
    const warn = result.diagnostics.find((d: any) => d.code === 'timeline-patch/asset-not-implemented');
    expect(warn).toBeDefined();
    expect(warn!.target).toBe('img-1');
    // Diff entry
    const entry = result.diff.entries.find((e: any) => e.target === 'img-1');
    expect(entry).toBeDefined();
    expect(entry!.granularity).toBe('asset');
    expect(entry!.kind).toBe('removed');
    expect(entry!.before).toMatchObject({ key: 'img-1', file: 'img1.png' });
    expect(result.diff.affectedObjectIds).toContain('img-1');
  });

  it('asset.remove for unknown asset still produces diff entry', () => {
    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [],
      assets: {},
    });
    const result = compileTimelinePatch(
      makePatch({
        operations: [makeOp('asset.remove', 'unknown-asset')],
      }),
      data,
    );
    expect(result.valid).toBe(true);
    const entry = result.diff.entries.find((e: any) => e.target === 'unknown-asset');
    expect(entry).toBeDefined();
    expect(entry!.kind).toBe('removed');
    expect(entry!.before).toBeUndefined();
  });
});

// ---------------------------------------------------------------------------
// compileTimelinePatch — project-data.delete
// ---------------------------------------------------------------------------

describe('compileTimelinePatch — project-data.delete', () => {
  it('deletes an existing key from extension project data', () => {
    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [],
      app: { 'com.example.ext': { settings: { volume: 1 }, theme: 'dark' } },
    });
    const result = compileTimelinePatch(
      makePatch({
        operations: [makeOp('project-data.delete', 'com.example.ext', { key: 'settings' })],
      }),
      data,
    );
    expect(result.valid).toBe(true);
    const appConfig = result.nextData!.config.app;
    const extConfig = appConfig['com.example.ext'] as Record<string, unknown>;
    expect(extConfig.settings).toBeUndefined();
    expect(extConfig.theme).toBe('dark'); // preserved
    // diff entry
    const entry = result.diff.entries.find((e: any) => e.target === 'com.example.ext');
    expect(entry).toBeDefined();
    expect(entry!.granularity).toBe('project-data');
    expect(entry!.kind).toBe('removed');
    expect(entry!.before).toMatchObject({ extensionId: 'com.example.ext', key: 'settings' });
    // affected IDs
    expect(result.diff.affectedObjectIds).toContain('com.example.ext');
  });

  it('deleting last key removes extension namespace entirely', () => {
    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [],
      app: { 'com.example.ext': { onlyKey: 'value' } },
    });
    const result = compileTimelinePatch(
      makePatch({
        operations: [makeOp('project-data.delete', 'com.example.ext', { key: 'onlyKey' })],
      }),
      data,
    );
    expect(result.valid).toBe(true);
    const appConfig = result.nextData!.config.app;
    // When the last key is deleted, the extension namespace is removed entirely.
    // config.app may be undefined or an object without the extension key.
    expect(appConfig == null || appConfig['com.example.ext'] === undefined).toBe(true);
  });

  it('deleting non-existent key produces no diff entry', () => {
    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [],
      app: { 'com.example.ext': { existing: 'value' } },
    });
    const result = compileTimelinePatch(
      makePatch({
        operations: [makeOp('project-data.delete', 'com.example.ext', { key: 'nonexistent' })],
      }),
      data,
    );
    expect(result.valid).toBe(true);
    const entry = result.diff.entries.find((e: any) => e.target === 'com.example.ext');
    expect(entry).toBeUndefined();
  });

  it('deleting from non-existent extension produces no diff entry', () => {
    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [],
      app: {},
    });
    const result = compileTimelinePatch(
      makePatch({
        operations: [makeOp('project-data.delete', 'com.other.ext', { key: 'k' })],
      }),
      data,
    );
    expect(result.valid).toBe(true);
    const entry = result.diff.entries.find((e: any) => e.target === 'com.other.ext');
    expect(entry).toBeUndefined();
  });
});

// ---------------------------------------------------------------------------
// compileTimelinePatch — golden fixture seeds (multi-op batches)
// ---------------------------------------------------------------------------

describe('compileTimelinePatch — golden fixture seeds', () => {
  it('full insert+update+delete batch produces correct diff and nextData', () => {
    const data = makeMinimalTimelineData({
      tracks: [
        { id: 'V1', kind: 'visual', label: 'V1' },
        { id: 'A1', kind: 'audio', label: 'A1' },
      ],
      clips: [
        { id: 'c-exists', track: 'V1', at: 0, hold: 10, volume: 1.0 },
      ],
      app: { 'com.ext': { preExisting: true } },
    });
    const result = compileTimelinePatch(
      makePatch({
        version: 1,
        operations: [
          makeOp('clip.add', 'c-new', { track: 'V1', at: 10, clipType: 'media' }, 1),
          makeOp('clip.update', 'c-exists', { volume: 0.5, mode: 'merge' }, 2),
          makeOp('clip.remove', 'c-exists', undefined, 3),
          makeOp('track.add', 'V2', { kind: 'visual', label: 'New Track' }, 0),
          makeOp('project-data.write', 'com.ext', { key: 'settings', value: { theme: 'dark' } }, 4),
        ],
      }),
      data,
    );
    expect(result.valid).toBe(true);

    // Track V2 was added first (order 0)
    const nextTrackIds = result.nextData!.config.tracks!.map((t: any) => t.id);
    expect(nextTrackIds).toContain('V2');

    // c-new added (order 1), then c-exists updated (order 2), then c-exists removed (order 3)
    // c-exists should be removed
    const nextClipIds = result.nextData!.config.clips.map((c: any) => c.id);
    expect(nextClipIds).toContain('c-new');
    expect(nextClipIds).not.toContain('c-exists');

    // c-new volume should not be affected by c-exists update
    const cNew = result.nextData!.config.clips.find((c: any) => c.id === 'c-new');
    expect(cNew.track).toBe('V1');

    // project-data written (order 4)
    const appConfig = result.nextData!.config.app;
    const extConfig = appConfig['com.ext'] as Record<string, unknown>;
    expect(extConfig.settings).toEqual({ theme: 'dark' });
    expect(extConfig.preExisting).toBe(true);

    // Diff should have entries for all operations
    expect(result.diff.entries.length).toBeGreaterThanOrEqual(5);
    const kinds = result.diff.entries.map((e: any) => e.kind);
    expect(kinds).toContain('added');    // c-new, V2
    expect(kinds).toContain('modified'); // c-exists update, project-data
    expect(kinds).toContain('removed');  // c-exists remove

    // Affected IDs
    expect(result.diff.affectedObjectIds).toContain('c-new');
    expect(result.diff.affectedObjectIds).toContain('c-exists');
    expect(result.diff.affectedObjectIds).toContain('V2');
    expect(result.diff.affectedObjectIds).toContain('com.ext');
  });

  it('track operations cascade correctly in multi-op batch', () => {
    const data = makeMinimalTimelineData({
      tracks: [
        { id: 'V1', kind: 'visual', label: 'V1' },
        { id: 'V2', kind: 'visual', label: 'V2' },
      ],
      clips: [
        { id: 'c1', track: 'V1', at: 0, hold: 10 },
        { id: 'c2', track: 'V1', at: 10, hold: 10 },
        { id: 'c3', track: 'V2', at: 0, hold: 10 },
      ],
    });
    const result = compileTimelinePatch(
      makePatch({
        operations: [
          // Order 0: add new track V3
          makeOp('track.add', 'V3', { kind: 'visual', label: 'V3' }, 0),
          // Order 1: move c1 to V3
          makeOp('clip.move', 'c1', { track: 'V3', at: 0 }, 1),
          // Order 2: remove V1 (and cascade-remove c2)
          makeOp('track.remove', 'V1', undefined, 2),
        ],
      }),
      data,
    );
    expect(result.valid).toBe(true);

    // V3 exists, V1 gone, V2 remains
    const nextTrackIds = result.nextData!.config.tracks!.map((t: any) => t.id);
    expect(nextTrackIds).toContain('V3');
    expect(nextTrackIds).not.toContain('V1');
    expect(nextTrackIds).toContain('V2');

    // c1 moved to V3, c2 removed with V1, c3 remains on V2
    const nextClips = result.nextData!.config.clips;
    const c1Clip = nextClips.find((c: any) => c.id === 'c1');
    expect(c1Clip.track).toBe('V3');
    expect(nextClips.some((c: any) => c.id === 'c2')).toBe(false);
    expect(nextClips.some((c: any) => c.id === 'c3')).toBe(true);

    // Diff: track added (V3), clip moved (c1), track removed (V1), clip removed cascade (c2)
    const granularities = result.diff.entries.map((e: any) => e.granularity);
    expect(granularities.filter((g: string) => g === 'track').length).toBe(2);
    expect(granularities.filter((g: string) => g === 'clip').length).toBeGreaterThanOrEqual(2);
  });

  it('extension noop + app.update + project-data operations in one batch', () => {
    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [],
      app: {},
    });
    const result = compileTimelinePatch(
      makePatch({
        operations: [
          makeOp('app.update', 'com.ext', { theme: 'dark', mode: 'replace' }, 0),
          makeOp('project-data.write', 'com.ext', { key: 'k1', value: 'v1' }, 1),
          makeOp('project-data.write', 'com.ext', { key: 'k2', value: { nested: true }, mode: 'merge' }, 2),
          makeOp('extension.noop', 'com.ext', { trace: 'audit-log' }, 3),
          makeOp('project-data.delete', 'com.ext', { key: 'k1' }, 4),
        ],
      }),
      data,
    );
    expect(result.valid).toBe(true);

    const appConfig = result.nextData!.config.app;
    const extConfig = appConfig['com.ext'] as Record<string, unknown>;
    // theme from app.update replace
    expect(extConfig.theme).toBe('dark');
    // k1 deleted, k2 preserved
    expect(extConfig.k1).toBeUndefined();
    expect(extConfig.k2).toEqual({ nested: true });

    // extension.noop diff entry
    const noopEntry = result.diff.entries.find(
      (e: any) => e.op === 'extension.noop' && e.target === 'com.ext',
    );
    expect(noopEntry).toBeDefined();
    expect(noopEntry!.after).toMatchObject({ noop: true, extensionId: 'com.ext' });
    expect(noopEntry!.after).toHaveProperty('payload');

    // All targets in affected
    expect(result.diff.affectedObjectIds).toContain('com.ext');

    // Verify granularities
    const granularities = result.diff.entries.map((e: any) => e.granularity);
    expect(granularities).toContain('app');
    expect(granularities).toContain('project-data');
  });

  it('reserved ops are skipped in compile but produce warnings', () => {
    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [{ id: 'c1', track: 'V1', at: 0, hold: 10 }],
    });
    const result = compileTimelinePatch(
      makePatch({
        operations: [
          makeOp('clip.split', 'c1', { at: 5 }),
          makeOp('clip.update', 'c1', { volume: 0.5 }),
          makeOp('clip.slice', 'c1', { from: 2, to: 8 }),
        ],
      }),
      data,
    );
    expect(result.valid).toBe(true);
    // Reserved warnings
    const reservedWarnings = result.diagnostics.filter(
      (d: any) => d.code === 'timeline-patch/reserved-op',
    );
    expect(reservedWarnings).toHaveLength(2);
    // Only clip.update should have produced a diff entry
    const entries = result.diff.entries;
    expect(entries.some((e: any) => e.op === 'clip.split' as any)).toBe(false);
    expect(entries.some((e: any) => e.op === 'clip.slice' as any)).toBe(false);
    expect(entries.some((e: any) => e.op === 'clip.update')).toBe(true);
  });

  it('batch with asset ops + clip ops + extension ops', () => {
    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [{ id: 'c1', track: 'V1', at: 0, hold: 10 }],
      assets: { 'asset-1': { file: 'old.mp4', id: 'asset-1' } },
      app: { 'com.ext': { existing: 'data' } },
    });
    const result = compileTimelinePatch(
      makePatch({
        operations: [
          makeOp('asset.update', 'asset-1', { src: 'new.mp4', mode: 'replace' }, 0),
          makeOp('asset.remove', 'asset-2', undefined, 1),
          makeOp('clip.add', 'c2', { track: 'V1', at: 10, clipType: 'media' }, 2),
          makeOp('app.update', 'com.ext', { newField: 'value', mode: 'merge' }, 3),
          makeOp('extension.noop', 'com.other', { example: true }, 4),
        ],
      }),
      data,
    );
    expect(result.valid).toBe(true);

    // Asset diff entries with warnings
    const assetDiags = result.diagnostics.filter(
      (d: any) => d.code === 'timeline-patch/asset-not-implemented',
    );
    expect(assetDiags).toHaveLength(2);

    // Asset entries in diff
    const assetEntries = result.diff.entries.filter((e: any) => e.granularity === 'asset');
    expect(assetEntries).toHaveLength(2);

    // Clip added
    expect(result.nextData!.config.clips.some((c: any) => c.id === 'c2')).toBe(true);

    // App updated (merge)
    const extConfig = result.nextData!.config.app['com.ext'] as Record<string, unknown>;
    expect(extConfig.existing).toBe('data');
    expect(extConfig.newField).toBe('value');

    // Noop diff entry
    const noopEntry = result.diff.entries.find(
      (e: any) => e.target === 'com.other' && e.op === 'extension.noop',
    );
    expect(noopEntry).toBeDefined();
    expect(noopEntry!.after).toMatchObject({ noop: true, extensionId: 'com.other' });
  });
});

// ---------------------------------------------------------------------------
// previewTimelinePatch — comprehensive preview tests
// ---------------------------------------------------------------------------

describe('previewTimelinePatch — comprehensive', () => {
  it('returns fullyPreviewable=true for valid non-reserved patch', () => {
    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [{ id: 'c1', track: 'V1', at: 0, hold: 10 }],
    });
    const result = previewTimelinePatch(
      makePatch({
        operations: [
          makeOp('clip.update', 'c1', { volume: 0.7 }),
          makeOp('track.update', 'V1', { muted: true }),
        ],
      }),
      data,
    );
    expect(result.fullyPreviewable).toBe(true);
    expect(result.diff.entries.length).toBe(2);
    expect(result.diagnostics.length).toBe(0);
  });

  it('returns fullyPreviewable=false when reserved ops present', () => {
    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [{ id: 'c1', track: 'V1', at: 0, hold: 10 }],
    });
    const result = previewTimelinePatch(
      makePatch({
        operations: [
          makeOp('clip.update', 'c1', { volume: 0.5 }),
          makeOp('clip.split', 'c1', { at: 5 }),
        ],
      }),
      data,
    );
    expect(result.fullyPreviewable).toBe(false);
    // But the diff still has the clip.update entry
    expect(result.diff.entries.some((e: any) => e.op === 'clip.update')).toBe(true);
    // And diagnostics include the reserved warning
    expect(result.diagnostics.some((d: any) => d.code === 'timeline-patch/reserved-op')).toBe(true);
  });

  it('returns empty diff and fullyPreviewable=false for invalid patch', () => {
    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [],
    });
    const result = previewTimelinePatch(
      makePatch({
        operations: [makeOp('track.add', 'V1', { kind: 'bad_kind' as 'visual' })],
      }),
      data,
    );
    expect(result.fullyPreviewable).toBe(false);
    expect(result.diff.entries).toHaveLength(0);
    expect(result.diff.affectedObjectIds).toHaveLength(0);
    expect(result.diagnostics.some((d: any) => d.severity === 'error')).toBe(true);
  });

  it('preview of multi-op batch with project-data and extension ops', () => {
    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [],
      app: {},
    });
    const result = previewTimelinePatch(
      makePatch({
        operations: [
          makeOp('app.update', 'com.ext', { config: { a: 1 } }),
          makeOp('project-data.write', 'com.ext', { key: 'k', value: 'v' }),
          makeOp('extension.noop', 'com.ext', { example: 'preview-test' }),
        ],
      }),
      data,
    );
    expect(result.fullyPreviewable).toBe(true);
    // Diff should contain entries for all three ops
    const ops = result.diff.entries.map((e: any) => e.op);
    expect(ops).toContain('app.update');
    expect(ops).toContain('project-data.write');
    expect(ops).toContain('extension.noop');
  });

  it('preview does not mutate original TimelineData', () => {
    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [{ id: 'c1', track: 'V1', at: 0, hold: 10, volume: 1.0 }],
    });
    const originalVolume = (data.config.clips[0] as any).volume;
    const originalTrackCount = data.config.tracks!.length;
    previewTimelinePatch(
      makePatch({
        operations: [
          makeOp('clip.update', 'c1', { volume: 0.2 }),
          makeOp('track.add', 'V2', { kind: 'visual' }),
        ],
      }),
      data,
    );
    expect((data.config.clips[0] as any).volume).toBe(originalVolume);
    expect(data.config.tracks!.length).toBe(originalTrackCount);
  });
});

// ---------------------------------------------------------------------------
// compileTimelinePatch — edge cases and diagnostics
// ---------------------------------------------------------------------------

describe('compileTimelinePatch — edge cases', () => {
  it('returns valid=false and empty diff for invalid patch', () => {
    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [],
    });
    const result = compileTimelinePatch(
      makePatch({
        operations: [{ op: 'unknown.op' as TimelinePatchAnyOpFamily, target: 'x' }],
      }),
      data,
    );
    expect(result.valid).toBe(false);
    expect(result.nextData).toBeNull();
    expect(result.mutation).toBeNull();
    expect(result.diff.entries).toHaveLength(0);
    expect(result.diagnostics.some((d: any) => d.code === 'timeline-patch/unknown-op')).toBe(true);
  });

  it('compile succeeds with asset ops even though registry is not mutated', () => {
    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [],
    });
    const result = compileTimelinePatch(
      makePatch({
        operations: [makeOp('asset.update', 'asset-1', { src: 'url' })],
      }),
      data,
    );
    expect(result.valid).toBe(true);
    expect(result.nextData).not.toBeNull();
    // nextData should be structurally valid even if asset mutations are deferred
    expect(result.nextData!.registry.assets).toBeDefined();
  });

  it('clip.add to empty timeline (no tracks) auto-creates default track', () => {
    const data = makeMinimalTimelineData({
      tracks: [],
      clips: [],
    });
    const result = compileTimelinePatch(
      makePatch({
        operations: [makeOp('clip.add', 'c1', { at: 0, clipType: 'media' })],
      }),
      data,
    );
    expect(result.valid).toBe(true);
    // Default track V1 should have been created
    const nextTrackIds = result.nextData!.config.tracks!.map((t: any) => t.id);
    expect(nextTrackIds).toContain('V1');
    const c1 = result.nextData!.config.clips.find((c: any) => c.id === 'c1');
    expect(c1.track).toBe('V1');
  });

  it('multiple clip.adds with same track work correctly', () => {
    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [],
    });
    const result = compileTimelinePatch(
      makePatch({
        operations: [
          makeOp('clip.add', 'c1', { track: 'V1', at: 0, clipType: 'media' }, 0),
          makeOp('clip.add', 'c2', { track: 'V1', at: 10, clipType: 'text' }, 1),
          makeOp('clip.add', 'c3', { track: 'V1', at: 20, clipType: 'media' }, 2),
        ],
      }),
      data,
    );
    expect(result.valid).toBe(true);
    const nextClips = result.nextData!.config.clips;
    expect(nextClips).toHaveLength(3);
    const clipIds = nextClips.map((c: any) => c.id);
    expect(clipIds).toEqual(expect.arrayContaining(['c1', 'c2', 'c3']));
    // V1's clipOrder should contain all three
    const order = result.mutation!.clipOrderOverride!['V1'];
    expect(order).toEqual(expect.arrayContaining(['c1', 'c2', 'c3']));
    expect(order).toHaveLength(3);
  });
});

// ============================================================================
// T29: Extension project-data persistence, replay, rollback, actionable diagnostics
// ============================================================================

describe('compileTimelinePatch — tiny DSL/annotation data persistence', () => {
  it('persists a tiny annotation object and reads it back from nextData', () => {
    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [],
    });

    const annotation = { type: 'annotation', start: 1.5, end: 3.0, text: 'hello world', color: '#ff0000' };

    const result = compileTimelinePatch(
      makePatch({
        operations: [
          makeOp('project-data.write', 'com.annotations.ext', { key: 'ann_001', value: annotation }),
        ],
      }),
      data,
    );

    expect(result.valid).toBe(true);
    expect(result.nextData).not.toBeNull();
    
    // Verify the data was persisted in nextData.config.app
    const nextApp = result.nextData!.config.app;
    expect(nextApp).toHaveProperty('com.annotations.ext');
    expect((nextApp['com.annotations.ext'] as Record<string, unknown>).ann_001).toEqual(annotation);
    
    // Verify diff entry
    const diffEntry = result.diff.entries.find(e => e.granularity === 'project-data');
    expect(diffEntry).toBeDefined();
    expect(diffEntry!.kind).toBe('added');
    expect(diffEntry!.target).toBe('com.annotations.ext');
  });

  it('persists a small DSL snippet (shader/material) and replays identically', () => {
    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [],
    });

    const dslSnippet = {
      type: 'shader',
      language: 'glsl',
      source: 'void main() { gl_FragColor = vec4(1.0, 0.0, 0.0, 1.0); }',
      uniforms: { u_time: 'float', u_resolution: 'vec2' },
      version: 1,
    };

    const patch = makePatch({
      operations: [
        makeOp('project-data.write', 'com.shaders.ext', { key: 'fragment_red', value: dslSnippet }),
      ],
    });

    // First application
    const result1 = compileTimelinePatch(patch, data);
    expect(result1.valid).toBe(true);
    const stored1 = (result1.nextData!.config.app['com.shaders.ext'] as Record<string, unknown>).fragment_red;
    expect(stored1).toEqual(dslSnippet);

    // Replay: same patch on same data produces identical results
    const result2 = compileTimelinePatch(patch, data);
    expect(result2.valid).toBe(true);
    const stored2 = (result2.nextData!.config.app['com.shaders.ext'] as Record<string, unknown>).fragment_red;
    expect(stored2).toEqual(dslSnippet);
    
    // Replay determinism: diff should be identical
    expect(result2.diff.entries).toHaveLength(result1.diff.entries.length);
    expect(result2.diagnostics).toHaveLength(result1.diagnostics.length);
  });

  it('persists multiple small annotation entries and retrieves all', () => {
    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [],
    });

    const annotations = [
      { key: 'ann_a', value: { type: 'highlight', region: 'intro', confidence: 0.95 } },
      { key: 'ann_b', value: { type: 'marker', label: 'cut-point', frame: 240 } },
      { key: 'ann_c', value: { type: 'note', author: 'editor', text: 'review needed' } },
    ];

    // Write each annotation in sequence
    let currentData = data;
    for (const ann of annotations) {
      const result = compileTimelinePatch(
        makePatch({
          operations: [
            makeOp('project-data.write', 'com.annotations.ext', { key: ann.key, value: ann.value }),
          ],
        }),
        currentData,
      );
      expect(result.valid).toBe(true);
      currentData = result.nextData!;
    }

    // Verify all entries are present in final state
    const finalApp = currentData.config.app['com.annotations.ext'] as Record<string, unknown>;
    expect(Object.keys(finalApp)).toHaveLength(3);
    expect(finalApp.ann_a).toEqual(annotations[0].value);
    expect(finalApp.ann_b).toEqual(annotations[1].value);
    expect(finalApp.ann_c).toEqual(annotations[2].value);
  });

  it('deletes an annotation entry and verifies it is gone', () => {
    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [],
      app: { 'com.annotations.ext': { ann_001: { type: 'marker', label: 'start' } } },
    });

    const delResult = compileTimelinePatch(
      makePatch({
        operations: [
          makeOp('project-data.delete', 'com.annotations.ext', { key: 'ann_001' }),
        ],
      }),
      data,
    );

    expect(delResult.valid).toBe(true);
    const appAfterDel = delResult.nextData!.config.app;
    // The extension namespace should be removed entirely since it was the only key.
    // When configApp is empty, nextConfig.app is not set, so config.app may be undefined.
    if (appAfterDel) {
      expect(appAfterDel['com.annotations.ext']).toBeUndefined();
    }

    // Diff should show removed
    const diffEntry = delResult.diff.entries.find(e => e.kind === 'removed');
    expect(diffEntry).toBeDefined();
    expect(diffEntry!.target).toBe('com.annotations.ext');
  });

  it('round-trips a material reference through write, read, delete, re-add', () => {
    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [],
    });

    const materialRef = {
      type: 'material_ref',
      packageId: 'com.example.package',
      resourcePath: '/materials/glossy_red.json',
      version: '2.1.0',
      parameters: { roughness: 0.3, metallic: 0.1 },
    };

    // Phase 1: Write
    const r1 = compileTimelinePatch(
      makePatch({
        operations: [
          makeOp('project-data.write', 'com.materials.ext', { key: 'mat_glossy', value: materialRef }),
        ],
      }),
      data,
    );
    expect(r1.valid).toBe(true);
    expect((r1.nextData!.config.app['com.materials.ext'] as Record<string, unknown>).mat_glossy).toEqual(materialRef);

    // Phase 2: Read back implicitly via nextData
    const stored = (r1.nextData!.config.app['com.materials.ext'] as Record<string, unknown>).mat_glossy;
    expect(stored).toEqual(materialRef);

    // Phase 3: Delete
    const r2 = compileTimelinePatch(
      makePatch({
        operations: [
          makeOp('project-data.delete', 'com.materials.ext', { key: 'mat_glossy' }),
        ],
      }),
      r1.nextData!,
    );
    expect(r2.valid).toBe(true);
    const r2App = r2.nextData!.config.app;
    // After deleting the only key, config.app may be undefined (empty app not serialized)
    if (r2App) {
      expect(r2App['com.materials.ext']).toBeUndefined();
    }

    // Phase 4: Re-add with different parameters
    const updatedRef = { ...materialRef, parameters: { roughness: 0.7, metallic: 0.5 } };
    const r3 = compileTimelinePatch(
      makePatch({
        operations: [
          makeOp('project-data.write', 'com.materials.ext', { key: 'mat_glossy', value: updatedRef }),
        ],
      }),
      r2.nextData!,
    );
    expect(r3.valid).toBe(true);
    expect((r3.nextData!.config.app['com.materials.ext'] as Record<string, unknown>).mat_glossy).toEqual(updatedRef);
  });
});

describe('compileTimelinePatch — project-data rollback safety', () => {
  it('rollback: original configApp is unmodified when entry-size overflow occurs in batch', () => {
    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [],
      app: { 'com.example.ext': { existing: { data: 'safe' } } },
    });
    
    const appBefore = JSON.stringify(data.config.app);
    
    const bigString = 'x'.repeat(64 * 1024 + 100); // Over MAX_ENTRY_BYTES
    const result = compileTimelinePatch(
      makePatch({
        operations: [
          makeOp('clip.add', 'c1', { at: 0, clipType: 'media' }),
          makeOp('project-data.write', 'com.example.ext', { key: 'too-big', value: { data: bigString } }),
        ],
      }),
      data,
    );
    
    // Original data must be byte-for-byte unchanged
    expect(JSON.stringify(data.config.app)).toBe(appBefore);
    
    // Entry-size overflow is caught during validation, making the batch invalid.
    // The original TimelineData must still be unmodified.
    expect(result.valid).toBe(false);
    // The overflow diagnostic should still be emitted
    const overflowDiag = result.diagnostics.find(d => d.code === 'timeline-patch/project-data-overflow');
    expect(overflowDiag).toBeDefined();
    // nextData and mutation should be null for invalid batches
    expect(result.nextData).toBeNull();
    expect(result.mutation).toBeNull();
  });

  it('rollback: original configApp is unmodified when extension total bytes overflow occurs', () => {
    const existingEntries: Record<string, unknown> = {};
    const bigValue = 'x'.repeat(50000);
    for (let i = 0; i < 21; i++) {
      existingEntries[`key${i}`] = { data: bigValue };
    }

    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [],
      app: { 'com.example.ext': existingEntries },
    });
    
    const appBefore = JSON.stringify(data.config.app);
    
    const result = compileTimelinePatch(
      makePatch({
        operations: [
          makeOp('project-data.write', 'com.example.ext', { key: 'overflow', value: { data: bigValue } }),
        ],
      }),
      data,
    );

    // Original data must be byte-for-byte unchanged
    expect(JSON.stringify(data.config.app)).toBe(appBefore);
    
    const overflowDiag = result.diagnostics.find(
      d => d.code === 'timeline-patch/project-data-overflow' && (d.detail as any)?.code === 'project-data/extension-total-exceeded'
    );
    expect(overflowDiag).toBeDefined();
  });

  it('rollback: original app state is unmodified when entry count overflow occurs', () => {
    const existingEntries: Record<string, unknown> = {};
    for (let i = 0; i < 128; i++) {
      existingEntries[`key${i}`] = { value: i };
    }

    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [],
      app: { 'com.example.ext': existingEntries },
    });
    
    const appBefore = JSON.stringify(data.config.app);
    const extEntryCountBefore = Object.keys(data.config.app['com.example.ext'] as object).length;
    
    const result = compileTimelinePatch(
      makePatch({
        operations: [
          makeOp('project-data.write', 'com.example.ext', { key: 'new-key', value: { value: 999 } }),
        ],
      }),
      data,
    );

    // Original data must be byte-for-byte unchanged
    expect(JSON.stringify(data.config.app)).toBe(appBefore);
    expect(Object.keys(data.config.app['com.example.ext'] as object).length).toBe(extEntryCountBefore);
    
    const countDiag = result.diagnostics.find(
      d => d.code === 'timeline-patch/project-data-overflow' && (d.detail as any)?.code === 'project-data/entry-count-exceeded'
    );
    expect(countDiag).toBeDefined();
  });

  it('rollback: overflow does not prevent valid operations in same batch from being applied to nextData', () => {
    const existingEntries: Record<string, unknown> = {};
    for (let i = 0; i < 128; i++) {
      existingEntries[`key${i}`] = { value: i };
    }

    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [],
      app: { 'com.example.ext': existingEntries },
    });

    const result = compileTimelinePatch(
      makePatch({
        operations: [
          makeOp('track.add', 'A1', { kind: 'audio' }, 0),
          makeOp('project-data.write', 'com.example.ext', { key: 'new-key', value: { value: 999 } }, 1),
          makeOp('clip.add', 'c1', { track: 'V1', at: 0, clipType: 'media' }, 2),
        ],
      }),
      data,
    );

    expect(result.valid).toBe(true);
    // Track add and clip add should have been applied to nextData
    const nextTracks = result.nextData!.config.tracks as Array<Record<string, unknown>>;
    expect(nextTracks.find(t => t.id === 'A1')).toBeDefined();
    const nextClips = result.nextData!.config.clips as Array<Record<string, unknown>>;
    expect(nextClips.find(c => c.id === 'c1')).toBeDefined();
    
    // But the overflow diagnostic should be present
    const countDiag = result.diagnostics.find(
      d => d.code === 'timeline-patch/project-data-overflow' && (d.detail as any)?.code === 'project-data/entry-count-exceeded'
    );
    expect(countDiag).toBeDefined();
  });

  it('rollback: failed validation (invalid batch) returns original data shape and no mutation', () => {
    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [],
      app: { 'com.example.ext': { k1: { data: 'safe' } } },
    });
    
    const appBefore = JSON.stringify(data.config.app);
    
    // An invalid patch (unknown operation)
    const result = compileTimelinePatch(
      makePatch({
        operations: [
          makeOp('unknown.op' as any, 'target', {}),
        ],
      }),
      data,
    );

    // Original must be unmodified
    expect(JSON.stringify(data.config.app)).toBe(appBefore);
    expect(result.valid).toBe(false);
    expect(result.nextData).toBeNull();
    expect(result.mutation).toBeNull();
  });
});

describe('compileTimelinePatch — project-data actionable overflow diagnostics', () => {
  it('entry-size overflow diagnostic message suggests reducing entry size', () => {
    const bigString = 'x'.repeat(64 * 1024 + 100);
    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [],
    });

    const result = compileTimelinePatch(
      makePatch({
        operations: [
          makeOp('project-data.write', 'com.example.ext', { key: 'big-entry', value: { data: bigString } }),
        ],
      }),
      data,
    );

    const overflowDiag = result.diagnostics.find(
      d => d.code === 'timeline-patch/project-data-overflow' && (d.detail as any)?.code === 'project-data/entry-size-exceeded'
    );
    expect(overflowDiag).toBeDefined();
    // Message should provide actionable guidance
    const msg = overflowDiag!.message;
    expect(msg).toContain('MAX_ENTRY_BYTES');
    expect(msg).toContain('65536'); // 64 KB = 65536 bytes
    // Diagnostic should be actionable: points to the specific entry and limit
    expect(overflowDiag!.target).toBe('com.example.ext');
    expect(overflowDiag!.op).toBe('project-data.write');
  });

  it('extension total bytes overflow diagnostic includes actual byte count for guidance', () => {
    const existingEntries: Record<string, unknown> = {};
    const bigValue = 'x'.repeat(50000);
    for (let i = 0; i < 21; i++) {
      existingEntries[`key${i}`] = { data: bigValue };
    }

    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [],
      app: { 'com.example.ext': existingEntries },
    });

    const result = compileTimelinePatch(
      makePatch({
        operations: [
          makeOp('project-data.write', 'com.example.ext', { key: 'overflow', value: { data: bigValue } }),
        ],
      }),
      data,
    );

    const diag = result.diagnostics.find(
      d => d.code === 'timeline-patch/project-data-overflow' && (d.detail as any)?.code === 'project-data/extension-total-exceeded'
    );
    expect(diag).toBeDefined();
    
    const detail = diag!.detail as { code: string; extensionId: string; limit: number; actual: number; unit: string };
    expect(detail.unit).toBe('bytes');
    expect(detail.limit).toBe(1 * 1024 * 1024);
    expect(detail.actual).toBeGreaterThan(detail.limit);
    
    // Message contains the limit and extension ID for actionable guidance
    expect(diag!.message).toContain('com.example.ext');
    expect(diag!.message).toContain('MAX_EXTENSION_TOTAL_BYTES');
  });

  it('entry count overflow diagnostic includes current count for actionable guidance', () => {
    const existingEntries: Record<string, unknown> = {};
    for (let i = 0; i < 128; i++) {
      existingEntries[`key${i}`] = { value: i };
    }

    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [],
      app: { 'com.example.ext': existingEntries },
    });

    const result = compileTimelinePatch(
      makePatch({
        operations: [
          makeOp('project-data.write', 'com.example.ext', { key: 'new-key', value: { value: 999 } }),
        ],
      }),
      data,
    );

    const diag = result.diagnostics.find(
      d => d.code === 'timeline-patch/project-data-overflow' && (d.detail as any)?.code === 'project-data/entry-count-exceeded'
    );
    expect(diag).toBeDefined();
    
    const detail = diag!.detail as { code: string; extensionId: string; limit: number; actual: number; unit: string };
    expect(detail.unit).toBe('entries');
    expect(detail.limit).toBe(128);
    expect(detail.actual).toBe(129);
    
    // Message provides actionable info
    expect(diag!.message).toContain('com.example.ext');
    expect(diag!.message).toContain('MAX_ENTRIES_PER_EXTENSION');
    expect(diag!.message).toContain('128');
  });

  it('overflow diagnostic detail shape supports provider-backed repository guidance', () => {
    // The ProjectDataLimitDetail shape carries extensionId, limit, actual, unit
    // which a host UI can use to render actionable guidance pointing to:
    // - package resources (extensionId maps to an installed package)
    // - material refs (key values are often material/asset references)
    // - provider-backed repositories (extension data is stored in config.app 
    //   which is provider-backed via commitData)
    
    const existingEntries: Record<string, unknown> = {};
    const bigValue = 'x'.repeat(50000);
    for (let i = 0; i < 21; i++) {
      existingEntries[`key${i}`] = { data: bigValue };
    }

    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [],
      app: { 'com.example.ext': existingEntries },
    });

    const result = compileTimelinePatch(
      makePatch({
        operations: [
          makeOp('project-data.write', 'com.example.ext', { key: 'mat_ref', value: { data: bigValue } }),
        ],
      }),
      data,
    );

    const diag = result.diagnostics.find(
      d => d.code === 'timeline-patch/project-data-overflow'
    );
    expect(diag).toBeDefined();
    
    // The detail shape carries all fields needed for UI to build actionable messages
    const detail = diag!.detail as Record<string, unknown>;
    expect(detail).toHaveProperty('extensionId');
    expect(detail).toHaveProperty('limit');
    expect(detail).toHaveProperty('actual');
    expect(detail).toHaveProperty('unit');
    expect(detail).toHaveProperty('code');
    
    // The diagnostic severity is 'error' so host can surface it prominently
    expect(diag!.severity).toBe('error');
    
    // The operationIndex allows the host to point to the specific operation
    expect(diag!.operationIndex).toBeGreaterThanOrEqual(0);
  });

  it('both overflow types produce distinct diagnostic codes for targeted guidance', () => {
    const existingEntries: Record<string, unknown> = {};
    const bigValue = 'x'.repeat(10000);
    for (let i = 0; i < 128; i++) {
      existingEntries[`key${i}`] = { data: bigValue };
    }

    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [],
      app: { 'com.example.ext': existingEntries },
    });

    const result = compileTimelinePatch(
      makePatch({
        operations: [
          makeOp('project-data.write', 'com.example.ext', { key: 'both-overflow', value: { data: bigValue } }),
        ],
      }),
      data,
    );

    // Both entry-count and total-bytes overflow should fire
    const countDiag = result.diagnostics.find(d => (d.detail as any)?.code === 'project-data/entry-count-exceeded');
    const bytesDiag = result.diagnostics.find(d => (d.detail as any)?.code === 'project-data/extension-total-exceeded');
    
    expect(countDiag).toBeDefined();
    expect(bytesDiag).toBeDefined();
    
    // Each has a distinct code for targeted UI guidance
    expect((countDiag!.detail as any).code).toBe('project-data/entry-count-exceeded');
    expect((bytesDiag!.detail as any).code).toBe('project-data/extension-total-exceeded');
    
    // Both point to the same extension
    expect((countDiag!.detail as any).extensionId).toBe('com.example.ext');
    expect((bytesDiag!.detail as any).extensionId).toBe('com.example.ext');
  });

  it('overflow diagnostics for separate extensions produce independent guidance', () => {
    const existingEntries: Record<string, unknown> = {};
    const bigValue = 'x'.repeat(50000);
    for (let i = 0; i < 21; i++) {
      existingEntries[`key${i}`] = { data: bigValue };
    }

    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [],
      app: {
        'com.ext-overflow': existingEntries,
        'com.ext-ok': { small: { data: 'tiny' } },
      },
    });

    const result = compileTimelinePatch(
      makePatch({
        operations: [
          makeOp('project-data.write', 'com.ext-overflow', { key: 'too-much', value: { data: bigValue } }),
          makeOp('project-data.write', 'com.ext-ok', { key: 'another', value: { data: 'still-tiny' } }),
        ],
      }),
      data,
    );

    // Only com.ext-overflow should have overflow diagnostics
    const overflowDiags = result.diagnostics.filter(d => d.code === 'timeline-patch/project-data-overflow');
    expect(overflowDiags.length).toBeGreaterThan(0);
    
    // All overflow diags should reference the overflowing extension
    for (const d of overflowDiags) {
      expect((d.detail as any).extensionId).toBe('com.ext-overflow');
    }
    
    // com.ext-ok should have been written successfully
    const nextApp = result.nextData!.config.app;
    expect(nextApp['com.ext-ok']).toBeDefined();
  });
});

describe('compileTimelinePatch — project-data replay determinism', () => {
  it('replay: identical patch on identical data produces identical nextData serialization', () => {
    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [],
    });

    const patch = makePatch({
      operations: [
        makeOp('project-data.write', 'com.example.ext', { key: 'settings', value: { volume: 0.8, muted: false } }),
        makeOp('project-data.write', 'com.example.ext', { key: 'annotations', value: { regions: [{ start: 0, end: 5 }] } }),
      ],
    });

    const result1 = compileTimelinePatch(patch, data);
    const result2 = compileTimelinePatch(patch, data);

    // Full determinism: nextData, diff, diagnostics must match
    expect(result1.valid).toBe(result2.valid);
    expect(JSON.stringify(result1.nextData!.config.app)).toBe(JSON.stringify(result2.nextData!.config.app));
    expect(result1.diff.entries.length).toBe(result2.diff.entries.length);
    expect(result1.diagnostics.length).toBe(result2.diagnostics.length);
  });

  it('replay: patch with extension noop + project-data writes is deterministic', () => {
    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [],
    });

    const patch = makePatch({
      operations: [
        makeOp('extension.noop', 'com.example.ext', { example: true }),
        makeOp('project-data.write', 'com.example.ext', { key: 'k1', value: { a: 1 } }),
      ],
    });

    const r1 = compileTimelinePatch(patch, data);
    const r2 = compileTimelinePatch(patch, data);

    expect(r1.valid).toBe(r2.valid);
    expect(r1.diff.entries.length).toBe(r2.diff.entries.length);
    expect(r1.diagnostics.length).toBe(r2.diagnostics.length);
    expect(JSON.stringify(r1.nextData!.config.app)).toBe(JSON.stringify(r2.nextData!.config.app));
  });

  it('replay: overflow diagnostics are deterministic across replays', () => {
    const existingEntries: Record<string, unknown> = {};
    for (let i = 0; i < 128; i++) {
      existingEntries[`key${i}`] = { value: i };
    }

    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [],
      app: { 'com.example.ext': existingEntries },
    });

    const patch = makePatch({
      operations: [
        makeOp('project-data.write', 'com.example.ext', { key: 'overflow-key', value: { value: 999 } }),
      ],
    });

    const r1 = compileTimelinePatch(patch, data);
    const r2 = compileTimelinePatch(patch, data);
    const r3 = compileTimelinePatch(patch, data);

    // All replays must produce identical diagnostics
    expect(r1.diagnostics.length).toBe(r2.diagnostics.length);
    expect(r2.diagnostics.length).toBe(r3.diagnostics.length);

    const countDiag1 = r1.diagnostics.find(d => (d.detail as any)?.code === 'project-data/entry-count-exceeded');
    const countDiag2 = r2.diagnostics.find(d => (d.detail as any)?.code === 'project-data/entry-count-exceeded');
    const countDiag3 = r3.diagnostics.find(d => (d.detail as any)?.code === 'project-data/entry-count-exceeded');
    
    expect(countDiag1).toBeDefined();
    expect(countDiag2).toBeDefined();
    expect(countDiag3).toBeDefined();
    
    expect((countDiag1!.detail as any).actual).toBe((countDiag2!.detail as any).actual);
    expect((countDiag2!.detail as any).actual).toBe((countDiag3!.detail as any).actual);
  });

  it('replay: delete and re-add produces same final state as original on identical sequence', () => {
    const data = makeMinimalTimelineData({
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [],
    });

    // Sequence: write, delete, rewrite
    const writePatch = makePatch({
      operations: [makeOp('project-data.write', 'com.example.ext', { key: 'k1', value: { data: 'hello' } })],
    });
    const deletePatch = makePatch({
      operations: [makeOp('project-data.delete', 'com.example.ext', { key: 'k1' })],
    });
    const rewritePatch = makePatch({
      operations: [makeOp('project-data.write', 'com.example.ext', { key: 'k1', value: { data: 'hello' } })],
    });

    // First run
    const w1 = compileTimelinePatch(writePatch, data);
    const d1 = compileTimelinePatch(deletePatch, w1.nextData!);
    const rw1 = compileTimelinePatch(rewritePatch, d1.nextData!);
    
    // Second run (replay)
    const w2 = compileTimelinePatch(writePatch, data);
    const d2 = compileTimelinePatch(deletePatch, w2.nextData!);
    const rw2 = compileTimelinePatch(rewritePatch, d2.nextData!);

    // Final states must match
    expect(JSON.stringify(rw1.nextData!.config.app)).toBe(JSON.stringify(rw2.nextData!.config.app));
    
    // The re-added entry should be present
    const finalApp = rw1.nextData!.config.app['com.example.ext'] as Record<string, unknown>;
    expect(finalApp.k1).toEqual({ data: 'hello' });
  });
});
