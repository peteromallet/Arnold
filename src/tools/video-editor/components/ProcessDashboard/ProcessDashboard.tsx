import { memo, useCallback, useEffect, useMemo, useState } from 'react';
import type { ProcessStatus } from '@/sdk/video/families/processes';
import { useOptionalVideoEditorRuntime } from '@/tools/video-editor/contexts/DataProviderContext.tsx';
import type { ProcessResultAttachRecord } from '@/tools/video-editor/runtime/composition/processResultAttach.ts';
import type {
  ExtensionRuntime,
  VideoEditorProcessDescriptor,
} from '@/tools/video-editor/runtime/extensionSurface.ts';

const TRANSIENT_PROCESS_STATES = new Set<ProcessStatus['state']>([
  'starting',
  'busy',
  'stopping',
]);

const TRUSTED_LOCAL_PROTOCOLS = new Set<VideoEditorProcessDescriptor['protocol']>([
  'stdio-jsonrpc',
]);

export interface ProcessDashboardActionState {
  readonly hidden?: boolean;
  readonly disabled?: boolean;
  readonly reason?: string;
}

export interface ProcessDashboardEntry {
  readonly descriptor: VideoEditorProcessDescriptor;
  readonly status?: ProcessStatus;
  readonly isTrustedLocal: boolean;
  readonly configStatus: string;
  readonly settingsStatus: string;
  readonly routes: readonly string[];
  readonly operations: readonly VideoEditorProcessDescriptor['operations'][number][];
  readonly operationsWithMaterialOutput: readonly VideoEditorProcessDescriptor['operations'][number][];
  readonly blockers: readonly string[];
  readonly diagnostics: readonly string[];
  readonly logs: readonly string[];
  readonly attachRecords: readonly ProcessResultAttachRecord[];
  readonly latestAttachRecord?: ProcessResultAttachRecord;
  readonly runningTaskLabel?: string;
  readonly runningTaskId?: string;
  readonly isTransient: boolean;
  readonly actions: {
    readonly start: ProcessDashboardActionState;
    readonly cancel: ProcessDashboardActionState;
    readonly shutdown: ProcessDashboardActionState;
    readonly retry: ProcessDashboardActionState;
  };
}

function readStatusString(status: ProcessStatus | undefined, key: string): string | undefined {
  if (!status) return undefined;
  const value = (status as Record<string, unknown>)[key];
  return typeof value === 'string' && value.length > 0 ? value : undefined;
}

function readStatusTaskId(status: ProcessStatus | undefined): string | undefined {
  return readStatusString(status, 'taskId')
    ?? readStatusString(status, 'requestId')
    ?? readStatusString(status, 'activeTaskId');
}

function statusForCancelTask(
  descriptor: VideoEditorProcessDescriptor,
  status: ProcessStatus | undefined,
): { operationId?: string; taskId?: string } {
  if (!status || status.state !== 'busy') {
    return {};
  }

  const operationId = status.operationId ?? status.progress?.operationId;
  if (!operationId) {
    return {};
  }

  const taskId = readStatusTaskId(status) ?? `${descriptor.processId}:${operationId}`;
  return { operationId, taskId };
}

function collectDeclaredProcesses(
  extensionRuntime: ExtensionRuntime | undefined,
): readonly VideoEditorProcessDescriptor[] {
  if (!extensionRuntime) {
    return [];
  }

  const ordered = [
    ...(extensionRuntime.config.processes ?? []),
    ...(extensionRuntime.processes ?? []),
  ];
  const seen = new Set<string>();
  const deduped: VideoEditorProcessDescriptor[] = [];
  for (const process of ordered) {
    if (seen.has(process.id)) continue;
    seen.add(process.id);
    deduped.push(process);
  }
  return deduped;
}

function uniqueStrings(values: readonly (string | undefined)[]): readonly string[] {
  return [...new Set(values.filter((value): value is string => typeof value === 'string' && value.length > 0))];
}

