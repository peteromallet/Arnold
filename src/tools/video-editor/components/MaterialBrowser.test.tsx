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
    const action = { kind: 'resolve-blocker' as const, label: 'Materialize mat-a', message: 'Materialize mat-a' };
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
          }],
          diagnostics: [],
        }}
        onAction={onAction}
      />,
    );

    expect(screen.getByLabelText('Material detail')).toHaveTextContent('asset-registry: asset://mat-a');
    expect(screen.getByText('Material mat-a is missing')).toBeInTheDocument();
    fireEvent.click(screen.getByText('Materialize mat-a'));
    expect(onAction).toHaveBeenCalledWith(action, expect.objectContaining({ id: 'mat-a' }));
  });
});
