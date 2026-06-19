/**
 * Shared host-owned service factory for trusted component clip-type registration.
 *
 * Creates a per-extension {@link ClipTypeRegistrationService} backed by the
 * provider-scoped {@link ClipTypeRegistry}. The returned service validates that
 * every `registerClipType()` call references a `ClipTypeContribution` declared
 * in the extension manifest, builds a {@link ClipTypeRegistryRecord} with
 * provenance / owner / schema / renderability / diagnostics, supports HMR
 * replacement via re-registration, and disposes records exactly once.
 */

import type {
  ClipParameterDefinition,
  ClipParameterSchema,
  ClipRenderer,
  ClipInspector,
  ClipTypeContribution,
  ClipTypeRegistrationOptions,
  ClipTypeRegistrationService,
  DisposeHandle,
  ExtensionDiagnostic,
  ExtensionDiagnosticsService,
  ReighExtension,
} from '@reigh/editor-sdk';
import type { ClipTypeRegistry } from '@/tools/video-editor/clip-types/ClipTypeRegistry.ts';
import type {
  ClipTypeRegistryRecord,
  ClipTypeRegistryRecordStatus,
} from '@/tools/video-editor/clip-types/ClipTypeRegistry.ts';
import type {
  ContributionRenderability,
  RenderCapability,
  DeterminismStatus,
} from '@/tools/video-editor/runtime/renderability.ts';
import { validateClipTypeParameterSchema } from '@/tools/video-editor/clip-types/ClipTypeRegistry.ts';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Extract `ClipTypeContribution` entries from a frozen manifest. */
function getClipTypeContributions(
  manifest: ReighExtension['manifest'],
): readonly ClipTypeContribution[] {
  return (manifest.contributions?.filter(
    (c): c is ClipTypeContribution => c.kind === 'clipType',
  ) ?? []) as readonly ClipTypeContribution[];
}

/**
 * Build a {@link ContributionRenderability} from a `ClipTypeContribution`'s
 * declared capabilities.
 *
 * Per SD2: trusted component clip types default to preview-only. Browser-export
 * and worker-export are blocked unless the contribution declares them.
 */
function buildRenderability(
  contrib: ClipTypeContribution,
): ContributionRenderability {
  const capabilities: RenderCapability[] = [];

  // Preview is always supported for trusted local components.
  capabilities.push({
    route: 'preview',
    status: 'supported',
    determinism: 'preview-only',
  });

  // Browser export: blocked unless allowBrowserExport is true.
  capabilities.push({
    route: 'browser-export',
    status: contrib.allowBrowserExport ? 'supported' : 'blocked',
    determinism: contrib.allowBrowserExport ? 'preview-only' : 'preview-only',
    ...(contrib.allowBrowserExport
      ? {}
      : {
          blockerReason: 'route-unsupported' as const,
          message:
            'Browser export is not declared for this trusted component clip type.',
        }),
  });

  // Worker export: blocked unless allowWorkerExport is true.
  capabilities.push({
    route: 'worker-export',
    status: contrib.allowWorkerExport ? 'supported' : 'blocked',
    determinism: contrib.allowWorkerExport ? 'preview-only' : 'preview-only',
    ...(contrib.allowWorkerExport
      ? {}
      : {
          blockerReason: 'route-unsupported' as const,
          message:
            'Worker export is not declared for this trusted component clip type.',
        }),
  });

  const determinism: DeterminismStatus = 'preview-only';

  return {
    capabilities: Object.freeze(capabilities.map((c) => Object.freeze(c))),
    defaultRoute: 'preview',
    determinism,
  };
}

/** Convert SDK-level ClipParameterSchema to ClipTypeRegistry schema format. */
function toClipTypeSchema(
  sdkSchema: ClipParameterSchema | readonly ClipParameterDefinition[] | undefined,
): ReadonlyArray<{
  name: string;
  label: string;
  description: string;
  type: 'number' | 'select' | 'boolean' | 'color' | 'audio-binding';
  default?: number | string | boolean | Record<string, unknown>;
  min?: number;
  max?: number;
  step?: number;
  options?: readonly { label: string; value: string }[];
}> | undefined {
  if (!sdkSchema || !Array.isArray(sdkSchema)) return undefined;
  return sdkSchema.map((def) => ({ ...def }));
}

/** Create a no-op DisposeHandle. */
function noopDisposeHandle(): DisposeHandle {
  return { dispose() {} };
}

// ---------------------------------------------------------------------------
// Factory
// ---------------------------------------------------------------------------