function formatConfigStatus(process: VideoEditorProcessDescriptor): string {
  const envFields = process.spec.env ?? [];
  const requiredEnvCount = envFields.filter((field) => field.required).length;
  const cwd = process.spec.spawn.cwd ? 'cwd declared' : 'cwd default';
  const env = envFields.length > 0
    ? `${envFields.length} env field${envFields.length === 1 ? '' : 's'}${requiredEnvCount > 0 ? ` (${requiredEnvCount} required)` : ''}`
    : 'no env fields';
  return `${process.spec.spawn.command} · ${cwd} · ${env}`;
}

function formatSettingsStatus(
  process: VideoEditorProcessDescriptor,
  extensionRuntime: ExtensionRuntime | undefined,
): string {
  const defaults = extensionRuntime?.settingsDefaults?.[process.extensionId];
  const defaultKeys = defaults ? Object.keys(defaults) : [];
  if (defaultKeys.length === 0) {
    return 'No extension settings defaults declared.';
  }
  return `${defaultKeys.length} extension setting default${defaultKeys.length === 1 ? '' : 's'} declared.`;
}

function deriveActionState(
  process: VideoEditorProcessDescriptor,
  status: ProcessStatus | undefined,
): ProcessDashboardEntry['actions'] {
  const trustedLocal = TRUSTED_LOCAL_PROTOCOLS.has(process.protocol);
  const cancelTarget = statusForCancelTask(process, status);

  return {
    start: status?.state === 'stopped'
      ? trustedLocal
        ? {}
        : { disabled: true, reason: 'Start is available only for trusted local stdio-jsonrpc processes.' }
      : { hidden: true },
    cancel: status?.state === 'starting'
      ? {}
      : status?.state === 'busy'
        ? cancelTarget.operationId
          ? {}
          : { disabled: true, reason: 'Cancel requires an active operation ID.' }
        : { hidden: true },
    shutdown: status?.state === 'ready' || status?.state === 'busy' || status?.state === 'degraded'
      ? {}
      : { hidden: true },
    retry: status?.state === 'failed'
      ? status.recoverable === true
        ? trustedLocal
          ? {}
          : { disabled: true, reason: 'Retry is available only for trusted local stdio-jsonrpc processes.' }
        : { disabled: true, reason: 'Retry is only available for recoverable failures.' }
      : { hidden: true },
  };
}

export function isTransientProcessState(status: ProcessStatus | undefined): boolean {
  return Boolean(status && TRANSIENT_PROCESS_STATES.has(status.state));
}

