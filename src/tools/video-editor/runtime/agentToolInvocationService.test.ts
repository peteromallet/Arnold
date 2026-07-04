import { describe, expect, it, vi } from 'vitest';
import {
  createAgentToolInvocationService,
} from '@/tools/video-editor/runtime/agentToolInvocationService';
import type {
  AgentToolInvocationRequest,
  ProposalRuntime,
  ToolMaterialArtifactResult,
} from '@reigh/editor-sdk';
import type { AgentToolRegistry } from '@/tools/video-editor/runtime/agentToolRegistry';

function makeRequest(): AgentToolInvocationRequest {
  return {
    toolId: 'materializer',
    extensionId: 'ext.materials',
    contributionId: 'materializer-tool',
    context: {
      projectId: 'project-1',
    },
  };
}

function createService(result: ToolMaterialArtifactResult) {
  const registry = {
    invokeTool: vi.fn().mockResolvedValue(result),
  } as unknown as AgentToolRegistry;

  const proposalRuntime = {
    currentVersion: 7,
    create: vi.fn(),
  } as unknown as ProposalRuntime;

  return {
    service: createAgentToolInvocationService({
      registry,
      proposalRuntime,
    }),
    registry,
    proposalRuntime,
  };
}

describe('createAgentToolInvocationService material/artifact promotion', () => {
  it('promotes material and asset refs into durable records without creating proposals', async () => {
    const input: ToolMaterialArtifactResult = {
      family: 'material/artifact',
      refs: [
        {
          ref: 'mat-1',
          kind: 'material',
          meta: {
            promotion: {
              schemaVersion: 1,
              mediaKind: 'image',
              locator: {
                kind: 'artifact-store',
                uri: 'artifact://materials/mat-1.png',
                contentSha256: 'hash-mat-1',
                mimeType: 'image/png',
              },
              determinism: 'deterministic',
              replacementPolicy: 'materialize-on-export',
              routeConstraints: ['preview', 'browser-export'],
              provenance: {
                capture: 'agent-bake',
                model: 'render-model-1',
              },
              consumedRefs: ['clip-1'],
              inputHashes: {
                'clip-1': 'hash-input-1',
              },
              producedAt: '2026-07-04T02:38:00.000Z',
              diagnostics: [
                {
                  severity: 'info',
                  code: 'promotion/material-ready',
                  message: 'Material promotion succeeded.',
                },
              ],
            },
          },
        },
        {
          ref: 'artifact-1',
          kind: 'asset',
          meta: {
            promotion: {
              schemaVersion: 1,
              mediaKind: 'image',
              locator: {
                kind: 'artifact-store',
                uri: 'artifact://renders/artifact-1.png',
                contentSha256: 'hash-artifact-1',
                mimeType: 'image/png',
              },
              determinism: 'process-dependent',
              replacementPolicy: 'preserve-live-ref',
              routeConstraints: ['worker-export', 'browser-export'],
              route: 'worker-export',
              provenance: {
                capture: 'agent-export',
                model: 'render-model-1',
              },
              consumedRefs: ['mat-1'],
              consumedMaterialRefs: [
                {
                  id: 'mat-1',
                  mediaKind: 'image',
                  locator: {
                    kind: 'artifact-store',
                    uri: 'artifact://materials/mat-1.png',
                    contentSha256: 'hash-mat-1',
                    mimeType: 'image/png',
                  },
                  producerExtensionId: 'ext.materials',
                  producerVersion: '1.0.0',
                  provenance: {
                    capture: 'agent-bake',
                  },
                  determinism: 'deterministic',
                  replacementPolicy: 'materialize-on-export',
                },
              ],
              inputHashes: {
                'mat-1': 'hash-mat-1',
              },
              producedAt: '2026-07-04T02:38:01.000Z',
              diagnostics: [
                {
                  severity: 'warning',
                  code: 'promotion/artifact-needs-review',
                  message: 'Artifact requires operator review.',
                },
              ],
            },
          },
        },
      ],
      diagnostics: [
        {
          severity: 'info',
          code: 'agent-tool/raw-material-result',
          message: 'Tool returned material refs.',
        },
      ],
    };

    const { service, proposalRuntime } = createService(input);
    const result = await service.invokeTool(makeRequest());

    expect(result?.family).toBe('material/artifact');
    expect(proposalRuntime.create).not.toHaveBeenCalled();

    const promoted = result as ToolMaterialArtifactResult;
    const materialRecord = promoted.refs[0].durableRecord;
    const artifactRecord = promoted.refs[1].durableRecord;

    expect(materialRecord?.durableKind).toBe('material');
    expect(materialRecord).toMatchObject({
      id: 'mat-1',
      mediaKind: 'image',
      determinism: 'deterministic',
      replacementPolicy: 'materialize-on-export',
      producer: {
        extensionId: 'ext.materials',
        toolId: 'materializer',
      },
      routeConstraints: ['preview', 'browser-export'],
      inputHashes: {
        'clip-1': 'hash-input-1',
      },
    });
    expect(materialRecord?.locator).toMatchObject({
      uri: 'artifact://materials/mat-1.png',
      contentSha256: 'hash-mat-1',
    });
    expect(materialRecord?.diagnostics[0]?.detail).toMatchObject({
      toolDiagnosticCode: 'promotion/material-ready',
    });

    expect(artifactRecord?.durableKind).toBe('artifact');
    expect(artifactRecord).toMatchObject({
      id: 'artifact-1',
      route: 'worker-export',
      determinism: 'process-dependent',
      replacementPolicy: 'preserve-live-ref',
      routeConstraints: ['worker-export', 'browser-export'],
      consumedRefs: ['mat-1'],
    });
    expect(artifactRecord?.manifest).toMatchObject({
      artifactId: 'artifact-1',
      route: 'worker-export',
      inputHashes: {
        'mat-1': 'hash-mat-1',
      },
      createdAt: '2026-07-04T02:38:01.000Z',
    });
    expect(artifactRecord?.diagnostics[0]?.detail).toMatchObject({
      toolDiagnosticCode: 'promotion/artifact-needs-review',
    });
    expect(promoted.diagnostics?.map((diagnostic) => diagnostic.code)).toEqual([
      'agent-tool/raw-material-result',
    ]);
  });

  it('rejects durable promotion when provenance evidence is absent', async () => {
    const input: ToolMaterialArtifactResult = {
      family: 'material/artifact',
      refs: [
        {
          ref: 'mat-no-provenance',
          kind: 'material',
          meta: {
            promotion: {
              schemaVersion: 1,
              mediaKind: 'image',
              locator: {
                kind: 'artifact-store',
                uri: 'artifact://materials/mat-no-provenance.png',
                contentSha256: 'hash-missing-provenance',
              },
              determinism: 'deterministic',
              replacementPolicy: 'preserve-live-ref',
              routeConstraints: ['preview'],
              consumedRefs: ['clip-2'],
              inputHashes: {
                'clip-2': 'hash-input-2',
              },
              producedAt: '2026-07-04T02:38:02.000Z',
            },
          },
        },
      ],
    };

    const { service, proposalRuntime } = createService(input);
    const result = await service.invokeTool(makeRequest());

    expect(result?.family).toBe('material/artifact');
    expect(proposalRuntime.create).not.toHaveBeenCalled();

    const promoted = result as ToolMaterialArtifactResult;
    expect(promoted.refs[0].durableRecord).toBeUndefined();
    expect(promoted.diagnostics?.map((diagnostic) => diagnostic.code)).toContain(
      'agent-tool/material-promotion-missing-provenance',
    );
  });
});
