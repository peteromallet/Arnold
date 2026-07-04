import { describe, expect, it } from 'vitest';
import type {
  CompositionGraph,
  ExtensionDiagnostic,
  TimelineShaderSummary,
  TimelineSnapshot,
} from '@reigh/editor-sdk';
import { decideRenderRoute } from '@/tools/video-editor/lib/renderRouter.ts';
import { planRender } from '@/tools/video-editor/runtime/renderPlanner.ts';
import type { VideoEditorShaderDescriptor } from '@/tools/video-editor/runtime/extensionSurface.ts';

function snapshotWithShaders(
  shaders: readonly TimelineShaderSummary[],
): TimelineSnapshot {
  return {
    projectId: 'project-graph',
    baseVersion: 1,
    currentVersion: 1,
    extensionRequirements: [],
    clips: [
      {
        id: 'clip-1',
        track: 'V1',
        at: 0,
        clipType: 'media',
        duration: 30,
        managed: false,
      },
    ],
    tracks: [
      {
        id: 'V1',
        kind: 'visual',
        label: 'V1',
        muted: false,
      },
    ],
    assetKeys: [],
    app: {},
    shaders,
    outputMetadata: {
      resolution: '1920x1080',
      fps: 30,
      file: 'out.mp4',
    },
  };
}

function makeDiagnostic(
  code: string,
  severity: 'warning' | 'error',
  detail: Record<string, unknown>,
): ExtensionDiagnostic {
  return {
    code,
    severity,
    message: `Diagnostic ${code}`,
    extensionId: detail.extensionId as string | undefined,
    contributionId: detail.contributionId as string | undefined,
    detail,
  };
}

function makeGraph(options?: {
  readonly includeResolvedClipShader?: boolean;
  readonly includeMissingPostprocessShader?: boolean;
  readonly diagnostics?: readonly ExtensionDiagnostic[];
}): CompositionGraph {
  const graphNodes: CompositionGraph['nodes'][number][] = [
    {
      id: 'clip:clip-1',
      kind: 'clip' as const,
      detail: { clipId: 'clip-1' },
    },
    {
      id: 'timeline-postprocess',
      kind: 'timeline-postprocess' as const,
    },
  ];
  const edges: CompositionGraph['edges'][number][] = [];
  const referenceStates: CompositionGraph['referenceStates'][number][] = [];

  if (options?.includeResolvedClipShader) {
    graphNodes.push({
      id: 'contribution:shader:ext.shader:clip',
      kind: 'contribution',
      ref: {
        kind: 'shader',
        extensionId: 'ext.shader',
        contributionId: 'clip',
      },
    });
    edges.push({
      id: 'edge:clip',
      kind: 'consumes',
      sourceNodeId: 'clip:clip-1',
      targetNodeId: 'contribution:shader:ext.shader:clip',
      detail: {
        scope: 'clip',
        clipId: 'clip-1',
        shaderId: 'shader.clip',
      },
    });
    referenceStates.push({
      refKey: 'shader:ext.shader:clip',
      state: 'resolved',
      nodeIds: ['contribution:shader:ext.shader:clip'],
    });
  }

  if (options?.includeMissingPostprocessShader) {
    graphNodes.push({
      id: 'contribution:shader:ext.shader:missing-post',
      kind: 'contribution',
      ref: {
        kind: 'shader',
        extensionId: 'ext.shader',
        contributionId: 'missing-post',
      },
    });
    edges.push({
      id: 'edge:post',
      kind: 'consumes',
      sourceNodeId: 'timeline-postprocess',
      targetNodeId: 'contribution:shader:ext.shader:missing-post',
      detail: {
        scope: 'postprocess',
        shaderId: 'shader.post',
      },
    });
    referenceStates.push({
      refKey: 'shader:ext.shader:missing-post',
      state: 'missing',
      nodeIds: ['contribution:shader:ext.shader:missing-post'],
    });
  }

  return {
    nodes: graphNodes,
    edges,
    referenceStates,
    diagnostics: options?.diagnostics ?? [],
  };
}

function shaderDescriptor(): VideoEditorShaderDescriptor {
  return {
    id: 'clip',
    extensionId: 'ext.shader',
    shaderId: 'shader.clip',
    label: 'Clip shader',
    pass: 'clip',
    materializer: {
      processId: 'shader-materializer',
      operationId: 'materializeClipShader',
      requiredCapabilities: ['render-material', 'shader-materializer'],
    },
    hasSourceMetadata: false,
  };
}

