import { describe, expect, it } from 'vitest';
import {
  validateWorkspaceSourcePackage,
  validateInstalledBundlePackage,
  validatePackage,
  detectPackageForm,
  isBlockingDiagnostic,
  isWorkspaceSourceWarning,
  isInstalledPackBlocker,
  isContributionIdDuplicate,
} from '@/tools/video-editor/runtime/extensionPackageManifest';
import type {
  PackageValidationResult,
  WorkspaceSourcePackage,
  InstalledBundlePackage,
} from '@/tools/video-editor/runtime/extensionPackageManifest';
import type {
  ExtensionManifest,
  InstalledExtensionPackage,
  InstalledExtensionMetadata,
} from '@reigh/editor-sdk';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Create a minimal valid workspace source (reigh-extension.json shape). */
function workspaceSource(overrides?: Partial<ExtensionManifest>): Record<string, unknown> {
  const manifest: ExtensionManifest = {
    id: 'com.test.example' as any,
    version: '1.0.0',
    label: 'Test Extension',
    publisher: 'Test Publisher',
    license: 'MIT',
    settingsSchema: { version: 1 },
    ...overrides,
  };
  return { manifest };
}

/** Create a minimal valid installed bundle package. */
function installedBundle(overrides?: {
  metadata?: Partial<InstalledExtensionMetadata>;
  manifest?: Partial<ExtensionManifest>;
  bundleContent?: string;
}): InstalledExtensionPackage {
  const manifest: ExtensionManifest = {
    id: 'com.test.example' as any,
    version: '1.0.0',
    label: 'Test Extension',
    publisher: 'Test Publisher',
    license: 'MIT',
    settingsSchema: { version: 1 },
    ...overrides?.manifest,
  };
  const metadata: InstalledExtensionMetadata = {
    extensionId: 'com.test.example' as any,
    version: '1.0.0',
    integrity: { algorithm: 'sha256', value: 'abc123' },
    enabled: true,
    publisher: 'Test Publisher',
    license: 'MIT',
    ...overrides?.metadata,
  };
  return {
    metadata,
    manifest,
    bundleContent: overrides?.bundleContent ?? 'export function activate() {}',
  };
}

// ---------------------------------------------------------------------------
// validateWorkspaceSourcePackage
// ---------------------------------------------------------------------------