export function deriveProcessDashboardEntries(args: {
  readonly extensionRuntime: ExtensionRuntime | undefined;
  readonly statuses: readonly ProcessStatus[];
  readonly attachRecords: readonly ProcessResultAttachRecord[];
}): readonly ProcessDashboardEntry[] {
  const statusesById = new Map(args.statuses.map((status) => [status.processId, status]));
  const attachByProcessId = new Map<string, ProcessResultAttachRecord[]>();
  for (const record of args.attachRecords) {
    const bucket = attachByProcessId.get(record.processId);
    if (bucket) {
      bucket.push(record);
    } else {
      attachByProcessId.set(record.processId, [record]);
    }
  }

  return collectDeclaredProcesses(args.extensionRuntime).map((descriptor) => {
    const status = statusesById.get(descriptor.processId);
    const attachRecords = Object.freeze(
      [...(attachByProcessId.get(descriptor.processId) ?? [])]
        .sort((left, right) => right.provenance.attachedAt.localeCompare(left.provenance.attachedAt)),
    );
    const latestAttachRecord = attachRecords[0];
    const routes = uniqueStrings([
      ...descriptor.availableRoutes,
      ...descriptor.operations.flatMap((operation) => operation.routes ?? []),
    ]);
    const operationsWithMaterialOutput = descriptor.operations.filter((operation) => (
      operation.outputKinds?.includes('material')
    ));
    const blockers = uniqueStrings([
      ...descriptor.blockers.map((blocker) => blocker.message),
      status?.message,
    ]);
    const diagnostics = uniqueStrings([
      ...(status?.diagnostics?.map((diagnostic) => diagnostic.message) ?? []),
      ...(latestAttachRecord?.diagnostics.map((diagnostic) => diagnostic.message) ?? []),
    ]);
    const logs = uniqueStrings([
      ...(latestAttachRecord?.logs.map((log) => `${log.level}: ${log.message}`) ?? []),
    ]);
    const runningTaskLabel = status?.state === 'busy'
      ? status.operationId ?? status.progress?.operationId ?? 'Operation in progress'
      : status?.state === 'starting'
        ? 'Startup in progress'
        : undefined;
    const runningTaskId = readStatusTaskId(status);

    return {
      descriptor,
      status,
      isTrustedLocal: TRUSTED_LOCAL_PROTOCOLS.has(descriptor.protocol),
      configStatus: formatConfigStatus(descriptor),
      settingsStatus: formatSettingsStatus(descriptor, args.extensionRuntime),
      routes,
      operations: descriptor.operations,
      operationsWithMaterialOutput,
      blockers,
      diagnostics,
      logs,
      attachRecords,
      latestAttachRecord,
      runningTaskLabel,
      runningTaskId,
      isTransient: isTransientProcessState(status),
      actions: deriveActionState(descriptor, status),
    } satisfies ProcessDashboardEntry;
  });
}

export function lifecycleBadgeClass(state: ProcessStatus['state'] | undefined): string {
  switch (state) {
    case 'ready':
      return 'border-emerald-300 bg-emerald-50 text-emerald-700';
    case 'busy':
    case 'starting':
    case 'stopping':
      return 'border-amber-300 bg-amber-50 text-amber-700';
    case 'degraded':
      return 'border-orange-300 bg-orange-50 text-orange-700';
    case 'failed':
    case 'not-installed':
      return 'border-rose-300 bg-rose-50 text-rose-700';
    case 'stopped':
    default:
      return 'border-border bg-muted text-muted-foreground';
  }
}

