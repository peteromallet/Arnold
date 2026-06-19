import {
  collectBuiltInKnownIds,
  collectExtensionDeclaredIds,
  scanExportConfig,
  type ExportGuardResult,
  type InactiveKnownIds,
  type KnownIdCollection,
} from '@/tools/video-editor/runtime/exportGuard.ts';
import type {
  EffectRegistryRecord,
  EffectRegistrySnapshot,
} from '@/tools/video-editor/effects/registry/types.ts';
import type { TransitionRegistryRecord, TransitionRegistrySnapshot } from '@/tools/video-editor/transitions/registry/types.ts';
import type { ExtensionRuntime } from '@/tools/video-editor/runtime/extensionSurface.ts';
import type { ResolvedTimelineConfig } from '@/tools/video-editor/types/index.ts';
import type {
  CapabilityFinding,
  CapabilityFindingSeverity,
  RenderBlocker,
  RenderBlockerReason,
  RenderCapability,
  RenderCapabilityStatus,
  RenderRoute,
} from '@/tools/video-editor/runtime/renderability.ts';
import { RENDER_ROUTES } from '@/tools/video-editor/runtime/renderability.ts';
import type { ExtensionContribution } from '@reigh/editor-sdk';

export interface RenderPlannerInput {
  readonly config: ResolvedTimelineConfig | null;
  readonly effectRegistrySnapshot?: EffectRegistrySnapshot;
  readonly transitionRegistrySnapshot?: TransitionRegistrySnapshot;
  readonly extensionRuntime?: ExtensionRuntime;
  readonly builtInKnownIds?: KnownIdCollection;
  readonly inactiveKnownIds?: InactiveKnownIds;
}

export interface RenderRouteSummary {
  readonly route: RenderRoute;
  readonly blockerCount: number;
  readonly findingCount: number;
  readonly blocked: boolean;
}

export interface RenderPlannerResult {
  readonly guard: ExportGuardResult;
  readonly findings: readonly CapabilityFinding[];
  readonly blockers: readonly RenderBlocker[];
  readonly routes: readonly RenderRouteSummary[];
  readonly canBrowserExport: boolean;
  readonly canWorkerExport: boolean;
}

function extensionContributions(extensionRuntime: ExtensionRuntime | undefined): ExtensionContribution[] {
  if (!extensionRuntime) return [];
  return extensionRuntime.extensions.flatMap((extension) => extension.manifest.contributions ?? []);
}

function findingSeverityForStatus(status: RenderCapabilityStatus): CapabilityFindingSeverity {
  switch (status) {
    case 'blocked':
      return 'error';
    case 'unknown':
      return 'warning';
    case 'supported':
      return 'info';
  }
}

function blockerReasonForCapability(capability: RenderCapability): RenderBlockerReason {
  if (capability.blockerReason) return capability.blockerReason;
  return capability.status === 'unknown' ? 'unknown' : 'route-unsupported';
}

/** Record shape shared by EffectRegistryRecord and TransitionRegistryRecord for capability scanning. */
interface RegistryRecordLike {
  readonly contributorId: string;
  readonly contributionId: string;
  readonly ownerExtensionId?: string;
  readonly provenance: string;
  readonly status: string;
}

function findingForCapability(record: RegistryRecordLike, capability: RenderCapability): CapabilityFinding | undefined {
  if (capability.status === 'supported') return undefined;

  const reason = blockerReasonForCapability(capability);
  const isEffect = !!(record as any).effectId;
  const sourceLabel = isEffect ? 'effect-registry' : 'transition-registry';
  const typeKey = isEffect ? 'effectType' : 'transitionType';
  const typeValue = (record as any).effectId ?? (record as any).transitionId;
  const idPrefix = isEffect ? 'registry.effect' : 'registry.transition';
  return Object.freeze({
    id: `${idPrefix}.${typeValue}.${capability.route}.${reason}`,
    severity: findingSeverityForStatus(capability.status),
    route: capability.route,
    reason,
    message: capability.message
      ?? `\"${typeValue}\" ${capability.status === 'unknown' ? 'has unknown support for' : 'does not support'} ${capability.route}.`,
    ...(record.ownerExtensionId ? { extensionId: record.ownerExtensionId } : {}),
    contributionId: record.contributionId,
    detail: {
      source: sourceLabel,
      [typeKey]: typeValue,
      provenance: record.provenance,
      status: record.status,
      determinism: capability.determinism,
    },
  });
}

function blockerForRegistryBlocker(record: RegistryRecordLike, blocker: RenderBlocker): RenderBlocker {
  const isEffect = !!(record as any).effectId;
  const sourceLabel = isEffect ? 'effect-registry' : 'transition-registry';
  const typeKey = isEffect ? 'effectType' : 'transitionType';
  const typeValue = (record as any).effectId ?? (record as any).transitionId;
  return Object.freeze({
    ...blocker,
    ...(blocker.extensionId ?? record.ownerExtensionId ? { extensionId: blocker.extensionId ?? record.ownerExtensionId } : {}),
    contributionId: blocker.contributionId ?? record.contributionId,
    detail: {
      source: sourceLabel,
      [typeKey]: typeValue,
      provenance: record.provenance,
      status: record.status,
      ...(blocker.detail ?? {}),
    },
  });
}

