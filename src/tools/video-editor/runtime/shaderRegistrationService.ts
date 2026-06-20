/**
 * Shared host-owned service factory for WebGL shader registration.
 *
 * Creates a per-extension ShaderRegistrationService backed by the provider-
 * scoped ShaderEffectRegistry. Shader registration stays on the dedicated
 * WebGL surface and never routes through component effect registration.
 */

import type {
  DisposeHandle,
  ExtensionDiagnostic,
  ExtensionDiagnosticsService,
  ReighExtension,
  ShaderContribution,
  ShaderMaterializerDescriptor,
  ShaderRegistrationOptions,
  ShaderRegistrationService,
  ShaderSourceDescriptor,
} from '@reigh/editor-sdk';
import { validateShaderSchemas } from '@/tools/video-editor/shaders/compile/diagnostics.ts';
import type { ShaderEffectRegistry } from '@/tools/video-editor/shaders/registry/types.ts';
import type {
  ShaderEffectRegistryRecord,
  ShaderEffectRegistryRecordStatus,
} from '@/tools/video-editor/shaders/registry/types.ts';
import type {
  ContributionRenderability,
  RenderCapability,
  RenderRoute,
} from '@/tools/video-editor/runtime/renderability.ts';

function getShaderContributions(
  manifest: ReighExtension['manifest'],
): readonly ShaderContribution[] {
  return (manifest.contributions?.filter(
    (contribution): contribution is ShaderContribution => contribution.kind === 'shader',
  ) ?? []) as readonly ShaderContribution[];
}

function noopDisposeHandle(): DisposeHandle {
  return { dispose() {} };
}

function materializerRoutes(
  materializer: ShaderMaterializerDescriptor | undefined,
): ReadonlySet<RenderRoute> {
  return new Set((materializer?.routes ?? []) as readonly RenderRoute[]);
}

function buildShaderRenderability(
  extensionId: string,
  contribution: ShaderContribution,
  materializer: ShaderMaterializerDescriptor | undefined,
): ContributionRenderability {
  const routes = materializerRoutes(materializer);
  const capabilities: RenderCapability[] = [
    Object.freeze({
      route: 'preview',
      status: 'supported',
      determinism: 'preview-only',
    }),
  ];

  for (const route of ['browser-export', 'worker-export', 'sidecar-export'] as const) {
    const materializerSupportsRoute = routes.has(route);
    capabilities.push(Object.freeze({
      route,
      status: materializerSupportsRoute ? 'supported' : 'blocked',
      determinism: materializerSupportsRoute ? 'process-dependent' : 'preview-only',
      ...(materializerSupportsRoute
        ? {}
        : {
            blockerReason: 'missing-material' as const,
            message:
              `Shader "${contribution.shaderId}" is preview-only until extension "${extensionId}" ` +
              'declares a materializer route that can produce RenderMaterial.',
          }),
    }));
  }

  return Object.freeze({
    capabilities: Object.freeze(capabilities),
    defaultRoute: 'preview',
    determinism: routes.size > 0 ? 'process-dependent' : 'preview-only',
  });
}

export interface CreateShaderRegistrationServiceParams {
  readonly extension: ReighExtension;
  readonly shaderRegistry: ShaderEffectRegistry;
  readonly diagnosticsService: ExtensionDiagnosticsService;
}

export function createShaderRegistrationService(
  params: CreateShaderRegistrationServiceParams,
): ShaderRegistrationService {
  const { extension, shaderRegistry, diagnosticsService } = params;
  const extensionId = extension.manifest.id as string;
  const shaderContributions = getShaderContributions(extension.manifest);
  const contributionsByShaderId = new Map<string, ShaderContribution>();

  for (const contribution of shaderContributions) {
    contributionsByShaderId.set(contribution.shaderId, contribution);
  }

  function emit(
    severity: ExtensionDiagnostic['severity'],
    code: string,
    message: string,
    detail?: Record<string, unknown>,
  ): void {
    diagnosticsService.report({ severity, code, message, detail });
  }

  function registerShader(
    shaderId: string,
    source: ShaderSourceDescriptor,
    options?: ShaderRegistrationOptions,
  ): DisposeHandle {
    const contribution = contributionsByShaderId.get(shaderId);
    if (!contribution) {
      emit(
        'error',
        'shaders/undeclared-shader',
        `Shader "${shaderId}" is not declared as a ShaderContribution in extension "${extensionId}". ` +
          `Declared shader IDs: [${[...contributionsByShaderId.keys()].join(', ') || '(none)'}].`,
        { shaderId, extensionId },
      );
      return noopDisposeHandle();
    }

    const uniforms = options?.uniforms ?? contribution.uniforms;
    const textures = options?.textures ?? contribution.textures;
    const schemaDiagnostics = validateShaderSchemas(
      { uniforms, textures },
      {
        shaderId,
        extensionId,
        contributionId: contribution.id as string,
      },
    );

    for (const diagnostic of schemaDiagnostics) {
      emit(diagnostic.severity, diagnostic.code, diagnostic.message, diagnostic.detail);
    }

    const hasSchemaErrors = schemaDiagnostics.some((diagnostic) => diagnostic.severity === 'error');
    const status: ShaderEffectRegistryRecordStatus = hasSchemaErrors ? 'error' : 'active';
    const materializer = options?.materializer ?? contribution.materializer;

    const record: ShaderEffectRegistryRecord = {
      shaderId,
      contributionId: contribution.id as string,
      label: options?.label ?? contribution.label ?? shaderId,
      description: contribution.description,
      source,
      pass: options?.pass ?? contribution.pass,
      uniforms,
      textures,
      fallback: options?.fallback ?? contribution.fallback,
      materializer,
      provenance: 'bundled-extension',
      ownerExtensionId: extensionId,
      renderability: buildShaderRenderability(extensionId, contribution, materializer),
      status,
      ...(schemaDiagnostics.length > 0 ? { diagnostics: schemaDiagnostics } : {}),
    };

    const handle = shaderRegistry.register(record);
    emit(
      hasSchemaErrors ? 'warning' : 'info',
      'shaders/registered',
      `Shader "${shaderId}" registered for extension "${extensionId}"${hasSchemaErrors ? ' with schema errors' : ''}.`,
      {
        shaderId,
        extensionId,
        contributionId: contribution.id as string,
        status,
      },
    );

    let disposed = false;
    return {
      dispose(): void {
        if (disposed) return;
        disposed = true;

        try {
          handle.dispose();
        } catch (error) {
          emit(
            'error',
            'shaders/dispose-failed',
            `Failed to dispose shader "${shaderId}" for extension "${extensionId}": ${String(error)}`,
            { shaderId, extensionId, error: String(error) },
          );
        }

        emit(
          'info',
          'shaders/disposed',
          `Shader "${shaderId}" disposed for extension "${extensionId}".`,
          { shaderId, extensionId },
        );
      },
    };
  }

  return { registerShader };
}
