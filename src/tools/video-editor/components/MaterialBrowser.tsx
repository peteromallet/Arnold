import { useMemo, useState } from 'react';
import type { CapabilityFinding, RenderMaterialRef } from '@reigh/editor-sdk';
import {
  BlockerActionCard,
  normalizeBlockerActionCardNextAction,
} from '@/tools/video-editor/components/BlockerActionCard.tsx';
import type {
  RenderPlannerMaterialStatus,
  RenderPlannerResult,
} from '@/tools/video-editor/runtime/renderPlanner.ts';
import type {
  VideoEditorPlannerNextActionDescriptor,
  VideoEditorPlannerNextActionKind,
} from '@/tools/video-editor/runtime/extensionSurface.ts';

export interface MaterialBrowserFilters {
  producerExtensionId?: string;
  mediaKind?: RenderMaterialRef['mediaKind'];
  passName?: string;
  renderGroupId?: string;
  determinism?: RenderMaterialRef['determinism'];
  state?: RenderPlannerMaterialStatus['state'] | 'missing-or-stale';
  sourceRef?: string;
  provenance?: string;
}

export interface MaterialBrowserProps {
  materials: readonly RenderMaterialRef[];
  materialStatuses?: readonly RenderPlannerMaterialStatus[];
  plannerResult?: Pick<RenderPlannerResult, 'nextActions' | 'blockers' | 'diagnostics'>;
  onAction?: (action: VideoEditorPlannerNextActionDescriptor, material: RenderMaterialRef) => void;
}

function text(value: unknown): string {
  if (value === null || value === undefined) return '';
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  try {
    return JSON.stringify(value);
  } catch {
    return '';
  }
}

function detailValue(material: RenderMaterialRef, key: string): string {
  const record = material as unknown as Record<string, unknown>;
  return text(record[key] ?? (material.locator as unknown as Record<string, unknown>)[key]);
}

function statusFor(
  material: RenderMaterialRef,
  statuses: readonly RenderPlannerMaterialStatus[],
): RenderPlannerMaterialStatus {
  return statuses.find((status) => status.materialRefId === material.id)
    ?? {
      materialRefId: material.id,
      state: material.determinism === 'deterministic' ? 'resolved' : 'pending',
      detail: material.determinism === 'deterministic' ? undefined : { phase: 'queued' },
    };
}

function matches(material: RenderMaterialRef, status: RenderPlannerMaterialStatus, filters: MaterialBrowserFilters): boolean {
  if (filters.producerExtensionId && material.producerExtensionId !== filters.producerExtensionId) return false;
  if (filters.mediaKind && material.mediaKind !== filters.mediaKind) return false;
  if (filters.determinism && material.determinism !== filters.determinism) return false;
  if (filters.state === 'missing-or-stale' && status.state !== 'missing' && status.state !== 'stale') return false;
  if (filters.state && filters.state !== 'missing-or-stale' && status.state !== filters.state) return false;
  if (filters.passName && detailValue(material, 'passName') !== filters.passName) return false;
  if (filters.renderGroupId && detailValue(material, 'renderGroupId') !== filters.renderGroupId) return false;
  if (filters.sourceRef && !text(material.locator.uri).includes(filters.sourceRef)) return false;
  if (filters.provenance && !text((material as unknown as Record<string, unknown>).provenance).includes(filters.provenance)) return false;
  return true;
}

function actionFor(
  material: RenderMaterialRef,
  actions: readonly VideoEditorPlannerNextActionDescriptor[],
): VideoEditorPlannerNextActionDescriptor | undefined {
  const isMaterialRepairAction = (action: VideoEditorPlannerNextActionDescriptor) =>
    action.kind === 'materialize'
    || action.kind === 'bake'
    || action.kind === 'open-settings'
    || action.kind === 'select-route';
  const materialActions = actions.filter((action) =>
    isMaterialRepairAction(action));
  return materialActions.find((action) => action.message?.includes(material.id) || action.label.includes(material.id))
    ?? materialActions[0];
}

function relatedFindings(
  material: RenderMaterialRef,
  findings: readonly CapabilityFinding[],
): readonly CapabilityFinding[] {
  return findings.filter((finding) =>
    finding.materialRefId === material.id
    || finding.message.includes(material.id)
    || text(finding.detail).includes(material.id));
}

function findingCode(finding: CapabilityFinding): string {
  const detailCode = finding.detail?.code;
  if (typeof detailCode === 'string' && detailCode.length > 0) {
    return detailCode;
  }
  if (finding.route && finding.reason) {
    return `planner/${finding.route}/${finding.reason}`;
  }
  if (finding.reason) {
    return `planner/${finding.reason}`;
  }
  return 'planner/finding';
}

function plannerActionFromRecord(
  value: unknown,
  fallback?: VideoEditorPlannerNextActionDescriptor,
): VideoEditorPlannerNextActionDescriptor | undefined {
  const action = normalizeBlockerActionCardNextAction(value, fallback);
  if (!action) return fallback;

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
  ];
  if (!allowedKinds.includes(action.kind as VideoEditorPlannerNextActionKind)) {
    return fallback;
  }

  return {
    kind: action.kind as VideoEditorPlannerNextActionKind,
    label: action.label,
    ...(action.message ? { message: action.message } : {}),
    ...(route ? { route } : {}),
  };
}

