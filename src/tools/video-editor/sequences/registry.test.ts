import { describe, expect, it } from 'vitest';
import type { FC } from 'react';
import {
  describeClipCapabilityWith,
  resolveClipCapabilityDescriptor,
  resolveSequenceClipEntry,
  type DynamicSequenceComponentEntry,
} from '@/tools/video-editor/sequences/registry';

const FakeComponent: FC = () => null;

const myPulseEntry: DynamicSequenceComponentEntry = {
  clipType: 'my-pulse',
  component: FakeComponent as DynamicSequenceComponentEntry['component'],
  schemaJson: { type: 'object', properties: {} },
  themeId: 'custom-theme',
};

describe('resolveSequenceClipEntry — `custom:` prefix-strip lookup', () => {
  it('resolves a DB entry stored as `my-pulse` when queried as `custom:my-pulse`', () => {
    const entry = resolveSequenceClipEntry('custom:my-pulse', [myPulseEntry]);
    expect(entry).toBe(myPulseEntry);
  });

  it('also resolves the same DB entry when queried as plain `my-pulse` (no static collision)', () => {
    const entry = resolveSequenceClipEntry('my-pulse', [myPulseEntry]);
    expect(entry).toBe(myPulseEntry);
  });

  it('returns undefined when no dynamic entry matches the (stripped) clipType', () => {
    expect(resolveSequenceClipEntry('custom:does-not-exist', [myPulseEntry])).toBeUndefined();
    expect(resolveSequenceClipEntry('does-not-exist', [myPulseEntry])).toBeUndefined();
  });

  it('returns undefined when clipType is missing or the dynamic registry is empty', () => {
    expect(resolveSequenceClipEntry(undefined, [myPulseEntry])).toBeUndefined();
    expect(resolveSequenceClipEntry('custom:my-pulse', [])).toBeUndefined();
    expect(resolveSequenceClipEntry('custom:my-pulse', undefined)).toBeUndefined();
  });
});

describe('resolveClipCapabilityDescriptor — DB entries surface workerRender:false', () => {
  it('emits browser-only capabilities for a DB-stored entry queried via the custom: prefix', () => {
    const descriptor = resolveClipCapabilityDescriptor('custom:my-pulse', [myPulseEntry]);
    expect(descriptor).toBeDefined();
    expect(descriptor?.source).toBe('db-sequence-component');
    expect(descriptor?.capabilities).toEqual({
      preview: 'browser',
      browserRender: true,
      workerRender: false,
      externalRender: false,
    });
  });

  it('falls back to the static CLIP_CAPABILITY_REGISTRY for built-in clipTypes', () => {
    // `text` is one of the BUILTIN_CLIP_TYPES; the static registry should answer
    // with builtin source + workerRender:false (built-ins render in browser).
    const descriptor = resolveClipCapabilityDescriptor('text', []);
    expect(descriptor?.source).toBe('builtin');
  });
});

describe('describeClipCapabilityWith — clip-shaped wrapper', () => {
  it('returns workerRender:false for a clip whose clipType matches a DB entry via custom: prefix', () => {
    const descriptor = describeClipCapabilityWith(
      { id: 'c1', clipType: 'custom:my-pulse' } as Parameters<typeof describeClipCapabilityWith>[0],
      [myPulseEntry],
    );
    expect(descriptor?.capabilities.workerRender).toBe(false);
    expect(descriptor?.capabilities.browserRender).toBe(true);
  });
});
