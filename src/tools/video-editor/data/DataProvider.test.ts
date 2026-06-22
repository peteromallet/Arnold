import { describe, expect, it } from 'vitest';
import {
  pushUnsupportedCapabilityDiagnostics,
  PROVIDER_CAPABILITY_EXTENSION_STATE_UNSUPPORTED,
  PROVIDER_CAPABILITY_EXTENSION_SETTINGS_UNSUPPORTED,
  PROVIDER_CAPABILITY_EXTENSION_PROPOSALS_UNSUPPORTED,
  isDataProviderPersistenceEnabled,
  type DataProvider,
  type ExtensionPersistenceScope,
} from '@/tools/video-editor/data/DataProvider';
import type { ExtensionDiagnostic } from '@reigh/editor-sdk';

// ---------------------------------------------------------------------------
// Test double: a DataProvider that does NOT implement extension persistence
// ---------------------------------------------------------------------------

/**
 * Minimal DataProvider stub that omits the optional
 * {@link DataProvider.createExtensionPersistenceService} factory, simulating a
 * provider that has no extension persistence support (e.g. Astrid bridge).
 */
function createProviderWithoutExtensionPersistence(): DataProvider {
  return {
    persistenceEnabled: true,
    async loadTimeline(_timelineId: string) {
      throw new Error('not implemented');
    },
    async saveTimeline(_timelineId: string, _config: any, _expectedVersion: number) {
      throw new Error('not implemented');
    },
    async loadAssetRegistry(_timelineId: string) {
      throw new Error('not implemented');
    },
    async resolveAssetUrl(_file: string) {
      return _file;
    },
    // createExtensionPersistenceService intentionally not defined
  };
}

// ---------------------------------------------------------------------------
// Tests: pushUnsupportedCapabilityDiagnostics
// ---------------------------------------------------------------------------