function blockerForFinding(finding: CapabilityFinding): RenderBlocker | undefined {
  if (finding.severity !== 'error' || !finding.route || !finding.reason) return undefined;
  return Object.freeze({
    ...finding,
    severity: 'error',
    route: finding.route,
    reason: finding.reason,
  });
}

function collectRegistryFindingsAndBlockers(snapshot: EffectRegistrySnapshot | undefined): {
  findings: CapabilityFinding[];
  blockers: RenderBlocker[];
} {
  const findings: CapabilityFinding[] = [];
  const blockers: RenderBlocker[] = [];

  for (const record of snapshot?.records ?? []) {
    for (const capability of record.renderability.capabilities) {
      const finding = findingForCapability(record, capability);
      if (!finding) continue;
      findings.push(finding);
      const blocker = blockerForFinding(finding);
      if (blocker) blockers.push(blocker);
    }

    for (const blocker of record.renderability.blockers ?? []) {
      blockers.push(blockerForRegistryBlocker(record, blocker));
    }
  }

  return { findings, blockers };
}

function collectTransitionRegistryFindingsAndBlockers(snapshot: TransitionRegistrySnapshot | undefined): {
  findings: CapabilityFinding[];
  blockers: RenderBlocker[];
} {
  const findings: CapabilityFinding[] = [];
  const blockers: RenderBlocker[] = [];

  for (const record of snapshot?.records ?? []) {
    for (const capability of record.renderability.capabilities) {
      const finding = findingForCapability(record, capability);
      if (!finding) continue;
      findings.push(finding);
      const blocker = blockerForFinding(finding);
      if (blocker) blockers.push(blocker);
    }

    for (const blocker of record.renderability.blockers ?? []) {
      blockers.push(blockerForRegistryBlocker(record, blocker));
    }

    // Worker-export default-block: if no worker-export capability is declared, block worker export
    const hasWorkerCapability = record.renderability.capabilities.some(
      (cap) => cap.route === 'worker-export',
    );
    if (!hasWorkerCapability && record.status === 'active') {
      const id = `transition.${record.transitionId}.worker-export.route-unsupported`;
      const message = `Transition \"${record.transitionId}\" does not declare worker-export support. Worker export is blocked by default.`;
      findings.push({
        id,
        severity: 'error',
        route: 'worker-export',
        reason: 'route-unsupported',
        message,
        ...(record.ownerExtensionId ? { extensionId: record.ownerExtensionId } : {}),
        contributionId: record.contributionId,
        detail: {
          source: 'transition-registry',
          transitionType: record.transitionId,
          provenance: record.provenance,
          status: record.status,
        },
      });
      blockers.push({
        id,
        severity: 'error',
        route: 'worker-export',
        reason: 'route-unsupported',
        message,
        ...(record.ownerExtensionId ? { extensionId: record.ownerExtensionId } : {}),
        contributionId: record.contributionId,
        detail: {
          source: 'transition-registry',
          transitionType: record.transitionId,
          provenance: record.provenance,
          status: record.status,
        },
      });
    }
  }

  return { findings, blockers };
}

function dedupeById<T extends { readonly id: string }>(items: readonly T[]): T[] {
  const seen = new Set<string>();
  const deduped: T[] = [];
  for (const item of items) {
    if (seen.has(item.id)) continue;
    seen.add(item.id);
    deduped.push(item);
  }
  return deduped;
}

function routeSummary(
  route: RenderRoute,
  findings: readonly CapabilityFinding[],
  blockers: readonly RenderBlocker[],
): RenderRouteSummary {
  const routeBlockers = blockers.filter((blocker) => blocker.route === route);
  const routeFindings = findings.filter((finding) => !finding.route || finding.route === route);
  return Object.freeze({
    route,
    blockerCount: routeBlockers.length,
    findingCount: routeFindings.length,
    blocked: routeBlockers.length > 0,
  });
}

export function planRender(input: RenderPlannerInput): RenderPlannerResult {
  const builtIn = input.builtInKnownIds ?? collectBuiltInKnownIds();
  const inactiveIds = input.inactiveKnownIds
    ?? collectExtensionDeclaredIds(extensionContributions(input.extensionRuntime));
  const guard = scanExportConfig(
    input.config,
    builtIn,
    inactiveIds,
    input.effectRegistrySnapshot,
    input.transitionRegistrySnapshot,
  );
  const registry = collectRegistryFindingsAndBlockers(input.effectRegistrySnapshot);
  const transitionRegistry = collectTransitionRegistryFindingsAndBlockers(input.transitionRegistrySnapshot);
  const findings = Object.freeze(
    dedupeById([...guard.findings, ...registry.findings, ...transitionRegistry.findings]).sort((a, b) => a.id.localeCompare(b.id)),
  );
  const blockers = Object.freeze(
    dedupeById([...guard.blockers, ...registry.blockers, ...transitionRegistry.blockers]).sort((a, b) => a.id.localeCompare(b.id)),
  );

  const routes: readonly RenderRouteSummary[] = Object.freeze(
    RENDER_ROUTES.map((route) => routeSummary(route, findings, blockers)),
  );
  const browserRoute = routes.find((route) => route.route === 'browser-export');
  const workerRoute = routes.find((route) => route.route === 'worker-export');

  return Object.freeze({
    guard,
    findings,
    blockers,
    routes,
    canBrowserExport: !browserRoute?.blocked,
    canWorkerExport: !workerRoute?.blocked,
  });
}
