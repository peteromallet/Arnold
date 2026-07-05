/**
 * Process projector — pure descriptor projection.
 *
 * Contains no imports from `extensionSurface.ts`, `useTimelineState.types.ts`,
 * or broad runtime slice modules.
 *
 * @module families/projectors/processProjector
 */

import type {
  ProcessContribution,
  ProcessOperationSpec,
  RenderRoute,
} from '@reigh/editor-sdk';
import type {
  VideoEditorProcessDescriptor,
  VideoEditorProcessOperationDescriptor,
  VideoEditorRouteScopeDescriptor,
  VideoEditorPlannerNextActionDescriptor,
} from '../../extensionSurface';
import type { CollectedContribution } from '../FamilyContributionSequence';
import { sortFamilyContributions, freezeDescriptor } from '../familyAdapterUtils';

export function buildProcessDescriptors(
  contributions: readonly CollectedContribution[],
  extensionOrder?: ReadonlyMap<string, number>,
): readonly VideoEditorProcessDescriptor[] {
  const sorted = sortFamilyContributions(contributions, extensionOrder);
  return sorted.map(({ contribution, extensionId }) => {
    const processContrib = contribution as unknown as ProcessContribution;
    const spec = processContrib.spec;
    const operations = normalizeOperations(spec.operations ?? []);
    const availableRoutes = Object.freeze(
      Array.from(new Set(operations.flatMap((operation) => operation.routes))),
    );
    const id = contribution.id as string;
    const label = processContrib.label ?? spec.label ?? spec.id;

    return freezeDescriptor({
      id,
      extensionId,
      order: contribution.order,
      processId: spec.id,
      label,
      description: spec.description,
      spec,
      protocol: spec.protocol,
      operations,
      availableRoutes,
      capabilities: spec.capabilities,
      requiredBy: Object.freeze([...(spec.requiredBy ?? [])]),
      blockers: Object.freeze([]),
      nextActions: Object.freeze([] as VideoEditorPlannerNextActionDescriptor[]),
    });
  });
}

function normalizeOperations(
  operations: readonly ProcessOperationSpec[],
): readonly VideoEditorProcessOperationDescriptor[] {
  return Object.freeze(operations.map((operation) => {
    const routes = Object.freeze([...(operation.routes ?? [])]);
    return freezeDescriptor({
      ...operation,
      routes,
      routeScope: buildRouteScope('process-operation', routes),
    });
  }));
}

function buildRouteScope(
  source: VideoEditorRouteScopeDescriptor['source'],
  routes: readonly RenderRoute[],
): VideoEditorRouteScopeDescriptor {
  return freezeDescriptor({
    source,
    mode: routes.length > 0 ? 'explicit-routes' : 'missing-routes',
    routes,
  });
}
