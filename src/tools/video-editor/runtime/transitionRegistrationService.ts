/**
 * Shared host-owned service factory for trusted component transition registration.
 *
 * Creates a per-extension {@link TransitionRegistrationService} backed by the
 * provider-scoped {@link TransitionRegistry}. The returned service validates that
 * every `registerRenderer()` call references a `TransitionContribution` declared
 * in the extension manifest, builds an {@link TransitionRegistryRecord} with
 * provenance / owner / schema / renderability / diagnostics, supports HMR
 * replacement via re-registration, and disposes records exactly once.
 */

import type {
  DisposeHandle,
  TransitionContribution,
  TransitionRenderer,
  TransitionParameterDefinition,
  TransitionParameterSchema,
  TransitionRegistrationOptions,
  TransitionRegistrationService,
  ExtensionDiagnostic,
  ExtensionDiagnosticsService,
  ReighExtension,
} from '@reigh/editor-sdk';
import type { TransitionRegistry } from '@/tools/video-editor/transitions/registry/types.ts';
import type {
  TransitionRegistryRecord,
  TransitionRegistryRecordStatus,
} from '@/tools/video-editor/transitions/registry/types.ts';
import type {
  ContributionRenderability,
  RenderCapability,
  DeterminismStatus,
} from '@/tools/video-editor/runtime/renderability.ts';
import type { ParameterSchema } from '@/tools/video-editor/types/index.ts';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Extract `TransitionContribution` entries from a frozen manifest. */
function getTransitionContributions(
  manifest: ReighExtension['manifest'],
): readonly TransitionContribution[] {
  return (manifest.contributions?.filter(
    (c): c is TransitionContribution => c.kind === 'transition',
  ) ?? []) as readonly TransitionContribution[];
}

// ---------------------------------------------------------------------------
// Schema validation (registration-time)
// ---------------------------------------------------------------------------

const VALID_PARAMETER_TYPES = new Set<string>([
  'number',
  'select',
  'boolean',
  'color',
  'audio-binding',
]);

const AUDIO_SOURCES = new Set<string>(['bass', 'mid', 'treble', 'amplitude']);

/**
 * Validate a single parameter definition and return diagnostics.
 * Returns an empty array if the definition is valid.
 *
 * Validation rules:
 * - `name` must be a non-empty string
 * - `label` must be a non-empty string
 * - `type` must be one of the valid ParameterType values
 * - `number` type: `default`, `min`, `max`, `step` must be numbers if present; `min <= max` if both present
 * - `select` type: `options` must be a non-empty array with valid option objects
 * - `boolean` type: `default` must be a boolean if present
 * - `color` type: `default` must be a valid hex string if present
 * - `audio-binding` type: `default` must be a valid AudioBindingValue if present
 */
