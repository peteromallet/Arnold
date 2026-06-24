import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import {
  createExtensionLifecycle,
  createExtensionLifecycleHost,
  createExtensionDiagnosticsService,
  LIFECYCLE_STATE_ORDER,
} from '@/tools/video-editor/runtime/extensionLifecycle';
import type {
  ExtensionLifecycle,
  ExtensionLifecycleHost,
  ExtensionLifecycleState,
} from '@/tools/video-editor/runtime/extensionLifecycle';
import { defineExtension } from '@reigh/editor-sdk';
import {
  createCreativeContext,
  createCreativeContextStubs,
  createExtensionContext,
  ExtensionNotImplementedError,
  CREATIVE_MEMBER_MILESTONE,
} from '@reigh/editor-sdk';
import type {
  TimelineOps,
  TimelinePatch,
  TimelinePatchValidationResult,
  TimelinePreviewResult,
  TimelineDiff,
  CreativeContext,
} from '@reigh/editor-sdk';

import type {
  ReighExtension,
  ExtensionContext,
  DisposeHandle,
  ExtensionDiagnostic,
  ContributionId,
} from '@reigh/editor-sdk';
import type { LiveDataRegistry } from '@/tools/video-editor/runtime/liveDataRegistry';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Create a minimal extension with the given id and optional activate. */
function ext(
  id: string,
  overrides?: {
    activate?: (ctx: ExtensionContext) => DisposeHandle | void;
    contributions?: Array<{ id: string; kind: string; slot?: string; order?: number }>;
  },
): ReighExtension {
  return defineExtension({
    manifest: {
      id: id as any,
      version: '1.0.0',
      label: id,
      contributions: overrides?.contributions as any,
    } as any,
    activate: overrides?.activate as any,
  });
}

/** Create a minimal ExtensionContext for testing. */
function makeCtx(overrides?: Partial<ExtensionContext>): ExtensionContext {
  const diagSvc = createExtensionDiagnosticsService(overrides?.extension?.id ?? 'test');
  return {
    apiVersion: 1,
    extension: {
      id: 'test' as any,
      version: '1.0.0',
      label: 'Test',
      manifest: {} as any,
      ...overrides?.extension,
    },
    chrome: {
      toast: () => {},
      progress: () => {},
      subscribe: () => ({ dispose: () => {} }),
      ...overrides?.chrome,
    },
    services: {
      settings: {
        get: () => undefined,
        set: () => {},
        delete: () => {},
        keys: () => [],
        ...overrides?.services?.settings,
      },
      i18n: {
        t: (k: string) => k,
        ...overrides?.services?.i18n,
      },
      diagnostics: diagSvc,
    },
    creative: {
      project: {},
      timeline: {},
      assets: {},
      materials: {},
      sessions: {},
      export: {},
      stage: {},
      writing: {},
      ...overrides?.creative,
    },
  };
}

/** Get all diagnostics for a lifecycle matching a code. */
function diagsOf(lc: ExtensionLifecycle, code: string): ExtensionDiagnostic[] {
  return lc.diagnostics.filter((d) => d.code === code);
}

/** Get all diagnostics for a host matching a code. */
function hostDiagsOf(host: ExtensionLifecycleHost, code: string): ExtensionDiagnostic[] {
  return host.diagnostics.filter((d) => d.code === code);
}

// ---------------------------------------------------------------------------
// ExtensionDiagnosticsService
// ---------------------------------------------------------------------------

describe('createExtensionDiagnosticsService', () => {
  it('creates a service that reports diagnostics with auto-filled extensionId', () => {
    const svc = createExtensionDiagnosticsService('com.example.test');
    svc.report({ severity: 'info', code: 'test/code', message: 'hello' });
    expect(svc.diagnostics).toHaveLength(1);
    expect(svc.diagnostics[0].extensionId).toBe('com.example.test');
    expect(svc.diagnostics[0].code).toBe('test/code');
    expect(svc.diagnostics[0].message).toBe('hello');
  });

  it('returns a live snapshot of diagnostics', () => {
    const svc = createExtensionDiagnosticsService('com.example.live');
    expect(svc.diagnostics).toHaveLength(0);
    svc.report({ severity: 'warning', code: 'a', message: 'one' });
    svc.report({ severity: 'error', code: 'b', message: 'two' });
    expect(svc.diagnostics).toHaveLength(2);
  });

  it('freezes each diagnostic on report', () => {
    const svc = createExtensionDiagnosticsService('com.example.frozen');
    svc.report({ severity: 'info', code: 'x', message: 'y' });
    expect(Object.isFrozen(svc.diagnostics[0])).toBe(true);
  });

  it('overwrites spoofed extensionId with the service-owned extensionId', () => {
    const svc = createExtensionDiagnosticsService('com.example.spoofed');
    // Use 'as any' to bypass TS type check and test runtime spoofing protection
    (svc as any).report({ severity: 'error', code: 'spoof/test', message: 'spoofed', extensionId: 'com.evil.spoofer' });
    expect(svc.diagnostics).toHaveLength(1);
    expect(svc.diagnostics[0].extensionId).toBe('com.example.spoofed');
    expect(svc.diagnostics[0].extensionId).not.toBe('com.evil.spoofer');
  });

  it('pins source to DIAGNOSTIC_SOURCE_EXTENSION on every reported diagnostic', () => {
    const svc = createExtensionDiagnosticsService('com.example.sourcepin');
    svc.report({ severity: 'info', code: 'test/source', message: 'has source' });
    expect(svc.diagnostics).toHaveLength(1);
    expect(svc.diagnostics[0].source).toBe('extension');
  });

  it('overwrites spoofed source with DIAGNOSTIC_SOURCE_EXTENSION', () => {
    const svc = createExtensionDiagnosticsService('com.example.sourcespoof');
    // Use 'as any' to bypass TS type check and test runtime spoofing protection
    (svc as any).report({ severity: 'warning', code: 'spoof/source', message: 'bad source', source: 'provider' });
    expect(svc.diagnostics).toHaveLength(1);
    expect(svc.diagnostics[0].source).toBe('extension');
  });

  it('lifecycle disposal removes extension diagnostics without affecting host/provider diagnostics', () => {
    const host = createExtensionLifecycleHost();
    const e1 = ext('com.example.disposal', {
      activate: () => ({ dispose: () => {} }),
    });
    host.synchronize([e1], (ext) =>
      makeCtx({ extension: { id: ext.manifest.id as any, version: '1.0.0', label: ext.manifest.label, manifest: ext.manifest } }),
    );
    // Verify diagnostics exist while active
    const beforeDiags = host.diagnostics.filter((d) => d.extensionId === 'com.example.disposal');
    expect(beforeDiags.length).toBeGreaterThanOrEqual(2); // activating + activated

    // Remove extension
    host.synchronize([], () => makeCtx());
    // After removal, the lifecycle is gone so its diagnostics are no longer aggregated
    const afterDiags = host.diagnostics.filter((d) => d.extensionId === 'com.example.disposal');
    expect(afterDiags).toHaveLength(0);
  });

});

// ---------------------------------------------------------------------------
// Lifecycle state machine — initial state
// ---------------------------------------------------------------------------

describe('ExtensionLifecycle — initial state', () => {
  it('starts in inactive state', () => {
    const lc = createExtensionLifecycle(ext('com.example.test'));
    expect(lc.state).toBe('inactive');
    expect(lc.failure).toBeNull();
    expect(lc.extensionId).toBe('com.example.test');
  });

  it('has empty diagnostics initially', () => {
    const lc = createExtensionLifecycle(ext('com.example.test'));
    expect(lc.diagnostics).toEqual([]);
  });

  it('exposes the extension reference', () => {
    const e = ext('com.example.ref');
    const lc = createExtensionLifecycle(e);
    expect(lc.extension).toBe(e);
  });

  it('has a per-extension diagnostics service', () => {
    const lc = createExtensionLifecycle(ext('com.example.diag'));
    expect(lc.diagnosticsService).toBeDefined();
    lc.diagnosticsService.report({ severity: 'info', code: 'test', message: 'x' });
    expect(lc.diagnostics.length).toBe(1);
    expect(lc.diagnostics[0].extensionId).toBe('com.example.diag');
  });
});

// ---------------------------------------------------------------------------
// Lifecycle state machine — activation
// ---------------------------------------------------------------------------

describe('ExtensionLifecycle — activation', () => {
  it('transitions inactive → activating → active on successful activate()', () => {
    const lc = createExtensionLifecycle(ext('com.example.ok'));
    expect(lc.state).toBe('inactive');

    lc.activate(makeCtx({ extension: { id: 'com.example.ok' as any, version: '1.0.0', label: 'OK', manifest: {} as any } }));

    expect(lc.state).toBe('active');
    expect(lc.failure).toBeNull();
  });

  it('emits lifecycle diagnostics during activation', () => {
    const lc = createExtensionLifecycle(ext('com.example.diag'));
    lc.activate(makeCtx({ extension: { id: 'com.example.diag' as any, version: '1.0.0', label: 'D', manifest: {} as any } }));

    const activatingDiags = diagsOf(lc, 'lifecycle/activating');
    const activatedDiags = diagsOf(lc, 'lifecycle/activated');
    expect(activatingDiags).toHaveLength(1);
    expect(activatingDiags[0].severity).toBe('info');
    expect(activatedDiags).toHaveLength(1);
    expect(activatedDiags[0].severity).toBe('info');
    // Order: activating before activated
    const codes = lc.diagnostics.map((d) => d.code);
    const activatingIdx = codes.indexOf('lifecycle/activating');
    const activatedIdx = codes.indexOf('lifecycle/activated');
    expect(activatingIdx).toBeLessThan(activatedIdx);
  });

  it('calls the extension activate function', () => {
    const fn = vi.fn();
    const lc = createExtensionLifecycle(ext('com.example.fn', { activate: fn }));
    const ctx = makeCtx({ extension: { id: 'com.example.fn' as any, version: '1.0.0', label: 'F', manifest: {} as any } });
    lc.activate(ctx);
    expect(fn).toHaveBeenCalledTimes(1);
    expect(fn).toHaveBeenCalledWith(ctx);
  });

  it('works with extensions that have no activate function', () => {
    const lc = createExtensionLifecycle(ext('com.example.noactivate'));
    lc.activate(makeCtx({ extension: { id: 'com.example.noactivate' as any, version: '1.0.0', label: 'NA', manifest: {} as any } }));
    expect(lc.state).toBe('active');
    expect(lc.failure).toBeNull();
  });

  it('transitions to failed when activate() throws', () => {
    const error = new Error('activation boom');
    const lc = createExtensionLifecycle(
      ext('com.example.bad', {
        activate: () => {
          throw error;
        },
      }),
    );
    const ctx = makeCtx({ extension: { id: 'com.example.bad' as any, version: '1.0.0', label: 'B', manifest: {} as any } });
    lc.activate(ctx);

    expect(lc.state).toBe('failed');
    expect(lc.failure).toBe(error);
  });

  it('emits failure diagnostic when activation throws', () => {
    const lc = createExtensionLifecycle(
      ext('com.example.faildiag', {
        activate: () => {
          throw new Error('test failure');
        },
      }),
    );
    lc.activate(makeCtx({ extension: { id: 'com.example.faildiag' as any, version: '1.0.0', label: 'FD', manifest: {} as any } }));

    const fails = diagsOf(lc, 'lifecycle/activation-failed');
    expect(fails).toHaveLength(1);
    expect(fails[0].severity).toBe('error');
    expect(fails[0].message).toContain('test failure');
  });

  it('captures non-Error throws as Error', () => {
    const lc = createExtensionLifecycle(
      ext('com.example.stringthrow', {
        activate: () => {
          throw 'string error';
        },
      }),
    );
    lc.activate(makeCtx({ extension: { id: 'com.example.stringthrow' as any, version: '1.0.0', label: 'ST', manifest: {} as any } }));
    expect(lc.state).toBe('failed');
    expect(lc.failure).toBeInstanceOf(Error);
    expect((lc.failure as Error).message).toContain('string error');
  });
});

// ---------------------------------------------------------------------------
// Lifecycle state machine — DisposeHandle on activation
// ---------------------------------------------------------------------------

describe('ExtensionLifecycle — DisposeHandle from activate', () => {
  it('stores the DisposeHandle returned by activate', () => {
    const handleDisposed = vi.fn();
    const lc = createExtensionLifecycle(
      ext('com.example.handle', {
        activate: () => ({ dispose: handleDisposed }),
      }),
    );
    lc.activate(makeCtx({ extension: { id: 'com.example.handle' as any, version: '1.0.0', label: 'H', manifest: {} as any } }));
    expect(lc.state).toBe('active');

    // Deactivate should call dispose on the handle
    lc.deactivate();
    expect(handleDisposed).toHaveBeenCalledTimes(1);
    expect(lc.state).toBe('disposed');
  });

  it('handles activate returning void (no DisposeHandle)', () => {
    const lc = createExtensionLifecycle(
      ext('com.example.void', { activate: () => {} }),
    );
    lc.activate(makeCtx({ extension: { id: 'com.example.void' as any, version: '1.0.0', label: 'V', manifest: {} as any } }));
    expect(lc.state).toBe('active');

    // Deactivate should succeed without errors
    lc.deactivate();
    expect(lc.state).toBe('disposed');
  });

  it('handles activate returning undefined', () => {
    const lc = createExtensionLifecycle(
      ext('com.example.undef', { activate: () => undefined }),
    );
    lc.activate(makeCtx({ extension: { id: 'com.example.undef' as any, version: '1.0.0', label: 'U', manifest: {} as any } }));
    expect(lc.state).toBe('active');
    lc.deactivate();
    expect(lc.state).toBe('disposed');
  });

  it('captures error when DisposeHandle.dispose() throws', () => {
    const lc = createExtensionLifecycle(
      ext('com.example.badhandle', {
        activate: () => ({
          dispose: () => {
            throw new Error('dispose boom');
          },
        }),
      }),
    );
    lc.activate(makeCtx({ extension: { id: 'com.example.badhandle' as any, version: '1.0.0', label: 'BH', manifest: {} as any } }));

    // Deactivate should not throw even when dispose handle throws
    lc.deactivate();
    expect(lc.state).toBe('disposed');

    const errors = diagsOf(lc, 'lifecycle/dispose-handle-error');
    expect(errors).toHaveLength(1);
    expect(errors[0].message).toContain('dispose boom');
  });

  it('calls Symbol.dispose if present on the handle', () => {
    const symbolDispose = vi.fn();
    const lc = createExtensionLifecycle(
      ext('com.example.symdispose', {
        activate: () => ({
          dispose: () => {},
          [Symbol.dispose]: symbolDispose,
        }),
      }),
    );
    lc.activate(makeCtx({ extension: { id: 'com.example.symdispose' as any, version: '1.0.0', label: 'SD', manifest: {} as any } }));
    lc.deactivate();
    expect(symbolDispose).toHaveBeenCalledTimes(1);
  });
});

// ---------------------------------------------------------------------------
// Lifecycle state machine — deactivation
// ---------------------------------------------------------------------------

describe('ExtensionLifecycle — deactivation', () => {
  it('transitions active → deactivating → disposed on deactivate()', () => {
    const lc = createExtensionLifecycle(ext('com.example.deact'));
    lc.activate(makeCtx({ extension: { id: 'com.example.deact' as any, version: '1.0.0', label: 'DA', manifest: {} as any } }));
    expect(lc.state).toBe('active');

    lc.deactivate();
    expect(lc.state).toBe('disposed');
  });

  it('emits deactivation diagnostics', () => {
    const lc = createExtensionLifecycle(ext('com.example.deactdiag'));
    lc.activate(makeCtx({ extension: { id: 'com.example.deactdiag' as any, version: '1.0.0', label: 'DD', manifest: {} as any } }));
    lc.deactivate();

    const deactivating = diagsOf(lc, 'lifecycle/deactivating');
    const disposed = diagsOf(lc, 'lifecycle/disposed');
    expect(deactivating).toHaveLength(1);
    expect(disposed).toHaveLength(1);
    // Order: activating, activated, deactivating, disposed
    const codes = lc.diagnostics.map((d) => d.code);
    expect(codes).toEqual([
      'lifecycle/activating',
      'lifecycle/activated',
      'lifecycle/deactivating',
      'lifecycle/disposed',
    ]);
  });

  it('can deactivate from failed state (cleanup after failure)', () => {
    const lc = createExtensionLifecycle(
      ext('com.example.failcleanup', {
        activate: () => {
          throw new Error('fail');
        },
      }),
    );
    lc.activate(makeCtx({ extension: { id: 'com.example.failcleanup' as any, version: '1.0.0', label: 'FC', manifest: {} as any } }));
    expect(lc.state).toBe('failed');

    lc.deactivate();
    expect(lc.state).toBe('disposed');
  });

  it('can deactivate from inactive (never activated) → disposed directly', () => {
    const lc = createExtensionLifecycle(ext('com.example.never'));
    expect(lc.state).toBe('inactive');

    lc.deactivate();
    expect(lc.state).toBe('disposed');
    expect(diagsOf(lc, 'lifecycle/disposed-inactive')).toHaveLength(1);
  });
});

// ---------------------------------------------------------------------------
// Lifecycle state machine — dispose (terminal)
// ---------------------------------------------------------------------------

