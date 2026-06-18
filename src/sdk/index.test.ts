import { describe, expect, it, beforeEach } from 'vitest';
import {
  defineExtension,
  validateExtensionId,
  validateContributionId,
  contributionKindNotYetBridged,
  CONTRIBUTION_KIND_MILESTONE,
  createExtensionContext,
  createCreativeContextStubs,
  ExtensionNotImplementedError,
  CREATIVE_MEMBER_MILESTONE,
} from '@/sdk/index';
import type {
  ReighExtension,
  ExtensionManifest,
  ExtensionContribution,
  ExtensionContext,
  DisposeHandle,
  ExtensionDiagnostic,
  ProcessManifestEntry,
} from '@/sdk/index';

// ---------------------------------------------------------------------------
// ID validation
// ---------------------------------------------------------------------------

describe('validateExtensionId', () => {
  it('accepts valid dot-separated IDs', () => {
    expect(validateExtensionId('com.example.my-ext')).toEqual([]);
    expect(validateExtensionId('myExtension')).toEqual([]);
    expect(validateExtensionId('a.b.c')).toEqual([]);
    expect(validateExtensionId('toolbar-extra')).toEqual([]);
    expect(validateExtensionId('my_ext_v2')).toEqual([]);
  });

  it('rejects empty strings', () => {
    const errors = validateExtensionId('');
    expect(errors.length).toBeGreaterThan(0);
    expect(errors[0]).toContain('non-empty');
  });

  it('rejects IDs starting with a digit', () => {
    const errors = validateExtensionId('1bad');
    expect(errors.length).toBeGreaterThan(0);
  });

  it('rejects IDs with spaces or special chars', () => {
    expect(validateExtensionId('bad id').length).toBeGreaterThan(0);
    expect(validateExtensionId('bad/id').length).toBeGreaterThan(0);
    expect(validateExtensionId('bad@id').length).toBeGreaterThan(0);
  });

  it('rejects IDs longer than 128 characters', () => {
    const long = 'a'.repeat(129);
    expect(validateExtensionId(long).length).toBeGreaterThan(0);
  });

  it('accepts exactly 128 characters', () => {
    const ok = 'a' + 'b'.repeat(127);
    expect(validateExtensionId(ok)).toEqual([]);
  });
});

describe('validateContributionId', () => {
  it('validates the same as extension IDs', () => {
    expect(validateContributionId('myToolbar')).toEqual([]);
    expect(validateContributionId('').length).toBeGreaterThan(0);
  });
});

// ---------------------------------------------------------------------------
// defineExtension — literal ID preservation and freezing
// ---------------------------------------------------------------------------

