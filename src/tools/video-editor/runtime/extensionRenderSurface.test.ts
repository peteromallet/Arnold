// @vitest-environment jsdom

import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { createElement } from 'react';
import { getExtensionSmokeExtension, EXTENSION_SMOKE_ACTIVE_VALUE, EXTENSION_SMOKE_CONTRIBUTION_ID, EXTENSION_SMOKE_QUERY_PARAM } from '@/sdk/smoke/extensionSmoke';
import { INTERNAL_EXTENSION_RENDER_SURFACE } from '@/sdk/internalExtensionRenderSurface';
import { normalizeExtensionRuntime } from '@/tools/video-editor/runtime/extensionSurface';
import { createRendererRegistry } from '@/tools/video-editor/runtime/extensionRendererRegistry';
import {
  createInternalExtensionRenderSurface,
  resolveRegisteredSlotRenderers,
} from '@/tools/video-editor/runtime/extensionRenderSurface';

afterEach(() => {
  cleanup();
});

describe('resolveRegisteredSlotRenderers', () => {
  it('projects the smoke status-bar renderer into the runtime config and removes it on dispose', () => {
    const extension = getExtensionSmokeExtension(
      new URLSearchParams({
        [EXTENSION_SMOKE_QUERY_PARAM]: EXTENSION_SMOKE_ACTIVE_VALUE,
      }),
    )!;
    const runtime = normalizeExtensionRuntime([extension]);
    const rendererRegistry = createRendererRegistry();
    const diagnosticsService = {
      report: vi.fn(),
      diagnostics: [],
    };
    const renderSurface = createInternalExtensionRenderSurface({
      extension,
      diagnosticsService: diagnosticsService as never,
      rendererRegistry,
    });

    const activationHandle = extension.activate!({
      [INTERNAL_EXTENSION_RENDER_SURFACE]: renderSurface,
    } as never);

    const withRenderer = resolveRegisteredSlotRenderers(
      runtime,
      rendererRegistry.getSnapshot(),
    );
    expect(withRenderer).not.toBe(runtime.config);
    expect(typeof withRenderer.slots.statusBar).toBe('function');

    render(createElement('div', null, withRenderer.slots.statusBar!({} as never)));
    expect(screen.getByTestId(EXTENSION_SMOKE_CONTRIBUTION_ID)).toHaveTextContent('Extension smoke active');

    activationHandle.dispose();

    const afterDispose = resolveRegisteredSlotRenderers(
      runtime,
      rendererRegistry.getSnapshot(),
    );
    expect(afterDispose).toBe(runtime.config);
    expect(afterDispose.slots.statusBar).toBeFalsy();
  });
});
