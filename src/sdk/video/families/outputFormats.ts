/**
 * Output Format family module.
 *
 * Houses the manifest contribution interfaces extracted from the public
 * barrel (src/sdk/index.ts).  Runtime contracts (CompileOnlyOutputResult,
 * OutputFormatHandler, OutputFormatContext, ExportService,
 * OutputFormatRegistrationOptions) stay in src/sdk/video/exports/outputFormats.ts
 * as portable runtime contracts.
 *
 * This module contains only data-only types and read-only surfaces; no
 * registry, provider, resolver, upload, or storage behaviour lives here.
 *
 * @publicContract
 */

import type { ContributionId } from '../../ids';
import type { SamplingConfig } from '../../capabilities';
import type { RenderRoute, DeterminismStatus } from '../rendering/renderability';
import type { RenderArtifactSidecarDescriptor } from '../rendering/artifacts';

// Boundary assertion: the family module imports runtime contracts to
// confirm the module boundary between manifest declarations (here) and
// runtime execution surfaces (../exports/outputFormats).
import type {
  CompileOnlyOutputResult,
  OutputFormatHandler,
  OutputFormatContext,
  ExportService,
  OutputFormatRegistrationOptions,
} from '../exports/outputFormats';

// Suppress unused-import diagnostics for boundary-assertion imports;
// keep them in scope so the compiler verifies module resolution.
void ({} as {
  _boundary: [
    CompileOnlyOutputResult,
    OutputFormatHandler,
    OutputFormatContext,
    ExportService,
    OutputFormatRegistrationOptions,
  ];
});

/**
 * M6: An output format contribution declared in an extension manifest.
 *
 * Output formats produce an artifact from timeline and asset data.
 * Compile-only formats (requiresRender: false) do not invoke the render
 * pipeline; they read timeline/asset data and produce a deterministic
 * artifact (e.g. metadata JSON).
 *
 * Render-dependent formats (requiresRender: true) are declaration-only
 * in M6 and appear disabled in the export UI with a diagnostic explaining
 * that execution is unavailable until render planning activates the route.
 */
export interface OutputFormatContribution {
  /** Unique within the extension. */
  id: ContributionId;
  kind: 'outputFormat';
  /** Human-readable label for the export UI. */
  label: string;
  /**
   * When false, this is a compile-only format that does not invoke the
   * render pipeline.  When true, the format requires render planning and
   * is surfaced as disabled/reserved in M6.
   */
  requiresRender: boolean;
  /** File extension for the output artifact (e.g. 'json', 'xml'). */
  outputExtension: string;
  /** MIME type for the output artifact (e.g. 'application/json'). */
  outputMimeType?: string;
  /** Optional human-readable description shown in the export UI. */
  description?: string;
  /** Lower values sort first. Default 0. */
  order?: number;
  /**
   * Render-dependent output route requirements.
   * Required when `requiresRender` is true; ignored for compile-only outputs.
   */
  render?: RenderDependentOutputDescriptor;
  /** Optional declarative sampling defaults for export configuration. */
  sampling?: SamplingConfig;
  /** Sidecar kinds this output may emit. */
  sidecars?: readonly RenderArtifactSidecarDescriptor[];
}

/** M12: Compile-only output formats never enter render planning. */
export interface CompileOnlyOutputFormatContribution extends OutputFormatContribution {
  requiresRender: false;
  render?: never;
}

/** M12: Render-dependent output formats require planner-owned route execution. */
export interface RenderDependentOutputFormatContribution extends OutputFormatContribution {
  requiresRender: true;
  render: RenderDependentOutputDescriptor;
}

/** M12: Route/process requirements for a render-dependent output format. */
export interface RenderDependentOutputDescriptor {
  /** Routes this output can accept after planning. */
  readonly routes: readonly RenderRoute[];
  /** Capabilities required before the output can execute. */
  readonly requiredCapabilities?: readonly string[];
  /** Optional local process needed to produce this output. */
  readonly processId?: string;
  /** Optional process operation needed to produce this output. */
  readonly operationId?: string;
  /** Determinism posture claimed by this output route. */
  readonly determinism?: DeterminismStatus;
  /** Human-readable planner hint shown when the route is unavailable. */
  readonly unavailableMessage?: string;
}