describe('defineExtension', () => {
  const validManifest: ExtensionManifest = {
    id: 'com.example.test' as any,
    version: '1.0.0',
    label: 'Test Extension',
    description: 'A test extension for SDK verification',
    apiVersion: 1,
    contributions: [
      {
        id: 'toolbar-main' as any,
        kind: 'slot',
        slot: 'toolbar',
        order: 10,
        label: 'Main toolbar widget',
      },
    ],
  };

  it('returns a frozen object', () => {
    const ext = defineExtension({ manifest: validManifest });
    expect(Object.isFrozen(ext)).toBe(true);
    expect(Object.isFrozen(ext.manifest)).toBe(true);
  });

  it('preserves literal extension ID', () => {
    const ext = defineExtension({ manifest: validManifest });
    expect(ext.manifest.id).toBe('com.example.test');
  });

  it('preserves literal contribution IDs', () => {
    const ext = defineExtension({ manifest: validManifest });
    expect(ext.manifest.contributions![0].id).toBe('toolbar-main');
  });

  it('preserves contribution order', () => {
    const ext = defineExtension({ manifest: validManifest });
    expect(ext.manifest.contributions![0].order).toBe(10);
  });

  it('preserves contribution kind', () => {
    const ext = defineExtension({ manifest: validManifest });
    expect(ext.manifest.contributions![0].kind).toBe('slot');
  });

  it('preserves slot name', () => {
    const ext = defineExtension({ manifest: validManifest });
    expect(ext.manifest.contributions![0].slot).toBe('toolbar');
  });

  it('freezes contributions array', () => {
    const ext = defineExtension({ manifest: validManifest });
    expect(Object.isFrozen(ext.manifest.contributions!)).toBe(true);
    expect(Object.isFrozen(ext.manifest.contributions![0])).toBe(true);
  });

  it('preserves activate function when provided', () => {
    const activate = () => {};
    const ext = defineExtension({ manifest: validManifest, activate });
    expect(ext.activate).toBe(activate);
  });

  it('throws on invalid extension ID', () => {
    expect(() =>
      defineExtension({
        manifest: { ...validManifest, id: '' as any },
      }),
    ).toThrow(/Invalid extension ID/);
  });

  it('throws on duplicate contribution IDs', () => {
    expect(() =>
      defineExtension({
        manifest: {
          ...validManifest,
          contributions: [
            { id: 'dup' as any, kind: 'slot' as const, slot: 'toolbar' as const },
            { id: 'dup' as any, kind: 'slot' as const, slot: 'statusBar' as const },
          ],
        },
      }),
    ).toThrow(/Duplicate contribution ID/);
  });

  it('throws on invalid contribution ID', () => {
    expect(() =>
      defineExtension({
        manifest: {
          ...validManifest,
          contributions: [
            { id: '' as any, kind: 'slot' as const, slot: 'toolbar' as const },
          ],
        },
      }),
    ).toThrow(/Invalid contribution ID/);
  });

  it('freezes nested arrays (permissions, processes, dependsOn) when provided', () => {
    const manifestWithAll: ExtensionManifest = {
      ...validManifest,
      permissions: [{ reason: 'testing', posture: { network: true } }],
      processes: [
        {
          id: 'proc1',
          label: 'Test process',
          spawn: { command: 'echo', args: ['hello'] },
          protocol: 'stdio-jsonrpc',
        },
      ],
      dependsOn: [{ extensionId: 'com.other.lib', versionRange: '^1.0.0' }],
    };
    const ext = defineExtension({ manifest: manifestWithAll });
    expect(Object.isFrozen(ext.manifest.permissions!)).toBe(true);
    expect(Object.isFrozen(ext.manifest.permissions![0])).toBe(true);
    expect(Object.isFrozen(ext.manifest.processes!)).toBe(true);
    expect(Object.isFrozen(ext.manifest.processes![0])).toBe(true);
    expect(Object.isFrozen(ext.manifest.dependsOn!)).toBe(true);
    expect(Object.isFrozen(ext.manifest.dependsOn![0])).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// Contribution kind bridging
// ---------------------------------------------------------------------------

describe('contributionKindNotYetBridged', () => {
  it('returns null for M1-bridged kinds', () => {
    expect(contributionKindNotYetBridged('slot')).toBeNull();
    expect(contributionKindNotYetBridged('dialog')).toBeNull();
    expect(contributionKindNotYetBridged('panel')).toBeNull();
    expect(contributionKindNotYetBridged('inspectorSection')).toBeNull();
  });

  it('returns milestone name for not-yet-bridged kinds', () => {
    expect(contributionKindNotYetBridged('effect')).toBe('M3');
    expect(contributionKindNotYetBridged('transition')).toBe('M3');
    expect(contributionKindNotYetBridged('clipType')).toBe('M3');
    expect(contributionKindNotYetBridged('parser')).toBe('M4');
    expect(contributionKindNotYetBridged('agentTool')).toBe('M5');
    expect(contributionKindNotYetBridged('agent')).toBe('M5');
  });
});

// ---------------------------------------------------------------------------
// Type-level tests (compile-time assertions)
// ---------------------------------------------------------------------------

describe('SDK type exports are complete', () => {
  it('ReighExtension has manifest and optional activate', () => {
    const ext: ReighExtension = defineExtension({ manifest: validManifest() });
    expect(ext.manifest.id).toBe('com.example.test');
    expect(typeof ext.activate).toBe('undefined');
  });

  it('ExtensionManifest supports all reserved fields', () => {
    const manifest: ExtensionManifest = {
      id: 'com.example.full' as any,
      version: '2.0.0',
      label: 'Full Manifest',
      apiVersion: 1,
      contributions: [],
      permissions: [],
      processes: [],
      migrations: [],
      comments: 'hello',
      dependsOn: [],
      renderability: {},
    };
    const ext = defineExtension({ manifest });
    expect(ext.manifest.id).toBe('com.example.full');
  });

  it('ProcessManifestEntry shape validates correctly', () => {
    const process: ProcessManifestEntry = {
      id: 'my-process',
      label: 'My Process',
      spawn: {
        command: 'node',
        args: ['--version'],
        env: { NODE_ENV: 'development' },
        cwd: '/tmp',
      },
      protocol: 'stdio-jsonrpc',
      healthCheck: 'ping',
      shutdown: 'SIGTERM',
      restartPolicy: 'on-failure',
    };
    expect(process.protocol).toBe('stdio-jsonrpc');
  });
});

// ---------------------------------------------------------------------------
// createExtensionContext — conservative shell
// ---------------------------------------------------------------------------

describe('createExtensionContext', () => {
  let extension: ReighExtension;
  let ctx: ExtensionContext;

  beforeEach(() => {
    extension = defineExtension({
      manifest: {
        id: 'com.example.ctx-test' as any,
        version: '2.3.4',
        label: 'Context Test Extension',
        description: 'Used for ExtensionContext tests',
        apiVersion: 1,
        contributions: [
          {
            id: 'ctx-slot' as any,
            kind: 'slot',
            slot: 'toolbar',
            order: 10,
            label: 'Test slot',
          },
        ],
      },
    });
    ctx = createExtensionContext(extension);
  });

  // ---- approved members ---------------------------------------------------

  it('exposes apiVersion: 1', () => {
    expect(ctx.apiVersion).toBe(1);
  });

  it('exposes readonly extension metadata', () => {
    expect(ctx.extension.id).toBe('com.example.ctx-test');
    expect(ctx.extension.version).toBe('2.3.4');
    expect(ctx.extension.label).toBe('Context Test Extension');
    expect(ctx.extension.description).toBe('Used for ExtensionContext tests');
    expect(ctx.extension.manifest).toBe(extension.manifest);
  });

  it('exposes chrome service', () => {
    expect(ctx.chrome).toBeDefined();
    expect(typeof ctx.chrome.toast).toBe('function');
    expect(typeof ctx.chrome.progress).toBe('function');
    expect(typeof ctx.chrome.subscribe).toBe('function');
  });

  it('exposes services.settings', () => {
    expect(ctx.services.settings).toBeDefined();
    expect(typeof ctx.services.settings.get).toBe('function');
    expect(typeof ctx.services.settings.set).toBe('function');
    expect(typeof ctx.services.settings.delete).toBe('function');
    expect(typeof ctx.services.settings.keys).toBe('function');
  });

  it('exposes services.i18n', () => {
    expect(ctx.services.i18n).toBeDefined();
    expect(typeof ctx.services.i18n.t).toBe('function');
  });

  it('exposes services.diagnostics', () => {
    expect(ctx.services.diagnostics).toBeDefined();
    expect(typeof ctx.services.diagnostics.report).toBe('function');
    expect(Array.isArray(ctx.services.diagnostics.diagnostics)).toBe(true);
  });

  it('exposes creative stubs', () => {
    expect(ctx.creative).toBeDefined();
    expect(Object.isFrozen(ctx.creative)).toBe(true);
  });

  // ---- creative stubs throw typed errors ----------------------------------

  it('creative.project throws ExtensionNotImplementedError', () => {
    expect(() => ctx.creative.project).toThrow(ExtensionNotImplementedError);
    try {
      ctx.creative.project;
    } catch (err) {
      expect(err).toBeInstanceOf(ExtensionNotImplementedError);
      expect((err as ExtensionNotImplementedError).feature).toBe('project');
      expect((err as ExtensionNotImplementedError).milestone).toBe('M2');
      expect((err as ExtensionNotImplementedError).message).toContain(
        'ctx.creative.project',
      );
      expect((err as ExtensionNotImplementedError).message).toContain('M2');
    }
  });

  it('creative.timeline throws ExtensionNotImplementedError', () => {
    expect(() => ctx.creative.timeline).toThrow(ExtensionNotImplementedError);
    try {
      ctx.creative.timeline;
    } catch (err) {
      expect((err as ExtensionNotImplementedError).feature).toBe('timeline');
      expect((err as ExtensionNotImplementedError).milestone).toBe('M2');
    }
  });

  it('creative.assets throws with M6 milestone', () => {
    expect(() => ctx.creative.assets).toThrow(ExtensionNotImplementedError);
    try {
      ctx.creative.assets;
    } catch (err) {
      expect((err as ExtensionNotImplementedError).feature).toBe('assets');
      expect((err as ExtensionNotImplementedError).milestone).toBe('M6');
    }
  });

  it('creative.materials throws with M6 milestone', () => {
    expect(() => ctx.creative.materials).toThrow(ExtensionNotImplementedError);
    try {
      ctx.creative.materials;
    } catch (err) {
      expect((err as ExtensionNotImplementedError).feature).toBe('materials');
      expect((err as ExtensionNotImplementedError).milestone).toBe('M6');
    }
  });

  it('creative.sessions throws with M4 milestone', () => {
    expect(() => ctx.creative.sessions).toThrow(ExtensionNotImplementedError);
    try {
      ctx.creative.sessions;
    } catch (err) {
      expect((err as ExtensionNotImplementedError).feature).toBe('sessions');
      expect((err as ExtensionNotImplementedError).milestone).toBe('M4');
    }
  });

  it('creative.export throws with M2 milestone', () => {
    expect(() => ctx.creative.export).toThrow(ExtensionNotImplementedError);
    try {
      ctx.creative.export;
    } catch (err) {
      expect((err as ExtensionNotImplementedError).feature).toBe('export');
      expect((err as ExtensionNotImplementedError).milestone).toBe('M2');
    }
  });

  it('creative.stage throws with M5 milestone', () => {
    expect(() => ctx.creative.stage).toThrow(ExtensionNotImplementedError);
    try {
      ctx.creative.stage;
    } catch (err) {
      expect((err as ExtensionNotImplementedError).feature).toBe('stage');
      expect((err as ExtensionNotImplementedError).milestone).toBe('M5');
    }
  });

  it('creative.writing throws with M2 milestone', () => {
    expect(() => ctx.creative.writing).toThrow(ExtensionNotImplementedError);
    try {
      ctx.creative.writing;
    } catch (err) {
      expect((err as ExtensionNotImplementedError).feature).toBe('writing');
      expect((err as ExtensionNotImplementedError).milestone).toBe('M2');
    }
  });

  // ---- settings service ---------------------------------------------------

  it('settings.get returns undefined for missing keys', () => {
    expect(ctx.services.settings.get('nonexistent')).toBeUndefined();
  });

  it('settings.set and get round-trip', () => {
    ctx.services.settings.set('theme', 'dark');
    expect(ctx.services.settings.get('theme')).toBe('dark');
  });

  it('settings.set and get round-trip objects', () => {
    const obj = { nested: { value: 42 } };
    ctx.services.settings.set('config', obj);
    expect(ctx.services.settings.get('config')).toEqual(obj);
  });

  it('settings.delete removes keys', () => {
    ctx.services.settings.set('temp', 'data');
    expect(ctx.services.settings.get('temp')).toBe('data');
    ctx.services.settings.delete('temp');
    expect(ctx.services.settings.get('temp')).toBeUndefined();
  });

  it('settings.keys lists all stored keys', () => {
    ctx.services.settings.set('a', 1);
    ctx.services.settings.set('b', 2);
    const keys = ctx.services.settings.keys();
    expect(keys).toContain('a');
    expect(keys).toContain('b');
  });

  it('settings are scoped per extension', () => {
    const ext2 = defineExtension({
      manifest: {
        id: 'com.other.ext' as any,
        version: '1.0.0',
        label: 'Other',
        contributions: [],
      },
    });
    const ctx2 = createExtensionContext(ext2);

    ctx.services.settings.set('shared-key', 'ext1-value');
    ctx2.services.settings.set('shared-key', 'ext2-value');

    expect(ctx.services.settings.get('shared-key')).toBe('ext1-value');
    expect(ctx2.services.settings.get('shared-key')).toBe('ext2-value');

    // Cleanup
    ctx.services.settings.delete('shared-key');
    ctx2.services.settings.delete('shared-key');
  });

  // ---- i18n service -------------------------------------------------------

  it('i18n.t returns the key verbatim when no replacements', () => {
    expect(ctx.services.i18n.t('hello.world')).toBe('hello.world');
  });

  it('i18n.t replaces placeholders', () => {
    const result = ctx.services.i18n.t('Hello, {{name}}!', { name: 'World' });
    expect(result).toBe('Hello, World!');
  });

  it('i18n.t replaces multiple placeholders', () => {
    const result = ctx.services.i18n.t('{{greeting}}, {{name}}!', {
      greeting: 'Hi',
      name: 'Alice',
    });
    expect(result).toBe('Hi, Alice!');
  });

  it('i18n.t replaces numeric values as strings', () => {
    const result = ctx.services.i18n.t('Count: {{n}}', { n: 42 });
    expect(result).toBe('Count: 42');
  });

  // ---- diagnostics service ------------------------------------------------

  it('diagnostics.report stores diagnostics with auto-filled extensionId', () => {
    ctx.services.diagnostics.report({
      severity: 'info',
      code: 'test/info',
      message: 'Test diagnostic',
    });
    const diags = ctx.services.diagnostics.diagnostics;
    expect(diags).toHaveLength(1);
    expect(diags[0].extensionId).toBe('com.example.ctx-test');
    expect(diags[0].severity).toBe('info');
    expect(diags[0].code).toBe('test/info');
    expect(diags[0].message).toBe('Test diagnostic');
  });

  it('diagnostics.report freezes stored diagnostics', () => {
    ctx.services.diagnostics.report({
      severity: 'warning',
      code: 'test/warn',
      message: 'Warning',
    });
    const diags = ctx.services.diagnostics.diagnostics;
    expect(Object.isFrozen(diags[0])).toBe(true);
  });

  // ---- chrome service -----------------------------------------------------

  it('chrome.toast does not throw', () => {
    expect(() => ctx.chrome.toast('Hello')).not.toThrow();
  });

  it('chrome.progress does not throw', () => {
    expect(() => ctx.chrome.progress(50, 'Rendering...')).not.toThrow();
  });

  it('chrome.subscribe returns a DisposeHandle', () => {
    const handle = ctx.chrome.subscribe('toast', () => {});
    expect(handle).toBeDefined();
    expect(typeof handle.dispose).toBe('function');
    handle.dispose();
  });

  it('chrome.subscribe delivers toast events to handlers', () => {
    const received: Array<{ message: string; severity: string }> = [];
    const handle = ctx.chrome.subscribe('toast', (payload) => {
      received.push(payload as any);
    });
    ctx.chrome.toast('Test message', 'warning');
    expect(received).toHaveLength(1);
    expect(received[0].message).toBe('Test message');
    expect(received[0].severity).toBe('warning');
    handle.dispose();
  });

  it('chrome.subscribe dispose removes the handler', () => {
    const received: string[] = [];
    const handle = ctx.chrome.subscribe('toast', (payload: any) => {
      received.push(payload.message);
    });
    handle.dispose();
    ctx.chrome.toast('After dispose');
    expect(received).toHaveLength(0);
  });

  it('chrome.subscribe delivers progress events', () => {
    const received: Array<{ percent: number; label?: string }> = [];
    const handle = ctx.chrome.subscribe('progress', (payload: any) => {
      received.push(payload);
    });
    ctx.chrome.progress(75, 'Exporting...');
    expect(received).toHaveLength(1);
    expect(received[0].percent).toBe(75);
    expect(received[0].label).toBe('Exporting...');
    handle.dispose();
  });

  // ---- no internal mutation escape hatch ----------------------------------

  it('does not expose DataProvider', () => {
    expect((ctx as any).DataProvider).toBeUndefined();
    expect((ctx as any).dataProvider).toBeUndefined();
    expect((ctx as any).provider).toBeUndefined();
    expect((ctx as any).data).toBeUndefined();
  });

  it('does not expose applyEdit', () => {
    expect((ctx as any).applyEdit).toBeUndefined();
    expect((ctx as any).edit).toBeUndefined();
    expect((ctx as any).mutate).toBeUndefined();
  });

  it('does not expose timeline store', () => {
    expect((ctx as any).timelineStore).toBeUndefined();
    expect((ctx as any).timeline).toBeUndefined();
    expect((ctx as any).store).toBeUndefined();
    expect((ctx as any).getTimeline).toBeUndefined();
  });

  it('does not expose internal ops', () => {
    expect((ctx as any).ops).toBeUndefined();
    expect((ctx as any).internalOps).toBeUndefined();
    expect((ctx as any)._internal).toBeUndefined();
    expect((ctx as any).__editorInternals).toBeUndefined();
  });

  it('has exactly the expected own property names', () => {
    const keys = Object.keys(ctx).sort();
    expect(keys).toEqual([
      'apiVersion',
      'chrome',
      'creative',
      'extension',
      'services',
    ]);
  });

  // ---- frozen / readonly --------------------------------------------------

  it('context is frozen', () => {
    expect(Object.isFrozen(ctx)).toBe(true);
  });

  it('extension metadata object is frozen', () => {
    expect(Object.isFrozen(ctx.extension)).toBe(true);
  });

  it('services object is frozen', () => {
    expect(Object.isFrozen(ctx.services)).toBe(true);
  });

  it('apiVersion cannot be reassigned (throws in strict mode)', () => {
    expect(() => {
      (ctx as any).apiVersion = 999;
    }).toThrow();
  });

  it('extension metadata cannot be mutated', () => {
    expect(() => {
      (ctx.extension as any).version = '999.0.0';
    }).toThrow();
  });

  it('manifest is the same frozen object from defineExtension', () => {
    // defineExtension freezes the manifest, and the context preserves that reference
    expect(ctx.extension.manifest).toBe(extension.manifest);
    expect(Object.isFrozen(ctx.extension.manifest)).toBe(true);
  });

  it('creative cannot be reassigned', () => {
    expect(() => {
      (ctx as any).creative = {};
    }).toThrow();
  });

  // ---- multiple contexts are independent -----------------------------------

  it('two contexts for different extensions have independent diagnostics', () => {
    const ext2 = defineExtension({
      manifest: {
        id: 'com.independent.ext' as any,
        version: '1.0.0',
        label: 'Independent',
        contributions: [],
      },
    });
    const ctx2 = createExtensionContext(ext2);

    ctx.services.diagnostics.report({
      severity: 'info',
      code: 'ctx1',
      message: 'From ctx1',
    });
    ctx2.services.diagnostics.report({
      severity: 'warning',
      code: 'ctx2',
      message: 'From ctx2',
    });

    expect(ctx.services.diagnostics.diagnostics).toHaveLength(1);
    expect(ctx.services.diagnostics.diagnostics[0].code).toBe('ctx1');
    expect(ctx2.services.diagnostics.diagnostics).toHaveLength(1);
    expect(ctx2.services.diagnostics.diagnostics[0].code).toBe('ctx2');
  });

  it('two contexts for different extensions have independent subscribers', () => {
    const ext2 = defineExtension({
      manifest: {
        id: 'com.independent2.ext' as any,
        version: '1.0.0',
        label: 'Independent2',
        contributions: [],
      },
    });
    const ctx2 = createExtensionContext(ext2);

    const received1: string[] = [];
    const received2: string[] = [];
    ctx.chrome.subscribe('toast', (p: any) => received1.push(p.message));
    ctx2.chrome.subscribe('toast', (p: any) => received2.push(p.message));

    ctx.chrome.toast('Only ctx1');
    expect(received1).toEqual(['Only ctx1']);
    expect(received2).toEqual([]);
  });
});

// ---------------------------------------------------------------------------
// createCreativeContextStubs — standalone
// ---------------------------------------------------------------------------

describe('createCreativeContextStubs', () => {
  it('returns a frozen object', () => {
    const stubs = createCreativeContextStubs();
    expect(Object.isFrozen(stubs)).toBe(true);
  });

  it('every member throws ExtensionNotImplementedError', () => {
    const stubs = createCreativeContextStubs();
    const members = Object.keys(CREATIVE_MEMBER_MILESTONE) as string[];
    for (const member of members) {
      expect(
        () => (stubs as Record<string, unknown>)[member],
        `creative.${member} should throw`,
      ).toThrow(ExtensionNotImplementedError);
    }
  });

  it('each member has the correct feature and milestone', () => {
    const stubs = createCreativeContextStubs();
    const members = Object.keys(CREATIVE_MEMBER_MILESTONE) as string[];
    for (const member of members) {
      try {
        (stubs as Record<string, unknown>)[member];
        // should not reach here
        expect(true).toBe(false);
      } catch (err) {
        expect(err).toBeInstanceOf(ExtensionNotImplementedError);
        const e = err as ExtensionNotImplementedError;
        expect(e.feature).toBe(member);
        expect(e.milestone).toBe(
          (CREATIVE_MEMBER_MILESTONE as Record<string, string>)[member],
        );
      }
    }
  });

  it('all 8 creative members are enumerable', () => {
    const stubs = createCreativeContextStubs();
    const keys = Object.keys(stubs).sort();
    expect(keys).toEqual([
      'assets',
      'export',
      'materials',
      'project',
      'sessions',
      'stage',
      'timeline',
      'writing',
    ]);
  });
});

// ---------------------------------------------------------------------------
// ExtensionNotImplementedError
// ---------------------------------------------------------------------------

describe('ExtensionNotImplementedError', () => {
  it('is an instance of Error', () => {
    const err = new ExtensionNotImplementedError('project', 'M2');
    expect(err).toBeInstanceOf(Error);
    expect(err).toBeInstanceOf(ExtensionNotImplementedError);
    expect(err.name).toBe('ExtensionNotImplementedError');
  });

  it('has feature and milestone properties', () => {
    const err = new ExtensionNotImplementedError('timeline', 'M3');
    expect(err.feature).toBe('timeline');
    expect(err.milestone).toBe('M3');
  });

  it('has a descriptive message', () => {
    const err = new ExtensionNotImplementedError('assets', 'M6');
    expect(err.message).toBe(
      'ctx.creative.assets is not implemented until M6.',
    );
  });
});

// ---------------------------------------------------------------------------
// CREATIVE_MEMBER_MILESTONE
// ---------------------------------------------------------------------------

describe('CREATIVE_MEMBER_MILESTONE', () => {
  it('has entries for all 8 creative members', () => {
    const keys = Object.keys(CREATIVE_MEMBER_MILESTONE).sort();
    expect(keys).toEqual([
      'assets',
      'export',
      'materials',
      'project',
      'sessions',
      'stage',
      'timeline',
      'writing',
    ]);
  });

  it('all values are milestone strings starting with M', () => {
    for (const milestone of Object.values(CREATIVE_MEMBER_MILESTONE)) {
      expect(milestone).toMatch(/^M\d+$/);
    }
  });
});

// ---------------------------------------------------------------------------
// Helper
// ---------------------------------------------------------------------------

function validManifest(): ExtensionManifest {
  return {
    id: 'com.example.test' as any,
    version: '1.0.0',
    label: 'Test Extension',
    contributions: [],
  };
}
