/**
 * Production-bundled smoke extension.
 *
 * Returns a statically-defined ReighExtension when the inert query parameter
 * `?extensionSmoke=1` is present.  The extension registers a tiny slot/status
 * contribution with a stable `data-testid`-equivalent identifier so E2E and
 * integration tests can verify the extension activation surface without
 * loading real user extensions.
 *
 * This module is intentionally free of dynamic imports, sandbox promises,
 * loaders, permission enforcement, or timeline mutation — it is a pure,
 * statically-bundled opt-in test hook with host-owned UI registration only.
 *
 * @publicContract
 */

import { defineExtension, type ReighExtension } from '../lifecycle';
import type { ContributionId, ExtensionId } from '../ids';
import { getInternalExtensionRenderSurface } from '../internalExtensionRenderSurface';
import { createElement } from 'react';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** The query-parameter name that triggers the smoke extension. */
export const EXTENSION_SMOKE_QUERY_PARAM = 'extensionSmoke';

/** The value that activates the smoke extension. */
export const EXTENSION_SMOKE_ACTIVE_VALUE = '1';

/** Stable contribution ID used as a test anchor (data-testid equivalent). */
export const EXTENSION_SMOKE_CONTRIBUTION_ID = 'extension-smoke-status';

// ---------------------------------------------------------------------------
// Smoke extension (lazily created, frozen by defineExtension)
// ---------------------------------------------------------------------------

let _smokeExtension: ReighExtension | undefined;

function createSmokeExtension(): ReighExtension {
  return defineExtension({
    manifest: {
      id: 'com.reigh.smoke.extension-smoke' as ExtensionId,
      version: '1.0.0',
      label: 'Production Smoke Extension',
      description:
        'Inert smoke extension activated via ?extensionSmoke=1. ' +
        'Provides a stable status-bar contribution for test hooks.',
      apiVersion: 1,
      contributions: [
        {
          id: EXTENSION_SMOKE_CONTRIBUTION_ID as ContributionId,
          kind: 'slot',
          slot: 'statusBar',
          render: EXTENSION_SMOKE_CONTRIBUTION_ID,
          order: 9999, // Sort last so it never collides visually
          label: 'Extension Smoke',
        },
      ],
    },
    activate(ctx) {
      const renderSurface = getInternalExtensionRenderSurface(ctx);
      if (!renderSurface) {
        return { dispose() {} };
      }

      return renderSurface.registerRenderer(
        EXTENSION_SMOKE_CONTRIBUTION_ID,
        () => createElement(
          'div',
          {
            'data-testid': EXTENSION_SMOKE_CONTRIBUTION_ID,
          },
          'Extension smoke active',
        ),
      );
    },
  });
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Parse a search-params source and return the smoke extension if the
 * `?extensionSmoke=1` trigger is present.
 *
 * Accepts a `URLSearchParams` instance, a raw query string (with or
 * without leading `?`), or `undefined`/`null` (returns null).
 *
 * @returns The frozen smoke extension, or `null` when the trigger is absent.
 */
export function getExtensionSmokeExtension(
  searchParams?: URLSearchParams | string | null,
): ReighExtension | null {
  const value = readSmokeParam(searchParams);
  if (value !== EXTENSION_SMOKE_ACTIVE_VALUE) {
    return null;
  }

  if (!_smokeExtension) {
    _smokeExtension = createSmokeExtension();
  }

  return _smokeExtension;
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

function readSmokeParam(
  source?: URLSearchParams | string | null,
): string | null {
  if (source === undefined || source === null) {
    return null;
  }

  if (typeof source === 'string') {
    const qs = source.startsWith('?') ? source.slice(1) : source;
    source = new URLSearchParams(qs);
  }

  return source.get(EXTENSION_SMOKE_QUERY_PARAM);
}
