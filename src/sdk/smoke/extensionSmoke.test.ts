// @vitest-environment jsdom
/**
 * Unit tests for the production-bundled smoke extension.
 *
 * Covers:
 *  - No extension returned when the query parameter is absent.
 *  - Extension returned when `?extensionSmoke=1` is present.
 *  - Extension NOT returned for other values (0, true, empty, etc.).
 *  - Contribution structure (correct ID, kind, slot).
 *  - Extension passes defineExtension validation (frozen, valid IDs).
 *  - Idempotent: same extension instance returned on repeated calls.
 *  - Works with URLSearchParams, raw query strings, and null/undefined.
 *
 * @publicContract
 */

import { render, screen, cleanup } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { createElement, type ReactNode } from 'react';
import {
  getExtensionSmokeExtension,
  EXTENSION_SMOKE_QUERY_PARAM,
  EXTENSION_SMOKE_ACTIVE_VALUE,
  EXTENSION_SMOKE_CONTRIBUTION_ID,
} from '@/sdk/smoke/extensionSmoke';
import { INTERNAL_EXTENSION_RENDER_SURFACE } from '@/sdk/internalExtensionRenderSurface';
import type { ReighExtension, ExtensionContribution } from '@reigh/editor-sdk';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeSearchParams(params: Record<string, string>): URLSearchParams {
  const sp = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    sp.set(key, value);
  }
  return sp;
}

function findContribution(
  ext: ReighExtension,
  contribId: string,
): ExtensionContribution | undefined {
  return ext.manifest.contributions?.find((c) => c.id === (contribId as any));
}

afterEach(() => {
  cleanup();
});

// ---------------------------------------------------------------------------
// Absent / null / undefined trigger
// ---------------------------------------------------------------------------