export interface CreateClipTypeRegistrationServiceParams {
  /** The extension whose manifest declares ClipTypeContributions. */
  readonly extension: ReighExtension;
  /** The provider-scoped ClipTypeRegistry. */
  readonly clipTypeRegistry: ClipTypeRegistry;
  /** Diagnostics service scoped to this extension's lifecycle. */
  readonly diagnosticsService: ExtensionDiagnosticsService;
}

/**
 * Create a {@link ClipTypeRegistrationService} for a single extension.
 *
 * The returned service is typically passed as the `clipTypes` argument to
 * {@link createExtensionContext} so extensions can imperatively register
 * trusted component clip types during `activate()`.
 */
export function createClipTypeRegistrationService(
  params: CreateClipTypeRegistrationServiceParams,
): ClipTypeRegistrationService {
  const { extension, clipTypeRegistry, diagnosticsService } = params;
  const extensionId = extension.manifest.id as string;
  const clipTypeContributions = getClipTypeContributions(extension.manifest);

  // Index contributions by clipTypeId for O(1) lookup during registerClipType.
  const contributionsByClipTypeId = new Map<string, ClipTypeContribution>();
  for (const contrib of clipTypeContributions) {
    contributionsByClipTypeId.set(contrib.clipTypeId, contrib);
  }

  /** Emit a structured diagnostic into the extension's diagnostics service. */
  function emit(
    severity: ExtensionDiagnostic['severity'],
    code: string,
    message: string,
    detail?: Record<string, unknown>,
  ): void {
    diagnosticsService.report({ severity, code, message, detail });
  }

  function registerClipType(
    clipTypeId: string,
    renderer: ClipRenderer,
    inspector?: ClipInspector,
    options?: ClipTypeRegistrationOptions,
  ): DisposeHandle {
    // ---- Validate contribution exists -------------------------------------
    const contrib = contributionsByClipTypeId.get(clipTypeId);
    if (!contrib) {
      emit(
        'error',
        'clipTypes/undeclared-clip-type',
        `Clip type "${clipTypeId}" is not declared as a ClipTypeContribution in extension "${extensionId}". ` +
          `Declared clip type IDs: [${[...contributionsByClipTypeId.keys()].join(', ') || '(none)'}].`,
        { clipTypeId, extensionId },
      );
      return noopDisposeHandle();
    }

    // ---- Schema validation (registration-time) ----------------------------
    const sdkSchema = options?.parameterSchema;
    const schemaDiags = validateClipTypeParameterSchema(sdkSchema);
    const schema = toClipTypeSchema(sdkSchema);

    // Emit schema diagnostics into the extension diagnostics service
    for (const diag of schemaDiags) {
      emit(diag.severity, diag.code, diag.message, diag.detail);
    }

    // ---- Build the ClipTypeRegistryRecord ---------------------------------
    const label = options?.label ?? contrib.label ?? clipTypeId;
    const renderability = buildRenderability(contrib);

    // If schema validation produced errors, mark the record as 'error'.
    const hasSchemaErrors = schemaDiags.some((d) => d.severity === 'error');
    const status: ClipTypeRegistryRecordStatus = hasSchemaErrors ? 'error' : 'active';

    // Collect record-level diagnostics
    const recordDiagnostics: readonly ExtensionDiagnostic[] | undefined =
      schemaDiags.length > 0 ? [...schemaDiags] : undefined;

    const record: ClipTypeRegistryRecord = {
      clipTypeId,
      contributionId: contrib.id,
      renderer,
      ...(inspector ? { inspector } : {}),
      ownerExtensionId: extensionId,
      renderability,
      status,
      ...(schema ? { schema } : {}),
      ...(recordDiagnostics ? { diagnostics: recordDiagnostics } : {}),
    };

    // ---- Register with the provider-scoped ClipTypeRegistry ----------------
    // ClipTypeRegistry.register() handles replacement: if an existing record
    // with the same clipTypeId exists, it is safely disposed first.
    const handle = clipTypeRegistry.register(record);

    const registrationSeverity: ExtensionDiagnostic['severity'] = hasSchemaErrors ? 'warning' : 'info';
    emit(
      registrationSeverity,
      'clipTypes/registered',
      `Clip type "${clipTypeId}" registered for extension "${extensionId}"${hasSchemaErrors ? ' with schema errors' : ''}.`,
      { clipTypeId, extensionId, contributionId: contrib.id, status },
    );

    // ---- Return a DisposeHandle that disposes exactly once ----------------
    let disposed = false;

    return {
      dispose(): void {
        if (disposed) return;
        disposed = true;

        try {
          handle.dispose();
        } catch (err) {
          emit(
            'error',
            'clipTypes/dispose-error',
            `Error disposing clip type "${clipTypeId}": ${String(err)}`,
            { clipTypeId, extensionId, contributionId: contrib.id },
          );
        }
      },
    };
  }

  return {
    registerClipType,
  };
}