describe('renderPlanner compositionGraph authority', () => {
  it('ignores legacy snapshot shader refs when a composition graph is present', () => {
    const result = planRender({
      snapshot: snapshotWithShaders([
        {
          id: 'legacy-only',
          shaderId: 'shader.legacy',
          scope: 'clip',
          clipId: 'clip-1',
          extensionId: 'ext.shader',
          contributionId: 'legacy-only',
          enabled: true,
        },
      ]),
      compositionGraph: makeGraph(),
    });

    expect(result.canBrowserExport).toBe(true);
    expect(result.canWorkerExport).toBe(true);
    expect(result.findings).not.toEqual(expect.arrayContaining([
      expect.objectContaining({ id: 'planner.compositionGraph.legacy-shader-ref-compatibility' }),
    ]));
    expect(result.blockers).toEqual([]);
  });

  it('uses graph reference states to keep unresolved refs diagnostic-only while resolved refs drive materializer blockers', () => {
    const result = planRender({
      compositionGraph: makeGraph({
        includeResolvedClipShader: true,
        includeMissingPostprocessShader: true,
        diagnostics: [
          makeDiagnostic('composition/missing-ref', 'warning', {
            nodeId: 'timeline-postprocess',
            refKey: 'shader:ext.shader:missing-post',
            refState: 'missing',
            scope: 'postprocess',
            extensionId: 'ext.shader',
            contributionId: 'missing-post',
            shaderId: 'shader.post',
          }),
        ],
      }),
      shaders: [shaderDescriptor()],
    });

    expect(result.blockers).toEqual(expect.arrayContaining([
      expect.objectContaining({
        route: 'browser-export',
        reason: 'missing-material',
        extensionId: 'ext.shader',
        contributionId: 'clip',
        message: 'Shader "shader.clip" cannot export because no shader materializer produced RenderMaterial for clip "clip-1".',
      }),
    ]));
    expect(result.blockers).not.toEqual(expect.arrayContaining([
      expect.objectContaining({
        contributionId: 'missing-post',
        reason: 'missing-material',
      }),
    ]));
    expect(result.findings).toEqual(expect.arrayContaining([
      expect.objectContaining({
        route: 'browser-export',
        severity: 'warning',
        reason: 'missing-contribution',
        extensionId: 'ext.shader',
        contributionId: 'missing-post',
        detail: expect.objectContaining({
          source: 'composition-graph',
          code: 'composition/missing-ref',
          refState: 'missing',
        }),
      }),
    ]));
  });

  it('emits a compatibility warning when shader planning falls back to legacy inputs', () => {
    const result = planRender({
      snapshot: snapshotWithShaders([
        {
          id: 'legacy-only',
          shaderId: 'shader.legacy',
          scope: 'clip',
          clipId: 'clip-1',
          extensionId: 'ext.shader',
          contributionId: 'legacy-only',
          enabled: true,
        },
      ]),
    });

    expect(result.findings).toEqual(expect.arrayContaining([
      expect.objectContaining({
        id: 'planner.compositionGraph.legacy-shader-ref-compatibility',
        severity: 'warning',
      }),
    ]));
  });
});

describe('renderRouter compositionGraph pass-through', () => {
  it('keeps the route decision stable while passing compositionGraph into the embedded planner', () => {
    const decision = decideRenderRoute(
      {
        clips: [{ clipType: 'media' }],
      },
      undefined,
      {
        compositionGraph: makeGraph({
          includeResolvedClipShader: true,
        }),
      },
    );

    expect(decision.route).toBe('browser-remotion');
    expect(decision.reason).toBe('pure_native_clips');
    expect(decision.planner.plannerResult.canBrowserExport).toBe(false);
  });
});