function validateParameterDefinition(
  def: TransitionParameterDefinition,
  index: number,
): ExtensionDiagnostic[] {
  const diags: ExtensionDiagnostic[] = [];
  const ctx = `parameter[${index}]`;

  // name: required, non-empty string
  if (typeof def.name !== 'string' || def.name.length === 0) {
    diags.push({
      severity: 'error',
      code: 'transitions/invalid-schema-name',
      message: `${ctx}: name must be a non-empty string.`,
      detail: { index, field: 'name', value: def.name },
    });
  }

  // label: required, non-empty string
  if (typeof def.label !== 'string' || def.label.length === 0) {
    diags.push({
      severity: 'error',
      code: 'transitions/invalid-schema-label',
      message: `${ctx}: label must be a non-empty string.`,
      detail: { index, field: 'label', value: def.label },
    });
  }

  // type: required, must be valid
  if (!VALID_PARAMETER_TYPES.has(def.type)) {
    diags.push({
      severity: 'error',
      code: 'transitions/invalid-schema-type',
      message: `${ctx}: type must be one of [${[...VALID_PARAMETER_TYPES].join(', ')}], got "${String(def.type)}".`,
      detail: { index, field: 'type', value: def.type },
    });
    // Cannot validate type-specific rules without a valid type
    return diags;
  }

  // Type-specific validation
  switch (def.type) {
    case 'number': {
      if (def.min !== undefined && typeof def.min !== 'number') {
        diags.push({
          severity: 'error',
          code: 'transitions/invalid-schema-min',
          message: `${ctx}: min must be a number for type "number".`,
          detail: { index, field: 'min', value: def.min },
        });
      }
      if (def.max !== undefined && typeof def.max !== 'number') {
        diags.push({
          severity: 'error',
          code: 'transitions/invalid-schema-max',
          message: `${ctx}: max must be a number for type "number".`,
          detail: { index, field: 'max', value: def.max },
        });
      }
      if (
        typeof def.min === 'number' &&
        typeof def.max === 'number' &&
        def.min > def.max
      ) {
        diags.push({
          severity: 'error',
          code: 'transitions/invalid-schema-range',
          message: `${ctx}: min (${def.min}) must not exceed max (${def.max}).`,
          detail: { index, min: def.min, max: def.max },
        });
      }
      if (def.step !== undefined && typeof def.step !== 'number') {
        diags.push({
          severity: 'error',
          code: 'transitions/invalid-schema-step',
          message: `${ctx}: step must be a number for type "number".`,
          detail: { index, field: 'step', value: def.step },
        });
      }
      if (def.default !== undefined && typeof def.default !== 'number') {
        diags.push({
          severity: 'error',
          code: 'transitions/invalid-schema-default',
          message: `${ctx}: default must be a number for type "number".`,
          detail: { index, field: 'default', value: def.default },
        });
      }
      break;
    }
    case 'select': {
      const options = def.options;
      if (!Array.isArray(options) || options.length === 0) {
        diags.push({
          severity: 'error',
          code: 'transitions/invalid-schema-options',
          message: `${ctx}: options must be a non-empty array for type "select".`,
          detail: { index, field: 'options', value: options },
        });
      } else {
        for (let oi = 0; oi < options.length; oi++) {
          const opt = options[oi];
          if (!opt || typeof opt.label !== 'string' || typeof opt.value !== 'string') {
            diags.push({
              severity: 'error',
              code: 'transitions/invalid-schema-option-entry',
              message: `${ctx}.options[${oi}]: each option must have label (string) and value (string).`,
              detail: { index, optionIndex: oi, option: opt },
            });
          }
        }
      }
      if (def.default !== undefined && typeof def.default !== 'string') {
        diags.push({
          severity: 'error',
          code: 'transitions/invalid-schema-default',
          message: `${ctx}: default must be a string for type "select".`,
          detail: { index, field: 'default', value: def.default },
        });
      }
      break;
    }
    case 'boolean': {
      if (def.default !== undefined && typeof def.default !== 'boolean') {
        diags.push({
          severity: 'error',
          code: 'transitions/invalid-schema-default',
          message: `${ctx}: default must be a boolean for type "boolean".`,
          detail: { index, field: 'default', value: def.default },
        });
      }
      break;
    }
    case 'color': {
      const COLOR_RE = /^#[0-9a-fA-F]{3,8}$/;
      if (def.default !== undefined && (typeof def.default !== 'string' || !COLOR_RE.test(def.default))) {
        diags.push({
          severity: 'error',
          code: 'transitions/invalid-schema-default',
          message: `${ctx}: default must be a valid hex color (e.g., "#ff0000") for type "color".`,
          detail: { index, field: 'default', value: def.default },
        });
      }
      break;
    }
    case 'audio-binding': {
      const d = def.default;
      if (d !== undefined) {
        const isValid =
          typeof d === 'object' &&
          d !== null &&
          typeof (d as Record<string, unknown>).source === 'string' &&
          AUDIO_SOURCES.has((d as Record<string, unknown>).source as string) &&
          typeof (d as Record<string, unknown>).min === 'number' &&
          Number.isFinite((d as Record<string, unknown>).min as number) &&
          typeof (d as Record<string, unknown>).max === 'number' &&
          Number.isFinite((d as Record<string, unknown>).max as number);
        if (!isValid) {
          diags.push({
            severity: 'error',
            code: 'transitions/invalid-schema-default',
            message: `${ctx}: default must be a valid AudioBindingValue { source, min, max } for type "audio-binding".`,
            detail: { index, field: 'default', value: d },
          });
        }
      }
      break;
    }
  }

  return diags;
}

