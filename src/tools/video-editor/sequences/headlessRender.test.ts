// @vitest-environment jsdom
import { describe, expect, it, vi } from 'vitest';
import { createElement, type FC } from 'react';

import * as compileSequenceModule from '@/tools/video-editor/sequences/compileSequenceComponent';
import { smokeRenderSequenceComponent } from '@/tools/video-editor/sequences/headlessRender';

const SCHEMA = { type: 'object', properties: {} };
const DEFAULTS = {};

describe('smokeRenderSequenceComponent', () => {
  it('returns { ok: true } when the component compiles and renders one frame', async () => {
    const GoodComponent: FC = () => createElement('div', { 'data-testid': 'smoke-good' }, 'ok');
    const spy = vi
      .spyOn(compileSequenceModule, 'compileSequenceComponentAsync')
      .mockResolvedValue(GoodComponent as unknown as Awaited<ReturnType<typeof compileSequenceModule.compileSequenceComponentAsync>>);

    const result = await smokeRenderSequenceComponent({
      code: '/* fake */',
      schemaJson: SCHEMA,
      defaultsJson: DEFAULTS,
      themeId: '2rp',
      fps: 30,
    });

    expect(result).toEqual({ ok: true });
    expect(spy).toHaveBeenCalledTimes(1);
  });

  it('returns { ok: false, error } when the component throws on render', async () => {
    const BrokenComponent: FC = () => {
      throw new Error('boom');
    };
    vi
      .spyOn(compileSequenceModule, 'compileSequenceComponentAsync')
      .mockResolvedValue(BrokenComponent as unknown as Awaited<ReturnType<typeof compileSequenceModule.compileSequenceComponentAsync>>);

    const result = await smokeRenderSequenceComponent({
      code: '/* fake */',
      schemaJson: SCHEMA,
      defaultsJson: DEFAULTS,
    });

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toMatch(/boom/);
    }
  });

  it('returns { ok: false, error } when compilation itself fails', async () => {
    vi
      .spyOn(compileSequenceModule, 'compileSequenceComponentAsync')
      .mockRejectedValue(new Error('compile failure'));

    const result = await smokeRenderSequenceComponent({
      code: '/* invalid */',
      schemaJson: SCHEMA,
      defaultsJson: DEFAULTS,
    });

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toMatch(/compile failure/);
    }
  });
});
