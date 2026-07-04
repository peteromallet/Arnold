import { render, screen, fireEvent } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { MaterialBrowser } from './MaterialBrowser';
import type { RenderMaterialRef } from '@reigh/editor-sdk';

function material(id: string, overrides: Partial<RenderMaterialRef> & Record<string, unknown> = {}): RenderMaterialRef {
  return {
    id,
    mediaKind: 'image',
    locator: { kind: 'asset-registry', uri: `asset://${id}` },
    producerExtensionId: 'ext.materials',
    determinism: 'live-unbaked',
    replacementPolicy: 'materialize-on-export',
    ...overrides,
  } as RenderMaterialRef;
}

describe('MaterialBrowser', () => {
  it('filters by producer, media kind, pass/group, determinism, state, source refs, and provenance', () => {
    render(
      <MaterialBrowser
        materials={[
          material('mat-a', { passName: 'beauty', renderGroupId: 'hero', provenance: { source: 'camera-a' } }),
          material('mat-b', {
            mediaKind: 'video',
            producerExtensionId: 'ext.other',
            passName: 'depth',
            renderGroupId: 'bg',
            determinism: 'deterministic',
            locator: { kind: 'url', uri: 'https://example.test/bg.mp4' },
          }),
        ]}
        materialStatuses={[
          { materialRefId: 'mat-a', state: 'stale' },
          { materialRefId: 'mat-b', state: 'resolved' },
        ]}
      />,
    );

    fireEvent.change(screen.getByLabelText('Producer filter'), { target: { value: 'ext.materials' } });
    fireEvent.change(screen.getByLabelText('Media kind filter'), { target: { value: 'image' } });
    fireEvent.change(screen.getByLabelText('Pass filter'), { target: { value: 'beauty' } });
    fireEvent.change(screen.getByLabelText('Group filter'), { target: { value: 'hero' } });
    fireEvent.change(screen.getByLabelText('Determinism filter'), { target: { value: 'live-unbaked' } });
    fireEvent.change(screen.getByLabelText('State filter'), { target: { value: 'missing-or-stale' } });
    fireEvent.change(screen.getByLabelText('Source ref filter'), { target: { value: 'mat-a' } });
    fireEvent.change(screen.getByLabelText('Provenance filter'), { target: { value: 'camera-a' } });

    expect(screen.getByText(/mat-a image live-unbaked stale/)).toBeInTheDocument();
    expect(screen.queryByText(/mat-b/)).not.toBeInTheDocument();
  });

  it('renders empty states, material detail, findings, and dispatches planner next actions', () => {
    const onAction = vi.fn();
    const action = {
      kind: 'materialize' as const,
      label: 'Materialize mat-a',
      message: 'Materialize mat-a',
      detail: { specificKind: 'resolve-blocker' as const },
    };
    const { rerender } = render(<MaterialBrowser materials={[]} />);
    expect(screen.getByText('No materials match the current filters.')).toBeInTheDocument();

    rerender(
      <MaterialBrowser
        materials={[material('mat-a', { provenance: { process: 'bake' } })]}
        materialStatuses={[{ materialRefId: 'mat-a', state: 'missing', message: 'Missing bytes' }]}
        plannerResult={{
          nextActions: [action],
          blockers: [{
            id: 'blocker-a',
            severity: 'error',
            route: 'browser-export',
            reason: 'missing-material',
            materialRefId: 'mat-a',
            message: 'Material mat-a is missing',
            detail: {
              code: 'composition/material-not-resolved',
              nextAction: { kind: 'materialize' },
            },
          }],
          diagnostics: [],
        }}
        onAction={onAction}
      />,
    );

    expect(screen.getByLabelText('Material detail')).toHaveTextContent('asset-registry: asset://mat-a');
    expect(screen.getByText('composition/material-not-resolved')).toBeInTheDocument();
    expect(screen.getByText('Material mat-a is missing')).toBeInTheDocument();
    fireEvent.click(screen.getByText('Materialize mat-a'));
    expect(onAction).toHaveBeenCalledWith(expect.objectContaining({
      kind: action.kind,
      label: action.label,
      message: action.message,
    }), expect.objectContaining({ id: 'mat-a' }));
  });

  it('recognizes bake actions alongside materialize and displays status detail phase/quality', () => {
    const onAction = vi.fn();
    const bakeAction = {
      kind: 'bake' as const,
      label: 'Bake mat-a',
      message: 'Material "mat-a" must be baked before export.',
      detail: { specificKind: 'resolve-blocker' as const },
    };
    render(
      <MaterialBrowser
        materials={[material('mat-a')]}
        materialStatuses={[{
          materialRefId: 'mat-a',
          state: 'pending',
          detail: { phase: 'active' as const, quality: 'route-incompatible' as const },
        }]}
        plannerResult={{
          nextActions: [bakeAction],
          blockers: [],
          diagnostics: [],
        }}
        onAction={onAction}
      />,
    );

    expect(screen.getByLabelText('Material detail')).toHaveTextContent('pending (active) [route-incompatible]');
    expect(screen.getByText('planner/material-action')).toBeInTheDocument();
    fireEvent.click(screen.getByText('Bake mat-a'));
    expect(onAction).toHaveBeenCalledWith(bakeAction, expect.objectContaining({ id: 'mat-a' }));
  });

  it('falls back nondeterministic materials to pending+queued when no status is provided', () => {
    render(
      <MaterialBrowser
        materials={[
          material('nd-mat', { determinism: 'live-unbaked' }),
          material('det-mat', { determinism: 'deterministic' }),
        ]}
      />,
    );

    // nondeterministic without explicit status → pending + queued
    expect(screen.getByText(/nd-mat image live-unbaked pending/)).toBeInTheDocument();
    expect(screen.getByLabelText('Material detail')).toHaveTextContent('pending (queued)');

    // click the det-mat row to switch detail view
    fireEvent.click(screen.getByText(/det-mat image deterministic resolved/));
    expect(screen.getByLabelText('Material detail')).toHaveTextContent('resolved');
  });

  it('filters by each of the five material statuses individually', () => {
    render(
      <MaterialBrowser
        materials={[
          material('m-missing', { determinism: 'deterministic' }),
          material('m-pending', { determinism: 'live-unbaked' }),
          material('m-resolved', { determinism: 'deterministic' }),
          material('m-stale', { determinism: 'deterministic' }),
          material('m-failed', { determinism: 'deterministic' }),
        ]}
        materialStatuses={[
          { materialRefId: 'm-missing', state: 'missing' },
          { materialRefId: 'm-pending', state: 'pending', detail: { phase: 'queued' } },
          { materialRefId: 'm-resolved', state: 'resolved' },
          { materialRefId: 'm-stale', state: 'stale' },
          { materialRefId: 'm-failed', state: 'failed' },
        ]}
      />,
    );

    const stateFilter = screen.getByLabelText('State filter');
    const results = () => screen.getByLabelText('Material results');

    fireEvent.change(stateFilter, { target: { value: 'missing' } });
    expect(results().textContent).toContain('m-missing');
    expect(results().textContent).not.toContain('m-pending');

    fireEvent.change(stateFilter, { target: { value: 'pending' } });
    expect(results().textContent).toContain('m-pending');
    expect(results().textContent).not.toContain('m-missing');

    fireEvent.change(stateFilter, { target: { value: 'resolved' } });
    expect(results().textContent).toContain('m-resolved');

    fireEvent.change(stateFilter, { target: { value: 'stale' } });
    expect(results().textContent).toContain('m-stale');

    fireEvent.change(stateFilter, { target: { value: 'failed' } });
    expect(results().textContent).toContain('m-failed');
  });

  it('applies missing-or-stale composite filter covering both states', () => {
    render(
      <MaterialBrowser
        materials={[
          material('mat-missing', { determinism: 'deterministic' }),
          material('mat-stale', { determinism: 'deterministic' }),
          material('mat-pending', { determinism: 'live-unbaked' }),
          material('mat-resolved', { determinism: 'deterministic' }),
        ]}
        materialStatuses={[
          { materialRefId: 'mat-missing', state: 'missing' },
          { materialRefId: 'mat-stale', state: 'stale' },
          { materialRefId: 'mat-pending', state: 'pending', detail: { phase: 'queued' } },
          { materialRefId: 'mat-resolved', state: 'resolved' },
        ]}
      />,
    );

    fireEvent.change(screen.getByLabelText('State filter'), { target: { value: 'missing-or-stale' } });
    const results = screen.getByLabelText('Material results');
    expect(results.textContent).toContain('mat-missing');
    expect(results.textContent).toContain('mat-stale');
    expect(results.textContent).not.toContain('mat-pending');
    expect(results.textContent).not.toContain('mat-resolved');
  });
});
