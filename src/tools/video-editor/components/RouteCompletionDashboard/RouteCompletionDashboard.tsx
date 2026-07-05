import type { RenderBlocker } from '@reigh/editor-sdk';
import type { ProcessStatus } from '@/sdk/video/families/processes';
import {
  BlockerActionCard,
  normalizeBlockerActionCardNextAction,
} from '@/tools/video-editor/components/BlockerActionCard.tsx';
import {
  deriveProcessDashboardEntries,
  lifecycleBadgeClass,
} from '@/tools/video-editor/components/ProcessDashboard/ProcessDashboard.tsx';
import type { ProcessResultAttachRecord } from '@/tools/video-editor/runtime/composition/processResultAttach.ts';
import type {
  RenderPlannerResult,
  RenderRoutePlan,
} from '@/tools/video-editor/runtime/renderPlanner.ts';
import type {
  ExtensionRuntime,
  VideoEditorPlannerNextActionDescriptor,
  VideoEditorPlannerNextActionKind,
} from '@/tools/video-editor/runtime/extensionSurface.ts';

export interface RouteCompletionDashboardProps {
  readonly routePlan: RenderRoutePlan;
  readonly plannerResult?: Pick<RenderPlannerResult, 'blockers' | 'nextActions'>;
  readonly extensionRuntime?: Pick<ExtensionRuntime, 'config' | 'processes' | 'settingsDefaults'>;
  readonly processStatuses?: readonly ProcessStatus[];
  readonly processResultAttachRecords?: readonly ProcessResultAttachRecord[];
  readonly onAction?: (action: VideoEditorPlannerNextActionDescriptor) => void;
}

function completionBadgeClass(status: RenderRoutePlan['artifactCompletion']['status']): string {
  switch (status) {
    case 'complete':
      return 'border-emerald-300 bg-emerald-50 text-emerald-700';
    case 'blocked':
      return 'border-rose-300 bg-rose-50 text-rose-700';
    case 'incomplete':
    default:
      return 'border-amber-300 bg-amber-50 text-amber-700';
  }
}

function blockerCode(blocker: RenderBlocker): string {
  const detailCode = blocker.detail?.code;
  if (typeof detailCode === 'string' && detailCode.length > 0) {
    return detailCode;
  }
  return `planner/${blocker.route}/${blocker.reason}`;
}