describe('getExtensionSmokeExtension — absent trigger', () => {
  it('returns null when no search params are provided', () => {
    expect(getExtensionSmokeExtension()).toBeNull();
  });

  it('returns null when search params is null', () => {
    expect(getExtensionSmokeExtension(null)).toBeNull();
  });

  it('returns null when search params is an empty URLSearchParams', () => {
    expect(getExtensionSmokeExtension(new URLSearchParams())).toBeNull();
  });

  it('returns null when search params contains other keys but not the smoke key', () => {
    const sp = makeSearchParams({ foo: 'bar', baz: '1' });
    expect(getExtensionSmokeExtension(sp)).toBeNull();
  });

  it('returns null for an empty query string', () => {
    expect(getExtensionSmokeExtension('')).toBeNull();
  });

  it('returns null for a query string with unrelated params', () => {
    expect(getExtensionSmokeExtension('foo=bar&baz=1')).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// Active trigger: ?extensionSmoke=1
// ---------------------------------------------------------------------------

describe('getExtensionSmokeExtension — active trigger (?extensionSmoke=1)', () => {
  it('returns a ReighExtension when extensionSmoke=1 via URLSearchParams', () => {
    const sp = makeSearchParams({ [EXTENSION_SMOKE_QUERY_PARAM]: EXTENSION_SMOKE_ACTIVE_VALUE });
    const ext = getExtensionSmokeExtension(sp);
    expect(ext).not.toBeNull();
    expect(ext!.manifest.id).toBe('com.reigh.smoke.extension-smoke');
  });

  it('returns a ReighExtension when extensionSmoke=1 via raw query string (without ?)', () => {
    const ext = getExtensionSmokeExtension(`${EXTENSION_SMOKE_QUERY_PARAM}=${EXTENSION_SMOKE_ACTIVE_VALUE}`);
    expect(ext).not.toBeNull();
    expect(ext!.manifest.id).toBe('com.reigh.smoke.extension-smoke');
  });

  it('returns a ReighExtension when extensionSmoke=1 via raw query string (with ?)', () => {
    const ext = getExtensionSmokeExtension(`?${EXTENSION_SMOKE_QUERY_PARAM}=${EXTENSION_SMOKE_ACTIVE_VALUE}`);
    expect(ext).not.toBeNull();
    expect(ext!.manifest.id).toBe('com.reigh.smoke.extension-smoke');
  });

  it('returns the same frozen extension instance on repeated calls', () => {
    const sp = makeSearchParams({ [EXTENSION_SMOKE_QUERY_PARAM]: EXTENSION_SMOKE_ACTIVE_VALUE });
    const a = getExtensionSmokeExtension(sp);
    const b = getExtensionSmokeExtension(sp);
    expect(a).toBe(b);
    expect(Object.isFrozen(a!)).toBe(true);
    expect(Object.isFrozen(a!.manifest)).toBe(true);
  });

  it('returns extension with frozen nested structures', () => {
    const sp = makeSearchParams({ [EXTENSION_SMOKE_QUERY_PARAM]: EXTENSION_SMOKE_ACTIVE_VALUE });
    const ext = getExtensionSmokeExtension(sp)!;
    expect(Object.isFrozen(ext.manifest)).toBe(true);
    expect(Object.isFrozen(ext.manifest.contributions!)).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// Inactive trigger values (not '1')
// ---------------------------------------------------------------------------

describe('getExtensionSmokeExtension — inactive trigger values', () => {
  it('returns null for extensionSmoke=0', () => {
    const sp = makeSearchParams({ [EXTENSION_SMOKE_QUERY_PARAM]: '0' });
    expect(getExtensionSmokeExtension(sp)).toBeNull();
  });

  it('returns null for extensionSmoke=true', () => {
    const sp = makeSearchParams({ [EXTENSION_SMOKE_QUERY_PARAM]: 'true' });
    expect(getExtensionSmokeExtension(sp)).toBeNull();
  });

  it('returns null for extensionSmoke="" (empty)', () => {
    const sp = makeSearchParams({ [EXTENSION_SMOKE_QUERY_PARAM]: '' });
    expect(getExtensionSmokeExtension(sp)).toBeNull();
  });

  it('returns null for extensionSmoke=yes', () => {
    const sp = makeSearchParams({ [EXTENSION_SMOKE_QUERY_PARAM]: 'yes' });
    expect(getExtensionSmokeExtension(sp)).toBeNull();
  });

  it('returns null for extensionSmoke=2', () => {
    const sp = makeSearchParams({ [EXTENSION_SMOKE_QUERY_PARAM]: '2' });
    expect(getExtensionSmokeExtension(sp)).toBeNull();
  });

  it('returns null when extensionSmoke is present alongside other params but value is not 1', () => {
    const sp = makeSearchParams({
      [EXTENSION_SMOKE_QUERY_PARAM]: '0',
      foo: 'bar',
    });
    expect(getExtensionSmokeExtension(sp)).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// Contribution structure
// ---------------------------------------------------------------------------

describe('getExtensionSmokeExtension — contribution structure', () => {
  const sp = makeSearchParams({ [EXTENSION_SMOKE_QUERY_PARAM]: EXTENSION_SMOKE_ACTIVE_VALUE });

  it('has exactly one contribution', () => {
    const ext = getExtensionSmokeExtension(sp)!;
    expect(ext.manifest.contributions).toHaveLength(1);
  });

  it('contribution has the stable test-anchor ID', () => {
    const ext = getExtensionSmokeExtension(sp)!;
    const contrib = findContribution(ext, EXTENSION_SMOKE_CONTRIBUTION_ID);
    expect(contrib).toBeDefined();
  });

  it('contribution kind is slot', () => {
    const ext = getExtensionSmokeExtension(sp)!;
    const contrib = findContribution(ext, EXTENSION_SMOKE_CONTRIBUTION_ID)!;
    expect(contrib.kind).toBe('slot');
  });

  it('contribution slot is statusBar', () => {
    const ext = getExtensionSmokeExtension(sp)!;
    const contrib = findContribution(ext, EXTENSION_SMOKE_CONTRIBUTION_ID)!;
    expect(contrib.slot).toBe('statusBar');
  });

  it('contribution sorts last (order 9999)', () => {
    const ext = getExtensionSmokeExtension(sp)!;
    const contrib = findContribution(ext, EXTENSION_SMOKE_CONTRIBUTION_ID)!;
    expect(contrib.order).toBe(9999);
  });

  it('contribution has a label for diagnostics/UI', () => {
    const ext = getExtensionSmokeExtension(sp)!;
    const contrib = findContribution(ext, EXTENSION_SMOKE_CONTRIBUTION_ID)!;
    expect(contrib.label).toBe('Extension Smoke');
  });

  it('manifest has expected metadata', () => {
    const ext = getExtensionSmokeExtension(sp)!;
    expect(ext.manifest.version).toBe('1.0.0');
    expect(ext.manifest.label).toBe('Production Smoke Extension');
    expect(ext.manifest.apiVersion).toBe(1);
  });
});

// ---------------------------------------------------------------------------
// Manifest validation (via defineExtension)
// ---------------------------------------------------------------------------

describe('getExtensionSmokeExtension — manifest validation', () => {
  it('activation registers a renderer that produces the stable smoke anchor', () => {
    const sp = makeSearchParams({ [EXTENSION_SMOKE_QUERY_PARAM]: EXTENSION_SMOKE_ACTIVE_VALUE });
    const ext = getExtensionSmokeExtension(sp)!;
    expect(typeof ext.activate).toBe('function');

    const disposeRenderer = vi.fn();
    const registerRenderer = vi.fn((_renderId: string, renderer: () => ReactNode) => {
      render(createElement('div', null, renderer()));
      return { dispose: disposeRenderer };
    });
    const handle = ext.activate!({
      [INTERNAL_EXTENSION_RENDER_SURFACE]: { registerRenderer },
    } as any);

    expect(handle).toBeDefined();
    expect(typeof handle.dispose).toBe('function');
    expect(registerRenderer).toHaveBeenCalledWith(
      EXTENSION_SMOKE_CONTRIBUTION_ID,
      expect.any(Function),
    );
    expect(screen.getByTestId(EXTENSION_SMOKE_CONTRIBUTION_ID)).toHaveTextContent('Extension smoke active');
    expect(() => handle.dispose()).not.toThrow();
    expect(disposeRenderer).toHaveBeenCalledTimes(1);
  });

  it('activation returns a no-op disposable when the host render surface is unavailable', () => {
    const sp = makeSearchParams({ [EXTENSION_SMOKE_QUERY_PARAM]: EXTENSION_SMOKE_ACTIVE_VALUE });
    const ext = getExtensionSmokeExtension(sp)!;
    const handle = ext.activate!({} as any);
    expect(handle).toBeDefined();
    expect(typeof handle.dispose).toBe('function');
    expect(() => handle.dispose()).not.toThrow();
  });

  it('extension manifest has no permissions (inert)', () => {
    const sp = makeSearchParams({ [EXTENSION_SMOKE_QUERY_PARAM]: EXTENSION_SMOKE_ACTIVE_VALUE });
    const ext = getExtensionSmokeExtension(sp)!;
    expect(ext.manifest.permissions).toBeUndefined();
  });

  it('extension manifest has no dependencies', () => {
    const sp = makeSearchParams({ [EXTENSION_SMOKE_QUERY_PARAM]: EXTENSION_SMOKE_ACTIVE_VALUE });
    const ext = getExtensionSmokeExtension(sp)!;
    expect(ext.manifest.dependsOn).toBeUndefined();
  });
});

// ---------------------------------------------------------------------------
// Mixed query params
// ---------------------------------------------------------------------------

describe('getExtensionSmokeExtension — mixed query params', () => {
  it('returns extension when smoke=1 is present alongside other params', () => {
    const sp = makeSearchParams({
      [EXTENSION_SMOKE_QUERY_PARAM]: EXTENSION_SMOKE_ACTIVE_VALUE,
      timeline: 'abc123',
      addGenerationId: 'gen-456',
    });
    const ext = getExtensionSmokeExtension(sp);
    expect(ext).not.toBeNull();
    expect(ext!.manifest.id).toBe('com.reigh.smoke.extension-smoke');
  });

  it('returns null when smoke param is absent but other params are present', () => {
    const sp = makeSearchParams({
      timeline: 'abc123',
      addGenerationId: 'gen-456',
    });
    expect(getExtensionSmokeExtension(sp)).toBeNull();
  });
});
