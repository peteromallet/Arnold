/**
 * Output format projector — pure descriptor projection.
 *
 * Contains no imports from `extensionSurface.ts`, `useTimelineState.types.ts`,
 * or broad runtime slice modules.  Only SDK contracts and descriptor types.
 *
 * @module families/projectors/outputFormatProjector
 */

import type {
  OutputFormatContribution,
  RenderDependentOutputDescriptor,
  IntegrationCapabilities,
  CapabilitySourceRef,
  CapabilityRequirement,
  RenderRoute,
} from '@reigh/editor-sdk';
import type {
  VideoEditorOutputFormatDescriptor,
  VideoEditorRouteRequirementDescriptor,
  VideoEditorProcessRequirementDescriptor,
  VideoEditorPlannerBlockerDescriptor,
  VideoEditorPlannerNextActionDescriptor,
} from '../../extensionSurface';
import type { CollectedContribution } from '../FamilyContributionSequence';
import { sortFamilyContributions, freezeDescriptor } from '../familyAdapterUtils';

export function buildOutputFormatDescriptors(
  contributions: readonly CollectedContribution[],
  extensionOrder?: ReadonlyMap<string, number>,
): readonly VideoEditorOutputFormatDescriptor[] {
  const sorted = sortFamilyContributions(contributions, extensionOrder);
  return sorted.map(({ contribution, extensionId }) => {
    const of = contribution as unknown as OutputFormatContribution;
    const requiresRender = of.requiresRender ?? false;
    const renderDescriptor = requiresRender ? of.render : undefined;
    const id = contribution.id as string;
    const routeRequirements = buildRouteRequirements(renderDescriptor);
    const processRequirements = buildProcessRequirements(renderDescriptor);
    const blockers = buildOutputFormatBlockers(extensionId, id, of, renderDescriptor);
    const nextActions = buildOutputFormatNextActions(of, renderDescriptor, blockers);
    const capabilities = buildOutputFormatCapabilities(extensionId, id, of, renderDescriptor, blockers);

    return freezeDescriptor({
      id,
      extensionId,
      order: contribution.order,
      label: of.label ?? id,
      requiresRender,
      outputExtension: of.outputExtension,
      outputMimeType: of.outputMimeType,
      description: of.description,
      disabled: false,
      disabledReason: undefined,
      availableRoutes: Object.freeze([...(renderDescriptor?.routes ?? [])]),
      routeRequirements,
      processRequirements,
      blockers,
      nextActions,
      capabilities,
      sampling: of.sampling,
      sidecars: Object.freeze([...(of.sidecars ?? [])]),
    });
  });
}

function buildRouteRequirements(
  renderDescriptor: RenderDependentOutputDescriptor | undefined,
): readonly VideoEditorRouteRequirementDescriptor[] {
  if (!renderDescriptor) return Object.freeze([]);

  return Object.freeze([
    freezeDescriptor({
      routes: Object.freeze([...renderDescriptor.routes]),
      requiredCapabilities: Object.freeze([...(renderDescriptor.requiredCapabilities ?? [])]),
      processId: renderDescriptor.processId,
      operationId: renderDescriptor.operationId,
      determinism: renderDescriptor.determinism ?? 'unknown',
      unavailableMessage: renderDescriptor.unavailableMessage,
    }),
  ]);
}

function buildProcessRequirements(
  renderDescriptor: RenderDependentOutputDescriptor | undefined,
): readonly VideoEditorProcessRequirementDescriptor[] {
  if (!renderDescriptor?.processId) return Object.freeze([]);

  return Object.freeze([
    freezeDescriptor({
      processId: renderDescriptor.processId,
      operationId: renderDescriptor.operationId,
      requiredCapabilities: Object.freeze([...(renderDescriptor.requiredCapabilities ?? [])]),
    }),
  ]);
}

function buildOutputFormatBlockers(
  extensionId: string,
  contributionId: string,
  contribution: OutputFormatContribution,
  renderDescriptor: RenderDependentOutputDescriptor | undefined,
): readonly VideoEditorPlannerBlockerDescriptor[] {
  if (!contribution.requiresRender || renderDescriptor) return Object.freeze([]);

  const nextAction: VideoEditorPlannerNextActionDescriptor = freezeDescriptor({
    kind: 'resolve-blocker',
    label: 'Add render route requirements',
    message: 'Render-dependent output formats must declare render routes before planning can execute them.',
  });

  return Object.freeze([
    freezeDescriptor({
      id: `${extensionId}.${contributionId}.missing-render-descriptor`,
      extensionId,
      contributionId,
      reason: 'route-unsupported',
      message: `Output format "${contribution.label ?? contributionId}" requires render planning but did not declare route requirements.`,
      nextAction,
    }),
  ]);
}