function ProcessDashboardComponent() {
  const runtime = useOptionalVideoEditorRuntime();
  const processManager = runtime?.processManager;
  const declaredProcesses = useMemo(
    () => collectDeclaredProcesses(runtime?.extensionRuntime),
    [runtime?.extensionRuntime],
  );
  const readStatuses = useCallback(
    () => processManager?.listStatuses() ?? runtime?.processStatuses ?? [],
    [processManager, runtime?.processStatuses],
  );
  const [statuses, setStatuses] = useState<readonly ProcessStatus[]>(() => readStatuses());
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [pendingActionByProcessId, setPendingActionByProcessId] = useState<Record<string, string | undefined>>({});
  const [actionErrorByProcessId, setActionErrorByProcessId] = useState<Record<string, string | undefined>>({});

  const refreshStatuses = useCallback(async () => {
    const next = readStatuses();
    setStatuses(next);
    return next;
  }, [readStatuses]);

  useEffect(() => {
    void refreshStatuses();
  }, [refreshStatuses]);

  const entries = useMemo(() => deriveProcessDashboardEntries({
    extensionRuntime: runtime?.extensionRuntime,
    statuses,
    attachRecords: runtime?.processResultAttachRecords ?? [],
  }), [runtime?.extensionRuntime, runtime?.processResultAttachRecords, statuses]);

  useEffect(() => {
    if (!processManager || !entries.some((entry) => entry.isTransient)) {
      return undefined;
    }

    const intervalId = window.setInterval(() => {
      void refreshStatuses();
    }, 1_000);

    return () => window.clearInterval(intervalId);
  }, [entries, processManager, refreshStatuses]);

  const runProcessAction = useCallback(async (
    entry: ProcessDashboardEntry,
    action: 'start' | 'cancel' | 'shutdown' | 'retry',
  ) => {
    if (!processManager) {
      setActionErrorByProcessId((prev) => ({
        ...prev,
        [entry.descriptor.processId]: 'Process manager is unavailable.',
      }));
      return;
    }

    setPendingActionByProcessId((prev) => ({
      ...prev,
      [entry.descriptor.processId]: action,
    }));
    setActionErrorByProcessId((prev) => ({
      ...prev,
      [entry.descriptor.processId]: undefined,
    }));

    try {
      await refreshStatuses();
      if (action === 'start' || action === 'retry') {
        await processManager.start(entry.descriptor.processId);
      } else if (action === 'shutdown') {
        await processManager.shutdown(entry.descriptor.processId, { reason: `dashboard-${action}` });
      } else if (entry.status?.state === 'starting') {
        await processManager.shutdown(entry.descriptor.processId, { reason: 'dashboard-cancel-startup' });
      } else {
        const cancelTarget = statusForCancelTask(entry.descriptor, entry.status);
        if (!cancelTarget.operationId || !cancelTarget.taskId) {
          throw new Error('Cancel requires an active operation/task correlation.');
        }
        await processManager.cancel(entry.descriptor.processId, {
          operationId: cancelTarget.operationId,
          taskId: cancelTarget.taskId,
          reason: 'dashboard-cancel',
        });
      }
    } catch (error) {
      setActionErrorByProcessId((prev) => ({
        ...prev,
        [entry.descriptor.processId]: error instanceof Error ? error.message : 'Process action failed.',
      }));
    } finally {
      await refreshStatuses();
      setPendingActionByProcessId((prev) => ({
        ...prev,
        [entry.descriptor.processId]: undefined,
      }));
    }
  }, [processManager, refreshStatuses]);

  if (!runtime) {
    return (
      <div className="flex items-center justify-center p-6 text-sm text-muted-foreground">
        Process dashboard is unavailable outside of a video editor runtime.
      </div>
    );
  }

  if (declaredProcesses.length === 0) {
    return (
      <div className="flex items-center justify-center p-6 text-sm text-muted-foreground">
        No trusted local processes are declared. Process execution will be available
        when extensions declare stdio-jsonrpc process contributions.
      </div>
    );
  }

  return (
    <div className="flex min-h-0 flex-col gap-3 p-3" data-testid="process-dashboard">
      <div className="text-xs text-muted-foreground">
        {declaredProcesses.length} process{declaredProcesses.length !== 1 ? 'es' : ''} declared
        {entries.some((entry) => entry.isTransient) ? ' · polling transient lifecycle state' : ' · stable snapshot'}
      </div>

      {entries.map((entry) => {
        const pendingAction = pendingActionByProcessId[entry.descriptor.processId];
        const actionError = actionErrorByProcessId[entry.descriptor.processId];
        const isExpanded = expanded[entry.descriptor.processId] ?? false;
        const statusMessage = entry.status?.message ?? 'No lifecycle status reported yet.';
        const progressLabel = entry.status?.state === 'busy' && entry.status.progress
          ? [
            entry.status.progress.currentStep,
            typeof entry.status.progress.percent === 'number' ? `${entry.status.progress.percent}%` : undefined,
            entry.status.progress.message,
          ].filter(Boolean).join(' · ')
          : undefined;

        return (
          <section
            key={entry.descriptor.id}
            data-testid={`process-card-${entry.descriptor.id}`}
            className="rounded-lg border border-border bg-card/70 p-3 shadow-sm"
          >
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="space-y-1">
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="text-sm font-medium">{entry.descriptor.label}</h3>
                  <span
                    data-testid={`process-status-${entry.descriptor.id}`}
                    className={`rounded-full border px-2 py-0.5 text-[11px] font-medium ${lifecycleBadgeClass(entry.status?.state)}`}
                  >
                    {entry.status?.state ?? 'unknown'}
                  </span>
                  <span className="rounded-full border border-border bg-muted px-2 py-0.5 text-[11px] text-muted-foreground">
                    {entry.isTrustedLocal ? 'Trusted local' : 'Declared only'}
                  </span>
                  <span className="rounded-full border border-border bg-muted px-2 py-0.5 text-[11px] text-muted-foreground">
                    {entry.descriptor.protocol}
                  </span>
                </div>
                <div className="text-xs text-muted-foreground">
                  {entry.descriptor.processId}
                </div>
                {entry.descriptor.description ? (
                  <p className="text-xs text-muted-foreground">{entry.descriptor.description}</p>
                ) : null}
              </div>

              <div className="flex flex-wrap items-center gap-2">
                {(['start', 'cancel', 'shutdown', 'retry'] as const).map((action) => {
                  const state = entry.actions[action];
                  if (state.hidden) return null;
                  const isPending = pendingAction === action;
                  return (
                    <button
                      key={action}
                      type="button"
                      data-testid={`process-action-${action}-${entry.descriptor.id}`}
                      className="rounded border border-border px-2 py-1 text-xs disabled:cursor-not-allowed disabled:opacity-50"
                      disabled={Boolean(state.disabled || isPending)}
                      title={state.reason}
                      onClick={() => {
                        void runProcessAction(entry, action);
                      }}
                    >
                      {isPending ? `${action}…` : action.charAt(0).toUpperCase() + action.slice(1)}
                    </button>
                  );
                })}
                <button
                  type="button"
                  data-testid={`process-action-inspect-${entry.descriptor.id}`}
                  className="rounded border border-border px-2 py-1 text-xs"
                  aria-expanded={isExpanded}
                  onClick={() => {
                    setExpanded((prev) => ({
                      ...prev,
                      [entry.descriptor.processId]: !isExpanded,
                    }));
                  }}
                >
                  {isExpanded ? 'Hide details' : 'Inspect'}
                </button>
              </div>
            </div>

            <div className="mt-3 grid gap-2 text-xs text-muted-foreground md:grid-cols-2">
              <div>
                <span className="font-medium text-foreground">Lifecycle</span>
                <div>{statusMessage}</div>
              </div>
              <div>
                <span className="font-medium text-foreground">Config</span>
                <div>{entry.configStatus}</div>
              </div>
              <div>
                <span className="font-medium text-foreground">Settings</span>
                <div>{entry.settingsStatus}</div>
              </div>
              <div>
                <span className="font-medium text-foreground">Routes</span>
                <div>{entry.routes.length > 0 ? entry.routes.join(', ') : 'No route support declared.'}</div>
              </div>
              <div>
                <span className="font-medium text-foreground">Operations</span>
                <div>{entry.operations.map((operation) => operation.label).join(', ') || 'No operations declared.'}</div>
              </div>
              <div>
                <span className="font-medium text-foreground">Material Output</span>
                <div>
                  {entry.operationsWithMaterialOutput.length > 0
                    ? entry.operationsWithMaterialOutput.map((operation) => operation.label).join(', ')
                    : 'No material outputs declared.'}
                </div>
              </div>
              <div>
                <span className="font-medium text-foreground">Running Task</span>
                <div>
                  {entry.runningTaskLabel
                    ? `${entry.runningTaskLabel}${entry.runningTaskId ? ` · ${entry.runningTaskId}` : ''}`
                    : 'No running task.'}
                </div>
              </div>
              <div>
                <span className="font-medium text-foreground">Progress</span>
                <div>{progressLabel ?? 'No active progress.'}</div>
              </div>
              <div>
                <span className="font-medium text-foreground">Attach Records</span>
                <div>
                  {entry.attachRecords.length > 0
                    ? `${entry.attachRecords.length} host-session record${entry.attachRecords.length === 1 ? '' : 's'}`
                    : 'No attach records yet.'}
                </div>
              </div>
              <div>
                <span className="font-medium text-foreground">Latest Result</span>
                <div>
                  {entry.latestAttachRecord
                    ? `${entry.latestAttachRecord.taskId} · ${entry.latestAttachRecord.status} · ${entry.latestAttachRecord.provenance.attachedAt}`
                    : 'No returned-ref provenance yet.'}
                </div>
              </div>
            </div>

            {actionError ? (
              <div className="mt-2 rounded border border-rose-200 bg-rose-50 px-2 py-1 text-xs text-rose-700">
                {actionError}
              </div>
            ) : null}

            {isExpanded ? (
              <div
                className="mt-3 grid gap-3 border-t border-border pt-3 text-xs"
                data-testid={`process-details-${entry.descriptor.id}`}
              >
                <div>
                  <div className="font-medium text-foreground">Blockers</div>
                  {entry.blockers.length > 0 ? (
                    <ul className="mt-1 space-y-1 text-muted-foreground">
                      {entry.blockers.map((blocker) => (
                        <li key={blocker}>{blocker}</li>
                      ))}
                    </ul>
                  ) : (
                    <p className="mt-1 text-muted-foreground">No blockers reported.</p>
                  )}
                </div>

                <div>
                  <div className="font-medium text-foreground">Diagnostics</div>
                  {entry.diagnostics.length > 0 ? (
                    <ul className="mt-1 space-y-1 text-muted-foreground">
                      {entry.diagnostics.map((diagnostic) => (
                        <li key={diagnostic}>{diagnostic}</li>
                      ))}
                    </ul>
                  ) : (
                    <p className="mt-1 text-muted-foreground">No diagnostics reported.</p>
                  )}
                </div>

                <div>
                  <div className="font-medium text-foreground">Logs</div>
                  {entry.logs.length > 0 ? (
                    <ul className="mt-1 space-y-1 text-muted-foreground">
                      {entry.logs.map((log) => (
                        <li key={log}>{log}</li>
                      ))}
                    </ul>
                  ) : (
                    <p className="mt-1 text-muted-foreground">No logs captured.</p>
                  )}
                </div>

                <div>
                  <div className="font-medium text-foreground">Operations Detail</div>
                  <ul className="mt-1 space-y-1 text-muted-foreground">
                    {entry.operations.map((operation) => (
                      <li key={operation.id}>
                        {operation.label}
                        {operation.routes?.length ? ` · routes ${operation.routes.join(', ')}` : ''}
                        {operation.outputKinds?.length ? ` · outputs ${operation.outputKinds.join(', ')}` : ''}
                      </li>
                    ))}
                  </ul>
                </div>

                <div>
                  <div className="font-medium text-foreground">Returned-Ref Provenance</div>
                  {entry.latestAttachRecord ? (
                    <div className="mt-1 space-y-1 text-muted-foreground">
                      <div>
                        {entry.latestAttachRecord.kind} · {entry.latestAttachRecord.provenance.descriptor.descriptorId}
                        {' · '}
                        {entry.latestAttachRecord.provenance.operation.label}
                      </div>
                      <div>
                        task {entry.latestAttachRecord.taskId} · request {entry.latestAttachRecord.provenance.result.requestId}
                        {' · '}
                        attached {entry.latestAttachRecord.provenance.attachedAt}
                      </div>
                      <div>
                        materials: {entry.latestAttachRecord.returnedMaterialRefs.join(', ') || 'none'}
                      </div>
                      <div>
                        artifacts: {entry.latestAttachRecord.artifactRefs.join(', ') || 'none'}
                      </div>
                      <div>
                        sidecars: {entry.latestAttachRecord.sidecars.map((sidecar) => sidecar.filename).join(', ') || 'none'}
                      </div>
                    </div>
                  ) : (
                    <p className="mt-1 text-muted-foreground">No process.result.attach evidence recorded yet.</p>
                  )}
                </div>
              </div>
            ) : null}
          </section>
        );
      })}
    </div>
  );
}

export const ProcessDashboard = memo(ProcessDashboardComponent);
