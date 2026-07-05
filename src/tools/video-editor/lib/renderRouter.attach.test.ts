import { beforeEach, describe, expect, it, vi } from 'vitest';

const planRenderMock = vi.hoisted(() => vi.fn(() => ({
  canBrowserExport: true,
  canWorkerExport: false,
})));

vi.mock('@/tools/video-editor/runtime/renderPlanner.ts', () => ({
  planRender: planRenderMock,
}));

import { decideRenderRoute } from '@/tools/video-editor/lib/renderRouter';

describe('renderRouter process attach planner inputs', () => {
  beforeEach(() => {
    planRenderMock.mockClear();
  });

  it('forwards process attach evidence and process runtime inputs into planner calls', () => {
    const attachRecord = { kind: 'process.result.attach', processId: 'dataset-process' } as const;
    const processStatus = { processId: 'dataset-process', state: 'ready' } as const;
    const processDescriptor = {
      id: 'proc.descriptor',
      extensionId: 'ext.process',
      processId: 'dataset-process',
      protocol: 'stdio-jsonrpc',
      availableRoutes: ['browser-export'],
      operations: [],
      requiredBy: [],
      blockers: [],
      nextActions: [],
      capabilities: { defaultRoute: 'browser-export', determinism: 'process-dependent', capabilityRequirements: [] },
      spec: { id: 'dataset-process', label: 'Dataset Process' },
    } as const;
    const materialRef = {
      id: 'mat-attached',
      mediaKind: 'video',
      locator: { kind: 'provider', uri: 'provider://materials/mat-attached' },
      determinism: 'process-dependent',
      replacementPolicy: 'materialize-on-export',
    } as const;
    const materialStatus = {
      materialRefId: 'mat-attached',
      state: 'resolved',
    } as const;
    const compositionGraph = {
      nodes: [],
      edges: [],
      referenceStates: [],
      diagnostics: [],
    } as const;

    decideRenderRoute(
      { clips: [{ clipType: 'media' }] },
      undefined,
      {
        compositionGraph,
        processes: [processDescriptor as any],
        processStatuses: [processStatus],
        processResultAttachRecords: [attachRecord as any],
        materialRefs: [materialRef as any],
        materialStatuses: [materialStatus as any],
      },
    );

    expect(planRenderMock).toHaveBeenCalledWith(expect.objectContaining({
      compositionGraph,
      processes: [processDescriptor],
      processStatuses: [processStatus],
      processResultAttachRecords: [attachRecord],
      materialRefs: [materialRef],
      materialStatuses: [materialStatus],
    }));
  });
});
