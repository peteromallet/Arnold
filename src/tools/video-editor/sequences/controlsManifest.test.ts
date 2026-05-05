import { describe, expect, it } from 'vitest';
import {
  buildDefaultsFromManifest,
  validateControlsManifest,
  type ControlManifestEntry,
} from './controlsManifest.ts';

const makePrimary = <T extends Partial<ControlManifestEntry>>(overrides: T) => ({
  name: 'duration',
  label: 'Duration',
  priority: 'primary',
  type: 'number',
  default: 30,
  ...overrides,
});

describe('validateControlsManifest', () => {
  it('accepts a manifest with one primary number control and one secondary boolean', () => {
    const manifest = [
      { name: 'duration', label: 'Duration', priority: 'primary', type: 'number', default: 30, min: 1, max: 120 },
      { name: 'showLabel', label: 'Show label', priority: 'secondary', type: 'boolean', default: true },
    ];
    const result = validateControlsManifest(manifest);
    expect(result.ok).toBe(true);
    if (result.ok) expect(result.manifest).toHaveLength(2);
  });

  it('accepts every type in the enum (number, slider, boolean, text, color, enum)', () => {
    const manifest = [
      { name: 'a', label: 'A', priority: 'primary', type: 'number', default: 1 },
      { name: 'b', label: 'B', priority: 'secondary', type: 'slider', default: 0.5, min: 0, max: 1, step: 0.01 },
      { name: 'c', label: 'C', priority: 'secondary', type: 'boolean', default: false },
      { name: 'd', label: 'D', priority: 'secondary', type: 'text', default: 'hi' },
      { name: 'e', label: 'E', priority: 'secondary', type: 'color', default: '#ff00ff' },
      { name: 'f', label: 'F', priority: 'secondary', type: 'enum', default: 'one', options: ['one', 'two'] },
    ];
    const result = validateControlsManifest(manifest);
    expect(result.ok).toBe(true);
  });

  it('rejects a non-array manifest', () => {
    const result = validateControlsManifest({ controls: [] });
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.errors[0].message).toMatch(/array/i);
  });

  it('rejects an entry with an empty name', () => {
    const result = validateControlsManifest([
      { ...makePrimary({}), name: '' },
    ]);
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.errors[0].message).toMatch(/non-empty name/);
  });

  it('rejects an entry with no priority', () => {
    const result = validateControlsManifest([
      { name: 'x', label: 'X', type: 'number', default: 1 },
    ]);
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.errors.some((e) => /priority/i.test(e.message))).toBe(true);
  });

  it('rejects an unknown widget type', () => {
    const result = validateControlsManifest([
      { name: 'x', label: 'X', priority: 'primary', type: 'date-picker', default: '' },
    ]);
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.errors[0].message).toMatch(/invalid type/i);
  });

  it('rejects a missing default value', () => {
    const result = validateControlsManifest([
      { name: 'x', label: 'X', priority: 'primary', type: 'number' },
    ]);
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.errors[0].message).toMatch(/default/i);
  });

  it('rejects an enum without options or with an out-of-set default', () => {
    const noOptions = validateControlsManifest([
      { name: 'mode', label: 'Mode', priority: 'primary', type: 'enum', default: 'a' },
    ]);
    expect(noOptions.ok).toBe(false);

    const badDefault = validateControlsManifest([
      { name: 'mode', label: 'Mode', priority: 'primary', type: 'enum', default: 'z', options: ['a', 'b'] },
    ]);
    expect(badDefault.ok).toBe(false);
  });

  it('rejects a color default that is not a hex string', () => {
    const result = validateControlsManifest([
      { name: 'tint', label: 'Tint', priority: 'primary', type: 'color', default: 'rebeccapurple' },
    ]);
    expect(result.ok).toBe(false);
  });

  it('rejects a slider missing min/max', () => {
    const result = validateControlsManifest([
      { name: 'speed', label: 'Speed', priority: 'primary', type: 'slider', default: 0.5 },
    ]);
    expect(result.ok).toBe(false);
  });

  it('rejects duplicate names', () => {
    const result = validateControlsManifest([
      { name: 'x', label: 'A', priority: 'primary', type: 'text', default: '' },
      { name: 'x', label: 'B', priority: 'secondary', type: 'text', default: '' },
    ]);
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.errors.some((e) => /duplicate/i.test(e.message))).toBe(true);
  });

  it('flags a manifest entry that is never consumed in code (dead control)', () => {
    const code = `function C({ params }) { return params.duration; }
exports.default = C;`;
    const result = validateControlsManifest(
      [
        { name: 'duration', label: 'Duration', priority: 'primary', type: 'number', default: 30 },
        { name: 'unused', label: 'Unused', priority: 'secondary', type: 'text', default: '' },
      ],
      { code },
    );
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.errors.some((e) => /never read/i.test(e.message))).toBe(true);
  });

  it('flags a code-side params.X with no manifest entry', () => {
    const code = `function C({ params }) { return params.duration + params.color; }
exports.default = C;`;
    const result = validateControlsManifest(
      [
        { name: 'duration', label: 'Duration', priority: 'primary', type: 'number', default: 30 },
      ],
      { code },
    );
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.errors.some((e) => /no controls manifest entry/i.test(e.message))).toBe(true);
  });

  it('accepts a manifest where every entry is consumed and no extra params.X is accessed', () => {
    const code = `function C({ params }) { return params.duration + params['mode']; }
exports.default = C;`;
    const result = validateControlsManifest(
      [
        { name: 'duration', label: 'Duration', priority: 'primary', type: 'number', default: 30 },
        { name: 'mode', label: 'Mode', priority: 'secondary', type: 'enum', default: 'a', options: ['a', 'b'] },
      ],
      { code },
    );
    expect(result.ok).toBe(true);
  });
});

describe('buildDefaultsFromManifest', () => {
  it('produces a key-per-entry default map', () => {
    const defaults = buildDefaultsFromManifest([
      { name: 'duration', label: 'Duration', priority: 'primary', type: 'number', default: 30 },
      { name: 'mode', label: 'Mode', priority: 'secondary', type: 'enum', default: 'a', options: ['a', 'b'] },
    ]);
    expect(defaults).toEqual({ duration: 30, mode: 'a' });
  });
});
