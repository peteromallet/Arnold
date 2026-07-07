/**
 * Internal host-owned render-registration surface for bundled extensions.
 *
 * This is intentionally not re-exported from the public SDK barrel. It lets
 * the host wire real UI renderers for statically-bundled test extensions
 * without expanding the public extension context contract.
 */

import type { DisposeHandle } from './dispose';
import type { ExtensionContext } from './context';

export type InternalExtensionRenderer = (...args: unknown[]) => unknown;

export interface InternalExtensionRenderSurface {
  registerRenderer(
    renderId: string,
    renderer: InternalExtensionRenderer,
  ): DisposeHandle;
}

export const INTERNAL_EXTENSION_RENDER_SURFACE = Symbol(
  'reigh.internal.extension-render-surface',
);

export function attachInternalExtensionRenderSurface(
  target: object,
  surface: InternalExtensionRenderSurface,
): void {
  Object.defineProperty(target, INTERNAL_EXTENSION_RENDER_SURFACE, {
    value: surface,
    writable: false,
    enumerable: false,
    configurable: false,
  });
}

export function getInternalExtensionRenderSurface(
  ctx: ExtensionContext,
): InternalExtensionRenderSurface | null {
  const value = (ctx as unknown as Record<PropertyKey, unknown>)[
    INTERNAL_EXTENSION_RENDER_SURFACE
  ];
  if (!value || typeof value !== 'object') {
    return null;
  }

  const registerRenderer = (value as { registerRenderer?: unknown }).registerRenderer;
  if (typeof registerRenderer !== 'function') {
    return null;
  }

  return value as InternalExtensionRenderSurface;
}