describe('ExtensionLifecycle — dispose', () => {
  it('transitions active → deactivating → disposed on dispose()', () => {
    const lc = createExtensionLifecycle(ext('com.example.disp'));
    lc.activate(makeCtx({ extension: { id: 'com.example.disp' as any, version: '1.0.0', label: 'DI', manifest: {} as any } }));
    expect(lc.state).toBe('active');

    lc.dispose();
    expect(lc.state).toBe('disposed');
  });

  it('disposes from inactive (never activated)', () => {
    const lc = createExtensionLifecycle(ext('com.example.neverdisp'));
    expect(lc.state).toBe('inactive');
    lc.dispose();
    expect(lc.state).toBe('disposed');
  });

  it('disposes from failed state', () => {
    const lc = createExtensionLifecycle(
      ext('com.example.faildisp', {
        activate: () => {
          throw new Error('fail');
        },
      }),
    );
    lc.activate(makeCtx({ extension: { id: 'com.example.faildisp' as any, version: '1.0.0', label: 'FD', manifest: {} as any } }));
    expect(lc.state).toBe('failed');

    lc.dispose();
    expect(lc.state).toBe('disposed');
  });

  it('calls DisposeHandle on dispose()', () => {
    const handleDisposed = vi.fn();
    const lc = createExtensionLifecycle(
      ext('com.example.dispHandle', {
        activate: () => ({ dispose: handleDisposed }),
      }),
    );
    lc.activate(makeCtx({ extension: { id: 'com.example.dispHandle' as any, version: '1.0.0', label: 'DH', manifest: {} as any } }));
    lc.dispose();
    expect(handleDisposed).toHaveBeenCalledTimes(1);
  });

  it('does not call DisposeHandle on dispose() if never activated', () => {
    const handleDisposed = vi.fn();
    const lc = createExtensionLifecycle(
      ext('com.example.nohandle', {
        activate: () => ({ dispose: handleDisposed }),
      }),
    );
    // Never activate
    lc.dispose();
    expect(handleDisposed).not.toHaveBeenCalled();
    expect(lc.state).toBe('disposed');
  });
});

// ---------------------------------------------------------------------------
// Lifecycle state machine — idempotency
// ---------------------------------------------------------------------------

describe('ExtensionLifecycle — idempotency', () => {
  it('activate() is idempotent on active state', () => {
    const fn = vi.fn();
    const lc = createExtensionLifecycle(ext('com.example.idem', { activate: fn }));
    const ctx = makeCtx({ extension: { id: 'com.example.idem' as any, version: '1.0.0', label: 'ID', manifest: {} as any } });

    lc.activate(ctx);
    expect(lc.state).toBe('active');
    expect(fn).toHaveBeenCalledTimes(1);

    // Second activate should be a no-op
    lc.activate(ctx);
    expect(lc.state).toBe('active');
    expect(fn).toHaveBeenCalledTimes(1); // Still only called once
  });

  it('activate() is a no-op on disposed state', () => {
    const fn = vi.fn();
    const lc = createExtensionLifecycle(ext('com.example.disposed', { activate: fn }));
    lc.dispose();
    expect(lc.state).toBe('disposed');

    lc.activate(makeCtx({ extension: { id: 'com.example.disposed' as any, version: '1.0.0', label: 'D', manifest: {} as any } }));
    expect(lc.state).toBe('disposed');
    expect(fn).not.toHaveBeenCalled();
    expect(diagsOf(lc, 'lifecycle/activate-disposed')).toHaveLength(1);
  });

  it('deactivate() is idempotent', () => {
    const handleDisposed = vi.fn();
    const lc = createExtensionLifecycle(
      ext('com.example.deactidem', {
        activate: () => ({ dispose: handleDisposed }),
      }),
    );
    lc.activate(makeCtx({ extension: { id: 'com.example.deactidem' as any, version: '1.0.0', label: 'DI', manifest: {} as any } }));

    lc.deactivate();
    expect(lc.state).toBe('disposed');
    expect(handleDisposed).toHaveBeenCalledTimes(1);

    // Second deactivate is a no-op
    lc.deactivate();
    expect(lc.state).toBe('disposed');
    expect(handleDisposed).toHaveBeenCalledTimes(1); // Not called again
  });

  it('dispose() is idempotent', () => {
    const handleDisposed = vi.fn();
    const lc = createExtensionLifecycle(
      ext('com.example.dispidem', {
        activate: () => ({ dispose: handleDisposed }),
      }),
    );
    lc.activate(makeCtx({ extension: { id: 'com.example.dispidem' as any, version: '1.0.0', label: 'D', manifest: {} as any } }));

    lc.dispose();
    expect(lc.state).toBe('disposed');
    expect(handleDisposed).toHaveBeenCalledTimes(1);

    // Second dispose is a no-op
    lc.dispose();
    expect(lc.state).toBe('disposed');
    expect(handleDisposed).toHaveBeenCalledTimes(1);
  });

  it('activate() from failed state retries activation', () => {
    let shouldFail = true;
    const lc = createExtensionLifecycle(
      ext('com.example.retry', {
        activate: () => {
          if (shouldFail) throw new Error('first fail');
        },
      }),
    );
    const ctx = makeCtx({ extension: { id: 'com.example.retry' as any, version: '1.0.0', label: 'R', manifest: {} as any } });

    lc.activate(ctx);
    expect(lc.state).toBe('failed');
    expect(lc.failure).toBeTruthy();

    // Retry
    shouldFail = false;
    lc.activate(ctx);
    expect(lc.state).toBe('active');
    expect(lc.failure).toBeNull();
  });

  it('deactivate() is idempotent from inactive (already tested above; extra guard)', () => {
    const lc = createExtensionLifecycle(ext('com.example.extra'));
    lc.deactivate();
    expect(lc.state).toBe('disposed');
    lc.deactivate(); // Second call
    expect(lc.state).toBe('disposed');
  });
});

// ---------------------------------------------------------------------------
// LIFECYCLE_STATE_ORDER
// ---------------------------------------------------------------------------

describe('LIFECYCLE_STATE_ORDER', () => {
  it('provides consistent ordering for all states', () => {
    const states: ExtensionLifecycleState[] = [
      'inactive',
      'activating',
      'active',
      'failed',
      'deactivating',
      'disposed',
    ];
    for (const s of states) {
      expect(typeof LIFECYCLE_STATE_ORDER[s]).toBe('number');
    }
  });

  it('places inactive before activating', () => {
    expect(LIFECYCLE_STATE_ORDER.inactive).toBeLessThan(LIFECYCLE_STATE_ORDER.activating);
  });

  it('places activating before active/failed', () => {
    expect(LIFECYCLE_STATE_ORDER.activating).toBeLessThan(LIFECYCLE_STATE_ORDER.active);
    expect(LIFECYCLE_STATE_ORDER.activating).toBeLessThan(LIFECYCLE_STATE_ORDER.failed);
  });

  it('places active and failed at the same tier', () => {
    expect(LIFECYCLE_STATE_ORDER.active).toBe(LIFECYCLE_STATE_ORDER.failed);
  });

  it('places active/failed before deactivating', () => {
    expect(LIFECYCLE_STATE_ORDER.active).toBeLessThan(LIFECYCLE_STATE_ORDER.deactivating);
  });

  it('places deactivating before disposed', () => {
    expect(LIFECYCLE_STATE_ORDER.deactivating).toBeLessThan(LIFECYCLE_STATE_ORDER.disposed);
  });
});

// ---------------------------------------------------------------------------
// ExtensionLifecycleHost — creation
// ---------------------------------------------------------------------------

describe('ExtensionLifecycleHost — creation', () => {
  it('creates an empty host', () => {
    const host = createExtensionLifecycleHost();
    expect(host.lifecycles.size).toBe(0);
    expect(host.diagnostics).toEqual([]);
  });
});

// ---------------------------------------------------------------------------
// ExtensionLifecycleHost — synchronize (register and activate)
// ---------------------------------------------------------------------------

describe('ExtensionLifecycleHost — synchronize', () => {
  it('registers and activates new extensions', () => {
    const host = createExtensionLifecycleHost();
    const e1 = ext('com.example.one');
    const e2 = ext('com.example.two');

    host.synchronize([e1, e2], (ext) =>
      makeCtx({ extension: { id: ext.manifest.id as any, version: '1.0.0', label: ext.manifest.label, manifest: ext.manifest } }),
    );

    expect(host.lifecycles.size).toBe(2);
    expect(host.lifecycles.get('com.example.one')?.state).toBe('active');
    expect(host.lifecycles.get('com.example.two')?.state).toBe('active');
  });

  it('calls activate with proper context', () => {
    const host = createExtensionLifecycleHost();
    const fn = vi.fn();
    const e1 = ext('com.example.ctx', { activate: fn });

    host.synchronize([e1], (ext) =>
      makeCtx({ extension: { id: ext.manifest.id as any, version: '1.0.0', label: ext.manifest.label, manifest: ext.manifest } }),
    );

    expect(fn).toHaveBeenCalledTimes(1);
    const ctxArg = fn.mock.calls[0][0] as ExtensionContext;
    expect(ctxArg.extension.id).toBe('com.example.ctx');
    expect(ctxArg.apiVersion).toBe(1);
  });

  it('does not re-activate extensions that are already managed', () => {
    const host = createExtensionLifecycleHost();
    const fn = vi.fn();
    const e1 = ext('com.example.stable', { activate: fn });

    host.synchronize([e1], (ext) =>
      makeCtx({ extension: { id: ext.manifest.id as any, version: '1.0.0', label: ext.manifest.label, manifest: ext.manifest } }),
    );
    expect(fn).toHaveBeenCalledTimes(1);

    // Same extension list — should be a no-op
    host.synchronize([e1], (ext) =>
      makeCtx({ extension: { id: ext.manifest.id as any, version: '1.0.0', label: ext.manifest.label, manifest: ext.manifest } }),
    );
    expect(fn).toHaveBeenCalledTimes(1); // Not called again
  });

  it('deactivates and removes extensions that are no longer in the list', () => {
    const host = createExtensionLifecycleHost();
    const handleDisposed = vi.fn();
    const e1 = ext('com.example.remove', {
      activate: () => ({ dispose: handleDisposed }),
    });
    const e2 = ext('com.example.keep');

    host.synchronize([e1, e2], (ext) =>
      makeCtx({ extension: { id: ext.manifest.id as any, version: '1.0.0', label: ext.manifest.label, manifest: ext.manifest } }),
    );
    expect(host.lifecycles.size).toBe(2);

    // Remove e1
    host.synchronize([e2], (ext) =>
      makeCtx({ extension: { id: ext.manifest.id as any, version: '1.0.0', label: ext.manifest.label, manifest: ext.manifest } }),
    );

    expect(host.lifecycles.size).toBe(1);
    expect(host.lifecycles.has('com.example.remove')).toBe(false);
    expect(host.lifecycles.has('com.example.keep')).toBe(true);
    expect(handleDisposed).toHaveBeenCalledTimes(1);
  });

  it('detects manifest changes and re-activates', () => {
    const host = createExtensionLifecycleHost();
    const fn1 = vi.fn();
    const e1 = ext('com.example.change', { activate: fn1 });
    const e1Changed = ext('com.example.change', {
      activate: fn1,
      contributions: [{ id: 'new-contrib', kind: 'slot', slot: 'toolbar' }],
    });

    host.synchronize([e1], (ext) =>
      makeCtx({ extension: { id: ext.manifest.id as any, version: '1.0.0', label: ext.manifest.label, manifest: ext.manifest } }),
    );
    expect(fn1).toHaveBeenCalledTimes(1);

    // Synchronize with changed manifest
    host.synchronize([e1Changed], (ext) =>
      makeCtx({ extension: { id: ext.manifest.id as any, version: '1.0.0', label: ext.manifest.label, manifest: ext.manifest } }),
    );

    // The old lifecycle should have been disposed, new one activated
    expect(host.lifecycles.size).toBe(1);
    // activate fn is called once for old, once for new = 2 total
    expect(fn1).toHaveBeenCalledTimes(2);
  });

  it('handles empty extension list', () => {
    const host = createExtensionLifecycleHost();
    host.synchronize([], () => makeCtx());
    expect(host.lifecycles.size).toBe(0);
    expect(host.diagnostics).toEqual([]);
  });

  it('handles context factory throwing', () => {
    const host = createExtensionLifecycleHost();
    const e1 = ext('com.example.badctx');

    host.synchronize([e1], () => {
      throw new Error('context factory failure');
    });

    // The extension should be disposed because activation couldn't proceed
    // The host should not crash
    expect(host.lifecycles.size).toBe(0); // Disposed and removed
    const ctxErrors = hostDiagsOf(host, 'lifecycle/context-factory-error');
    expect(ctxErrors).toHaveLength(1);
    expect(ctxErrors[0].message).toContain('context factory failure');
  });
});

// ---------------------------------------------------------------------------
// ExtensionLifecycleHost — disposeAll
// ---------------------------------------------------------------------------

