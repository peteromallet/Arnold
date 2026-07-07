import type {
  ExtensionDiagnostic,
  ExtensionDiagnosticsService,
  ReighExtension,
} from '@reigh/editor-sdk';
import type { InternalExtensionRenderSurface } from '@/sdk/internalExtensionRenderSurface';
import type {
  ExtensionRuntime,
  VideoEditorExtensionRuntimeConfig,
  VideoEditorSlotRenderer,
} from '@/tools/video-editor/runtime/extensionSurface';
import type {
  RendererRegistry,
  RendererRegistrySnapshot,
} from '@/tools/video-editor/runtime/extensionRendererRegistry';

function makeDiagnostic(
  extensionId: string,
  renderId: string,
  code: string,
  message: string,
): Omit<ExtensionDiagnostic, 'extensionId' | 'source'> {
  return {
    severity: 'warning',
    code,
    message,
    contributionId: renderId,
    detail: {
      extensionId,
      renderId,
    },
  };
}

export function createInternalExtensionRenderSurface(args: {
  extension: ReighExtension;
  diagnosticsService: ExtensionDiagnosticsService;
  rendererRegistry: RendererRegistry;
}): InternalExtensionRenderSurface {
  const { extension, diagnosticsService, rendererRegistry } = args;
  const extensionId = extension.manifest.id as string;
  const slotContributionsByRenderId = new Map<string, string>();

  for (const contribution of extension.manifest.contributions ?? []) {
    if (
      contribution.kind === 'slot'
      && typeof contribution.slot === 'string'
      && typeof contribution.render === 'string'
      && !slotContributionsByRenderId.has(contribution.render)
    ) {
      slotContributionsByRenderId.set(
        contribution.render,
        contribution.id as string,
      );
    }
  }

  return Object.freeze({
    registerRenderer(renderId, renderer) {
      const contributionId = slotContributionsByRenderId.get(renderId);
      if (!contributionId) {
        diagnosticsService.report(
          makeDiagnostic(
            extensionId,
            renderId,
            'render/unbound-render-id',
            `Cannot register renderer "${renderId}" for extension "${extensionId}" because no slot contribution declares that render ID.`,
          ),
        );
        return { dispose() {} };
      }

      return rendererRegistry.register(extensionId, renderId, renderer);
    },
  });
}

export function resolveRegisteredSlotRenderers(
  extensionRuntime: ExtensionRuntime,
  rendererSnapshot: RendererRegistrySnapshot,
): VideoEditorExtensionRuntimeConfig {
  if (rendererSnapshot.entries.length === 0) {
    return extensionRuntime.config;
  }

  const slots: Partial<Record<string, VideoEditorSlotRenderer>> = {
    ...extensionRuntime.config.slots,
  };
  let changed = false;

  for (const extension of extensionRuntime.extensions) {
    const extensionId = extension.manifest.id as string;
    for (const contribution of extension.manifest.contributions ?? []) {
      if (
        contribution.kind !== 'slot'
        || !contribution.slot
        || typeof contribution.render !== 'string'
        || slots[contribution.slot]
      ) {
        continue;
      }

      const renderer = rendererSnapshot.get(extensionId, contribution.render);
      if (!renderer) {
        continue;
      }

      slots[contribution.slot] = renderer as VideoEditorSlotRenderer;
      changed = true;
    }
  }

  if (!changed) {
    return extensionRuntime.config;
  }

  return Object.freeze({
    ...extensionRuntime.config,
    slots: Object.freeze(slots),
  });
}