function dedupeActions(
  actions: readonly VideoEditorPlannerNextActionDescriptor[],
): readonly VideoEditorPlannerNextActionDescriptor[] {
  const seen = new Set<string>();
  return actions.filter((action) => {
    const key = `${action.kind}:${action.route ?? ''}:${action.processId ?? ''}:${action.operationId ?? ''}:${action.label}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function plannerActionFromValue(
  value: unknown,
  fallback?: VideoEditorPlannerNextActionDescriptor,
): VideoEditorPlannerNextActionDescriptor | undefined {
  const nextAction = normalizeBlockerActionCardNextAction(value, fallback);
  if (!nextAction) {
    return fallback;
  }

  const record = value != null && typeof value === 'object'
    ? value as Record<string, unknown>
    : undefined;
  const route = typeof record?.route === 'string' ? record.route : fallback?.route;
  const allowedKinds: readonly VideoEditorPlannerNextActionKind[] = [
    'select-route',
    'materialize',
    'bake',
    'invoke-agent',
    'open-settings',
    'install-extension',
    'enable-extension',
    'start-process',
  ];
  if (!allowedKinds.includes(nextAction.kind as VideoEditorPlannerNextActionKind)) {
    return fallback;
  }

  return {
    kind: nextAction.kind as VideoEditorPlannerNextActionKind,
    label: nextAction.label,
    ...(route ? { route } : {}),
    ...(typeof record?.processId === 'string'
      ? { processId: record.processId }
      : fallback?.processId
        ? { processId: fallback.processId }
        : {}),
    ...(typeof record?.operationId === 'string'
      ? { operationId: record.operationId }
      : fallback?.operationId
        ? { operationId: fallback.operationId }
        : {}),
    ...(nextAction.message ? { message: nextAction.message } : {}),
  };
}

function routeBlockersFor(
  routePlan: RenderRoutePlan,
  plannerResult?: Pick<RenderPlannerResult, 'blockers' | 'nextActions'>,
): readonly RenderBlocker[] {
  return plannerResult
    ? plannerResult.blockers.filter((blocker) => blocker.route === routePlan.route)
    : routePlan.blockers;
}

function routeActionsFor(
  routePlan: RenderRoutePlan,
  plannerResult?: Pick<RenderPlannerResult, 'blockers' | 'nextActions'>,
): readonly VideoEditorPlannerNextActionDescriptor[] {
  const actions = plannerResult
    ? plannerResult.nextActions.filter((action) => !action.route || action.route === routePlan.route)
    : routePlan.nextActions;
  return dedupeActions(actions);
}

function routeProcessIds(routePlan: RenderRoutePlan): ReadonlySet<string> {
  return new Set(routePlan.processRequirements.map((requirement) => requirement.processId));
}

export function RouteCompletionDashboard({
  routePlan,
  plannerResult,
  extensionRuntime,
  processStatuses = [],
  processResultAttachRecords = [],
  onAction,
}: RouteCompletionDashboardProps) {
  const routeBlockers = routeBlockersFor(routePlan, plannerResult);
  const routeActions = routeActionsFor(routePlan, plannerResult);
  const processIds = routeProcessIds(routePlan);
  const processEntries = deriveProcessDashboardEntries({
    extensionRuntime,
    statuses: processStatuses,
    attachRecords: processResultAttachRecords,
  }).filter((entry) => (
    processIds.has(entry.descriptor.processId)
    && entry.routes.includes(routePlan.route)
  ));
  const artifacts = routePlan.artifactCompletion.profiles.flatMap((profile) => profile.artifacts);
  const sidecars = routePlan.artifactCompletion.profiles.flatMap((profile) => profile.sidecars);
  const consumedSources = routePlan.artifactCompletion.profiles.flatMap((profile) => profile.requiredBy);

  return (
    <section
      aria-label={`Route completion ${routePlan.route}`}
      className="space-y-4 rounded-lg border border-border bg-card/70 p-4 shadow-sm"
      data-testid={`route-completion-dashboard-${routePlan.route}`}
    >
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-sm font-medium">{routePlan.route}</h3>
            <span
              data-testid={`route-completion-status-${routePlan.route}`}
              className={`rounded-full border px-2 py-0.5 text-[11px] font-medium ${completionBadgeClass(routePlan.artifactCompletion.status)}`}
            >
              {routePlan.artifactCompletion.status}
            </span>
            <span className="rounded-full border border-border bg-muted px-2 py-0.5 text-[11px] text-muted-foreground">
              {routePlan.blocked ? `${routePlan.blockerCount} blocker${routePlan.blockerCount === 1 ? '' : 's'}` : 'unblocked'}
            </span>
          </div>
          <p className="text-xs text-muted-foreground">
            {routePlan.requiredCapabilities.length > 0
              ? `Capabilities: ${routePlan.requiredCapabilities.join(', ')}`
              : 'No additional capabilities declared.'}
          </p>
          <p className="text-xs text-muted-foreground">
            Determinism: {routePlan.determinism}
            {' · '}
            profiles {routePlan.artifactCompletion.completeProfiles.length}/{routePlan.artifactCompletion.requiredProfiles.length || routePlan.artifactCompletion.profiles.length} complete
          </p>
        </div>
        <div className="rounded border border-border bg-muted/40 px-3 py-2 text-xs text-muted-foreground">
          <div>output formats: {routePlan.outputFormatIds.join(', ') || 'none'}</div>
          <div>evidence sources: {consumedSources.length}</div>
        </div>
      </header>

      <div className="grid gap-3 md:grid-cols-2">
        {routePlan.artifactCompletion.profiles.map((profile) => (
          <article
            key={profile.profile}
            className="rounded border border-border bg-background/60 p-3"
            data-testid={`route-completion-profile-${profile.profile}`}
          >
            <div className="flex items-center justify-between gap-2">
              <h4 className="text-sm font-medium">{profile.profile}</h4>
              <span className={`rounded-full border px-2 py-0.5 text-[11px] font-medium ${completionBadgeClass(profile.status)}`}>
                {profile.status}
              </span>
            </div>
            <div className="mt-2 text-xs text-muted-foreground">
              required by {profile.requiredBy.map((source) => source.source).join(', ') || 'none'}
            </div>
            <div className="mt-2 text-xs text-muted-foreground">
              artifacts {profile.artifacts.length} · sidecars {profile.sidecars.length}
            </div>
            {profile.issues.length > 0 ? (
              <ul className="mt-2 space-y-1 text-xs text-rose-700">
                {profile.issues.map((issue) => (
                  <li key={issue}>{issue}</li>
                ))}
              </ul>
            ) : null}
          </article>
        ))}
      </div>

      <section className="space-y-2">
        <h4 className="text-sm font-medium">Artifacts</h4>
        {artifacts.length > 0 ? (
          <ul className="space-y-2 text-xs text-muted-foreground">
            {artifacts.map((artifact) => (
              <li
                key={artifact.id}
                className="rounded border border-border bg-background/60 px-3 py-2"
                data-testid={`route-completion-artifact-${artifact.id}`}
              >
                <div className="font-medium text-foreground">{artifact.id}</div>
                <div>{artifact.mediaKind} · {artifact.route}</div>
                <div>{artifact.locator.kind}: {artifact.locator.uri}</div>
                <div>manifest {artifact.manifest?.profile ?? 'none'} · sidecars {artifact.sidecars?.length ?? 0}</div>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-xs text-muted-foreground">No artifacts attached for this route yet.</p>
        )}
      </section>

      <section className="space-y-2">
        <h4 className="text-sm font-medium">Sidecars</h4>
        {sidecars.length > 0 ? (
          <ul className="space-y-2 text-xs text-muted-foreground">
            {sidecars.map((sidecar) => {
              const key = sidecar.id ?? `${sidecar.kind}:${sidecar.filename}`;
              return (
                <li
                  key={key}
                  className="rounded border border-border bg-background/60 px-3 py-2"
                  data-testid={`route-completion-sidecar-${key}`}
                >
                  <div className="font-medium text-foreground">{sidecar.filename}</div>
                  <div>{sidecar.kind} · {sidecar.mimeType}</div>
                  <div>{sidecar.locator?.kind ?? 'inline'}: {sidecar.locator?.uri ?? 'inline data only'}</div>
                </li>
              );
            })}
          </ul>
        ) : (
          <p className="text-xs text-muted-foreground">No sidecars attached for this route yet.</p>
        )}
      </section>

      <section className="space-y-2">
        <h4 className="text-sm font-medium">Processes</h4>
        {processEntries.length > 0 ? (
          <ul className="space-y-2">
            {processEntries.map((entry) => (
              <li
                key={entry.descriptor.processId}
                className="rounded border border-border bg-background/60 px-3 py-2 text-xs"
                data-testid={`route-completion-process-${entry.descriptor.processId}`}
              >
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium text-foreground">{entry.descriptor.label}</span>
                  <span
                    data-testid={`route-completion-process-status-${entry.descriptor.processId}`}
                    className={`rounded-full border px-2 py-0.5 text-[11px] font-medium ${lifecycleBadgeClass(entry.status?.state)}`}
                  >
                    {entry.status?.state ?? 'unknown'}
                  </span>
                  <span className="rounded-full border border-border bg-muted px-2 py-0.5 text-[11px] text-muted-foreground">
                    {entry.descriptor.protocol}
                  </span>
                </div>
                <div className="mt-1 text-muted-foreground">{entry.status?.message ?? 'No lifecycle status reported yet.'}</div>
                <div className="mt-1 text-muted-foreground">
                  routes {entry.routes.join(', ') || 'none'} · attach records {entry.attachRecords.length}
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-xs text-muted-foreground">No route-scoped process requirements for this selection.</p>
        )}
      </section>

      <section className="space-y-2">
        <h4 className="text-sm font-medium">Next Actions</h4>
        {routeBlockers.length > 0 || routeActions.length > 0 ? (
          <div className="space-y-2">
            {routeBlockers.map((blocker) => {
              const rawAction = blocker.detail?.nextAction;
              const fallback = plannerActionFromValue(rawAction);
              return (
                <BlockerActionCard
                  key={blocker.id}
                  severity={blocker.severity}
                  code={blockerCode(blocker)}
                  message={blocker.message}
                  nextAction={normalizeBlockerActionCardNextAction(rawAction, fallback)}
                  onAction={fallback && onAction ? () => onAction(fallback) : undefined}
                />
              );
            })}
            {routeActions
              .filter((action) => !routeBlockers.some((blocker) => (
                plannerActionFromValue(blocker.detail?.nextAction)?.label === action.label
              )))
              .map((action) => (
                <BlockerActionCard
                  key={`${action.kind}:${action.route ?? ''}:${action.processId ?? ''}:${action.operationId ?? ''}:${action.label}`}
                  severity="warning"
                  code={`planner/${routePlan.route}/next-action/${action.kind}`}
                  message={action.message ?? action.label}
                  nextAction={normalizeBlockerActionCardNextAction(action, action)}
                  onAction={onAction ? () => onAction(action) : undefined}
                />
              ))}
          </div>
        ) : (
          <p className="text-xs text-muted-foreground">No route-scoped repair actions are pending.</p>
        )}
      </section>
    </section>
  );
}