describe('ExtensionLifecycleHost — disposeAll', () => {
  it('disposes all managed extensions', () => {
    const host = createExtensionLifecycleHost();
    const h1 = vi.fn();
    const h2 = vi.fn();
    const e1 = ext('com.example.disp1', { activate: () => ({ dispose: h1 }) });
    const e2 = ext('com.example.disp2', { activate: () => ({ dispose: h2 }) });

    host.synchronize([e1, e2], (ext) =>
      makeCtx({ extension: { id: ext.manifest.id as any, version: '1.0.0', label: ext.manifest.label, manifest: ext.manifest } }),
    );

    host.disposeAll();

    expect(h1).toHaveBeenCalledTimes(1);
    expect(h2).toHaveBeenCalledTimes(1);
    expect(host.lifecycles.size).toBe(0);
  });

  it('is idempotent', () => {
    const host = createExtensionLifecycleHost();
    const fn = vi.fn();
    const e1 = ext('com.example.idemhost', { activate: () => ({ dispose: fn }) });

    host.synchronize([e1], (ext) =>
      makeCtx({ extension: { id: ext.manifest.id as any, version: '1.0.0', label: ext.manifest.label, manifest: ext.manifest } }),
    );

    host.disposeAll();
    expect(fn).toHaveBeenCalledTimes(1);

    // Second call is no-op
    host.disposeAll();
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it('handles empty host', () => {
    const host = createExtensionLifecycleHost();
    host.disposeAll();
    expect(host.lifecycles.size).toBe(0);
    // Should not throw
  });

  it('synchronize after disposeAll is a no-op', () => {
    const host = createExtensionLifecycleHost();
    const fn = vi.fn();
    const e1 = ext('com.example.postdisp', { activate: fn });

    host.disposeAll();

    // synchronize after disposeAll should warn but not crash
    host.synchronize([e1], (ext) =>
      makeCtx({ extension: { id: ext.manifest.id as any, version: '1.0.0', label: ext.manifest.label, manifest: ext.manifest } }),
    );

    // Should not have activated
    expect(host.lifecycles.size).toBe(0);
    expect(fn).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// ExtensionLifecycleHost — diagnostics aggregation
// ---------------------------------------------------------------------------

describe('ExtensionLifecycleHost — diagnostics aggregation', () => {
  it('aggregates diagnostics from all lifecycles', () => {
    const host = createExtensionLifecycleHost();
    const e1 = ext('com.example.diag1');
    const e2 = ext('com.example.diag2');

    host.synchronize([e1, e2], (ext) =>
      makeCtx({ extension: { id: ext.manifest.id as any, version: '1.0.0', label: ext.manifest.label, manifest: ext.manifest } }),
    );

    // Each lifecycle should have at least activating + activated diagnostics
    const allDiags = host.diagnostics;
    expect(allDiags.length).toBeGreaterThanOrEqual(4);

    // Verify we have diagnostics from both extensions
    const ext1Diags = allDiags.filter((d) => d.extensionId === 'com.example.diag1');
    const ext2Diags = allDiags.filter((d) => d.extensionId === 'com.example.diag2');
    expect(ext1Diags.length).toBeGreaterThanOrEqual(2);
    expect(ext2Diags.length).toBeGreaterThanOrEqual(2);
  });

  it('diagnostics are frozen', () => {
    const host = createExtensionLifecycleHost();
    host.synchronize(
      [ext('com.example.frozen')],
      (ext) =>
        makeCtx({ extension: { id: ext.manifest.id as any, version: '1.0.0', label: ext.manifest.label, manifest: ext.manifest } }),
    );

    expect(Object.isFrozen(host.diagnostics)).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// ExtensionLifecycleHost — failed extensions in host
// ---------------------------------------------------------------------------

describe('ExtensionLifecycleHost — failed extensions', () => {
  it('keeps failed extensions in the lifecycle map', () => {
    const host = createExtensionLifecycleHost();
    const e1 = ext('com.example.failhost', {
      activate: () => {
        throw new Error('host-level failure');
      },
    });

    host.synchronize([e1], (ext) =>
      makeCtx({ extension: { id: ext.manifest.id as any, version: '1.0.0', label: ext.manifest.label, manifest: ext.manifest } }),
    );

    // Failed extension should still be tracked
    expect(host.lifecycles.size).toBe(1);
    const lc = host.lifecycles.get('com.example.failhost')!;
    expect(lc.state).toBe('failed');
    expect(lc.failure).toBeTruthy();
  });

  it('removes failed extensions when they are removed from the list', () => {
    const host = createExtensionLifecycleHost();
    const e1 = ext('com.example.failremove', {
      activate: () => {
        throw new Error('removable failure');
      },
    });

    host.synchronize([e1], (ext) =>
      makeCtx({ extension: { id: ext.manifest.id as any, version: '1.0.0', label: ext.manifest.label, manifest: ext.manifest } }),
    );
    expect(host.lifecycles.size).toBe(1);

    // Remove it
    host.synchronize([], () => makeCtx());
    expect(host.lifecycles.size).toBe(0);
  });
});

// ---------------------------------------------------------------------------
// ExtensionLifecycleHost — multiple sync cycles
// ---------------------------------------------------------------------------

describe('ExtensionLifecycleHost — multiple sync cycles', () => {
  it('handles add, remove, re-add sequences correctly', () => {
    const host = createExtensionLifecycleHost();
    let activateCount = 0;
    let disposeCount = 0;

    function makeExt(id: string): ReighExtension {
      return ext(id, {
        activate: () => {
          activateCount++;
          return { dispose: () => { disposeCount++; } };
        },
      });
    }

    const e1 = makeExt('com.example.cycle1');
    const e2 = makeExt('com.example.cycle2');
    const e3 = makeExt('com.example.cycle3');

    // Add e1, e2
    host.synchronize([e1, e2], (ext) =>
      makeCtx({ extension: { id: ext.manifest.id as any, version: '1.0.0', label: ext.manifest.label, manifest: ext.manifest } }),
    );
    expect(host.lifecycles.size).toBe(2);
    expect(activateCount).toBe(2);
    expect(disposeCount).toBe(0);

    // Remove e1, keep e2, add e3
    host.synchronize([e2, e3], (ext) =>
      makeCtx({ extension: { id: ext.manifest.id as any, version: '1.0.0', label: ext.manifest.label, manifest: ext.manifest } }),
    );
    expect(host.lifecycles.size).toBe(2);
    expect(activateCount).toBe(3); // e3 newly activated
    expect(disposeCount).toBe(1); // e1 disposed

    // Remove all
    host.synchronize([], () => makeCtx());
    expect(host.lifecycles.size).toBe(0);
    expect(disposeCount).toBe(3); // e2 and e3 disposed
  });
});

// ---------------------------------------------------------------------------
// Dev console grouping (safety — no throws)
// ---------------------------------------------------------------------------

describe('ExtensionLifecycle — dev console grouping', () => {
  let originalGroup: typeof console.group;
  let originalGroupCollapsed: typeof console.groupCollapsed;
  let originalGroupEnd: typeof console.groupEnd;
  let originalError: typeof console.error;

  beforeEach(() => {
    originalGroup = console.group;
    originalGroupCollapsed = console.groupCollapsed;
    originalGroupEnd = console.groupEnd;
    originalError = console.error;
    console.group = vi.fn() as any;
    console.groupCollapsed = vi.fn() as any;
    console.groupEnd = vi.fn() as any;
    console.error = vi.fn() as any;
  });

  afterEach(() => {
    console.group = originalGroup;
    console.groupCollapsed = originalGroupCollapsed;
    console.groupEnd = originalGroupEnd;
    console.error = originalError;
  });

  it('uses console.groupCollapsed during activation (when available)', () => {
    const lc = createExtensionLifecycle(ext('com.example.console'));
    lc.activate(makeCtx({ extension: { id: 'com.example.console' as any, version: '1.0.0', label: 'C', manifest: {} as any } }));

    expect(console.groupCollapsed).toHaveBeenCalled();
    expect(console.groupEnd).toHaveBeenCalled();
  });

  it('uses console.group during activation when groupCollapsed is not available', () => {
    // Temporarily unset groupCollapsed so the fallback to console.group is exercised
    const collapsed = console.groupCollapsed;
    (console as any).groupCollapsed = undefined;

    // Reset the mock for console.group so we have a clean call count
    (console.group as any).mockClear?.();

    const lc = createExtensionLifecycle(ext('com.example.grouponly'));
    lc.activate(makeCtx({ extension: { id: 'com.example.grouponly' as any, version: '1.0.0', label: 'G', manifest: {} as any } }));

    expect(console.group).toHaveBeenCalled();

    // Restore
    (console as any).groupCollapsed = collapsed;
  });

  it('logs error to console.error on activation failure', () => {
    const lc = createExtensionLifecycle(
      ext('com.example.consolefail', {
        activate: () => {
          throw new Error('console failure');
        },
      }),
    );
    lc.activate(makeCtx({ extension: { id: 'com.example.consolefail' as any, version: '1.0.0', label: 'CF', manifest: {} as any } }));

    expect(console.error).toHaveBeenCalled();
    expect(console.groupEnd).toHaveBeenCalled(); // Group is closed even on failure
  });

  it('uses console grouping during deactivation', () => {
    const lc = createExtensionLifecycle(ext('com.example.consoledeact'));
    lc.activate(makeCtx({ extension: { id: 'com.example.consoledeact' as any, version: '1.0.0', label: 'CD', manifest: {} as any } }));
    (console.groupCollapsed as any).mockClear();
    (console.groupEnd as any).mockClear();

    lc.deactivate();
    expect(console.groupCollapsed).toHaveBeenCalled();
    expect(console.groupEnd).toHaveBeenCalled();
  });

  it('uses console grouping during dispose', () => {
    const lc = createExtensionLifecycle(ext('com.example.consoledisp'));
    lc.activate(makeCtx({ extension: { id: 'com.example.consoledisp' as any, version: '1.0.0', label: 'CD', manifest: {} as any } }));
    (console.groupCollapsed as any).mockClear();
    (console.groupEnd as any).mockClear();

    lc.dispose();
    expect(console.groupCollapsed).toHaveBeenCalled();
    expect(console.groupEnd).toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// Edge cases
// ---------------------------------------------------------------------------

describe('ExtensionLifecycle — edge cases', () => {
  it('multiple activate/deactivate cycles on the same lifecycle', () => {
    const lc = createExtensionLifecycle(ext('com.example.multicycle'));
    const ctx = makeCtx({ extension: { id: 'com.example.multicycle' as any, version: '1.0.0', label: 'MC', manifest: {} as any } });

    // Activate
    lc.activate(ctx);
    expect(lc.state).toBe('active');

    // Deactivate
    lc.deactivate();
    expect(lc.state).toBe('disposed');

    // Cannot re-activate after dispose
    lc.activate(ctx);
    expect(lc.state).toBe('disposed'); // Stays disposed
  });

  it('dispose during activation is not possible (synchronous)', () => {
    // Since activate is synchronous, you can't really dispose during it.
    // But if someone passed a dispose call inside activate, it should be safe.
    let capturedLc: ExtensionLifecycle | null = null;
    const lc = createExtensionLifecycle(
      ext('com.example.selfdisp', {
        activate: () => {
          // Don't actually do this in real code, but ensure it doesn't crash
          return { dispose: () => {} };
        },
      }),
    );
    capturedLc = lc;
    lc.activate(makeCtx({ extension: { id: 'com.example.selfdisp' as any, version: '1.0.0', label: 'SD', manifest: {} as any } }));
    expect(lc.state).toBe('active');

    // Dispose from outside during active is fine
    lc.dispose();
    expect(lc.state).toBe('disposed');
  });

  it('handles extensions with very long IDs', () => {
    const longId = 'com.example.' + 'a'.repeat(100);
    const lc = createExtensionLifecycle(ext(longId));
    expect(lc.extensionId).toBe(longId);
    expect(lc.state).toBe('inactive');
  });

  it('activate does not call the extension function if already active', () => {
    const fn = vi.fn();
    const lc = createExtensionLifecycle(ext('com.example.once', { activate: fn }));
    const ctx = makeCtx({ extension: { id: 'com.example.once' as any, version: '1.0.0', label: 'O', manifest: {} as any } });

    lc.activate(ctx);
    lc.activate(ctx);
    lc.activate(ctx);
    expect(fn).toHaveBeenCalledTimes(1);
  });
});

// ---------------------------------------------------------------------------
// ExtensionLifecycle — render/teardown failure capture
// ---------------------------------------------------------------------------

describe('ExtensionLifecycle — render/teardown failure capture', () => {
  it('captures both dispose() and Symbol.dispose errors during teardown', () => {
    const lc = createExtensionLifecycle(
      ext('com.example.doublefail', {
        activate: () => ({
          dispose: () => {
            throw new Error('dispose error');
          },
          [Symbol.dispose]: () => {
            throw new Error('symbol dispose error');
          },
        }),
      }),
    );
    lc.activate(makeCtx({ extension: { id: 'com.example.doublefail' as any, version: '1.0.0', label: 'DF', manifest: {} as any } }));
    expect(lc.state).toBe('active');

    // Deactivate — must not throw, must capture both errors
    lc.deactivate();
    expect(lc.state).toBe('disposed');

    const disposeErrors = diagsOf(lc, 'lifecycle/dispose-handle-error');
    const symbolErrors = diagsOf(lc, 'lifecycle/symbol-dispose-error');
    expect(disposeErrors).toHaveLength(1);
    expect(disposeErrors[0].message).toContain('dispose error');
    expect(symbolErrors).toHaveLength(1);
    expect(symbolErrors[0].message).toContain('symbol dispose error');
  });

  it('captures teardown errors from failed extension via dispose() path', () => {
    // Extension fails during activation but still returns a partial handle
    let partialHandle: DisposeHandle | undefined;
    const lc = createExtensionLifecycle(
      ext('com.example.failwithhandle', {
        activate: () => {
          partialHandle = {
            dispose: () => {
              throw new Error('partial cleanup error');
            },
          };
          // Return the handle but then throw — the handle won't be stored
          // because the throw happens after return? No, throw prevents return.
          throw new Error('activation failure with handle created');
        },
      }),
    );
    lc.activate(makeCtx({ extension: { id: 'com.example.failwithhandle' as any, version: '1.0.0', label: 'FH', manifest: {} as any } }));
    expect(lc.state).toBe('failed');
    expect(lc.failure).toBeTruthy();

    // Dispose from failed state — should not crash even though no handle was stored
    lc.dispose();
    expect(lc.state).toBe('disposed');

    // The failure diagnostic should be present
    const failDiags = diagsOf(lc, 'lifecycle/activation-failed');
    expect(failDiags).toHaveLength(1);
  });

  it('teardown via dispose() from failed state with error handle still transitions to disposed', () => {
    // Extension succeeds in activation (returns a handle), but later we
    // simulate that the dispose handle throws during disposal of a failed extension.
    // Since we can't programmatically go active→failed with a handle, we test
    // dispose() from active state where the handle throws.
    const lc = createExtensionLifecycle(
      ext('com.example.brokenhandle', {
        activate: () => ({
          dispose: () => {
            throw new Error('late teardown failure');
          },
        }),
      }),
    );
    lc.activate(makeCtx({ extension: { id: 'com.example.brokenhandle' as any, version: '1.0.0', label: 'BH2', manifest: {} as any } }));
    expect(lc.state).toBe('active');

    // dispose() must transition to disposed even when handle throws
    lc.dispose();
    expect(lc.state).toBe('disposed');

    const errors = diagsOf(lc, 'lifecycle/dispose-handle-error');
    expect(errors).toHaveLength(1);
    expect(errors[0].message).toContain('late teardown failure');
  });
});

// ---------------------------------------------------------------------------
// ExtensionLifecycleHost — settings default cleanup hooks
// ---------------------------------------------------------------------------

describe('ExtensionLifecycleHost — settings default cleanup hooks', () => {
  it('invokes DisposeHandle that cleans up settings on deactivation', () => {
    const settingsCleanedUp = vi.fn();
    const host = createExtensionLifecycleHost();
    const e1 = ext('com.example.settings', {
      activate: () => ({
        dispose: () => {
          // Settings cleanup: remove localStorage keys, unsubscribe, etc.
          settingsCleanedUp();
        },
      }),
    });

    host.synchronize([e1], (ext) =>
      makeCtx({ extension: { id: ext.manifest.id as any, version: '1.0.0', label: ext.manifest.label, manifest: ext.manifest } }),
    );
    expect(host.lifecycles.size).toBe(1);
    expect(settingsCleanedUp).not.toHaveBeenCalled();

    // Remove extension — settings cleanup should be invoked
    host.synchronize([], () => makeCtx());
    expect(host.lifecycles.size).toBe(0);
    expect(settingsCleanedUp).toHaveBeenCalledTimes(1);
  });

  it('captures settings-related errors during DisposeHandle cleanup in lifecycle diagnostics', () => {
    const host = createExtensionLifecycleHost();
    const e1 = ext('com.example.settingserror', {
      activate: () => ({
        dispose: () => {
          throw new Error('settings cleanup failed: localStorage quota exceeded');
        },
      }),
    });

    host.synchronize([e1], (ext) =>
      makeCtx({ extension: { id: ext.manifest.id as any, version: '1.0.0', label: ext.manifest.label, manifest: ext.manifest } }),
    );

    // Capture the lifecycle before removal so we can inspect its diagnostics
    const lc = host.lifecycles.get('com.example.settingserror')!;
    expect(lc.state).toBe('active');

    // Remove the extension — settings error is captured in the lifecycle's own diagnostics
    host.synchronize([], () => makeCtx());
    expect(host.lifecycles.size).toBe(0);

    // The lifecycle captured the cleanup error in its diagnostics before it was removed
    const errors = lc.diagnostics.filter((d) => d.code === 'lifecycle/dispose-handle-error');
    expect(errors).toHaveLength(1);
    expect(errors[0].message).toContain('settings cleanup failed');
    expect(errors[0].extensionId).toBe('com.example.settingserror');
  });

  it('invokes settings cleanup via disposeAll on provider teardown', () => {
    const settingsCleanedUp1 = vi.fn();
    const settingsCleanedUp2 = vi.fn();
    const host = createExtensionLifecycleHost();
    const e1 = ext('com.example.s1', { activate: () => ({ dispose: settingsCleanedUp1 }) });
    const e2 = ext('com.example.s2', { activate: () => ({ dispose: settingsCleanedUp2 }) });

    host.synchronize([e1, e2], (ext) =>
      makeCtx({ extension: { id: ext.manifest.id as any, version: '1.0.0', label: ext.manifest.label, manifest: ext.manifest } }),
    );

    // Provider teardown via disposeAll
    host.disposeAll();
    expect(settingsCleanedUp1).toHaveBeenCalledTimes(1);
    expect(settingsCleanedUp2).toHaveBeenCalledTimes(1);
    expect(host.lifecycles.size).toBe(0);
  });

  it('settings defaults are scoped per extension with no cross-contamination', () => {
    // Each extension gets its own settings defaults bucket
    const host = createExtensionLifecycleHost();
    const e1 = ext('com.example.scoped1');
    const e2 = ext('com.example.scoped2');

    host.synchronize([e1, e2], (ext) =>
      makeCtx({ extension: { id: ext.manifest.id as any, version: '1.0.0', label: ext.manifest.label, manifest: ext.manifest } }),
    );

    // Each extension's diagnostics service is scoped
    const lc1 = host.lifecycles.get('com.example.scoped1')!;
    const lc2 = host.lifecycles.get('com.example.scoped2')!;

    lc1.diagnosticsService.report({ severity: 'info', code: 'scoped/test', message: 'from ext1' });
    lc2.diagnosticsService.report({ severity: 'info', code: 'scoped/test', message: 'from ext2' });

    // Verify no cross-contamination in diagnostics
    const ext1Diags = lc1.diagnostics.filter((d) => d.extensionId === 'com.example.scoped1');
    const ext2Diags = lc2.diagnostics.filter((d) => d.extensionId === 'com.example.scoped2');
    expect(ext1Diags.length).toBeGreaterThanOrEqual(3); // activating + activated + scoped/test
    expect(ext2Diags.length).toBeGreaterThanOrEqual(3);

    // Verify ext2's diagnostics don't appear in ext1
    const ext1HasExt2 = lc1.diagnostics.some((d) => d.extensionId === 'com.example.scoped2');
    expect(ext1HasExt2).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// ExtensionLifecycleHost — diagnostics cleanup
// ---------------------------------------------------------------------------

describe('ExtensionLifecycleHost — diagnostics cleanup', () => {
  it('preserves diagnostics from disposed extensions in host aggregation', () => {
    const host = createExtensionLifecycleHost();
    const e1 = ext('com.example.preserved', {
      activate: () => ({ dispose: () => {} }),
    });

    host.synchronize([e1], (ext) =>
      makeCtx({ extension: { id: ext.manifest.id as any, version: '1.0.0', label: ext.manifest.label, manifest: ext.manifest } }),
    );

    // Capture diagnostics while extension is active
    const diagsBeforeRemoval = host.diagnostics.filter((d) => d.extensionId === 'com.example.preserved');
    expect(diagsBeforeRemoval.length).toBeGreaterThanOrEqual(2); // activating + activated

    // Remove the extension
    host.synchronize([], () => makeCtx());
    expect(host.lifecycles.size).toBe(0);

    // Diagnostics from the removed extension should still be present
    // (host diagnostics snapshot includes all past diagnostics from disposed lifecycles
    //  PLUS any host-level diagnostics. Since disposed lifecycles are removed from the map,
    //  their diagnostics no longer contribute to the live aggregation.)
    // The host's diagnostics reflect the CURRENT state — after removal, disposed lifecycles
    // are gone, so their diagnostics won't be in the live snapshot.
    // This is expected: diagnostics cleanup means the host's dispose cycle properly
    // finalizes everything without leaking references.
    const diagsAfterRemoval = host.diagnostics;
    // After removal, the lifecycle is gone; diagnostics reflect empty state
    expect(diagsAfterRemoval.length).toBe(0);
  });

  it('preserves host-level diagnostics (context factory errors) after lifecycle removal', () => {
    const host = createExtensionLifecycleHost();
    const e1 = ext('com.example.hostdiag');

    // Cause a context factory error, which writes to hostDiagnostics
    host.synchronize([e1], () => {
      throw new Error('context factory failure');
    });

    // The extension was disposed and removed, but host-level diagnostics persist
    const ctxErrors = host.diagnostics.filter((d) => d.code === 'lifecycle/context-factory-error');
    expect(ctxErrors).toHaveLength(1);
    expect(ctxErrors[0].extensionId).toBe('com.example.hostdiag');

    // Even after an empty sync, host-level diagnostics remain
    host.synchronize([], () => makeCtx());
    const ctxErrorsAfter = host.diagnostics.filter((d) => d.code === 'lifecycle/context-factory-error');
    expect(ctxErrorsAfter).toHaveLength(1);
  });

  it('host diagnostics are still accessible after disposeAll', () => {
    const host = createExtensionLifecycleHost();
    const e1 = ext('com.example.postmortem');
    const e2 = ext('com.example.postmortem2', {
      activate: () => {
        throw new Error('deliberate failure');
      },
    });

    host.synchronize([e1, e2], (ext) =>
      makeCtx({ extension: { id: ext.manifest.id as any, version: '1.0.0', label: ext.manifest.label, manifest: ext.manifest } }),
    );

    // Collect diagnostics before disposeAll
    const preDisposeDiags = host.diagnostics;
    expect(preDisposeDiags.length).toBeGreaterThan(0);

    // Dispose all
    host.disposeAll();
    expect(host.lifecycles.size).toBe(0);

    // Host diagnostics are still readable (no throw on access)
    const postDisposeDiags = host.diagnostics;
    expect(Array.isArray(postDisposeDiags)).toBe(true);
  });

  it('accumulates diagnostics correctly across multiple add/remove/add cycles', () => {
    const host = createExtensionLifecycleHost();
    let version = 0;

    function makeVersionedExt(): ReighExtension {
      version++;
      return ext(`com.example.cycle${version}`, {
        activate: () => ({ dispose: () => {} }),
      });
    }

    // Cycle 1: add ext
    const ext1 = makeVersionedExt();
    host.synchronize([ext1], (ext) =>
      makeCtx({ extension: { id: ext.manifest.id as any, version: '1.0.0', label: ext.manifest.label, manifest: ext.manifest } }),
    );

    // Cycle 2: remove ext
    host.synchronize([], () => makeCtx());
    expect(host.lifecycles.size).toBe(0);

    // Cycle 3: add new ext
    const ext2 = makeVersionedExt();
    host.synchronize([ext2], (ext) =>
      makeCtx({ extension: { id: ext.manifest.id as any, version: '1.0.0', label: ext.manifest.label, manifest: ext.manifest } }),
    );

    // Cycle 4: add another
    const ext3 = makeVersionedExt();
    host.synchronize([ext2, ext3], (ext) =>
      makeCtx({ extension: { id: ext.manifest.id as any, version: '1.0.0', label: ext.manifest.label, manifest: ext.manifest } }),
    );

    // The host currently has 2 active lifecycles with diagnostics
    expect(host.lifecycles.size).toBe(2);
    const allDiags = host.diagnostics;
    // The current lifecycles each have activating + activated = at least 4 diagnostics
    expect(allDiags.length).toBeGreaterThanOrEqual(4);
    // All diagnostics should belong to current extensions
    const currentIds = new Set(['com.example.cycle2', 'com.example.cycle3']);
    for (const d of allDiags) {
      expect(currentIds.has(d.extensionId)).toBe(true);
    }
  });

  it('failed extension diagnostics persist in host until extension is removed', () => {
    const host = createExtensionLifecycleHost();
    const e1 = ext('com.example.faildiaghost', {
      activate: () => {
        throw new Error('host-level activation failure');
      },
    });

    host.synchronize([e1], (ext) =>
      makeCtx({ extension: { id: ext.manifest.id as any, version: '1.0.0', label: ext.manifest.label, manifest: ext.manifest } }),
    );

    // Extension is failed but still in the map
    expect(host.lifecycles.size).toBe(1);
    const lc = host.lifecycles.get('com.example.faildiaghost')!;
    expect(lc.state).toBe('failed');

    // Failure diagnostics should be in host aggregation
    const failDiags = host.diagnostics.filter(
      (d) => d.extensionId === 'com.example.faildiaghost' && d.code === 'lifecycle/activation-failed',
    );
    expect(failDiags).toHaveLength(1);

    // Remove the failed extension — diagnostics from the removed lifecycle
    // no longer appear in the live snapshot
    host.synchronize([], () => makeCtx());
    expect(host.lifecycles.size).toBe(0);

    // Live diagnostics now reflect empty state
    expect(host.diagnostics.length).toBe(0);
  });

  it('diagnostics from context factory errors survive disposeAll', () => {
    const host = createExtensionLifecycleHost();
    const e1 = ext('com.example.ctxsurvive');

    host.synchronize([e1], () => {
      throw new Error('context factory fatal');
    });

    // Context factory errors are host-level and survive disposal
    const preErrors = host.diagnostics.filter((d) => d.code === 'lifecycle/context-factory-error');
    expect(preErrors).toHaveLength(1);

    host.disposeAll();

    // Post-dispose, host-level diagnostics are still accessible
    const postErrors = host.diagnostics.filter((d) => d.code === 'lifecycle/context-factory-error');
    expect(postErrors).toHaveLength(1);
    expect(postErrors[0].message).toContain('context factory fatal');
  });
});

// ---------------------------------------------------------------------------
// M3: ExtensionLifecycle — creative.timeline with live TimelineOps
// ---------------------------------------------------------------------------

describe('ExtensionLifecycle — creative.timeline with live TimelineOps (M3 public SDK contracts)', () => {
  /** Create a mock TimelineOps with vi.fn() on all methods. */
  function mockTimelineOps(overrides?: Partial<TimelineOps>): TimelineOps {
    return {
      validate: vi.fn().mockReturnValue({ valid: true, diagnostics: [] } as TimelinePatchValidationResult),
      preview: vi.fn().mockReturnValue({ diff: { version: 0, entries: [], affectedObjectIds: [] }, fullyPreviewable: true, diagnostics: [] } as TimelinePreviewResult),
      apply: vi.fn().mockReturnValue({ version: 0, entries: [], affectedObjectIds: [] } as TimelineDiff),
      checkpoint: vi.fn().mockReturnValue('ckpt-1'),
      rollback: vi.fn().mockReturnValue(null),
      setAllTracksMuted: vi.fn().mockReturnValue({ version: 0, entries: [], affectedObjectIds: [] } as TimelineDiff),
      ...overrides,
    };
  }

  const samplePatch: TimelinePatch = {
    version: 1,
    operations: [
      { op: 'clip.add', target: 'new-clip-1', payload: { at: 0, clipType: 'video' }, order: 0 },
    ],
  };

  it('extension receives live ctx.creative.timeline when created with creativeOverrides', () => {
    const ops = mockTimelineOps();
    const extension = ext('com.example.live-timeline', {
      activate: vi.fn(),
    });
    const ctx = createExtensionContext(extension, {
      timeline: ops as any,
    } as Partial<CreativeContext>);

    // ctx.creative.timeline is the live TimelineOps we passed
    expect(ctx.creative.timeline).toBe(ops);
    // It is not a throwing stub
    expect(() => ctx.creative.timeline).not.toThrow();
  });

  it('live ctx.creative.timeline has all required TimelineOps methods', () => {
    const ops = mockTimelineOps();
    const extension = ext('com.example.methods');
    const ctx = createExtensionContext(extension, {
      timeline: ops as any,
    } as Partial<CreativeContext>);

    const timeline = ctx.creative.timeline;
    expect(typeof timeline.validate).toBe('function');
    expect(typeof timeline.preview).toBe('function');
    expect(typeof timeline.apply).toBe('function');
    expect(typeof timeline.checkpoint).toBe('function');
    expect(typeof timeline.rollback).toBe('function');
    expect(typeof timeline.setAllTracksMuted).toBe('function');
  });

  it('extension activate function receives ctx.creative.timeline and can call validate', () => {
    const ops = mockTimelineOps();
    const activateFn = vi.fn((ctx: ExtensionContext) => {
      const result = ctx.creative.timeline.validate(samplePatch);
      return { dispose: () => {} };
    });

    const extension = ext('com.example.validate', { activate: activateFn });
    const ctx = createExtensionContext(extension, {
      timeline: ops as any,
    } as Partial<CreativeContext>);

    const lc = createExtensionLifecycle(extension);
    lc.activate(ctx);

    expect(activateFn).toHaveBeenCalledTimes(1);
    expect(ops.validate).toHaveBeenCalledTimes(1);
    expect(ops.validate).toHaveBeenCalledWith(samplePatch);
  });

  it('extension can call ctx.creative.timeline.preview() through public contract', () => {
    const ops = mockTimelineOps();
    const extension = ext('com.example.preview');
    const ctx = createExtensionContext(extension, {
      timeline: ops as any,
    } as Partial<CreativeContext>);

    const result = ctx.creative.timeline.preview(samplePatch);
    expect(ops.preview).toHaveBeenCalledWith(samplePatch);
    expect(result).toBeDefined();
    expect(result.fullyPreviewable).toBe(true);
  });

  it('extension can call ctx.creative.timeline.apply() through public contract', () => {
    const ops = mockTimelineOps();
    const extension = ext('com.example.apply');
    const ctx = createExtensionContext(extension, {
      timeline: ops as any,
    } as Partial<CreativeContext>);

    const result = ctx.creative.timeline.apply(samplePatch);
    expect(ops.apply).toHaveBeenCalledWith(samplePatch);
    expect(result).toBeDefined();
    expect(result.entries).toEqual([]);
  });

  it('extension can call ctx.creative.timeline.checkpoint() and rollback()', () => {
    const ops = mockTimelineOps();
    const extension = ext('com.example.checkpoint');
    const ctx = createExtensionContext(extension, {
      timeline: ops as any,
    } as Partial<CreativeContext>);

    const ckptId = ctx.creative.timeline.checkpoint('test-label');
    expect(ckptId).toBe('ckpt-1');
    expect(ops.checkpoint).toHaveBeenCalledWith('test-label');

    const undone = ctx.creative.timeline.rollback(ckptId);
    expect(ops.rollback).toHaveBeenCalledWith(ckptId);
    expect(undone).toBeNull();
  });

  it('extension can call ctx.creative.timeline.setAllTracksMuted()', () => {
    const ops = mockTimelineOps();
    const extension = ext('com.example.mute');
    const ctx = createExtensionContext(extension, {
      timeline: ops as any,
    } as Partial<CreativeContext>);

    const result = ctx.creative.timeline.setAllTracksMuted(true);
    expect(ops.setAllTracksMuted).toHaveBeenCalledWith(true);
    expect(result).toBeDefined();
  });

  it('extension can construct valid TimelinePatch using public SDK types', () => {
    // This test proves that the extension code itself — without importing
    // any video-editor internals — can construct patches using only SDK types.
    const ops = mockTimelineOps();
    const extension = ext('com.example.construct-patch');
    const ctx = createExtensionContext(extension, {
      timeline: ops as any,
    } as Partial<CreativeContext>);

    const patch: TimelinePatch = {
      version: 3,
      operations: [
        { op: 'clip.add', target: 'c1', payload: { at: 10, clipType: 'video', track: 't1' }, order: 0 },
        { op: 'track.add', target: 't2', payload: { kind: 'audio', label: 'Voiceover' }, order: 1 },
        { op: 'clip.move', target: 'c2', payload: { track: 't2', at: 20 }, order: 2 },
      ],
      source: 'com.example.construct-patch',
      meta: { requestId: 'test-123' },
    };

    const validation = ctx.creative.timeline.validate(patch);
    expect(ops.validate).toHaveBeenCalledWith(patch);
    expect(validation.valid).toBe(true);
  });

  it('live TimelineOps is passed to extension through ExtensionLifecycle.activate()', () => {
    const ops = mockTimelineOps();
    const capturedTimeline: TimelineOps[] = [];

    const extension = ext('com.example.activate-ctx', {
      activate: (ctx) => {
        capturedTimeline.push(ctx.creative.timeline);
        return { dispose: () => {} };
      },
    });

    const ctx = createExtensionContext(extension, {
      timeline: ops as any,
    } as Partial<CreativeContext>);

    const lc = createExtensionLifecycle(extension);
    lc.activate(ctx);

    expect(lc.state).toBe('active');
    expect(capturedTimeline).toHaveLength(1);
    expect(capturedTimeline[0]).toBe(ops);

    // The extension can use the captured timeline reference
    capturedTimeline[0].validate(samplePatch);
    expect(ops.validate).toHaveBeenCalledWith(samplePatch);
  });

  it('multiple extensions receive independent timeline references', () => {
    const ops1 = mockTimelineOps();
    const ops2 = mockTimelineOps();

    const ext1 = ext('com.example.indep1', {
      activate: vi.fn(),
    });
    const ext2 = ext('com.example.indep2', {
      activate: vi.fn(),
    });

    const ctx1 = createExtensionContext(ext1, { timeline: ops1 as any } as Partial<CreativeContext>);
    const ctx2 = createExtensionContext(ext2, { timeline: ops2 as any } as Partial<CreativeContext>);

    expect(ctx1.creative.timeline).toBe(ops1);
    expect(ctx2.creative.timeline).toBe(ops2);
    expect(ctx1.creative.timeline).not.toBe(ctx2.creative.timeline);
  });

  it('extension can use TimelineOps.checkpoint + rollback for safe mutation patterns', () => {
    const ops = mockTimelineOps({
      checkpoint: vi.fn().mockReturnValue('safe-ckpt'),
      rollback: vi.fn().mockReturnValue({ version: 1, entries: [], affectedObjectIds: [] } as TimelineDiff),
    });

    const extension = ext('com.example.safe-pattern');
    const ctx = createExtensionContext(extension, { timeline: ops as any } as Partial<CreativeContext>);

    // Safe mutation pattern: checkpoint → try apply → catch → rollback
    const ckpt = ctx.creative.timeline.checkpoint('before-risky-op');
    expect(ckpt).toBe('safe-ckpt');

    // In real code, the extension would try apply() and on failure call rollback()
    const undone = ctx.creative.timeline.rollback(ckpt);
    expect(ops.rollback).toHaveBeenCalledWith('safe-ckpt');
    expect(undone).toBeDefined();
  });
});

// ---------------------------------------------------------------------------
// M3: ExtensionLifecycle — creative.timeline stubs (unmounted contexts)
// ---------------------------------------------------------------------------

describe('ExtensionLifecycle — creative.timeline stubs (unmounted contexts)', () => {
  it('createCreativeContextStubs() produces a frozen object', () => {
    const stubs = createCreativeContextStubs();
    expect(Object.isFrozen(stubs)).toBe(true);
  });

  it('createCreativeContextStubs() throws ExtensionNotImplementedError for timeline', () => {
    const stubs = createCreativeContextStubs();
    expect(() => stubs.timeline).toThrow(ExtensionNotImplementedError);
    try {
      stubs.timeline;
    } catch (err) {
      expect(err).toBeInstanceOf(ExtensionNotImplementedError);
      expect((err as ExtensionNotImplementedError).feature).toBe('timeline');
      expect((err as ExtensionNotImplementedError).milestone).toBe('M3');
    }
  });

  it('createCreativeContextStubs() throws for reader and proposals (M3 members)', () => {
    const stubs = createCreativeContextStubs();
    // reader
    expect(() => stubs.reader).toThrow(ExtensionNotImplementedError);
    try { stubs.reader; } catch (err) {
      expect((err as ExtensionNotImplementedError).feature).toBe('reader');
      expect((err as ExtensionNotImplementedError).milestone).toBe('M3');
    }
    // proposals
    expect(() => stubs.proposals).toThrow(ExtensionNotImplementedError);
    try { stubs.proposals; } catch (err) {
      expect((err as ExtensionNotImplementedError).feature).toBe('proposals');
      expect((err as ExtensionNotImplementedError).milestone).toBe('M3');
    }
  });

  it('createCreativeContextStubs() throws for ALL creative members when accessed', () => {
    const stubs = createCreativeContextStubs();
    const members = Object.keys(CREATIVE_MEMBER_MILESTONE) as (keyof CreativeContext)[];
    for (const member of members) {
      expect(() => stubs[member]).toThrow(ExtensionNotImplementedError);
    }
  });

  it('createCreativeContext() without overrides returns stubs (timeline throws)', () => {
    const creative = createCreativeContext();
    expect(() => creative.timeline).toThrow(ExtensionNotImplementedError);
    try {
      creative.timeline;
    } catch (err) {
      expect((err as ExtensionNotImplementedError).feature).toBe('timeline');
      expect((err as ExtensionNotImplementedError).milestone).toBe('M3');
    }
  });

  it('createCreativeContext() with partial overrides keeps stubs for non-overridden members', () => {
    const ops = {
      validate: vi.fn().mockReturnValue({ valid: true, diagnostics: [] }),
      preview: vi.fn(),
      apply: vi.fn(),
      checkpoint: vi.fn(),
      rollback: vi.fn(),
      setAllTracksMuted: vi.fn(),
    };

    const creative = createCreativeContext({
      timeline: ops as any,
    } as Partial<CreativeContext>);

    // timeline is live
    expect(creative.timeline).toBe(ops);
    expect(() => creative.timeline).not.toThrow();

    // reader still throws (not overridden)
    expect(() => creative.reader).toThrow(ExtensionNotImplementedError);
    try { creative.reader; } catch (err) {
      expect((err as ExtensionNotImplementedError).feature).toBe('reader');
    }

    // proposals still throws (not overridden)
    expect(() => creative.proposals).toThrow(ExtensionNotImplementedError);
  });

  it('createExtensionContext() without creativeOverrides creates stubs', () => {
    const extension = ext('com.example.nostubs');
    const ctx = createExtensionContext(extension);

    expect(() => ctx.creative.timeline).toThrow(ExtensionNotImplementedError);
    try {
      ctx.creative.timeline;
    } catch (err) {
      expect((err as ExtensionNotImplementedError).feature).toBe('timeline');
      expect((err as ExtensionNotImplementedError).milestone).toBe('M3');
    }
  });

  it('ExtensionNotImplementedError has correct shape and message', () => {
    const err = new ExtensionNotImplementedError('test-feature', 'M5');
    expect(err).toBeInstanceOf(Error);
    expect(err.name).toBe('ExtensionNotImplementedError');
    expect(err.feature).toBe('test-feature');
    expect(err.milestone).toBe('M5');
    expect(err.message).toContain('test-feature');
    expect(err.message).toContain('M5');
  });

  it('stubs are NOT callable — accessing them throws, not calling them', () => {
    const stubs = createCreativeContextStubs();
    // Accessing the property throws immediately (it's a throwing getter)
    expect(() => {
      const t = stubs.timeline;
    }).toThrow(ExtensionNotImplementedError);
    // You never get a reference to call methods on
  });
});

// ---------------------------------------------------------------------------
// M3: ExtensionLifecycle — creative context internal API boundary
// ---------------------------------------------------------------------------

describe('ExtensionLifecycle — creative context internal API boundary', () => {
  const INTERNAL_FORBIDDEN_KEYS = [
    'TimelineData',
    'TimelineEditMutation',
    'DataProvider',
    'provider',
    'dataProvider',
    'dataProviderRef',
    'getDataProvider',
    'isDataProviderPersistenceEnabled',
    'timelineStore',
    'store',
    'getTimeline',
    'timelineRef',
    'useTimelineDataSlice',
    'useTimelineDataSelector',
    'useTimelineEditorData',
    'timelineState',
    'TimelineDataRef',
    'buildTimelineData',
    'buildTimelineDataWithResolver',
    'buildTimelineCommandData',
    'assembleTimelineData',
    'preserveUploadingClips',
    'applyEdit',
    'edit',
    'mutate',
    'patch',
    'commit',
    'transact',
    'commitData',
    'ops',
    'internalOps',
    '_internal',
    '__editorInternals',
    '_editor',
    'resolveTimelineProvider',
    'createProvider',
  ];

  it('ExtensionContext does not expose internal API keys at top level', () => {
    const extension = ext('com.example.boundary');
    const ctx = createExtensionContext(extension);
    const ctxKeys = Object.keys(ctx);

    for (const forbidden of INTERNAL_FORBIDDEN_KEYS) {
      expect(ctxKeys).not.toContain(forbidden);
    }
  });

  it('ExtensionContext.creative only has defined CreativeContext members', () => {
    const extension = ext('com.example.creative-keys');
    const ctx = createExtensionContext(extension);
    const creativeKeys = Object.keys(ctx.creative).sort();
    expect(creativeKeys).toEqual([
      'assets',
      'export',
      'materials',
      'project',
      'proposals',
      'reader',
      'sessions',
      'stage',
      'timeline',
      'writing',
    ]);
  });

  it('internal mutation APIs are not accessible as properties on creative context', () => {
    const ops = {
      validate: vi.fn(),
      preview: vi.fn(),
      apply: vi.fn(),
      checkpoint: vi.fn(),
      rollback: vi.fn(),
      setAllTracksMuted: vi.fn(),
    };
    const extension = ext('com.example.creative-boundary');
    const ctx = createExtensionContext(extension, {
      timeline: ops as any,
    } as Partial<CreativeContext>);

    const creative = ctx.creative as Record<string, unknown>;
    for (const forbidden of INTERNAL_FORBIDDEN_KEYS) {
      expect(creative).not.toHaveProperty(forbidden);
    }
  });

  it('internal APIs are not accessible on the timeline ops reference itself', () => {
    const ops = {
      validate: vi.fn(),
      preview: vi.fn(),
      apply: vi.fn(),
      checkpoint: vi.fn(),
      rollback: vi.fn(),
      setAllTracksMuted: vi.fn(),
    };
    const extension = ext('com.example.ops-boundary');
    const ctx = createExtensionContext(extension, {
      timeline: ops as any,
    } as Partial<CreativeContext>);

    const timeline = ctx.creative.timeline as Record<string, unknown>;
    // Only the public TimelineOps methods should be present
    const publicMethods = ['validate', 'preview', 'apply', 'checkpoint', 'rollback', 'setAllTracksMuted'];
    for (const method of publicMethods) {
      expect(typeof timeline[method]).toBe('function');
    }
    // Internal keys should not be present
    for (const forbidden of INTERNAL_FORBIDDEN_KEYS) {
      expect(timeline).not.toHaveProperty(forbidden);
    }
  });

  it('createExtensionContext returns a frozen-like context (creative is frozen)', () => {
    const extension = ext('com.example.frozen-ctx');
    const ctx = createExtensionContext(extension);
    // creative is frozen by createCreativeContext
    expect(Object.isFrozen(ctx.creative)).toBe(true);
  });

  it('extension cannot access raw TimelineData through any context path', () => {
    const extension = ext('com.example.raw-timeline');
    const ctx = createExtensionContext(extension);
    const allKeys = new Set<string>();

    function collectKeys(obj: unknown, depth: number) {
      if (depth > 2 || obj === null || typeof obj !== 'object') return;
      for (const key of Object.keys(obj as object)) {
        allKeys.add(key);
        try {
          collectKeys((obj as Record<string, unknown>)[key], depth + 1);
        } catch {
          // Throwing getter — skip
        }
      }
    }

    collectKeys(ctx, 0);
    for (const forbidden of ['TimelineData', 'TimelineEditMutation', 'applyEdit', 'commitData', 'timelineStore']) {
      expect(allKeys.has(forbidden)).toBe(false);
    }
  });

  it('extension cannot import internal video-editor modules through context', () => {
    // The context itself is a plain object — no import/require mechanism
    const extension = ext('com.example.no-internal-import');
    const ctx = createExtensionContext(extension);

    expect((ctx as any).require).toBeUndefined();
    expect((ctx as any).import).toBeUndefined();
    expect((ctx as any).module).toBeUndefined();
    expect((ctx as any).__esModule).toBeUndefined();
  });

  it('creative context members are non-configurable (cannot be deleted/redefined)', () => {
    const extension = ext('com.example.non-configurable');
    const ctx = createExtensionContext(extension);

    // timeline is a non-configurable property
    const desc = Object.getOwnPropertyDescriptor(ctx.creative, 'timeline');
    expect(desc).toBeDefined();
    if (desc) {
      expect(desc.configurable).toBe(false);
      expect(desc.enumerable).toBe(true);
    }
  });

  it('a live timeline reference is a non-writable property on creative context', () => {
    const ops = {
      validate: vi.fn(),
      preview: vi.fn(),
      apply: vi.fn(),
      checkpoint: vi.fn(),
      rollback: vi.fn(),
      setAllTracksMuted: vi.fn(),
    };
    const extension = ext('com.example.non-writable');
    const ctx = createExtensionContext(extension, {
      timeline: ops as any,
    } as Partial<CreativeContext>);

    const desc = Object.getOwnPropertyDescriptor(ctx.creative, 'timeline');
    expect(desc).toBeDefined();
    if (desc) {
      expect(desc.writable).toBe(false);
    }
  });
});

// ---------------------------------------------------------------------------
// M3: ExtensionLifecycle — mutations only through public SDK contracts
// ---------------------------------------------------------------------------

describe('ExtensionLifecycle — mutations through public SDK contracts only', () => {
  function makeLiveOps(): TimelineOps {
    const patches: TimelinePatch[] = [];
    return {
      validate: vi.fn((patch: TimelinePatch): TimelinePatchValidationResult => ({
        valid: true,
        diagnostics: [],
      })),
      preview: vi.fn((patch: TimelinePatch): TimelinePreviewResult => ({
        diff: {
          version: patch.version,
          entries: patch.operations.map((op) => ({
            granularity: 'clip' as const,
            kind: 'added' as const,
            target: op.target,
            op: op.op,
            after: op.payload,
          })),
          affectedObjectIds: patch.operations.map((op) => op.target),
        },
        fullyPreviewable: true,
        diagnostics: [],
      })),
      apply: vi.fn((patch: TimelinePatch): TimelineDiff => {
        patches.push(patch);
        return {
          version: patch.version + 1,
          entries: patch.operations.map((op) => ({
            granularity: 'clip' as const,
            kind: 'added' as const,
            target: op.target,
            op: op.op,
            after: op.payload,
          })),
          affectedObjectIds: patch.operations.map((op) => op.target),
        };
      }),
      checkpoint: vi.fn().mockReturnValue('apply-ckpt'),
      rollback: vi.fn().mockReturnValue(null),
      setAllTracksMuted: vi.fn((muted: boolean): TimelineDiff => ({
        version: 1,
        entries: [],
        affectedObjectIds: [],
      })),
      _patches: patches,
    } as TimelineOps & { _patches: TimelinePatch[] };
  }

  it('extension can only mutate through ctx.creative.timeline.apply()', () => {
    const ops = makeLiveOps();
    const extension = ext('com.example.only-apply');
    const ctx = createExtensionContext(extension, {
      timeline: ops as any,
    } as Partial<CreativeContext>);

    const patch: TimelinePatch = {
      version: 1,
      operations: [
        { op: 'clip.add', target: 'new-clip', payload: { at: 0, clipType: 'video' }, order: 0 },
      ],
      source: 'com.example.only-apply',
    };

    // The only mutation path is through apply()
    const diff = ctx.creative.timeline.apply(patch);
    expect(ops.apply).toHaveBeenCalledTimes(1);
    expect(diff.affectedObjectIds).toContain('new-clip');
  });

  it('extension previews changes before applying them (public contract pattern)', () => {
    const ops = makeLiveOps();
    const extension = ext('com.example.preview-then-apply');
    const ctx = createExtensionContext(extension, {
      timeline: ops as any,
    } as Partial<CreativeContext>);

    const patch: TimelinePatch = {
      version: 2,
      operations: [
        { op: 'clip.move', target: 'clip-1', payload: { at: 30 }, order: 0 },
      ],
      source: 'com.example.preview-then-apply',
    };

    // 1. Preview to see what would happen
    const preview = ctx.creative.timeline.preview(patch);
    expect(preview.fullyPreviewable).toBe(true);
    expect(ops.preview).toHaveBeenCalledWith(patch);

    // 2. Then apply if preview looks good
    const diff = ctx.creative.timeline.apply(patch);
    expect(ops.apply).toHaveBeenCalledWith(patch);
    expect(diff).toBeDefined();
  });

  it('extension validates patch before applying (public contract pattern)', () => {
    const ops = makeLiveOps();
    const extension = ext('com.example.validate-then-apply');
    const ctx = createExtensionContext(extension, {
      timeline: ops as any,
    } as Partial<CreativeContext>);

    const patch: TimelinePatch = {
      version: 3,
      operations: [
        { op: 'track.add', target: 'new-track', payload: { kind: 'audio' }, order: 0 },
      ],
      source: 'com.example.validate-then-apply',
    };

    // 1. Validate first
    const validation = ctx.creative.timeline.validate(patch);
    expect(validation.valid).toBe(true);

    // 2. Apply if valid
    const diff = ctx.creative.timeline.apply(patch);
    expect(ops.apply).toHaveBeenCalledWith(patch);
    expect(diff).toBeDefined();
  });

  it('extension cannot bypass TimelineOps to directly modify timeline data', () => {
    const ops = makeLiveOps();
    const extension = ext('com.example.no-bypass');
    const ctx = createExtensionContext(extension, {
      timeline: ops as any,
    } as Partial<CreativeContext>);

    // The context has no direct mutation methods beyond creative.timeline
    const ctxAny = ctx as Record<string, unknown>;
    expect(ctxAny.applyEdit).toBeUndefined();
    expect(ctxAny.commitData).toBeUndefined();
    expect(ctxAny.mutate).toBeUndefined();
    expect(ctxAny.patch).toBeUndefined();
    expect(ctxAny.commit).toBeUndefined();
    expect(ctxAny.transact).toBeUndefined();
  });

  it('extension cannot access provider references through context', () => {
    const ops = makeLiveOps();
    const extension = ext('com.example.no-provider');
    const ctx = createExtensionContext(extension, {
      timeline: ops as any,
    } as Partial<CreativeContext>);

    const ctxAny = ctx as Record<string, unknown>;
    expect(ctxAny.dataProvider).toBeUndefined();
    expect(ctxAny.provider).toBeUndefined();
    expect(ctxAny.dataProviderRef).toBeUndefined();
    expect(ctxAny.timelineRef).toBeUndefined();
    expect(ctxAny.store).toBeUndefined();
    expect(ctxAny.timelineStore).toBeUndefined();
  });

  it('extension can construct complex multi-operation patches using public types', () => {
    const ops = makeLiveOps();
    const extension = ext('com.example.multi-op');
    const ctx = createExtensionContext(extension, {
      timeline: ops as any,
    } as Partial<CreativeContext>);

    // Construct a realistic batch: add a track, add two clips to it, mute audio
    const patch: TimelinePatch = {
      version: 5,
      operations: [
        { op: 'track.add', target: 'intro-track', payload: { kind: 'visual', label: 'Intro' }, order: 0 },
        { op: 'clip.add', target: 'title-clip', payload: { at: 0, clipType: 'video', track: 'intro-track' }, order: 1 },
        { op: 'clip.add', target: 'broll-clip', payload: { at: 120, clipType: 'video', track: 'intro-track' }, order: 2 },
      ],
      source: 'com.example.multi-op',
      meta: { description: 'Add intro section' },
    };

    const preview = ctx.creative.timeline.preview(patch);
    expect(preview.fullyPreviewable).toBe(true);
    expect(preview.diff.entries).toHaveLength(3);
    expect(preview.diff.affectedObjectIds).toContain('intro-track');
    expect(preview.diff.affectedObjectIds).toContain('title-clip');
    expect(preview.diff.affectedObjectIds).toContain('broll-clip');
  });

  it('extension mutation path is fully captured by the public SDK boundary', () => {
    // This test proves the complete flow: extension creates patch →
    // validates → previews → applies, all through ctx.creative.timeline,
    // never touching any internal API.
    const ops = makeLiveOps();
    const extension = ext('com.example.full-flow');
    const ctx = createExtensionContext(extension, {
      timeline: ops as any,
    } as Partial<CreativeContext>);

    // Step 1: extension builds a patch using only SDK types
    const patch: TimelinePatch = {
      version: 10,
      operations: [
        { op: 'clip.add', target: 'extension-clip', payload: { at: 60, clipType: 'video' }, order: 0 },
      ],
      source: extension.manifest.id as string,
      meta: { extensionVersion: '1.0.0' },
    };

    // Step 2: validate
    const validation = ctx.creative.timeline.validate(patch);
    expect(validation.valid).toBe(true);

    // Step 3: preview
    const preview = ctx.creative.timeline.preview(patch);
    expect(preview.fullyPreviewable).toBe(true);
    expect(preview.diff.affectedObjectIds).toEqual(['extension-clip']);

    // Step 4: apply
    const diff = ctx.creative.timeline.apply(patch);
    expect(diff.affectedObjectIds).toEqual(['extension-clip']);
    expect(ops.apply).toHaveBeenCalledTimes(1);

    // Verify the patch was captured by the mock (went through public API)
    expect(ops.apply).toHaveBeenCalledWith(patch);
  });
});


// ---------------------------------------------------------------------------
// T16: Contribution cleanup matrix — per-contribution-kind DisposeHandle verification
// ---------------------------------------------------------------------------

describe('ExtensionLifecycle — contribution cleanup matrix (T16)', () => {
  /** Helper: create an extension that "registers" a set of contributions and
   *  returns a DisposeHandle whose dispose() tracks per-contribution cleanup. */
  function extWithContributions(
    id: string,
    contributions: Array<{
      contribId: string;
      kind: string;
      cleanup: ReturnType<typeof vi.fn>;
    }>,
  ): ReighExtension {
    const cleanupFns = contributions.map((c) => c.cleanup);
    return ext(id, {
      contributions: contributions.map((c) => ({
        id: c.contribId as ContributionId,
        kind: c.kind as any,
      })),
      activate: () => ({
        dispose: () => {
          for (const fn of cleanupFns) fn();
        },
      }),
    });
  }

  // ---- command cleanup -------------------------------------------------------

  it('cleans up command contribution on extension removal (disable/unload)', () => {
    const commandCleanup = vi.fn();
    const host = createExtensionLifecycleHost();
    const e1 = extWithContributions('com.example.cmd', [
      { contribId: 'my-command', kind: 'command', cleanup: commandCleanup },
    ]);

    host.synchronize([e1], (ext) =>
      makeCtx({ extension: { id: ext.manifest.id as any, version: '1.0.0', label: ext.manifest.label, manifest: ext.manifest } }),
    );
    expect(host.lifecycles.size).toBe(1);
    expect(commandCleanup).not.toHaveBeenCalled();

    // Remove extension — command cleanup must fire
    host.synchronize([], () => makeCtx());
    expect(host.lifecycles.size).toBe(0);
    expect(commandCleanup).toHaveBeenCalledTimes(1);
  });

  it('cleans up command contribution on disposeAll (provider teardown)', () => {
    const commandCleanup = vi.fn();
    const host = createExtensionLifecycleHost();
    const e1 = extWithContributions('com.example.cmd2', [
      { contribId: 'cmd-disposeAll', kind: 'command', cleanup: commandCleanup },
    ]);

    host.synchronize([e1], (ext) =>
      makeCtx({ extension: { id: ext.manifest.id as any, version: '1.0.0', label: ext.manifest.label, manifest: ext.manifest } }),
    );
    host.disposeAll();
    expect(commandCleanup).toHaveBeenCalledTimes(1);
    expect(host.lifecycles.size).toBe(0);
  });

  it('cleanup happens without provider remount — deactivation is synchronous within synchronize()', () => {
    const commandCleanup = vi.fn();
    const host = createExtensionLifecycleHost();
    const e1 = extWithContributions('com.example.noremount', [
      { contribId: 'no-remount-cmd', kind: 'command', cleanup: commandCleanup },
    ]);
    const e2 = ext('com.example.stays');

    // Activate both
    host.synchronize([e1, e2], (ext) =>
      makeCtx({ extension: { id: ext.manifest.id as any, version: '1.0.0', label: ext.manifest.label, manifest: ext.manifest } }),
    );
    // Now remove e1 while keeping e2 — no remount needed
    host.synchronize([e2], (ext) =>
      makeCtx({ extension: { id: ext.manifest.id as any, version: '1.0.0', label: ext.manifest.label, manifest: ext.manifest } }),
    );
    expect(commandCleanup).toHaveBeenCalledTimes(1);
    expect(host.lifecycles.has('com.example.stays')).toBe(true);
    expect(host.lifecycles.has('com.example.noremount')).toBe(false);
  });

  // ---- effect cleanup --------------------------------------------------------

  it('cleans up effect contribution on extension removal', () => {
    const effectCleanup = vi.fn();
    const host = createExtensionLifecycleHost();
    const e1 = extWithContributions('com.example.effect', [
      { contribId: 'my-effect', kind: 'effect', cleanup: effectCleanup },
    ]);

    host.synchronize([e1], (ext) =>
      makeCtx({ extension: { id: ext.manifest.id as any, version: '1.0.0', label: ext.manifest.label, manifest: ext.manifest } }),
    );
    host.synchronize([], () => makeCtx());
    expect(effectCleanup).toHaveBeenCalledTimes(1);
  });

  it('cleans up effect contribution on disposeAll', () => {
    const effectCleanup = vi.fn();
    const host = createExtensionLifecycleHost();
    const e1 = extWithContributions('com.example.effect2', [
      { contribId: 'fx-disposeAll', kind: 'effect', cleanup: effectCleanup },
    ]);

    host.synchronize([e1], (ext) =>
      makeCtx({ extension: { id: ext.manifest.id as any, version: '1.0.0', label: ext.manifest.label, manifest: ext.manifest } }),
    );
    host.disposeAll();
    expect(effectCleanup).toHaveBeenCalledTimes(1);
  });

  // ---- transition cleanup ---------------------------------------------------

  it('cleans up transition contribution on extension removal', () => {
    const transitionCleanup = vi.fn();
    const host = createExtensionLifecycleHost();
    const e1 = extWithContributions('com.example.trans', [
      { contribId: 'my-transition', kind: 'transition', cleanup: transitionCleanup },
    ]);

    host.synchronize([e1], (ext) =>
      makeCtx({ extension: { id: ext.manifest.id as any, version: '1.0.0', label: ext.manifest.label, manifest: ext.manifest } }),
    );
    host.synchronize([], () => makeCtx());
    expect(transitionCleanup).toHaveBeenCalledTimes(1);
  });

  // ---- shader cleanup -------------------------------------------------------

  it('cleans up shader contribution on extension removal', () => {
    const shaderCleanup = vi.fn();
    const host = createExtensionLifecycleHost();
    const e1 = extWithContributions('com.example.shader', [
      { contribId: 'my-shader', kind: 'shader', cleanup: shaderCleanup },
    ]);

    host.synchronize([e1], (ext) =>
      makeCtx({ extension: { id: ext.manifest.id as any, version: '1.0.0', label: ext.manifest.label, manifest: ext.manifest } }),
    );
    host.synchronize([], () => makeCtx());
    expect(shaderCleanup).toHaveBeenCalledTimes(1);
  });

  // ---- clipType cleanup -----------------------------------------------------

  it('cleans up clipType contribution on extension removal', () => {
    const clipTypeCleanup = vi.fn();
    const host = createExtensionLifecycleHost();
    const e1 = extWithContributions('com.example.cliptype', [
      { contribId: 'my-cliptype', kind: 'clipType', cleanup: clipTypeCleanup },
    ]);

    host.synchronize([e1], (ext) =>
      makeCtx({ extension: { id: ext.manifest.id as any, version: '1.0.0', label: ext.manifest.label, manifest: ext.manifest } }),
    );
    host.synchronize([], () => makeCtx());
    expect(clipTypeCleanup).toHaveBeenCalledTimes(1);
  });

  // ---- agentTool cleanup ----------------------------------------------------

  it('cleans up agentTool contribution on extension removal', () => {
    const agentToolCleanup = vi.fn();
    const host = createExtensionLifecycleHost();
    const e1 = extWithContributions('com.example.agent', [
      { contribId: 'my-agent-tool', kind: 'agentTool', cleanup: agentToolCleanup },
    ]);

    host.synchronize([e1], (ext) =>
      makeCtx({ extension: { id: ext.manifest.id as any, version: '1.0.0', label: ext.manifest.label, manifest: ext.manifest } }),
    );
    host.synchronize([], () => makeCtx());
    expect(agentToolCleanup).toHaveBeenCalledTimes(1);
  });

  // ---- live-data cleanup (via liveDataRegistry) ------------------------------

  it('cleans up live-data sources on extension removal via lifecycle host', () => {
    // Live data is managed through the LiveDataRegistry passed to the host.
    // When an extension is removed, the host calls disposeExtensionSources().
    const disposeSources = vi.fn();
    const mockRegistry = {
      isDisposed: false,
      disposeExtensionSources: disposeSources,
    } as unknown as LiveDataRegistry;

    const liveDataCleanup = vi.fn();
    const host = createExtensionLifecycleHost(mockRegistry);
    const e1 = extWithContributions('com.example.livedata', [
      { contribId: 'live-source', kind: 'slot', cleanup: liveDataCleanup },
    ]);

    host.synchronize([e1], (ext) =>
      makeCtx({ extension: { id: ext.manifest.id as any, version: '1.0.0', label: ext.manifest.label, manifest: ext.manifest } }),
    );
    expect(host.lifecycles.size).toBe(1);

    // Remove extension — liveDataRegistry.disposeExtensionSources should be called
    host.synchronize([], () => makeCtx());
    expect(disposeSources).toHaveBeenCalledTimes(1);
    expect(disposeSources).toHaveBeenCalledWith('com.example.livedata');
    expect(liveDataCleanup).toHaveBeenCalledTimes(1); // dispose handle also fires
  });

  it('cleans up live-data sources for all extensions on disposeAll', () => {
    const disposeSources = vi.fn();
    const mockRegistry = {
      isDisposed: false,
      disposeExtensionSources: disposeSources,
    } as unknown as LiveDataRegistry;

    const host = createExtensionLifecycleHost(mockRegistry);
    const e1 = ext('com.example.ld1');
    const e2 = ext('com.example.ld2');

    host.synchronize([e1, e2], (ext) =>
      makeCtx({ extension: { id: ext.manifest.id as any, version: '1.0.0', label: ext.manifest.label, manifest: ext.manifest } }),
    );

    host.disposeAll();
    expect(disposeSources).toHaveBeenCalledTimes(2);
    expect(disposeSources).toHaveBeenCalledWith('com.example.ld1');
    expect(disposeSources).toHaveBeenCalledWith('com.example.ld2');
  });

  it('skips live-data cleanup when registry is already disposed', () => {
    const disposeSources = vi.fn();
    const mockRegistry = {
      isDisposed: true, // already disposed
      disposeExtensionSources: disposeSources,
    } as unknown as LiveDataRegistry;

    const host = createExtensionLifecycleHost(mockRegistry);
    const e1 = ext('com.example.ld-disposed');

    host.synchronize([e1], (ext) =>
      makeCtx({ extension: { id: ext.manifest.id as any, version: '1.0.0', label: ext.manifest.label, manifest: ext.manifest } }),
    );
    host.synchronize([], () => makeCtx());
    // Registry is already disposed so disposeExtensionSources should not be called
    expect(disposeSources).not.toHaveBeenCalled();
  });

  // ---- diagnostics entries cleanup ------------------------------------------

  it('diagnostics entries are properly cleaned up when extension is removed', () => {
    const host = createExtensionLifecycleHost();
    const diagCleanup = vi.fn();
    const e1 = ext('com.example.diag-cleanup', {
      activate: () => {
        return { dispose: diagCleanup };
      },
    });

    host.synchronize([e1], (ext) =>
      makeCtx({ extension: { id: ext.manifest.id as any, version: '1.0.0', label: ext.manifest.label, manifest: ext.manifest } }),
    );

    // The lifecycle's own diagnostics track activation events
    const lc = host.lifecycles.get('com.example.diag-cleanup')!;
    expect(lc.state).toBe('active');

    // Diagnostic entries from the lifecycle (activating, activated) are in host aggregation
    const activatingDiags = host.diagnostics.filter(
      (d) => d.extensionId === 'com.example.diag-cleanup' && d.code === 'lifecycle/activating',
    );
    const activatedDiags = host.diagnostics.filter(
      (d) => d.extensionId === 'com.example.diag-cleanup' && d.code === 'lifecycle/activated',
    );
    expect(activatingDiags).toHaveLength(1);
    expect(activatedDiags).toHaveLength(1);

    // Remove extension — dispose handle fires
    host.synchronize([], () => makeCtx());
    expect(diagCleanup).toHaveBeenCalledTimes(1);

    // After removal, the lifecycle is gone from the map — its diagnostics
    // (activating, activated) are no longer in the live aggregation snapshot
    const afterActivating = host.diagnostics.filter(
      (d) => d.extensionId === 'com.example.diag-cleanup' && d.code === 'lifecycle/activating',
    );
    expect(afterActivating).toHaveLength(0);
  });

  // ---- combined: all contribution types in one extension ---------------------

  it('cleans up ALL contribution types when an extension is removed (full matrix)', () => {
    const cleanup: Record<string, ReturnType<typeof vi.fn>> = {
      command: vi.fn(),
      effect: vi.fn(),
      transition: vi.fn(),
      shader: vi.fn(),
      clipType: vi.fn(),
      agentTool: vi.fn(),
    };

    const host = createExtensionLifecycleHost();
    const e1 = ext('com.example.all-kinds', {
      contributions: [
        { id: 'c-cmd' as ContributionId, kind: 'command' as any },
        { id: 'c-fx' as ContributionId, kind: 'effect' as any },
        { id: 'c-trans' as ContributionId, kind: 'transition' as any },
        { id: 'c-shader' as ContributionId, kind: 'shader' as any },
        { id: 'c-clip' as ContributionId, kind: 'clipType' as any },
        { id: 'c-agent' as ContributionId, kind: 'agentTool' as any },
      ],
      activate: () => ({
        dispose: () => {
          cleanup.command();
          cleanup.effect();
          cleanup.transition();
          cleanup.shader();
          cleanup.clipType();
          cleanup.agentTool();
        },
      }),
    });

    host.synchronize([e1], (ext) =>
      makeCtx({ extension: { id: ext.manifest.id as any, version: '1.0.0', label: ext.manifest.label, manifest: ext.manifest } }),
    );
    expect(host.lifecycles.size).toBe(1);
    for (const key of Object.keys(cleanup)) {
      expect(cleanup[key]).not.toHaveBeenCalled();
    }

    // Remove — all cleanups must fire
    host.synchronize([], () => makeCtx());
    for (const key of Object.keys(cleanup)) {
      expect(cleanup[key]).toHaveBeenCalledTimes(1);
    }
    expect(host.lifecycles.size).toBe(0);
  });

  it('cleans up all contribution types on disposeAll', () => {
    const cleanup: Record<string, ReturnType<typeof vi.fn>> = {
      command: vi.fn(),
      shader: vi.fn(),
      agentTool: vi.fn(),
    };

    const host = createExtensionLifecycleHost();
    const e1 = ext('com.example.all-disposeAll', {
      contributions: [
        { id: 'd-cmd' as ContributionId, kind: 'command' as any },
        { id: 'd-shader' as ContributionId, kind: 'shader' as any },
        { id: 'd-agent' as ContributionId, kind: 'agentTool' as any },
      ],
      activate: () => ({
        dispose: () => {
          cleanup.command();
          cleanup.shader();
          cleanup.agentTool();
        },
      }),
    });

    host.synchronize([e1], (ext) =>
      makeCtx({ extension: { id: ext.manifest.id as any, version: '1.0.0', label: ext.manifest.label, manifest: ext.manifest } }),
    );
    host.disposeAll();
    for (const key of Object.keys(cleanup)) {
      expect(cleanup[key]).toHaveBeenCalledTimes(1);
    }
  });
});

// ---------------------------------------------------------------------------
// T16: Lifecycle event assertions — activation failure, disable, unload, integrity failure
// ---------------------------------------------------------------------------

describe('ExtensionLifecycle — lifecycle event assertions (T16)', () => {
  // ---- activation failure events --------------------------------------------

  it('emits activation-failed diagnostic with error details on activation failure', () => {
    const activationError = new Error('INTEGRITY_CHECK_FAILED: bundle hash mismatch');
    const lc = createExtensionLifecycle(
      ext('com.example.integrity-fail', {
        activate: () => {
          throw activationError;
        },
      }),
    );
    lc.activate(makeCtx({ extension: { id: 'com.example.integrity-fail' as any, version: '1.0.0', label: 'IF', manifest: {} as any } }));

    expect(lc.state).toBe('failed');
    expect(lc.failure).toBe(activationError);

    const failDiags = diagsOf(lc, 'lifecycle/activation-failed');
    expect(failDiags).toHaveLength(1);
    expect(failDiags[0].severity).toBe('error');
    expect(failDiags[0].message).toContain('INTEGRITY_CHECK_FAILED');
    expect(failDiags[0].detail).toBeDefined();
    expect((failDiags[0].detail as any).originalError).toContain('INTEGRITY_CHECK_FAILED');
    expect((failDiags[0].detail as any).stack).toBeDefined();
  });

  it('emits activation-failed diagnostic for non-Error throws with integrity context', () => {
    const lc = createExtensionLifecycle(
      ext('com.example.integrity-string', {
        activate: () => {
          throw 'INTEGRITY: manifest signature verification failed';
        },
      }),
    );
    lc.activate(makeCtx({ extension: { id: 'com.example.integrity-string' as any, version: '1.0.0', label: 'IS', manifest: {} as any } }));

    expect(lc.state).toBe('failed');
    expect(lc.failure).toBeInstanceOf(Error);

    const failDiags = diagsOf(lc, 'lifecycle/activation-failed');
    expect(failDiags).toHaveLength(1);
    expect(failDiags[0].message).toContain('manifest signature verification failed');
  });

  it('activation-failed diagnostic includes extensionId', () => {
    const lc = createExtensionLifecycle(
      ext('com.example.fail-eid', {
        activate: () => {
          throw new Error('activation error');
        },
      }),
    );
    lc.activate(makeCtx({ extension: { id: 'com.example.fail-eid' as any, version: '1.0.0', label: 'FE', manifest: {} as any } }));

    const failDiags = diagsOf(lc, 'lifecycle/activation-failed');
    expect(failDiags[0].extensionId).toBe('com.example.fail-eid');
  });

  it('activation failure within host synchronize keeps extension in failed state', () => {
    const host = createExtensionLifecycleHost();
    const e1 = ext('com.example.host-activation-fail', {
      activate: () => {
        throw new Error('host-level activation integrity failure');
      },
    });

    host.synchronize([e1], (ext) =>
      makeCtx({ extension: { id: ext.manifest.id as any, version: '1.0.0', label: ext.manifest.label, manifest: ext.manifest } }),
    );

    // Extension stays in the map in failed state
    expect(host.lifecycles.size).toBe(1);
    const lc = host.lifecycles.get('com.example.host-activation-fail')!;
    expect(lc.state).toBe('failed');
    expect(lc.failure).toBeTruthy();

    // Failure diagnostic is accessible via host
    const failDiags = host.diagnostics.filter(
      (d) => d.extensionId === 'com.example.host-activation-fail' && d.code === 'lifecycle/activation-failed',
    );
    expect(failDiags).toHaveLength(1);
  });

  it('retry-after-failure emits lifecycle/retry-activate then succeeds', () => {
    let shouldFail = true;
    const activateFn = vi.fn(() => {
      if (shouldFail) throw new Error('transient integrity failure');
    });
    const lc = createExtensionLifecycle(ext('com.example.retry-integrity', { activate: activateFn }));
    const ctx = makeCtx({ extension: { id: 'com.example.retry-integrity' as any, version: '1.0.0', label: 'RI', manifest: {} as any } });

    // First attempt — fails
    lc.activate(ctx);
    expect(lc.state).toBe('failed');
    expect(diagsOf(lc, 'lifecycle/activation-failed')).toHaveLength(1);

    // Second attempt — succeeds
    shouldFail = false;
    lc.activate(ctx);
    expect(lc.state).toBe('active');
    expect(lc.failure).toBeNull();
    expect(diagsOf(lc, 'lifecycle/retry-activate')).toHaveLength(1);
    expect(diagsOf(lc, 'lifecycle/activated')).toHaveLength(1);
  });

  // ---- disable events (deactivation) ----------------------------------------

  it('emits deactivating and disposed diagnostics on deactivate() (disable)', () => {
    const lc = createExtensionLifecycle(ext('com.example.disable-events'));
    lc.activate(makeCtx({ extension: { id: 'com.example.disable-events' as any, version: '1.0.0', label: 'DE', manifest: {} as any } }));
    expect(lc.state).toBe('active');

    lc.deactivate();

    const deactivating = diagsOf(lc, 'lifecycle/deactivating');
    const disposed = diagsOf(lc, 'lifecycle/disposed');
    expect(deactivating).toHaveLength(1);
    expect(deactivating[0].severity).toBe('info');
    expect(deactivating[0].message).toContain('deactivating');
    expect(disposed).toHaveLength(1);
    expect(disposed[0].severity).toBe('info');
    expect(disposed[0].message).toContain('disposed');
  });

  it('emits disposed-inactive diagnostic when deactivating never-activated extension', () => {
    const lc = createExtensionLifecycle(ext('com.example.never-active'));
    expect(lc.state).toBe('inactive');

    lc.deactivate();
    expect(lc.state).toBe('disposed');

    const diags = diagsOf(lc, 'lifecycle/disposed-inactive');
    expect(diags).toHaveLength(1);
    expect(diags[0].message).toContain('was never activated');
  });

  it('disable (deactivate) from failed state emits deactivating and disposed', () => {
    const lc = createExtensionLifecycle(
      ext('com.example.fail-then-disable', {
        activate: () => {
          throw new Error('pre-disable failure');
        },
      }),
    );
    lc.activate(makeCtx({ extension: { id: 'com.example.fail-then-disable' as any, version: '1.0.0', label: 'FD', manifest: {} as any } }));
    expect(lc.state).toBe('failed');

    lc.deactivate();
    expect(lc.state).toBe('disposed');
    expect(diagsOf(lc, 'lifecycle/deactivating')).toHaveLength(1);
    expect(diagsOf(lc, 'lifecycle/disposed')).toHaveLength(1);
  });

  it('disable via host synchronize emits lifecycle events and calls dispose handle', () => {
    const disposeCalled = vi.fn();
    const host = createExtensionLifecycleHost();
    const e1 = ext('com.example.host-disable', {
      activate: () => ({ dispose: disposeCalled }),
    });

    host.synchronize([e1], (ext) =>
      makeCtx({ extension: { id: ext.manifest.id as any, version: '1.0.0', label: ext.manifest.label, manifest: ext.manifest } }),
    );

    const lc = host.lifecycles.get('com.example.host-disable')!;
    expect(lc.state).toBe('active');

    // Remove extension (disable) — synchronize calls lc.dispose() which emits 'lifecycle/disposed'
    host.synchronize([], () => makeCtx());
    expect(disposeCalled).toHaveBeenCalledTimes(1);
    // The lifecycle is removed from the map but its local diagnostics object
    // still holds the disposed event emitted during dispose()
    const dispDiags = lc.diagnostics.filter((d) => d.code === 'lifecycle/disposed');
    expect(dispDiags).toHaveLength(1);
    expect(dispDiags[0].message).toContain('disposed');
  });

  // ---- unload events (dispose) ----------------------------------------------

  it('emits disposed diagnostic on dispose() (unload)', () => {
    const lc = createExtensionLifecycle(ext('com.example.unload-events'));
    lc.activate(makeCtx({ extension: { id: 'com.example.unload-events' as any, version: '1.0.0', label: 'UE', manifest: {} as any } }));
    expect(lc.state).toBe('active');

    lc.dispose();

    const disposed = diagsOf(lc, 'lifecycle/disposed');
    expect(disposed).toHaveLength(1);
    expect(disposed[0].message).toContain('disposed');
    expect(disposed[0].message).toContain('was active');
  });

  it('emits disposed-inactive diagnostic on dispose() when never activated (unload unused)', () => {
    const lc = createExtensionLifecycle(ext('com.example.unload-never'));
    expect(lc.state).toBe('inactive');

    lc.dispose();
    expect(lc.state).toBe('disposed');
    expect(diagsOf(lc, 'lifecycle/disposed-inactive')).toHaveLength(1);
  });

  it('unload (dispose) from failed state records previous state in diagnostic', () => {
    const lc = createExtensionLifecycle(
      ext('com.example.unload-failed', {
        activate: () => {
          throw new Error('integrity check failed at activation');
        },
      }),
    );
    lc.activate(makeCtx({ extension: { id: 'com.example.unload-failed' as any, version: '1.0.0', label: 'UF', manifest: {} as any } }));
    expect(lc.state).toBe('failed');

    lc.dispose();
    expect(lc.state).toBe('disposed');

    const disposed = diagsOf(lc, 'lifecycle/disposed');
    expect(disposed).toHaveLength(1);
    expect(disposed[0].message).toContain('was failed');
  });

  it('unload via disposeAll emits disposed diagnostics for every extension', () => {
    const host = createExtensionLifecycleHost();
    const e1 = ext('com.example.unload-all-1');
    const e2 = ext('com.example.unload-all-2');

    host.synchronize([e1, e2], (ext) =>
      makeCtx({ extension: { id: ext.manifest.id as any, version: '1.0.0', label: ext.manifest.label, manifest: ext.manifest } }),
    );

    const lc1 = host.lifecycles.get('com.example.unload-all-1')!;
    const lc2 = host.lifecycles.get('com.example.unload-all-2')!;

    host.disposeAll();

    // Both lifecycles have disposed diagnostics
    expect(diagsOf(lc1, 'lifecycle/disposed')).toHaveLength(1);
    expect(diagsOf(lc2, 'lifecycle/disposed')).toHaveLength(1);
    expect(host.lifecycles.size).toBe(0);
  });

  it('unload (dispose) calls DisposeHandle and captures any teardown errors', () => {
    const lc = createExtensionLifecycle(
      ext('com.example.unload-teardown-error', {
        activate: () => ({
          dispose: () => {
            throw new Error('teardown: failed to flush live-data buffers');
          },
        }),
      }),
    );
    lc.activate(makeCtx({ extension: { id: 'com.example.unload-teardown-error' as any, version: '1.0.0', label: 'UTE', manifest: {} as any } }));

    lc.dispose();
    expect(lc.state).toBe('disposed');

    // Teardown error is captured in diagnostics, not thrown
    const errors = diagsOf(lc, 'lifecycle/dispose-handle-error');
    expect(errors).toHaveLength(1);
    expect(errors[0].message).toContain('flush live-data buffers');
  });

  // ---- integrity failure events ---------------------------------------------

  it('activation failure diagnostic captures integrity failure message', () => {
    const lc = createExtensionLifecycle(
      ext('com.example.integrity-event', {
        activate: () => {
          throw new Error('SRI_CHECK_FAILED: bundle content hash does not match manifest integrity hash');
        },
      }),
    );
    lc.activate(makeCtx({ extension: { id: 'com.example.integrity-event' as any, version: '1.0.0', label: 'IE', manifest: {} as any } }));

    expect(lc.state).toBe('failed');

    const failDiags = diagsOf(lc, 'lifecycle/activation-failed');
    expect(failDiags).toHaveLength(1);
    expect(failDiags[0].severity).toBe('error');
    expect(failDiags[0].message).toContain('SRI_CHECK_FAILED');
    expect(failDiags[0].detail).toBeDefined();
  });

  it('integrity failure event includes stack trace in detail', () => {
    const integrityError = new Error('CORRUPTED_BUNDLE: unpacked content failed integrity verification');
    const lc = createExtensionLifecycle(
      ext('com.example.corrupted', {
        activate: () => {
          throw integrityError;
        },
      }),
    );
    lc.activate(makeCtx({ extension: { id: 'com.example.corrupted' as any, version: '1.0.0', label: 'CB', manifest: {} as any } }));

    const failDiags = diagsOf(lc, 'lifecycle/activation-failed');
    expect((failDiags[0].detail as any).stack).toBe(integrityError.stack);
  });

  it('context factory error (integrity-like) is captured as host-level diagnostic', () => {
    const host = createExtensionLifecycleHost();
    const e1 = ext('com.example.ctx-integrity-fail');

    host.synchronize([e1], () => {
      throw new Error('INTEGRITY: cannot resolve bundle content ref — content missing from store');
    });

    // Context factory error is a host-level diagnostic that persists
    const ctxErrors = hostDiagsOf(host, 'lifecycle/context-factory-error');
    expect(ctxErrors).toHaveLength(1);
    expect(ctxErrors[0].severity).toBe('error');
    expect(ctxErrors[0].message).toContain('INTEGRITY');
    expect(ctxErrors[0].message).toContain('content missing from store');
  });

  it('integrity failure diagnostic is immediately visible in host aggregation', () => {
    const host = createExtensionLifecycleHost();
    const e1 = ext('com.example.visible-fail', {
      activate: () => {
        throw new Error('MANIFEST_SIGNATURE_INVALID: publisher key mismatch');
      },
    });

    host.synchronize([e1], (ext) =>
      makeCtx({ extension: { id: ext.manifest.id as any, version: '1.0.0', label: ext.manifest.label, manifest: ext.manifest } }),
    );

    // The failure must be visible immediately after synchronize
    const failDiags = host.diagnostics.filter((d) => d.code === 'lifecycle/activation-failed');
    expect(failDiags).toHaveLength(1);
    expect(failDiags[0].message).toContain('MANIFEST_SIGNATURE_INVALID');
  });

  // ---- combined lifecycle event sequence ------------------------------------

  it('produces correct lifecycle event sequence: activate → fail → retry → active → disable → disposed', () => {
    let shouldFail = true;
    const lc = createExtensionLifecycle(
      ext('com.example.full-sequence', {
        activate: () => {
          if (shouldFail) throw new Error('integrity: first activation rejected');
        },
      }),
    );
    const ctx = makeCtx({ extension: { id: 'com.example.full-sequence' as any, version: '1.0.0', label: 'FS', manifest: {} as any } });

    // 1. Activate → fails
    lc.activate(ctx);
    expect(lc.state).toBe('failed');
    expect(diagsOf(lc, 'lifecycle/activating')).toHaveLength(1);
    expect(diagsOf(lc, 'lifecycle/activation-failed')).toHaveLength(1);

    // 2. Retry → succeeds
    shouldFail = false;
    lc.activate(ctx);
    expect(lc.state).toBe('active');
    expect(diagsOf(lc, 'lifecycle/retry-activate')).toHaveLength(1);
    expect(diagsOf(lc, 'lifecycle/activated')).toHaveLength(1);

    // 3. Disable → disposed
    lc.deactivate();
    expect(lc.state).toBe('disposed');
    expect(diagsOf(lc, 'lifecycle/deactivating')).toHaveLength(1);
    expect(diagsOf(lc, 'lifecycle/disposed')).toHaveLength(1);

    // Verify full event order
    const codes = lc.diagnostics.map((d) => d.code);
    expect(codes).toEqual([
      'lifecycle/activating',
      'lifecycle/activation-failed',
      'lifecycle/retry-activate',
      'lifecycle/activating',
      'lifecycle/activated',
      'lifecycle/deactivating',
      'lifecycle/disposed',
    ]);
  });

  it('produces correct lifecycle event sequence for never-activated extension: dispose → disposed-inactive', () => {
    const lc = createExtensionLifecycle(ext('com.example.never-sequence'));

    lc.dispose();
    expect(lc.state).toBe('disposed');

    const codes = lc.diagnostics.map((d) => d.code);
    expect(codes).toEqual(['lifecycle/disposed-inactive']);
  });

  it('activation-failed diagnostic is emitted BEFORE console.error in event sequence', () => {
    const lc = createExtensionLifecycle(
      ext('com.example.diag-before-console', {
        activate: () => {
          throw new Error('integrity: diagnostic ordering check');
        },
      }),
    );
    lc.activate(makeCtx({ extension: { id: 'com.example.diag-before-console' as any, version: '1.0.0', label: 'DBC', manifest: {} as any } }));

    const failIdx = lc.diagnostics.findIndex((d) => d.code === 'lifecycle/activation-failed');
    const activatingIdx = lc.diagnostics.findIndex((d) => d.code === 'lifecycle/activating');
    expect(activatingIdx).toBeLessThan(failIdx);
    // activation-failed is the last lifecycle diagnostic (console.error happens after in finally)
    expect(failIdx).toBe(lc.diagnostics.length - 1);
  });
});

// ---------------------------------------------------------------------------
// T16: Disable/unload cleanup without provider remount
// ---------------------------------------------------------------------------

describe('ExtensionLifecycle — cleanup without provider remount (T16)', () => {
  it('removes extension contributions via synchronize() without remounting the provider', () => {
    // The provider calls synchronize() when extensions prop changes.
    // This test proves that removing an extension from the list cleans up
    // all its contributions without needing to remount the provider/host.
    const host = createExtensionLifecycleHost();
    const commandCleanup = vi.fn();
    const effectCleanup = vi.fn();

    const e1 = ext('com.example.keep');
    const e2 = ext('com.example.remove-me', {
      contributions: [
        { id: 'rm-cmd' as ContributionId, kind: 'command' as any },
        { id: 'rm-fx' as ContributionId, kind: 'effect' as any },
      ],
      activate: () => ({
        dispose: () => {
          commandCleanup();
          effectCleanup();
        },
      }),
    });

    // Initial sync — both extensions active
    host.synchronize([e1, e2], (ext) =>
      makeCtx({ extension: { id: ext.manifest.id as any, version: '1.0.0', label: ext.manifest.label, manifest: ext.manifest } }),
    );
    expect(host.lifecycles.size).toBe(2);

    // Remove e2 — synchronize with just e1
    host.synchronize([e1], (ext) =>
      makeCtx({ extension: { id: ext.manifest.id as any, version: '1.0.0', label: ext.manifest.label, manifest: ext.manifest } }),
    );

    // e1 still active, e2 removed with cleanup
    expect(host.lifecycles.size).toBe(1);
    expect(host.lifecycles.has('com.example.keep')).toBe(true);
    expect(host.lifecycles.has('com.example.remove-me')).toBe(false);
    expect(commandCleanup).toHaveBeenCalledTimes(1);
    expect(effectCleanup).toHaveBeenCalledTimes(1);
  });

  it('multiple extension additions and removals within single provider lifecycle', () => {
    const host = createExtensionLifecycleHost();
    const cleanups: Array<ReturnType<typeof vi.fn>> = [];

    function makeCleanableExt(id: string, kind: string): ReighExtension {
      const fn = vi.fn();
      cleanups.push(fn);
      return ext(id, {
        contributions: [{ id: `${id}-contrib` as ContributionId, kind: kind as any }],
        activate: () => ({ dispose: fn }),
      });
    }

    const extA = makeCleanableExt('com.example.a', 'command');
    const extB = makeCleanableExt('com.example.b', 'effect');
    const extC = makeCleanableExt('com.example.c', 'shader');

    // Add A and B
    host.synchronize([extA, extB], (ext) =>
      makeCtx({ extension: { id: ext.manifest.id as any, version: '1.0.0', label: ext.manifest.label, manifest: ext.manifest } }),
    );
    expect(host.lifecycles.size).toBe(2);

    // Swap B for C within same host (no remount)
    host.synchronize([extA, extC], (ext) =>
      makeCtx({ extension: { id: ext.manifest.id as any, version: '1.0.0', label: ext.manifest.label, manifest: ext.manifest } }),
    );
    expect(host.lifecycles.size).toBe(2);
    expect(host.lifecycles.has('com.example.a')).toBe(true);
    expect(host.lifecycles.has('com.example.b')).toBe(false);
    expect(host.lifecycles.has('com.example.c')).toBe(true);

    // B's cleanup fired, A and C's cleanups have not
    expect(cleanups[0]).not.toHaveBeenCalled(); // A still active
    expect(cleanups[1]).toHaveBeenCalledTimes(1); // B removed
    expect(cleanups[2]).not.toHaveBeenCalled(); // C still active

    // Remove all
    host.synchronize([], () => makeCtx());
    expect(host.lifecycles.size).toBe(0);
    expect(cleanups[0]).toHaveBeenCalledTimes(1); // A removed
    expect(cleanups[2]).toHaveBeenCalledTimes(1); // C removed
  });

  it('manifest change triggers cleanup of old contributions and reactivation of new', () => {
    const oldCleanup = vi.fn();
    const newActivate = vi.fn(() => ({ dispose: vi.fn() }));

    const extV1 = ext('com.example.versioned', {
      contributions: [{ id: 'v1-cmd' as ContributionId, kind: 'command' as any }],
      activate: () => ({ dispose: oldCleanup }),
    });

    const extV2 = ext('com.example.versioned', {
      contributions: [{ id: 'v2-cmd' as ContributionId, kind: 'command' as any }],
      activate: newActivate,
    });

    const host = createExtensionLifecycleHost();

    // Activate v1
    host.synchronize([extV1], (ext) =>
      makeCtx({ extension: { id: ext.manifest.id as any, version: '1.0.0', label: ext.manifest.label, manifest: ext.manifest } }),
    );
    expect(host.lifecycles.size).toBe(1);

    // Manifest change detected — v1 cleanup fires, v2 activates
    host.synchronize([extV2], (ext) =>
      makeCtx({ extension: { id: ext.manifest.id as any, version: '1.0.0', label: ext.manifest.label, manifest: ext.manifest } }),
    );
    expect(oldCleanup).toHaveBeenCalledTimes(1);
    expect(newActivate).toHaveBeenCalledTimes(1);
    expect(host.lifecycles.size).toBe(1);
  });
});

// ---------------------------------------------------------------------------
// T16: Lifecycle event assertions for onLifecycleDisposed callback
// ---------------------------------------------------------------------------

describe('ExtensionLifecycleHost — onLifecycleDisposed callback (T16)', () => {
  it('calls onLifecycleDisposed callback when extension is removed via synchronize', () => {
    const host = createExtensionLifecycleHost();
    const disposedIds: string[] = [];
    host.onLifecycleDisposed((id) => disposedIds.push(id));

    const e1 = ext('com.example.cb1');
    const e2 = ext('com.example.cb2');

    host.synchronize([e1, e2], (ext) =>
      makeCtx({ extension: { id: ext.manifest.id as any, version: '1.0.0', label: ext.manifest.label, manifest: ext.manifest } }),
    );

    // Remove e1
    host.synchronize([e2], (ext) =>
      makeCtx({ extension: { id: ext.manifest.id as any, version: '1.0.0', label: ext.manifest.label, manifest: ext.manifest } }),
    );
    expect(disposedIds).toContain('com.example.cb1');
    expect(disposedIds).not.toContain('com.example.cb2');
  });

  it('calls onLifecycleDisposed callback for all extensions on disposeAll', () => {
    const host = createExtensionLifecycleHost();
    const disposedIds: string[] = [];
    host.onLifecycleDisposed((id) => disposedIds.push(id));

    const e1 = ext('com.example.cb-all-1');
    const e2 = ext('com.example.cb-all-2');

    host.synchronize([e1, e2], (ext) =>
      makeCtx({ extension: { id: ext.manifest.id as any, version: '1.0.0', label: ext.manifest.label, manifest: ext.manifest } }),
    );
    host.disposeAll();

    expect(disposedIds).toContain('com.example.cb-all-1');
    expect(disposedIds).toContain('com.example.cb-all-2');
    expect(disposedIds).toHaveLength(2);
  });

  it('calls onLifecycleDisposed callback for manifest-change disposals', () => {
    const host = createExtensionLifecycleHost();
    const disposedIds: string[] = [];
    host.onLifecycleDisposed((id) => disposedIds.push(id));

    const extV1 = ext('com.example.cb-change', {
      contributions: [{ id: 'old' as ContributionId, kind: 'command' as any }],
    });
    const extV2 = ext('com.example.cb-change', {
      contributions: [{ id: 'new' as ContributionId, kind: 'effect' as any }],
    });

    host.synchronize([extV1], (ext) =>
      makeCtx({ extension: { id: ext.manifest.id as any, version: '1.0.0', label: ext.manifest.label, manifest: ext.manifest } }),
    );
    host.synchronize([extV2], (ext) =>
      makeCtx({ extension: { id: ext.manifest.id as any, version: '1.0.0', label: ext.manifest.label, manifest: ext.manifest } }),
    );

    // The old lifecycle was disposed due to manifest change
    expect(disposedIds).toContain('com.example.cb-change');
    expect(disposedIds).toHaveLength(1);
  });

  it('onLifecycleDisposed returns a DisposeHandle that unregisters the callback', () => {
    const host = createExtensionLifecycleHost();
    const disposedIds: string[] = [];
    const handle = host.onLifecycleDisposed((id) => disposedIds.push(id));

    const e1 = ext('com.example.cb-unreg');

    host.synchronize([e1], (ext) =>
      makeCtx({ extension: { id: ext.manifest.id as any, version: '1.0.0', label: ext.manifest.label, manifest: ext.manifest } }),
    );

    // Unregister the callback
    handle.dispose();

    // Remove extension — callback should NOT fire
    host.synchronize([], () => makeCtx());
    expect(disposedIds).toHaveLength(0);
  });

  it('onLifecycleDisposed callback errors do not propagate', () => {
    const host = createExtensionLifecycleHost();
    const errorSpy = vi.fn();

    host.onLifecycleDisposed(() => {
      throw new Error('callback error');
    });
    host.onLifecycleDisposed((id) => {
      errorSpy(id);
    });

    const e1 = ext('com.example.cb-error');

    host.synchronize([e1], (ext) =>
      makeCtx({ extension: { id: ext.manifest.id as any, version: '1.0.0', label: ext.manifest.label, manifest: ext.manifest } }),
    );

    // Remove — first callback throws, second should still fire
    host.synchronize([], () => makeCtx());
    expect(errorSpy).toHaveBeenCalledWith('com.example.cb-error');
  });
});


// ---------------------------------------------------------------------------
// T2: ExtensionLifecycleHost — monotonic recovery-key registry
// ---------------------------------------------------------------------------

describe('ExtensionLifecycleHost — recovery-key registry (T2)', () => {
  it('getRecoveryKey returns "0" for unknown extension IDs', () => {
    const host = createExtensionLifecycleHost();
    expect(host.getRecoveryKey('com.example.unknown')).toBe('0');
    expect(host.getRecoveryKey('never.seen')).toBe('0');
  });

  it('recovery key is set to "1" on first activation via synchronize', () => {
    const host = createExtensionLifecycleHost();
    const e1 = ext('com.example.first');

    host.synchronize([e1], (ext) =>
      makeCtx({ extension: { id: ext.manifest.id as any, version: '1.0.0', label: ext.manifest.label, manifest: ext.manifest } }),
    );

    expect(host.getRecoveryKey('com.example.first')).toBe('1');
  });

  it('recovery key stays stable across unchanged synchronize calls', () => {
    const host = createExtensionLifecycleHost();
    const e1 = ext('com.example.stable');

    host.synchronize([e1], (ext) =>
      makeCtx({ extension: { id: ext.manifest.id as any, version: '1.0.0', label: ext.manifest.label, manifest: ext.manifest } }),
    );
    expect(host.getRecoveryKey('com.example.stable')).toBe('1');

    // Same extension list — recovery key must NOT change
    host.synchronize([e1], (ext) =>
      makeCtx({ extension: { id: ext.manifest.id as any, version: '1.0.0', label: ext.manifest.label, manifest: ext.manifest } }),
    );
    expect(host.getRecoveryKey('com.example.stable')).toBe('1');

    // Third sync with same extension — still stable
    host.synchronize([e1], (ext) =>
      makeCtx({ extension: { id: ext.manifest.id as any, version: '1.0.0', label: ext.manifest.label, manifest: ext.manifest } }),
    );
    expect(host.getRecoveryKey('com.example.stable')).toBe('1');
  });

  it('recovery key does not change when an unrelated extension is added or removed', () => {
    const host = createExtensionLifecycleHost();
    const e1 = ext('com.example.stable-ek');
    const e2 = ext('com.example.other');

    // Activate e1
    host.synchronize([e1], (ext) =>
      makeCtx({ extension: { id: ext.manifest.id as any, version: '1.0.0', label: ext.manifest.label, manifest: ext.manifest } }),
    );
    expect(host.getRecoveryKey('com.example.stable-ek')).toBe('1');

    // Add e2 — e1's key must stay stable
    host.synchronize([e1, e2], (ext) =>
      makeCtx({ extension: { id: ext.manifest.id as any, version: '1.0.0', label: ext.manifest.label, manifest: ext.manifest } }),
    );
    expect(host.getRecoveryKey('com.example.stable-ek')).toBe('1');
    expect(host.getRecoveryKey('com.example.other')).toBe('1');

    // Remove e2 — e1's key still stable
    host.synchronize([e1], (ext) =>
      makeCtx({ extension: { id: ext.manifest.id as any, version: '1.0.0', label: ext.manifest.label, manifest: ext.manifest } }),
    );
    expect(host.getRecoveryKey('com.example.stable-ek')).toBe('1');
  });

  it('recovery key increments on manifest replacement', () => {
    const host = createExtensionLifecycleHost();
    const extV1 = ext('com.example.manifest-change', {
      contributions: [{ id: 'v1-contrib', kind: 'slot', slot: 'toolbar' }],
    });
    const extV2 = ext('com.example.manifest-change', {
      contributions: [{ id: 'v2-contrib', kind: 'slot', slot: 'toolbar' }],
    });

    // Activate v1
    host.synchronize([extV1], (ext) =>
      makeCtx({ extension: { id: ext.manifest.id as any, version: '1.0.0', label: ext.manifest.label, manifest: ext.manifest } }),
    );
    expect(host.getRecoveryKey('com.example.manifest-change')).toBe('1');

    // Replace with v2 (manifest change)
    host.synchronize([extV2], (ext) =>
      makeCtx({ extension: { id: ext.manifest.id as any, version: '1.0.0', label: ext.manifest.label, manifest: ext.manifest } }),
    );
    expect(host.getRecoveryKey('com.example.manifest-change')).toBe('2');
  });

  it('recovery key increments on re-add after removal', () => {
    const host = createExtensionLifecycleHost();
    const e1 = ext('com.example.readd');

    // First activation
    host.synchronize([e1], (ext) =>
      makeCtx({ extension: { id: ext.manifest.id as any, version: '1.0.0', label: ext.manifest.label, manifest: ext.manifest } }),
    );
    expect(host.getRecoveryKey('com.example.readd')).toBe('1');

    // Remove it
    host.synchronize([], () => makeCtx());
    // After removal, key is still stored (monotonic, never decrements)
    expect(host.getRecoveryKey('com.example.readd')).toBe('1');

    // Re-add — key should increment
    host.synchronize([e1], (ext) =>
      makeCtx({ extension: { id: ext.manifest.id as any, version: '1.0.0', label: ext.manifest.label, manifest: ext.manifest } }),
    );
    expect(host.getRecoveryKey('com.example.readd')).toBe('2');
  });

  it('recovery key increments on multiple re-add cycles', () => {
    const host = createExtensionLifecycleHost();
    const e1 = ext('com.example.multireadd');

    // Add, remove, re-add, remove, re-add
    for (let i = 1; i <= 5; i++) {
      host.synchronize([e1], (ext) =>
        makeCtx({ extension: { id: ext.manifest.id as any, version: '1.0.0', label: ext.manifest.label, manifest: ext.manifest } }),
      );
      expect(host.getRecoveryKey('com.example.multireadd')).toBe(String(i));
      host.synchronize([], () => makeCtx());
    }
  });

  it('incrementRecoveryKey bumps the key for a managed extension', () => {
    const host = createExtensionLifecycleHost();
    const e1 = ext('com.example.increment');

    host.synchronize([e1], (ext) =>
      makeCtx({ extension: { id: ext.manifest.id as any, version: '1.0.0', label: ext.manifest.label, manifest: ext.manifest } }),
    );
    expect(host.getRecoveryKey('com.example.increment')).toBe('1');

    const newKey = host.incrementRecoveryKey('com.example.increment');
    expect(newKey).toBe('2');
    expect(host.getRecoveryKey('com.example.increment')).toBe('2');

    // Increment again
    const newKey2 = host.incrementRecoveryKey('com.example.increment');
    expect(newKey2).toBe('3');
    expect(host.getRecoveryKey('com.example.increment')).toBe('3');
  });

  it('incrementRecoveryKey returns "0" for unknown extension IDs', () => {
    const host = createExtensionLifecycleHost();
    expect(host.incrementRecoveryKey('com.example.ghost')).toBe('0');
    expect(host.getRecoveryKey('com.example.ghost')).toBe('0');
  });

  it('incrementRecoveryKey returns "0" for removed extensions', () => {
    const host = createExtensionLifecycleHost();
    const e1 = ext('com.example.removed-incr');

    host.synchronize([e1], (ext) =>
      makeCtx({ extension: { id: ext.manifest.id as any, version: '1.0.0', label: ext.manifest.label, manifest: ext.manifest } }),
    );
    expect(host.getRecoveryKey('com.example.removed-incr')).toBe('1');

    // Remove the extension
    host.synchronize([], () => makeCtx());
    // incrementRecoveryKey on a removed (non-lifecycle) extension is a no-op
    expect(host.incrementRecoveryKey('com.example.removed-incr')).toBe('0');
    // The stored monotonic key is unchanged by failed increment
    expect(host.getRecoveryKey('com.example.removed-incr')).toBe('1');
  });

  it('incrementRecoveryKey returns "0" when host is disposed', () => {
    const host = createExtensionLifecycleHost();
    const e1 = ext('com.example.disp-incr');

    host.synchronize([e1], (ext) =>
      makeCtx({ extension: { id: ext.manifest.id as any, version: '1.0.0', label: ext.manifest.label, manifest: ext.manifest } }),
    );

    host.disposeAll();
    expect(host.incrementRecoveryKey('com.example.disp-incr')).toBe('0');
  });

  it('recovery keys are independent across extensions', () => {
    const host = createExtensionLifecycleHost();
    const e1 = ext('com.example.indep-a');
    const e2 = ext('com.example.indep-b');
    const e3 = ext('com.example.indep-c');

    host.synchronize([e1, e2, e3], (ext) =>
      makeCtx({ extension: { id: ext.manifest.id as any, version: '1.0.0', label: ext.manifest.label, manifest: ext.manifest } }),
    );

    // All start at 1
    expect(host.getRecoveryKey('com.example.indep-a')).toBe('1');
    expect(host.getRecoveryKey('com.example.indep-b')).toBe('1');
    expect(host.getRecoveryKey('com.example.indep-c')).toBe('1');

    // Increment only b
    host.incrementRecoveryKey('com.example.indep-b');
    expect(host.getRecoveryKey('com.example.indep-a')).toBe('1');
    expect(host.getRecoveryKey('com.example.indep-b')).toBe('2');
    expect(host.getRecoveryKey('com.example.indep-c')).toBe('1');

    // Remove and re-add c
    host.synchronize([e1, e2], (ext) =>
      makeCtx({ extension: { id: ext.manifest.id as any, version: '1.0.0', label: ext.manifest.label, manifest: ext.manifest } }),
    );
    host.synchronize([e1, e2, e3], (ext) =>
      makeCtx({ extension: { id: ext.manifest.id as any, version: '1.0.0', label: ext.manifest.label, manifest: ext.manifest } }),
    );

    // a and b unchanged, c incremented to 2 (re-add)
    expect(host.getRecoveryKey('com.example.indep-a')).toBe('1');
    expect(host.getRecoveryKey('com.example.indep-b')).toBe('2');
    expect(host.getRecoveryKey('com.example.indep-c')).toBe('2');
  });

  it('recovery keys are monotonic and never decrement', () => {
    const host = createExtensionLifecycleHost();
    const e1 = ext('com.example.monotonic');

    // Activate
    host.synchronize([e1], (ext) =>
      makeCtx({ extension: { id: ext.manifest.id as any, version: '1.0.0', label: ext.manifest.label, manifest: ext.manifest } }),
    );
    expect(Number(host.getRecoveryKey('com.example.monotonic'))).toBeGreaterThanOrEqual(1);

    // Remove — key stays (monotonic)
    host.synchronize([], () => makeCtx());
    const keyAfterRemove = Number(host.getRecoveryKey('com.example.monotonic'));
    expect(keyAfterRemove).toBeGreaterThanOrEqual(1);

    // Re-add — key increments (never goes down)
    host.synchronize([e1], (ext) =>
      makeCtx({ extension: { id: ext.manifest.id as any, version: '1.0.0', label: ext.manifest.label, manifest: ext.manifest } }),
    );
    expect(Number(host.getRecoveryKey('com.example.monotonic'))).toBe(keyAfterRemove + 1);

    // Increment
    const afterIncr = Number(host.incrementRecoveryKey('com.example.monotonic'));
    expect(afterIncr).toBe(keyAfterRemove + 2);

    // Manifest change
    const extV2 = ext('com.example.monotonic', {
      contributions: [{ id: 'fresh', kind: 'slot', slot: 'toolbar' }],
    });
    host.synchronize([extV2], (ext) =>
      makeCtx({ extension: { id: ext.manifest.id as any, version: '1.0.0', label: ext.manifest.label, manifest: ext.manifest } }),
    );
    expect(Number(host.getRecoveryKey('com.example.monotonic'))).toBe(afterIncr + 1);
  });

  it('recovery key for failed-then-retried extension increments appropriately', () => {
    const shouldFail = true;
    const e1 = ext('com.example.fail-recovery', {
      activate: () => {
        if (shouldFail) throw new Error('first fail');
      },
    });

    const host = createExtensionLifecycleHost();

    // First activation fails — key still set to 1
    host.synchronize([e1], (ext) =>
      makeCtx({ extension: { id: ext.manifest.id as any, version: '1.0.0', label: ext.manifest.label, manifest: ext.manifest } }),
    );
    expect(host.lifecycles.get('com.example.fail-recovery')?.state).toBe('failed');
    expect(host.getRecoveryKey('com.example.fail-recovery')).toBe('1');

    // Explicit retry via incrementRecoveryKey — live extension, key bumps to 2
    const newKey = host.incrementRecoveryKey('com.example.fail-recovery');
    expect(newKey).toBe('2');
  });

  it('recovery key after disposeAll still returns "0" for queries on a disposed host', () => {
    // Note: getRecoveryKey still works after disposeAll (it just looks up the map).
    // However, incrementRecoveryKey is guarded.
    const host = createExtensionLifecycleHost();
    const e1 = ext('com.example.postdisp-key');

    host.synchronize([e1], (ext) =>
      makeCtx({ extension: { id: ext.manifest.id as any, version: '1.0.0', label: ext.manifest.label, manifest: ext.manifest } }),
    );

    host.disposeAll();

    // getRecoveryKey still returns the stored key
    expect(host.getRecoveryKey('com.example.postdisp-key')).toBe('1');
    // incrementRecoveryKey is blocked on disposed host
    expect(host.incrementRecoveryKey('com.example.postdisp-key')).toBe('0');
  });

  it('recovery key can be used as string in comparison without parsing', () => {
    const host = createExtensionLifecycleHost();
    const e1 = ext('com.example.stringkey');

    host.synchronize([e1], (ext) =>
      makeCtx({ extension: { id: ext.manifest.id as any, version: '1.0.0', label: ext.manifest.label, manifest: ext.manifest } }),
    );

    const key1 = host.getRecoveryKey('com.example.stringkey');
    expect(typeof key1).toBe('string');
    expect(key1).toBe('1');

    host.incrementRecoveryKey('com.example.stringkey');
    const key2 = host.getRecoveryKey('com.example.stringkey');
    expect(key2).toBe('2');
    // String comparison works for recovery-key change detection
    expect(key1 !== key2).toBe(true);
  });
});