describe('validateWorkspaceSourcePackage', () => {
  it('accepts a valid workspace source package', () => {
    const result = validateWorkspaceSourcePackage(workspaceSource());
    expect(result.valid).toBe(true);
    expect(result.form).toBe('workspace-source');
    expect(result.errors).toHaveLength(0);
  });

  it('rejects a package missing the manifest property', () => {
    const result = validateWorkspaceSourcePackage({});
    expect(result.valid).toBe(false);
    expect(result.form).toBe('workspace-source');
    expect(result.errors).toHaveLength(1);
    expect(result.errors[0].code).toBe('package/workspace-missing-manifest');
  });

  it('rejects a package with null manifest', () => {
    const result = validateWorkspaceSourcePackage({ manifest: null });
    expect(result.valid).toBe(false);
    expect(result.errors).toHaveLength(1);
    expect(result.errors[0].code).toBe('package/workspace-missing-manifest');
  });

  it('rejects a workspace source with an invalid extension ID', () => {
    const result = validateWorkspaceSourcePackage(
      workspaceSource({ id: '!!invalid!!' as any }),
    );
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.code === 'manifest/invalid-id')).toBe(true);
  });

  it('rejects a workspace source with missing version', () => {
    const result = validateWorkspaceSourcePackage(
      workspaceSource({ version: '' }),
    );
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.code === 'manifest/missing-version')).toBe(true);
  });

  it('rejects a workspace source with invalid semver', () => {
    const result = validateWorkspaceSourcePackage(
      workspaceSource({ version: 'not-semver' }),
    );
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.code === 'manifest/invalid-version')).toBe(true);
  });

  it('rejects a workspace source with missing label', () => {
    const result = validateWorkspaceSourcePackage(
      workspaceSource({ label: '' }),
    );
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.code === 'manifest/missing-label')).toBe(true);
  });

  it('warns (does not block) when workspace source is missing publisher', () => {
    const result = validateWorkspaceSourcePackage(
      workspaceSource({ publisher: undefined }),
    );
    expect(result.valid).toBe(true);
    expect(result.warnings.some((w) => w.code === 'manifest/dev-missing-publisher')).toBe(true);
  });

  it('warns (does not block) when workspace source is missing license', () => {
    const result = validateWorkspaceSourcePackage(
      workspaceSource({ license: undefined }),
    );
    expect(result.valid).toBe(true);
    expect(result.warnings.some((w) => w.code === 'manifest/dev-missing-license')).toBe(true);
  });

  it('warns (does not block) when workspace source is missing settingsSchema', () => {
    const result = validateWorkspaceSourcePackage(
      workspaceSource({ settingsSchema: undefined }),
    );
    expect(result.valid).toBe(true);
    expect(result.warnings.some((w) => w.code === 'manifest/dev-missing-settings-schema')).toBe(true);
  });

  it('validates contribution ID uniqueness in workspace source', () => {
    const result = validateWorkspaceSourcePackage(
      workspaceSource({
        contributions: [
          { id: 'dup-id', kind: 'command', command: 'test.cmd', label: 'A' },
          { id: 'dup-id', kind: 'command', command: 'test.cmd2', label: 'B' },
        ] as any,
      }),
    );
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.code === 'manifest/duplicate-contribution-id')).toBe(true);
  });

  it('does not block when contributions have unique IDs', () => {
    const result = validateWorkspaceSourcePackage(
      workspaceSource({
        contributions: [
          { id: 'cmd-a', kind: 'command', command: 'test.a', label: 'A' },
          { id: 'cmd-b', kind: 'command', command: 'test.b', label: 'B' },
        ] as any,
      }),
    );
    expect(result.valid).toBe(true);
    expect(result.errors.some((e) => e.code === 'manifest/duplicate-contribution-id')).toBe(false);
  });

  it('allows cross-kind reuse of the same bare contribution ID (SD3)', () => {
    const result = validateWorkspaceSourcePackage(
      workspaceSource({
        contributions: [
          { id: 'shared-id', kind: 'command', command: 'test.cmd', label: 'Command' },
          { id: 'shared-id', kind: 'effect', effectId: 'test.effect', label: 'Effect' },
        ] as any,
      }),
    );
    expect(result.valid).toBe(true);
    expect(result.errors.some((e) => e.code === 'manifest/duplicate-contribution-id')).toBe(false);
  });

  it('warns about extra top-level keys beyond manifest', () => {
    const result = validateWorkspaceSourcePackage({
      manifest: workspaceSource().manifest,
      extraKey: 'should be warned about',
      anotherExtra: 42,
    });
    expect(result.valid).toBe(true);
    const extraKeyWarnings = result.warnings.filter(
      (w) => w.code === 'package/workspace-extra-key',
    );
    expect(extraKeyWarnings).toHaveLength(2);
  });

  it('accepts a minimal M1-style manifest (id+version+label only)', () => {
    const result = validateWorkspaceSourcePackage(
      workspaceSource({
        publisher: undefined,
        license: undefined,
        settingsSchema: undefined,
        apiVersion: undefined,
        contributions: undefined,
      }),
    );
    // Should be valid — M1 compat
    expect(result.valid).toBe(true);
    // Should have dev warnings about missing fields
    expect(result.warnings.length).toBeGreaterThan(0);
  });

  it('validates API version format', () => {
    const result = validateWorkspaceSourcePackage(
      workspaceSource({ apiVersion: -1 }),
    );
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.code === 'manifest/invalid-api-version')).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// validateInstalledBundlePackage
// ---------------------------------------------------------------------------

