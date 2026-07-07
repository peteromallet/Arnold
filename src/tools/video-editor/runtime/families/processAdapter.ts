/**
 * Process adapter — real runtime-bridged HostFamilyAdapter.
 *
 * Owns normalization, lifecycle, diagnostics, and conformance reporting
 * for process contributions.  Replaces the delegated M12 placeholder
 * previously registered for this family.
 *
 * @module families/processAdapter
 */

import type {
  HostFamilyAdapter,
  HostAdapterManifest,
  NormalizeFamilyInput,
  FamilyNormalizeResult,
  FamilyConformanceReport,
  ExecutionMaturity,
  ProcessContribution,
} from '@reigh/editor-sdk';
import { getVideoFamilyDefinition } from '@reigh/editor-sdk';
import type { ProcessStatus } from '@/sdk/video/families/processes';
import type { VideoEditorProcessDescriptor } from '../extensionSurface';
import { buildProcessDescriptors } from './projectors/processProjector';
import { buildConformanceReport } from '@/sdk/core/families/conformance';

// ---------------------------------------------------------------------------
// Adapter manifest
// ---------------------------------------------------------------------------

const MANIFEST: HostAdapterManifest = Object.freeze({
  adapterId: 'process-default',
  kind: 'process',
  version: '1.0.0',
  maturity: 'runtime-bridged' as ExecutionMaturity,
  description:
    'Normalizes process contributions into VideoEditorProcessDescriptor ' +
    'records for the runtime.  Owns spec/operation projection, capability ' +
    'enumeration, route scoping, and host-supplied ProcessStatus overlay.',
  metadata: Object.freeze({
    classification: 'real',
    owner: 'video-editor-runtime',
    reason: 'Process execution remains delegated until the trusted local process lifecycle is fully release-gated.',
    expiration: 'M12',
  }),
});

// ---------------------------------------------------------------------------
// Extended normalize input
// ---------------------------------------------------------------------------

/**
 * Normalize input for the process adapter, extending the base
 * {@link NormalizeFamilyInput} with optional host-supplied process
 * status overlays.
 */
export interface ProcessNormalizeInput
  extends NormalizeFamilyInput<ProcessContribution> {
  /**
   * Optional host-supplied process statuses to overlay onto the
   * normalized descriptors (e.g. from {@link ProcessManager}).
   */
  readonly processStatuses?: readonly ProcessStatus[];
}

// ---------------------------------------------------------------------------
// Adapter implementation
// ---------------------------------------------------------------------------

/**
 * The process host family adapter.
 *
 * This is a real (non-placeholder) adapter that owns process contribution
 * normalization.  It surfaces spec/operation/capability information from
 * declared contributions and optionally consumes host-supplied
 * {@link ProcessStatus} overlays to enrich descriptors with current
 * lifecycle state.
 */
export const processAdapter: HostFamilyAdapter<
  'process',
  ProcessContribution,
  VideoEditorProcessDescriptor
