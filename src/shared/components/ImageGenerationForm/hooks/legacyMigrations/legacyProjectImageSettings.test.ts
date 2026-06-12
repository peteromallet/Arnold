import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  LEGACY_PROJECT_IMAGE_SETTINGS_FIELDS,
  LEGACY_PROJECT_IMAGE_SETTINGS_SUNSET,
  enforceLegacyProjectImageSettingsSunset,
  getLegacyProjectImageSettingsFields,
  stripLegacyProjectImageSettings,
  type ProjectImageSettingsInput,
} from './legacyProjectImageSettings';

describe('legacyProjectImageSettings sunset enforcement', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('returns no legacy fields for null settings', () => {
    expect(getLegacyProjectImageSettingsFields(null)).toEqual([]);
  });

  it('returns settings unchanged before sunset date and does not throw', () => {
    const settings = {
      selectedReferenceId: 'ref-1',
    } as ProjectImageSettingsInput;

    expect(() => stripLegacyProjectImageSettings(settings, new Date('2026-02-24T00:00:00.000Z'))).not.toThrow();
    expect(stripLegacyProjectImageSettings(settings, new Date('2026-02-24T00:00:00.000Z'))).toBe(settings);
  });

  it('strips legacy fields after sunset date and does not throw', () => {
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
    const settings = {
      references: [],
      selectedLorasByTextModel: {},
      selectedReferenceId: 'ref-1',
      styleReferenceImage: 'style.png',
      styleReferenceImageOriginal: 'style-original.png',
      styleReferenceStrength: 0.5,
      subjectStrength: 0.75,
      subjectDescription: 'subject',
      inThisScene: true,
    } as ProjectImageSettingsInput;

    let cleaned: ProjectImageSettingsInput | null | undefined;
    expect(() => {
      cleaned = stripLegacyProjectImageSettings(settings, new Date('2026-06-01T00:00:00.000Z'));
    }).not.toThrow();

    expect(cleaned).not.toBe(settings);
    expect(cleaned).toEqual({ references: [] });
    for (const field of LEGACY_PROJECT_IMAGE_SETTINGS_FIELDS) {
      expect(cleaned).not.toHaveProperty(field);
      expect(settings).toHaveProperty(field);
    }
    if (import.meta.env.DEV) {
      expect(warnSpy).toHaveBeenCalledTimes(1);
      expect(warnSpy).toHaveBeenCalledWith(
        expect.stringContaining(LEGACY_PROJECT_IMAGE_SETTINGS_SUNSET.removeBy)
      );
      expect(warnSpy).toHaveBeenCalledWith(
        expect.stringContaining('selectedLorasByTextModel')
      );
    }
  });

  it('returns settings unchanged after sunset when no legacy fields remain', () => {
    const settings = {
      references: [],
      selectedReferenceIdByShot: { none: 'ref-1' },
    } as ProjectImageSettingsInput;

    expect(() => stripLegacyProjectImageSettings(settings, new Date('2026-06-01T00:00:00.000Z'))).not.toThrow();
    expect(stripLegacyProjectImageSettings(settings, new Date('2026-06-01T00:00:00.000Z'))).toBe(settings);
  });

  it('keeps legacy sunset enforcement non-throwing for backward compatibility', () => {
    vi.spyOn(console, 'warn').mockImplementation(() => {});
    const settings = {
      selectedReferenceId: 'ref-1',
      styleReferenceStrength: 0.5,
    } as ProjectImageSettingsInput;

    expect(() =>
      enforceLegacyProjectImageSettingsSunset(settings, new Date('2026-06-01T00:00:00.000Z'))
    ).not.toThrow();
  });
});