describe('validateInstalledBundlePackage', () => {
  it('accepts a valid installed bundle package', () => {
    const result = validateInstalledBundlePackage(installedBundle());
    expect(result.valid).toBe(true);
    expect(result.form).toBe('installed-bundle');
    expect(result.errors).toHaveLength(0);
  });

  it('rejects an installed bundle with missing publisher', () => {
    const result = validateInstalledBundlePackage(
      installedBundle({
        metadata: { publisher: undefined },
        manifest: { publisher: undefined },
      }),
    );
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.code === 'manifest/installed-missing-publisher')).toBe(true);
  });

  it('rejects an installed bundle with missing license', () => {
    const result = validateInstalledBundlePackage(
      installedBundle({
        metadata: { license: undefined },
        manifest: { license: undefined },
      }),
    );
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.code === 'manifest/installed-missing-license')).toBe(true);
  });

  it('rejects an installed bundle with missing integrity', () => {
    const pack = installedBundle();
    (pack.metadata as any).integrity = undefined;
    const result = validateInstalledBundlePackage(pack);
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.code === 'package/missing-integrity')).toBe(true);
  });

  it('rejects an installed bundle with invalid integrity algorithm', () => {
    const pack = installedBundle();
    pack.metadata.integrity = { algorithm: 'md5' as any, value: 'abc' };
    const result = validateInstalledBundlePackage(pack);
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.code === 'package/invalid-integrity-algorithm')).toBe(true);
  });

  it('rejects an installed bundle with missing integrity value', () => {
    const pack = installedBundle();
    pack.metadata.integrity = { algorithm: 'sha256', value: '' };
    const result = validateInstalledBundlePackage(pack);
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.code === 'package/missing-integrity-value')).toBe(true);
  });

  it('rejects an installed bundle with id mismatch between metadata and manifest', () => {
    const result = validateInstalledBundlePackage(
      installedBundle({
        metadata: { extensionId: 'com.other.id' as any },
      }),
    );
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.code === 'package/id-mismatch')).toBe(true);
  });

  it('rejects an installed bundle with version mismatch', () => {
    const result = validateInstalledBundlePackage(
      installedBundle({
        metadata: { version: '2.0.0' },
      }),
    );
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.code === 'package/version-mismatch')).toBe(true);
  });

  it('rejects an installed bundle with missing bundleContent', () => {
    const result = validateInstalledBundlePackage(
      installedBundle({ bundleContent: '' }),
    );
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.code === 'package/missing-bundle')).toBe(true);
  });

  it('rejects an installed bundle with missing manifest', () => {
    const pack = installedBundle();
    (pack as any).manifest = undefined;
    const result = validateInstalledBundlePackage(pack);
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.code === 'package/missing-manifest')).toBe(true);
  });

  it('rejects an installed bundle with missing metadata', () => {
    const pack = installedBundle();
    (pack as any).metadata = undefined;
    const result = validateInstalledBundlePackage(pack);
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.code === 'package/missing-metadata')).toBe(true);
  });

  it('validates contribution ID uniqueness in installed bundle', () => {
    const result = validateInstalledBundlePackage(
      installedBundle({
        manifest: {
          contributions: [
            { id: 'dup-id', kind: 'command', command: 'test.cmd', label: 'A' },
            { id: 'dup-id', kind: 'command', command: 'test.cmd2', label: 'B' },
          ] as any,
        },
      }),
    );
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.code === 'manifest/duplicate-contribution-id')).toBe(true);
  });

  it('allows cross-kind reuse in installed bundle (SD3)', () => {
    const result = validateInstalledBundlePackage(
      installedBundle({
        manifest: {
          contributions: [
            { id: 'shared-id', kind: 'command', command: 'test.cmd', label: 'Command' },
            { id: 'shared-id', kind: 'effect', effectId: 'test.effect', label: 'Effect' },
          ] as any,
        },
      }),
    );
    expect(result.valid).toBe(true);
    expect(result.errors.some((e) => e.code === 'manifest/duplicate-contribution-id')).toBe(false);
  });

  it('rejects invalid contribution IDs', () => {
    const result = validateInstalledBundlePackage(
      installedBundle({
        manifest: {
          contributions: [
            { id: '!!!bad!!!', kind: 'command', command: 'test.cmd', label: 'Bad' },
          ] as any,
        },
      }),
    );
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.code === 'manifest/invalid-contribution-id')).toBe(true);
  });

  it('warns about missing settingsSchema in installed bundle (non-blocking)', () => {
    const pack = installedBundle({
      manifest: { settingsSchema: undefined },
      metadata: { settingsSchemaVersion: undefined },
    });
    const result = validateInstalledBundlePackage(pack);
    // Missing settingsSchema is a warning in installed mode, not an error
    expect(result.warnings.some((w) => w.code === 'manifest/installed-missing-settings-schema')).toBe(true);
  });

  it('rejects invalid enabled field', () => {
    const pack = installedBundle();
    (pack.metadata as any).enabled = 'not-a-boolean';
    const result = validateInstalledBundlePackage(pack);
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.code === 'package/invalid-enabled')).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// validatePackage (unified)
// ---------------------------------------------------------------------------