> = Object.freeze({
  kind: 'process' as const,
  classification: 'real',
  manifest: MANIFEST,

  // -----------------------------------------------------------------------
  // Normalization
  // -----------------------------------------------------------------------

  /**
   * Normalize a batch of process contributions into deterministically
   * ordered {@link VideoEditorProcessDescriptor} records.
   *
   * When {@link ProcessNormalizeInput.processStatuses} is provided, each
   * descriptor is enriched with host-supplied status overlays.  Status
   * overlays surface the current lifecycle state so downstream consumers
   * (planner, command services, route-fit mapper) can derive blockers
   * without coupling to {@link ProcessManager} directly.
   *
   * @param input — Sorted process contributions with their owning extension
   *                IDs, and optional host-supplied process status overlays.
   * @returns A frozen array of normalized process descriptors.
   */
  normalize(
    input: NormalizeFamilyInput<ProcessContribution>,
  ): FamilyNormalizeResult<VideoEditorProcessDescriptor> {
    const processInput = input as ProcessNormalizeInput;
    const descriptors = buildProcessDescriptors(
      processInput.contributions,
      processInput.extensionOrder,
    );

    const statuses = processInput.processStatuses;

    // Fast path: no status overlays to apply
    if (!statuses || statuses.length === 0) {
      return { descriptors };
    }

    // Build a lookup from processId → ProcessStatus for efficient overlay
    const statusById = new Map<string, ProcessStatus>();
    for (const status of statuses) {
      statusById.set(status.processId, status);
    }

    // Overlay status onto each descriptor (no mutation)
    const overlaid = descriptors.map((descriptor) => {
      const status = statusById.get(descriptor.processId);
      if (!status) {
        return descriptor;
      }

      // Merge status-derived metadata into the descriptor while
      // preserving all existing fields.  The descriptor is frozen
      // after merging.
      return Object.freeze({
        ...descriptor,
        blockers: Object.freeze([
          ...descriptor.blockers,
          ...buildStatusBlockers(descriptor, status),
        ]),
      } satisfies VideoEditorProcessDescriptor);
    });

    return { descriptors: Object.freeze(overlaid) };
  },

  // -----------------------------------------------------------------------
  // Conformance
  // -----------------------------------------------------------------------

  /**
   * Build a {@link FamilyConformanceReport} for the process family
   * by reading the canonical family definition from the SDK registry.
   *
   * @returns The conformance report for the process family.
   */
  buildConformanceReport(): FamilyConformanceReport<'process'> {
    const definition = getVideoFamilyDefinition('process');
    if (!definition) {
      throw new Error(
        'processAdapter: family definition not found for kind "process".',
      );
    }
    return buildConformanceReport(definition);
  },
});

// ---------------------------------------------------------------------------
// Status overlay helpers
// ---------------------------------------------------------------------------

/**
 * Build blocker descriptors from a host-supplied {@link ProcessStatus}.
 *
 * Uses the locked {@link RenderBlockerReason} vocabulary.  Only
 * non-ready, non-stopped states produce blockers — ready and stopped
 * are unblocked lifecycle positions.
 */
function buildStatusBlockers(
  descriptor: VideoEditorProcessDescriptor,
  status: ProcessStatus,
): VideoEditorProcessDescriptor['blockers'] {
  // Ready and stopped are unblocked — no blockers needed
  if (status.state === 'ready' || status.state === 'stopped') {
    return [];
  }

  const message = blockerMessageForStatus(status);
  if (!message) {
    return [];
  }

  const routes = descriptor.availableRoutes.length > 0
    ? descriptor.availableRoutes
    : undefined;

  const blocker = Object.freeze({
    id: `${descriptor.id}-status-${status.state}`,
    extensionId: descriptor.extensionId,
    contributionId: descriptor.id,
    reason: 'process-dependent' as const,
    message,
    ...(routes ? { route: routes[0] } : {}),
  });

  return [blocker];
}

function blockerMessageForStatus(status: ProcessStatus): string | null {
  const id = status.processId;

  switch (status.state) {
    case 'not-installed':
      return `Process "${id}" is not installed.${status.installHint ? ` Hint: ${status.installHint}` : ''}`;

    case 'starting':
      return `Process "${id}" is starting and not yet ready for execution.`;

    case 'busy':
      return `Process "${id}" is busy${status.operationId ? ` (operation "${status.operationId}")` : ''} and cannot accept new work.`;

    case 'degraded':
      return `Process "${id}" is running in a degraded state.${status.healthCheck ? ` Health: ${status.healthCheck}` : ''} Execution may be unreliable.`;

    case 'failed':
      return `Process "${id}" has failed${status.errorCode ? ` (${status.errorCode})` : ''}.${status.recoverable === true ? ' The process may be recoverable.' : ''}`;

    case 'stopping':
      return `Process "${id}" is shutting down${status.reason ? ` (${status.reason})` : ''} and cannot accept new work.`;

    default:
      return null;
  }
}

// ---------------------------------------------------------------------------
// Static helpers (convenience exports)
// ---------------------------------------------------------------------------

/**
 * The contribution kind this adapter services.
 * Convenience re-export for consumers that need the kind without
 * importing the adapter object.
 */
export const PROCESS_ADAPTER_KIND = 'process' as const;

/**
 * Build a conformance report for the process family via the adapter.
 *
 * This is a convenience wrapper around
 * `processAdapter.buildConformanceReport()`.
 */
export function buildProcessConformanceReport(): FamilyConformanceReport<'process'> {
  return processAdapter.buildConformanceReport();
}