/**
 * Validate a complete parameter schema at registration time.
 *
 * Returns diagnostics for any invalid definitions. An empty array means the
 * schema is valid. Duplicate parameter names are flagged as errors.
 *
 * Render-time coercion is NOT affected by registration-time validation
 * failures — legacy applied parameters continue to be coerced at render time
 * regardless of the record's status.
 */
export function validateTransitionParameterSchema(
  schema: TransitionParameterSchema | readonly TransitionParameterDefinition[] | undefined,
): ExtensionDiagnostic[] {
  if (!schema) return [];
  if (!Array.isArray(schema)) {
    return [{
      severity: 'error',
      code: 'transitions/invalid-schema-not-array',
      message: 'Parameter schema must be an array.',
      detail: { value: schema },
    }];
  }

  const diags: ExtensionDiagnostic[] = [];

  // Validate each definition
  for (let i = 0; i < schema.length; i++) {
    diags.push(...validateParameterDefinition(schema[i] as TransitionParameterDefinition, i));
  }

  // Check for duplicate parameter names
  const seen = new Map<string, number>();
  for (let i = 0; i < schema.length; i++) {
    const name = (schema[i] as TransitionParameterDefinition)?.name;
    if (typeof name === 'string' && name.length > 0) {
      if (seen.has(name)) {
        diags.push({
          severity: 'error',
          code: 'transitions/invalid-schema-duplicate-name',
          message: `parameters[${i}]: duplicate name "${name}" (first seen at index ${seen.get(name)}).`,
          detail: { index: i, name, firstIndex: seen.get(name) },
        });
      } else {
        seen.set(name, i);
      }
    }
  }

  return diags;
}

/**
 * Convert SDK-level TransitionParameterSchema to video-editor internal ParameterSchema.
 * The types are structurally compatible; this performs a safe cast with runtime
 * array copy for immutability.
 */
function toInternalSchema(
  sdkSchema: TransitionParameterSchema | readonly TransitionParameterDefinition[] | undefined,
): ParameterSchema | undefined {
  if (!sdkSchema || !Array.isArray(sdkSchema)) return undefined;
  return sdkSchema.map((def) => ({ ...def })) as unknown as ParameterSchema;
}

/**
 * Build a {@link ContributionRenderability} from a `TransitionContribution`'s
 * declared capabilities.
 *
 * Per SD3: trusted component transitions default to preview-only. Browser-export
 * and worker-export are blocked unless the contribution declares them.
 */
function buildRenderability(
  contrib: TransitionContribution,
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
            'Browser export is not declared for this trusted component transition.',
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
            'Worker export is not declared for this trusted component transition.',
        }),
  });

  const determinism: DeterminismStatus = 'preview-only';

  return {
    capabilities: Object.freeze(capabilities.map((c) => Object.freeze(c))),
    defaultRoute: 'preview',
    determinism,
  };
}

/** Create a no-op DisposeHandle. */
function noopDisposeHandle(): DisposeHandle {
  return { dispose() {} };
}

// ---------------------------------------------------------------------------
// Factory
// ---------------------------------------------------------------------------

export interface CreateTransitionRegistrationServiceParams {
  /** The extension whose manifest declares TransitionContributions. */
  readonly extension: ReighExtension;
  /** The provider-scoped TransitionRegistry. */
  readonly transitionRegistry: TransitionRegistry;
  /** Diagnostics service scoped to this extension's lifecycle. */
  readonly diagnosticsService: ExtensionDiagnosticsService;
}