describe('validatePackage', () => {
  it('routes workspace source shapes to workspace validation', () => {
    const result = validatePackage(workspaceSource());
    expect(result.form).toBe('workspace-source');
    expect(result.valid).toBe(true);
  });

  it('routes installed bundle shapes to installed validation', () => {
    const pack = installedBundle();
    const result = validatePackage(pack as unknown as Record<string, unknown>);
    expect(result.form).toBe('installed-bundle');
    expect(result.valid).toBe(true);
  });

  it('rejects unrecognised shapes', () => {
    const result = validatePackage({ notA: 'package' });
    expect(result.valid).toBe(false);
    expect(result.errors).toHaveLength(1);
    expect(result.errors[0].code).toBe('package/unrecognised-shape');
  });

  it('distinguishes workspace source warnings from installed blockers', () => {
    // Same manifest data, different forms produce different diagnostics
    const manifest = {
      id: 'com.test.example',
      version: '1.0.0',
      label: 'Test',
      // No publisher, license, or settingsSchema
    };

    // Workspace source: dev warnings
    const wsResult = validatePackage({ manifest } as any);
    expect(wsResult.form).toBe('workspace-source');
    expect(wsResult.valid).toBe(true);
    const wsWarnings = wsResult.warnings.filter(
      (w) =>
        w.code === 'manifest/dev-missing-publisher' ||
        w.code === 'manifest/dev-missing-license' ||
        w.code === 'manifest/dev-missing-settings-schema',
    );
    expect(wsWarnings.length).toBeGreaterThan(0);
    // No blocking errors from these missing fields
    expect(wsResult.errors.filter((e) => e.code.startsWith('manifest/dev-'))).toHaveLength(0);

    // Installed bundle: blocking errors
    const ibResult = validatePackage({
      metadata: {
        extensionId: 'com.test.example',
        version: '1.0.0',
        integrity: { algorithm: 'sha256', value: 'abc123' },
        enabled: true,
      },
      manifest,
      bundleContent: 'export function activate() {}',
    } as any);
    expect(ibResult.form).toBe('installed-bundle');
    // Missing publisher and license are blocking errors for installed
    expect(ibResult.errors.some((e) => e.code === 'manifest/installed-missing-publisher')).toBe(true);
    expect(ibResult.errors.some((e) => e.code === 'manifest/installed-missing-license')).toBe(true);
    expect(ibResult.valid).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// detectPackageForm
// ---------------------------------------------------------------------------

describe('detectPackageForm', () => {
  it('detects workspace source shape', () => {
    expect(detectPackageForm(workspaceSource())).toBe('workspace-source');
  });

  it('detects installed bundle shape', () => {
    const pack = installedBundle();
    expect(detectPackageForm(pack as unknown as Record<string, unknown>)).toBe('installed-bundle');
  });

  it('returns null for unrecognised shapes', () => {
    expect(detectPackageForm({})).toBeNull();
    expect(detectPackageForm({ metadata: {} } as any)).toBeNull();
    expect(detectPackageForm({ manifest: null } as any)).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// Diagnostic classification helpers
// ---------------------------------------------------------------------------

describe('isBlockingDiagnostic', () => {
  it('returns true for contribution ID duplicate errors', () => {
    const diag = {
      severity: 'error' as const,
      code: 'manifest/duplicate-contribution-id',
      message: 'dup',
      extensionId: 'com.test',
    };
    expect(isBlockingDiagnostic(diag)).toBe(true);
  });

  it('returns true for installed-only blocker codes', () => {
    const diag = {
      severity: 'error' as const,
      code: 'manifest/installed-missing-publisher',
      message: 'missing publisher',
      extensionId: 'com.test',
    };
    expect(isBlockingDiagnostic(diag)).toBe(true);
  });

  it('returns false for warnings', () => {
    const diag = {
      severity: 'warning' as const,
      code: 'manifest/dev-missing-publisher',
      message: 'missing publisher',
      extensionId: 'com.test',
    };
    expect(isBlockingDiagnostic(diag)).toBe(false);
  });

  it('returns false for info diagnostics', () => {
    const diag = {
      severity: 'info' as const,
      code: 'some/info',
      message: 'info',
      extensionId: 'com.test',
    };
    expect(isBlockingDiagnostic(diag)).toBe(false);
  });

  it('returns false for unrecognised error codes', () => {
    const diag = {
      severity: 'error' as const,
      code: 'unknown/code',
      message: 'unknown',
      extensionId: 'com.test',
    };
    expect(isBlockingDiagnostic(diag)).toBe(false);
  });
});

describe('isWorkspaceSourceWarning', () => {
  it('returns true for dev-missing-publisher warning', () => {
    const diag = {
      severity: 'warning' as const,
      code: 'manifest/dev-missing-publisher',
      message: 'missing publisher',
      extensionId: 'com.test',
    };
    expect(isWorkspaceSourceWarning(diag)).toBe(true);
  });

  it('returns true for dev-missing-license warning', () => {
    const diag = {
      severity: 'warning' as const,
      code: 'manifest/dev-missing-license',
      message: 'missing license',
      extensionId: 'com.test',
    };
    expect(isWorkspaceSourceWarning(diag)).toBe(true);
  });

  it('returns true for dev-missing-settings-schema warning', () => {
    const diag = {
      severity: 'warning' as const,
      code: 'manifest/dev-missing-settings-schema',
      message: 'missing schema',
      extensionId: 'com.test',
    };
    expect(isWorkspaceSourceWarning(diag)).toBe(true);
  });

  it('returns false for other warnings', () => {
    const diag = {
      severity: 'warning' as const,
      code: 'manifest/dependency-posture-mismatch',
      message: 'mismatch',
      extensionId: 'com.test',
    };
    expect(isWorkspaceSourceWarning(diag)).toBe(false);
  });

  it('returns false for errors', () => {
    const diag = {
      severity: 'error' as const,
      code: 'manifest/dev-missing-publisher',
      message: 'missing publisher',
      extensionId: 'com.test',
    };
    expect(isWorkspaceSourceWarning(diag)).toBe(false);
  });
});

describe('isInstalledPackBlocker', () => {
  it('returns true for installed-missing-publisher error', () => {
    const diag = {
      severity: 'error' as const,
      code: 'manifest/installed-missing-publisher',
      message: 'missing publisher',
      extensionId: 'com.test',
    };
    expect(isInstalledPackBlocker(diag)).toBe(true);
  });

  it('returns true for installed-missing-license error', () => {
    const diag = {
      severity: 'error' as const,
      code: 'manifest/installed-missing-license',
      message: 'missing license',
      extensionId: 'com.test',
    };
    expect(isInstalledPackBlocker(diag)).toBe(true);
  });

  it('returns false for universal block codes', () => {
    const diag = {
      severity: 'error' as const,
      code: 'manifest/duplicate-contribution-id',
      message: 'dup',
      extensionId: 'com.test',
    };
    expect(isInstalledPackBlocker(diag)).toBe(false);
  });

  it('returns false for warnings', () => {
    const diag = {
      severity: 'warning' as const,
      code: 'manifest/installed-missing-publisher',
      message: 'missing publisher',
      extensionId: 'com.test',
    };
    expect(isInstalledPackBlocker(diag)).toBe(false);
  });
});

describe('isContributionIdDuplicate', () => {
  it('returns true for duplicate-contribution-id', () => {
    const diag = {
      severity: 'error' as const,
      code: 'manifest/duplicate-contribution-id',
      message: 'dup',
      extensionId: 'com.test',
    };
    expect(isContributionIdDuplicate(diag)).toBe(true);
  });

  it('returns false for other codes', () => {
    const diag = {
      severity: 'error' as const,
      code: 'manifest/invalid-id',
      message: 'invalid',
      extensionId: 'com.test',
    };
    expect(isContributionIdDuplicate(diag)).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// Cross-cutting: distinguishing workspace source warnings from installed-pack blockers
// ---------------------------------------------------------------------------

describe('distinction between workspace source warnings and installed-pack blockers', () => {
  it('workspace source: missing publisher is a warning, not an error', () => {
    const result = validateWorkspaceSourcePackage(
      workspaceSource({ publisher: undefined }),
    );
    expect(result.valid).toBe(true);
    expect(result.errors).toHaveLength(0);
    const publisherWarnings = result.warnings.filter(
      (w) => w.code === 'manifest/dev-missing-publisher',
    );
    expect(publisherWarnings).toHaveLength(1);
    expect(publisherWarnings[0].severity).toBe('warning');
  });

  it('installed bundle: missing publisher is a blocking error, not a warning', () => {
    const result = validateInstalledBundlePackage(
      installedBundle({
        metadata: { publisher: undefined },
        manifest: { publisher: undefined },
      }),
    );
    expect(result.valid).toBe(false);
    const publisherErrors = result.errors.filter(
      (e) => e.code === 'manifest/installed-missing-publisher',
    );
    expect(publisherErrors).toHaveLength(1);
    expect(publisherErrors[0].severity).toBe('error');
    // No dev-missing-publisher warning in installed mode
    expect(result.warnings.some((w) => w.code === 'manifest/dev-missing-publisher')).toBe(false);
  });

  it('contribution ID uniqueness is always a blocking error (both forms)', () => {
    const withDup = {
      contributions: [
        { id: 'dup', kind: 'command', command: 'a', label: 'A' },
        { id: 'dup', kind: 'command', command: 'b', label: 'B' },
      ] as any,
    };

    const wsResult = validateWorkspaceSourcePackage(workspaceSource(withDup));
    expect(wsResult.valid).toBe(false);
    expect(wsResult.errors.some((e) => e.code === 'manifest/duplicate-contribution-id')).toBe(true);

    const ibResult = validateInstalledBundlePackage(
      installedBundle({ manifest: withDup }),
    );
    expect(ibResult.valid).toBe(false);
    expect(ibResult.errors.some((e) => e.code === 'manifest/duplicate-contribution-id')).toBe(true);
  });
});