describe('renderPlanner M5 composition graph diagnostics', () => {
  function makeM5Graph(diagnostics: ExtensionDiagnostic[]): CompositionGraph {
    return {
      nodes: [
        { id: 'clip:clip-1', kind: 'clip' as const, detail: { clipId: 'clip-1' } },
      ],
      edges: [],
      referenceStates: [],
      diagnostics,
    };
  }

  it('blocks browser and worker export for M5 effect error diagnostic', () => {
    const graph = makeM5Graph([
      makeDiagnostic('composition/effect-disabled-ref', 'error', {
        clipId: 'clip-1',
        nodeId: 'contribution:effect:ext.fx:disabled',
        refKey: 'effect:ext.fx:disabled',
        refState: 'disabled',
        extensionId: 'ext.fx',
        contributionId: 'disabled',
        resolverState: 'disabled',
        packageState: 'disabled-by-user',
        ownerKind: 'effect',
        ownerId: 'disabled-fx',
      }),
    ]);

    const result = planRender({ compositionGraph: graph });

    expect(result.canBrowserExport).toBe(false);
    expect(result.canWorkerExport).toBe(false);
    expect(result.findings).toEqual(expect.arrayContaining([
      expect.objectContaining({
        severity: 'error',
        route: 'browser-export',
        reason: 'inactive-extension',
        detail: expect.objectContaining({
          source: 'composition-graph',
          code: 'composition/effect-disabled-ref',
        }),
      }),
    ]));
  });

  it('does not block export for M5 effect warning diagnostic (missing ref)', () => {
    const graph = makeM5Graph([
      makeDiagnostic('composition/effect-missing-ref', 'warning', {
        clipId: 'clip-1',
        nodeId: 'contribution:effect:ext.fx:missing',
        refKey: 'effect:ext.fx:missing',
        refState: 'missing',
        extensionId: 'ext.fx',
        contributionId: 'missing',
        resolverState: 'missing',
        ownerKind: 'effect',
        ownerId: 'missing-fx',
      }),
    ]);

    const result = planRender({ compositionGraph: graph });

    // Warnings surface as findings but don't block export
    expect(result.canBrowserExport).toBe(true);
    expect(result.canWorkerExport).toBe(true);
    expect(result.findings).toEqual(expect.arrayContaining([
      expect.objectContaining({
        severity: 'warning',
        route: 'browser-export',
        detail: expect.objectContaining({
          source: 'composition-graph',
          code: 'composition/effect-missing-ref',
        }),
      }),
    ]));
  });

  it('blocks export for M5 transition error diagnostic', () => {
    const graph = makeM5Graph([
      makeDiagnostic('composition/transition-disabled-ref', 'error', {
        clipId: 'clip-1',
        nodeId: 'contribution:transition:ext.tx:disabled',
        refKey: 'transition:ext.tx:disabled',
        refState: 'disabled',
        extensionId: 'ext.tx',
        contributionId: 'disabled',
        resolverState: 'disabled',
        packageState: 'disabled-by-user',
        ownerKind: 'transition',
        ownerId: 'disabled-tx',
      }),
    ]);

    const result = planRender({ compositionGraph: graph });

    expect(result.canBrowserExport).toBe(false);
    expect(result.canWorkerExport).toBe(false);
    expect(result.findings).toEqual(expect.arrayContaining([
      expect.objectContaining({
        severity: 'error',
        route: 'browser-export',
        reason: 'inactive-extension',
        detail: expect.objectContaining({
          source: 'composition-graph',
          code: 'composition/transition-disabled-ref',
        }),
      }),
    ]));
  });

  it('does not block export for M5 transition warning diagnostic (missing ref)', () => {
    const graph = makeM5Graph([
      makeDiagnostic('composition/transition-missing-ref', 'warning', {
        clipId: 'clip-1',
        nodeId: 'contribution:transition:ext.tx:missing',
        refKey: 'transition:ext.tx:missing',
        refState: 'missing',
        extensionId: 'ext.tx',
        contributionId: 'missing',
        resolverState: 'missing',
        ownerKind: 'transition',
        ownerId: 'missing-tx',
      }),
    ]);

    const result = planRender({ compositionGraph: graph });

    expect(result.canBrowserExport).toBe(true);
    expect(result.canWorkerExport).toBe(true);
  });

  it('clears blockers when M5 diagnostics are resolved (no diagnostics)', () => {
    const graph = makeM5Graph([]);

    const result = planRender({ compositionGraph: graph });

    expect(result.canBrowserExport).toBe(true);
    expect(result.canWorkerExport).toBe(true);
    expect(result.findings).toEqual([]);
  });
});