/**
 * Create a {@link TransitionRegistrationService} for a single extension.
 *
 * The returned service is typically passed as the `transitions` argument to
 * {@link createExtensionContext} so extensions can imperatively register
 * trusted component transitions during `activate()`.
 */
export function createTransitionRegistrationService(
  params: CreateTransitionRegistrationServiceParams,
): TransitionRegistrationService {
  const { extension, transitionRegistry, diagnosticsService } = params;
  const extensionId = extension.manifest.id as string;
  const transitionContributions = getTransitionContributions(extension.manifest);

  // Index contributions by transitionId for O(1) lookup during registerRenderer.
  const contributionsByTransitionId = new Map<string, TransitionContribution>();
  for (const contrib of transitionContributions) {
    contributionsByTransitionId.set(contrib.transitionId, contrib);
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

  function registerRenderer(
    transitionId: string,
    renderer: TransitionRenderer,
    options?: TransitionRegistrationOptions,
  ): DisposeHandle {
    // ---- Validate contribution exists -------------------------------------
    const contrib = contributionsByTransitionId.get(transitionId);
    if (!contrib) {
      emit(
        'error',
        'transitions/undeclared-transition',
        `Transition "${transitionId}" is not declared as a TransitionContribution in extension "${extensionId}". ` +
          `Declared transition IDs: [${[...contributionsByTransitionId.keys()].join(', ') || '(none)'}].`,
        { transitionId, extensionId },
      );
      return noopDisposeHandle();
    }

    // ---- Schema validation (registration-time) ----------------------------
    const sdkSchema = options?.parameterSchema;
    const schemaDiags = validateTransitionParameterSchema(sdkSchema);
    const schema = toInternalSchema(sdkSchema);

    // Emit schema diagnostics into the extension diagnostics service
    for (const diag of schemaDiags) {
      emit(diag.severity, diag.code, diag.message, diag.detail);
    }

    // ---- Build the TransitionRegistryRecord -------------------------------
    const label = options?.label ?? contrib.label ?? transitionId;
    const renderability = buildRenderability(contrib);

    // If schema validation produced errors, mark the record as 'error'.
    // The renderer is still registered and render-time parameter coercion
    // continues to work for already-applied legacy data.
    const hasSchemaErrors = schemaDiags.some((d) => d.severity === 'error');
    const status: TransitionRegistryRecordStatus = hasSchemaErrors ? 'error' : 'active';

    // Collect record-level diagnostics
    const recordDiagnostics: ExtensionDiagnostic[] | undefined =
      schemaDiags.length > 0 ? [...schemaDiags] : undefined;

    const record: TransitionRegistryRecord = {
      transitionId,
      contributionId: contrib.id,
      renderer,
      provenance: 'bundled-extension',
      ownerExtensionId: extensionId,
      renderability,
      status,
      ...(schema ? { schema } : {}),
      ...(recordDiagnostics ? { diagnostics: recordDiagnostics } : {}),
    };

    // ---- Register with the provider-scoped TransitionRegistry -------------
    // TransitionRegistry.register() handles replacement: if an existing record
    // with the same transitionId exists, it is safely disposed first.
    const handle = transitionRegistry.register(record);

    const registrationSeverity: ExtensionDiagnostic['severity'] = hasSchemaErrors ? 'warning' : 'info';
    emit(
      registrationSeverity,
      'transitions/registered',
      `Transition "${transitionId}" registered for extension "${extensionId}"${hasSchemaErrors ? ' with schema errors' : ''}.`,
      { transitionId, extensionId, contributionId: contrib.id, status },
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
            'transitions/dispose-failed',
            `Failed to dispose transition "${transitionId}" for extension "${extensionId}": ${String(err)}`,
            { transitionId, extensionId, error: String(err) },
          );
        }

        emit(
          'info',
          'transitions/disposed',
          `Transition "${transitionId}" disposed for extension "${extensionId}".`,
          { transitionId, extensionId },
        );
      },
    };
  }

  return { registerRenderer };
}