function buildOutputFormatNextActions(
  contribution: OutputFormatContribution,
  renderDescriptor: RenderDependentOutputDescriptor | undefined,
  blockers: readonly VideoEditorPlannerBlockerDescriptor[],
): readonly VideoEditorPlannerNextActionDescriptor[] {
  if (!contribution.requiresRender) return Object.freeze([]);
  if (blockers[0]?.nextAction) return Object.freeze([blockers[0].nextAction]);

  const actions: VideoEditorPlannerNextActionDescriptor[] = [];
  if (renderDescriptor?.processId) {
    actions.push(freezeDescriptor({
      kind: 'start-process',
      label: `Start process ${renderDescriptor.processId}`,
      processId: renderDescriptor.processId,
      operationId: renderDescriptor.operationId,
      message: renderDescriptor.unavailableMessage,
    }));
  }

  for (const route of renderDescriptor?.routes ?? []) {
    actions.push(freezeDescriptor({
      kind: 'select-route',
      label: `Plan ${route}`,
      route,
      processId: renderDescriptor?.processId,
      operationId: renderDescriptor?.operationId,
      message: renderDescriptor?.unavailableMessage,
    }));
  }

  return Object.freeze(actions);
}

function buildOutputFormatCapabilities(
  extensionId: string,
  contributionId: string,
  contribution: OutputFormatContribution,
  renderDescriptor: RenderDependentOutputDescriptor | undefined,
  blockers: readonly VideoEditorPlannerBlockerDescriptor[],
): IntegrationCapabilities | undefined {
  const sourceRef: CapabilitySourceRef = Object.freeze({
    source: 'extension',
    extensionId,
    contributionId,
  });

  if (!contribution.requiresRender) {
    return freezeDescriptor({
      extensionId,
      contributionId,
      routes: Object.freeze([]),
      determinism: 'deterministic',
      capabilityRequirements: Object.freeze([]),
      sourceRefs: Object.freeze([sourceRef]),
      fullySupported: true,
      anyBlocked: false,
    });
  }

  const routes = Object.freeze([...(renderDescriptor?.routes ?? [])]);
  const determinism = renderDescriptor?.determinism ?? 'unknown';
  const requiredCapabilities = Object.freeze([...(renderDescriptor?.requiredCapabilities ?? [])]);
  const routeFit = renderDescriptor
    ? undefined
    : freezeDescriptor({
        route: 'sidecar-export' as const,
        fit: 'blocked' as const,
        reason: 'route-unsupported' as const,
        message: blockers[0]?.message,
      });

  const capabilityRequirements: CapabilityRequirement[] = (routes as readonly RenderRoute[]).map((route) => freezeDescriptor({
    id: `${extensionId}.${contributionId}.${route}`,
    sourceRef,
    route,
    requiredCapabilities,
    determinism,
    routeFit: freezeDescriptor({
      route,
      fit: 'supported' as const,
      message: renderDescriptor?.unavailableMessage,
    }),
    blocking: false,
  }));

  if (!renderDescriptor) {
    capabilityRequirements.push(freezeDescriptor({
      id: `${extensionId}.${contributionId}.missing-render-descriptor`,
      sourceRef,
      route: 'sidecar-export',
      requiredCapabilities: Object.freeze([]),
      determinism: 'unknown',
      routeFit,
      findings: Object.freeze(blockers.map((blocker) => freezeDescriptor({
        id: blocker.id,
        severity: 'error' as const,
        route: blocker.route,
        reason: blocker.reason,
        message: blocker.message,
        extensionId: blocker.extensionId,
        contributionId: blocker.contributionId,
      }))),
      blocking: true,
    }));
  }

  return freezeDescriptor({
    extensionId,
    contributionId,
    routes,
    determinism,
    capabilityRequirements: Object.freeze(capabilityRequirements),
    sourceRefs: Object.freeze([sourceRef]),
    fullySupported: blockers.length === 0,
    anyBlocked: blockers.length > 0,
  });
}