describe('pushUnsupportedCapabilityDiagnostics', () => {
  it('emits state, settings, and proposals diagnostics when all capabilities are unsupported (undefined)', () => {
    const diagnostics: ExtensionDiagnostic[] = [];

    pushUnsupportedCapabilityDiagnostics(diagnostics);

    expect(diagnostics).toHaveLength(3);

    const codes = diagnostics.map((d) => d.code);
    expect(codes).toContain(PROVIDER_CAPABILITY_EXTENSION_STATE_UNSUPPORTED);
    expect(codes).toContain(PROVIDER_CAPABILITY_EXTENSION_SETTINGS_UNSUPPORTED);
    expect(codes).toContain(PROVIDER_CAPABILITY_EXTENSION_PROPOSALS_UNSUPPORTED);

    for (const d of diagnostics) {
      expect(d.severity).toBe('info');
      expect(d.milestone).toBe('m2');
    }
  });

  it('emits state, settings, and proposals diagnostics when all capabilities are explicitly false', () => {
    const diagnostics: ExtensionDiagnostic[] = [];

    pushUnsupportedCapabilityDiagnostics(diagnostics, {
      state: false,
      settings: false,
      proposals: false,
    });

    expect(diagnostics).toHaveLength(3);
    expect(diagnostics.map((d) => d.code)).toEqual([
      PROVIDER_CAPABILITY_EXTENSION_STATE_UNSUPPORTED,
      PROVIDER_CAPABILITY_EXTENSION_SETTINGS_UNSUPPORTED,
      PROVIDER_CAPABILITY_EXTENSION_PROPOSALS_UNSUPPORTED,
    ]);
  });

  it('emits zero diagnostics when all capabilities are true', () => {
    const diagnostics: ExtensionDiagnostic[] = [];

    pushUnsupportedCapabilityDiagnostics(diagnostics, {
      state: true,
      settings: true,
      proposals: true,
    });

    expect(diagnostics).toHaveLength(0);
  });

  // -- Partial capability coverage ------------------------------------------

  it('emits only settings and proposals diagnostics when state is supported', () => {
    const diagnostics: ExtensionDiagnostic[] = [];

    pushUnsupportedCapabilityDiagnostics(diagnostics, { state: true });

    expect(diagnostics).toHaveLength(2);
    const codes = diagnostics.map((d) => d.code);
    expect(codes).not.toContain(PROVIDER_CAPABILITY_EXTENSION_STATE_UNSUPPORTED);
    expect(codes).toContain(PROVIDER_CAPABILITY_EXTENSION_SETTINGS_UNSUPPORTED);
    expect(codes).toContain(PROVIDER_CAPABILITY_EXTENSION_PROPOSALS_UNSUPPORTED);
  });

  it('emits only state and proposals diagnostics when settings is supported', () => {
    const diagnostics: ExtensionDiagnostic[] = [];

    pushUnsupportedCapabilityDiagnostics(diagnostics, { settings: true });

    expect(diagnostics).toHaveLength(2);
    const codes = diagnostics.map((d) => d.code);
    expect(codes).toContain(PROVIDER_CAPABILITY_EXTENSION_STATE_UNSUPPORTED);
    expect(codes).not.toContain(PROVIDER_CAPABILITY_EXTENSION_SETTINGS_UNSUPPORTED);
    expect(codes).toContain(PROVIDER_CAPABILITY_EXTENSION_PROPOSALS_UNSUPPORTED);
  });

  it('emits only state and settings diagnostics when proposals is supported', () => {
    const diagnostics: ExtensionDiagnostic[] = [];

    pushUnsupportedCapabilityDiagnostics(diagnostics, { proposals: true });

    expect(diagnostics).toHaveLength(2);
    const codes = diagnostics.map((d) => d.code);
    expect(codes).toContain(PROVIDER_CAPABILITY_EXTENSION_STATE_UNSUPPORTED);
    expect(codes).toContain(PROVIDER_CAPABILITY_EXTENSION_SETTINGS_UNSUPPORTED);
    expect(codes).not.toContain(PROVIDER_CAPABILITY_EXTENSION_PROPOSALS_UNSUPPORTED);
  });

  it('emits only a single diagnostic when two capabilities are supported', () => {
    const diagnostics: ExtensionDiagnostic[] = [];

    pushUnsupportedCapabilityDiagnostics(diagnostics, {
      state: true,
      settings: true,
    });

    expect(diagnostics).toHaveLength(1);
    expect(diagnostics[0].code).toBe(PROVIDER_CAPABILITY_EXTENSION_PROPOSALS_UNSUPPORTED);
  });

  // -- Provider name in messages --------------------------------------------

  it('uses the supplied provider name in diagnostic messages', () => {
    const diagnostics: ExtensionDiagnostic[] = [];

    pushUnsupportedCapabilityDiagnostics(diagnostics, {
      state: false,
      settings: false,
      proposals: false,
    }, 'Astrid bridge');

    expect(diagnostics).toHaveLength(3);
    for (const d of diagnostics) {
      expect(d.message).toContain('Astrid bridge');
    }
    expect(diagnostics[0].message).toBe('Extension state persistence is not supported by Astrid bridge.');
    expect(diagnostics[1].message).toBe('Extension settings persistence is not supported by Astrid bridge.');
    expect(diagnostics[2].message).toBe('Extension proposal persistence is not supported by Astrid bridge.');
  });

  it('uses "this provider" when no provider name is supplied', () => {
    const diagnostics: ExtensionDiagnostic[] = [];

    pushUnsupportedCapabilityDiagnostics(diagnostics, {
      state: false,
      settings: false,
      proposals: false,
    });

    for (const d of diagnostics) {
      expect(d.message).toContain('this provider');
    }
  });

  // -- Empty capabilities object (all keys omitted = all unsupported) --------

  it('treats an empty capabilities object as all-unsupported', () => {
    const diagnostics: ExtensionDiagnostic[] = [];

    pushUnsupportedCapabilityDiagnostics(diagnostics, {});

    expect(diagnostics).toHaveLength(3);
  });

  // -- Idempotency: multiple calls append, not overwrite --------------------

  it('appends diagnostics on multiple calls (does not clear the array)', () => {
    const diagnostics: ExtensionDiagnostic[] = [];

    pushUnsupportedCapabilityDiagnostics(diagnostics, { state: true, proposals: true });
    expect(diagnostics).toHaveLength(1);
    expect(diagnostics[0].code).toBe(PROVIDER_CAPABILITY_EXTENSION_SETTINGS_UNSUPPORTED);

    pushUnsupportedCapabilityDiagnostics(diagnostics, { settings: true, proposals: true });
    expect(diagnostics).toHaveLength(2);
    expect(diagnostics[1].code).toBe(PROVIDER_CAPABILITY_EXTENSION_STATE_UNSUPPORTED);
  });
});

// ---------------------------------------------------------------------------
// Tests: Diagnostic code constants
// ---------------------------------------------------------------------------

describe('diagnostic code constants', () => {
  it('PROVIDER_CAPABILITY_EXTENSION_STATE_UNSUPPORTED is the expected string', () => {
    expect(PROVIDER_CAPABILITY_EXTENSION_STATE_UNSUPPORTED).toBe(
      'provider_capability_extension_state_unsupported',
    );
  });

  it('PROVIDER_CAPABILITY_EXTENSION_SETTINGS_UNSUPPORTED is the expected string', () => {
    expect(PROVIDER_CAPABILITY_EXTENSION_SETTINGS_UNSUPPORTED).toBe(
      'provider_capability_extension_settings_unsupported',
    );
  });

  it('PROVIDER_CAPABILITY_EXTENSION_PROPOSALS_UNSUPPORTED is the expected string', () => {
    expect(PROVIDER_CAPABILITY_EXTENSION_PROPOSALS_UNSUPPORTED).toBe(
      'provider_capability_extension_proposals_unsupported',
    );
  });

  it('all three codes are distinct', () => {
    const codes = [
      PROVIDER_CAPABILITY_EXTENSION_STATE_UNSUPPORTED,
      PROVIDER_CAPABILITY_EXTENSION_SETTINGS_UNSUPPORTED,
      PROVIDER_CAPABILITY_EXTENSION_PROPOSALS_UNSUPPORTED,
    ];
    expect(new Set(codes).size).toBe(3);
  });
});