export function MaterialBrowser({
  materials,
  materialStatuses = [],
  plannerResult,
  onAction,
}: MaterialBrowserProps) {
  const [filters, setFilters] = useState<MaterialBrowserFilters>({});
  const [selectedId, setSelectedId] = useState(materials[0]?.id ?? '');
  const findings = [...(plannerResult?.blockers ?? []), ...(plannerResult?.diagnostics ?? [])];
  const rows = useMemo(() => materials
    .map((material) => ({ material, status: statusFor(material, materialStatuses) }))
    .filter(({ material, status }) => matches(material, status, filters)), [filters, materialStatuses, materials]);
  const selected = rows.find((row) => row.material.id === selectedId) ?? rows[0];
  const selectedAction = selected ? actionFor(selected.material, plannerResult?.nextActions ?? []) : undefined;
  const selectedFindings = selected ? relatedFindings(selected.material, findings) : [];

  return (
    <section aria-label="Material browser" className="space-y-3">
      <div className="grid gap-2 sm:grid-cols-3">
        <input aria-label="Producer filter" placeholder="Producer" value={filters.producerExtensionId ?? ''} onChange={(event) => setFilters((next) => ({ ...next, producerExtensionId: event.target.value || undefined }))} />
        <input aria-label="Media kind filter" placeholder="Media kind" value={filters.mediaKind ?? ''} onChange={(event) => setFilters((next) => ({ ...next, mediaKind: event.target.value as MaterialBrowserFilters['mediaKind'] || undefined }))} />
        <input aria-label="Pass filter" placeholder="Pass" value={filters.passName ?? ''} onChange={(event) => setFilters((next) => ({ ...next, passName: event.target.value || undefined }))} />
        <input aria-label="Group filter" placeholder="Group" value={filters.renderGroupId ?? ''} onChange={(event) => setFilters((next) => ({ ...next, renderGroupId: event.target.value || undefined }))} />
        <input aria-label="Determinism filter" placeholder="Determinism" value={filters.determinism ?? ''} onChange={(event) => setFilters((next) => ({ ...next, determinism: event.target.value as MaterialBrowserFilters['determinism'] || undefined }))} />
        <input aria-label="State filter" placeholder="State" value={filters.state ?? ''} onChange={(event) => setFilters((next) => ({ ...next, state: event.target.value as MaterialBrowserFilters['state'] || undefined }))} />
        <input aria-label="Source ref filter" placeholder="Source ref" value={filters.sourceRef ?? ''} onChange={(event) => setFilters((next) => ({ ...next, sourceRef: event.target.value || undefined }))} />
        <input aria-label="Provenance filter" placeholder="Provenance" value={filters.provenance ?? ''} onChange={(event) => setFilters((next) => ({ ...next, provenance: event.target.value || undefined }))} />
      </div>
      {rows.length === 0 ? (
        <p>No materials match the current filters.</p>
      ) : (
        <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_minmax(280px,0.8fr)]">
          <ul aria-label="Material results">
            {rows.map(({ material, status }) => (
              <li key={material.id}>
                <button type="button" onClick={() => setSelectedId(material.id)}>
                  {material.id} {material.mediaKind} {material.determinism} {status.state}
                </button>
              </li>
            ))}
          </ul>
          {selected && (
            <article aria-label="Material detail">
              <h3>{selected.material.id}</h3>
              <dl>
                <dt>Producer</dt><dd>{selected.material.producerExtensionId ?? 'unknown'}</dd>
                <dt>Locator</dt><dd>{selected.material.locator.kind}: {selected.material.locator.uri}</dd>
                <dt>State</dt><dd>{selected.status.state}{selected.status.detail?.phase ? ` (${selected.status.detail.phase})` : ''}{selected.status.detail?.quality ? ` [${selected.status.detail.quality}]` : ''}</dd>
                <dt>Pass</dt><dd>{detailValue(selected.material, 'passName') || 'none'}</dd>
                <dt>Group</dt><dd>{detailValue(selected.material, 'renderGroupId') || 'none'}</dd>
                <dt>Provenance</dt><dd>{text((selected.material as unknown as Record<string, unknown>).provenance) || 'none'}</dd>
              </dl>
              <div className="space-y-2" data-video-editor-material-blockers="true">
                {selectedFindings.map((finding) => {
                  const rawAction = finding.detail?.repairAction ?? finding.detail?.nextAction;
                  const plannerAction = plannerActionFromRecord(rawAction, selectedAction);
                  return (
                    <BlockerActionCard
                      key={finding.id}
                      severity={finding.severity}
                      code={findingCode(finding)}
                      message={finding.message}
                      nextAction={normalizeBlockerActionCardNextAction(rawAction, plannerAction)}
                      onAction={plannerAction ? () => onAction?.(plannerAction, selected.material) : undefined}
                    />
                  );
                })}
                {selectedFindings.length === 0 && selectedAction && (
                  <BlockerActionCard
                    severity="warning"
                    code="planner/material-action"
                    message={selectedAction.message ?? selectedAction.label}
                    nextAction={normalizeBlockerActionCardNextAction(selectedAction, selectedAction)}
                    onAction={() => onAction?.(selectedAction, selected.material)}
                  />
                )}
              </div>
            </article>
          )}
        </div>
      )}
    </section>
  );
}
