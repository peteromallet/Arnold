import { describe, expect, it } from 'vitest';
import { validateSequenceDraft, validateSequenceDrafts } from '@/tools/video-editor/sequences/validation';

const allowedAssetKeys = ['selected-asset', 'attached-asset'];

const expectErrorCode = (input: unknown, code: string): void => {
  const result = validateSequenceDraft(input, { allowedAssetKeys });
  expect(result.ok).toBe(false);
  if (result.ok) return;
  expect(result.errors.map((error) => error.code)).toContain(code);
};

describe('validateSequenceDraft', () => {
  it('accepts a valid string-param draft', () => {
    const result = validateSequenceDraft({
      clipType: 'section-hook',
      hold: 3,
      params: {
        kicker: '2RP',
        title: 'A new renaissance',
        subtitle: 'Beauty at planetary scale',
      },
    });

    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.draft).toEqual({
      clipType: 'section-hook',
      hold: 3,
      params: {
        kicker: '2RP',
        title: 'A new renaissance',
        subtitle: 'Beauty at planetary scale',
      },
    });
  });

  it('accepts selected/current-attached registry asset keys for resource-card previewAssetKeys', () => {
    const result = validateSequenceDraft({
      clipType: 'resource-card',
      hold: 4,
      params: {
        title: 'Leverage for creators',
        previewAssetKeys: ['selected-asset', 'attached-asset'],
      },
    }, { allowedAssetKeys });

    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.draft.params.previewAssetKeys).toEqual(['selected-asset', 'attached-asset']);
  });

  it('validates batches without hiding per-draft failures', () => {
    const results = validateSequenceDrafts([
      { clipType: 'cta-card', hold: 3, params: { title: 'Create' } },
      { clipType: 'not-real', hold: 3, params: {} },
    ]);

    expect(results[0].ok).toBe(true);
    expect(results[1].ok).toBe(false);
  });

  it('rejects unknown clip types', () => {
    expectErrorCode({
      clipType: 'not-real',
      hold: 3,
      params: {},
    }, 'unknown_clip_type');
  });

  it('rejects missing params objects', () => {
    expectErrorCode({
      clipType: 'section-hook',
      hold: 3,
    }, 'invalid_params');
  });

  it('rejects clip types outside the caller allowed list', () => {
    const result = validateSequenceDraft({
      clipType: 'cta-card',
      hold: 3,
      params: { title: 'Create' },
    }, { allowedClipTypes: ['section-hook'] });

    expect(result.ok).toBe(false);
    if (result.ok) return;
    expect(result.errors.map((error) => error.code)).toContain('clip_type_not_allowed');
  });

  it('rejects missing, non-finite, non-positive, and out-of-range hold values', () => {
    expectErrorCode({ clipType: 'section-hook', params: { title: 'Title' } }, 'invalid_hold');
    expectErrorCode({ clipType: 'section-hook', hold: Number.POSITIVE_INFINITY, params: { title: 'Title' } }, 'invalid_hold');
    expectErrorCode({ clipType: 'section-hook', hold: 0, params: { title: 'Title' } }, 'invalid_hold');
    expectErrorCode({ clipType: 'section-hook', hold: 99, params: { title: 'Title' } }, 'hold_out_of_range');
  });

  it('rejects unknown params', () => {
    expectErrorCode({
      clipType: 'section-hook',
      hold: 3,
      params: {
        title: 'Title',
        madeUp: 'nope',
      },
    }, 'unknown_param');
  });

  it('rejects invalid scalar/list values', () => {
    expectErrorCode({
      clipType: 'section-hook',
      hold: 3,
      params: {
        title: { text: 'Title' },
      },
    }, 'invalid_param_value');
    expectErrorCode({
      clipType: 'resource-card',
      hold: 3,
      params: {
        title: 'Resource',
        previewAssetKeys: 'selected-asset',
      },
    }, 'invalid_param_value');
  });

  it('rejects non-serializable param values', () => {
    expectErrorCode({
      clipType: 'section-hook',
      hold: 3,
      params: {
        title: undefined,
      },
    }, 'non_serializable');
  });

  it('rejects generated code fields and JSX/import strings', () => {
    expectErrorCode({
      clipType: 'section-hook',
      hold: 3,
      code: 'export default function Sequence() {}',
      params: { title: 'Title' },
    }, 'generated_code_field');
    expectErrorCode({
      clipType: 'section-hook',
      hold: 3,
      params: {
        title: '<GeneratedSequence />',
      },
    }, 'generated_code');
  });

  it('rejects raw URLs in string params and asset-list params', () => {
    expectErrorCode({
      clipType: 'cta-card',
      hold: 3,
      params: {
        title: 'Go to https://example.com',
      },
    }, 'raw_url');
    expectErrorCode({
      clipType: 'resource-card',
      hold: 3,
      params: {
        title: 'Resource',
        previewAssetKeys: ['https://cdn.example.com/image.png'],
      },
    }, 'raw_url');
  });

  it('rejects component-facing previews URLs instead of previewAssetKeys', () => {
    const result = validateSequenceDraft({
      clipType: 'resource-card',
      hold: 3,
      params: {
        title: 'Resource',
        previews: ['https://cdn.example.com/image.png'],
      },
    }, { allowedAssetKeys });

    expect(result.ok).toBe(false);
    if (result.ok) return;
    expect(result.errors.map((error) => error.code)).toContain('reserved_component_param');
  });

  it('rejects entrance/exit and other animation refs', () => {
    expectErrorCode({
      clipType: 'section-hook',
      hold: 3,
      params: {
        title: 'Title',
        entrance: ['fade-up'],
      },
    }, 'animation_ref');
    expectErrorCode({
      clipType: 'section-hook',
      hold: 3,
      animationRefs: ['fade-up'],
      params: { title: 'Title' },
    }, 'animation_ref');
  });

  it('rejects disallowed timeline-wide asset keys', () => {
    const result = validateSequenceDraft({
      clipType: 'resource-card',
      hold: 3,
      params: {
        title: 'Resource',
        previewAssetKeys: ['selected-asset', 'timeline-wide-asset'],
      },
    }, { allowedAssetKeys });

    expect(result.ok).toBe(false);
    if (result.ok) return;
    expect(result.errors).toContainEqual(expect.objectContaining({
      path: '$.params.previewAssetKeys.1',
      code: 'asset_not_allowed',
    }));
  });
});