// ---------------------------------------------------------------------------
// Tests: Provider test double with no persistence factory
// ---------------------------------------------------------------------------

describe('provider without extension persistence factory', () => {
  it('does not have a createExtensionPersistenceService method', () => {
    const provider = createProviderWithoutExtensionPersistence();

    // The method is optional and intentionally omitted
    expect(provider.createExtensionPersistenceService).toBeUndefined();
  });

  it('isDataProviderPersistenceEnabled returns true when persistenceEnabled is not false', () => {
    const provider = createProviderWithoutExtensionPersistence();
    expect(isDataProviderPersistenceEnabled(provider)).toBe(true);
  });

  it('simulates the unsupported-path: pushing diagnostics and returning null', () => {
    // Simulate what a provider's createExtensionPersistenceService would do
    // when it does not support extension persistence: push diagnostics and
    // return null.
    const diagnostics: ExtensionDiagnostic[] = [];

    pushUnsupportedCapabilityDiagnostics(diagnostics, {
      state: false,
      settings: false,
      proposals: false,
    }, 'Astrid bridge');

    expect(diagnostics).toHaveLength(3);

    // Each normalized unsupported code must be emitted exactly once
    const codes = diagnostics.map((d) => d.code);
    expect(codes.filter((c) => c === PROVIDER_CAPABILITY_EXTENSION_STATE_UNSUPPORTED)).toHaveLength(1);
    expect(codes.filter((c) => c === PROVIDER_CAPABILITY_EXTENSION_SETTINGS_UNSUPPORTED)).toHaveLength(1);
    expect(codes.filter((c) => c === PROVIDER_CAPABILITY_EXTENSION_PROPOSALS_UNSUPPORTED)).toHaveLength(1);

    // Verify message content references the correct provider name
    expect(diagnostics[0].message).toContain('Astrid bridge');
    expect(diagnostics[1].message).toContain('Astrid bridge');
    expect(diagnostics[2].message).toContain('Astrid bridge');

    // Severity is always 'info' for unsupported capability notifications
    for (const d of diagnostics) {
      expect(d.severity).toBe('info');
    }
  });

  it('unsupported diagnostic codes follow the stable naming convention', () => {
    // All three codes share the provider_capability_ prefix and _unsupported suffix
    const stateDiag: ExtensionDiagnostic = {
      severity: 'info',
      code: PROVIDER_CAPABILITY_EXTENSION_STATE_UNSUPPORTED,
      message: 'Extension state persistence is not supported by test provider.',
      milestone: 'm2',
    };

    expect(stateDiag.code.startsWith('provider_capability_')).toBe(true);
    expect(stateDiag.code.endsWith('_unsupported')).toBe(true);
    expect(stateDiag.severity).toBe('info');
    expect(stateDiag.milestone).toBe('m2');
  });
});

// ---------------------------------------------------------------------------
// Tests: ExtensionPersistenceScope shape (contract validation)
// ---------------------------------------------------------------------------

describe('ExtensionPersistenceScope contract', () => {
  it('accepts a minimal scope with userId and timelineId', () => {
    const scope: ExtensionPersistenceScope = {
      userId: 'user-1',
      timelineId: 'timeline-1',
    };

    expect(scope.userId).toBe('user-1');
    expect(scope.timelineId).toBe('timeline-1');
  });
});

// ---------------------------------------------------------------------------
// Tests: isDataProviderPersistenceEnabled
// ---------------------------------------------------------------------------

describe('isDataProviderPersistenceEnabled', () => {
  it('returns true for null / undefined provider', () => {
    expect(isDataProviderPersistenceEnabled(null)).toBe(true);
    expect(isDataProviderPersistenceEnabled(undefined)).toBe(true);
  });

  it('returns true when persistenceEnabled is not set', () => {
    const provider = createProviderWithoutExtensionPersistence();
    expect(isDataProviderPersistenceEnabled(provider)).toBe(true);
  });

  it('returns false when persistenceEnabled is explicitly false', () => {
    const provider = createProviderWithoutExtensionPersistence();
    provider.persistenceEnabled = false;
    expect(isDataProviderPersistenceEnabled(provider)).toBe(false);
  });

  it('returns true when persistenceEnabled is explicitly true', () => {
    const provider = createProviderWithoutExtensionPersistence();
    provider.persistenceEnabled = true;
    expect(isDataProviderPersistenceEnabled(provider)).toBe(true);
  });
});
