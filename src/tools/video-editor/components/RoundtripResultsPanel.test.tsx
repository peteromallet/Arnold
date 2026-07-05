// @vitest-environment jsdom

import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { RenderMaterial } from '@reigh/editor-sdk';
import type { ProcessRoundtripResult } from '@/sdk/capabilities';
import {
  createProcessResultAttachRecord,
  type ProcessResultAttachRecord,
} from '@/tools/video-editor/runtime/composition/processResultAttach.ts';
import type { VideoEditorProcessDescriptor } from '@/tools/video-editor/runtime/extensionSurface.ts';
import { createRoundtripProposalInput, RoundtripResultsPanel } from './RoundtripResultsPanel';

const material: RenderMaterial = {
  id: 'mat-returned',
  mediaKind: 'image',
  locator: { kind: 'url', uri: 'https://example.test/returned.png' },
  producerExtensionId: 'ext.process',
  determinism: 'process-dependent',
  replacementPolicy: 'replace-live-ref',
};

function result(overrides: Partial<ProcessRoundtripResult> = {}): ProcessRoundtripResult {
  return {
    requestId: 'request-1',
    processId: 'upscale',
    operationId: 'run',
    status: 'completed',
    returnedMaterials: [material],
    sidecars: [{
      id: 'log-1',
      filename: 'run.log',
      kind: 'log',
      mimeType: 'text/plain',
      data: new TextEncoder().encode('finished'),
    }],
    diagnostics: [{ id: 'diag-1', severity: 'warning', message: 'Low confidence' }],
    logs: [{ level: 'info', message: 'Process finished' }],
    metadata: { model: 'upscaler' },
    availableActions: ['insert-as-clip', 'replace-clip', 'attach-to-clip', 'download-sidecar', 'discard', 'create-proposal'],
    ...overrides,
  };
}

function descriptor(): VideoEditorProcessDescriptor {
  return {
    id: 'process.upscale',
    extensionId: 'ext.process',
    processId: 'upscale',
    label: 'Upscale',
    spec: {
      id: 'upscale',
      label: 'Upscale',
      spawn: { command: 'upscale-bin' },
      protocol: 'stdio-jsonrpc',
      operations: [{
        id: 'run',
        label: 'Upscale image',
        routes: ['browser-export'],
        outputKinds: ['material', 'artifact', 'sidecar'],
        requiredCapabilities: ['browser-export'],
      }],
    },
    protocol: 'stdio-jsonrpc',
    operations: [{
      id: 'run',
      label: 'Upscale image',
      routes: ['browser-export'],
      outputKinds: ['material', 'artifact', 'sidecar'],
      requiredCapabilities: ['browser-export'],
    }],
    availableRoutes: ['browser-export'],
    requiredBy: [],
    blockers: [],
    nextActions: [],
  };
}

function attachRecord(): ProcessResultAttachRecord {
  return createProcessResultAttachRecord({
    processDescriptor: descriptor(),
    attachedAt: '2026-07-04T23:40:00.000Z',
    result: result({
      artifacts: [{
        id: 'artifact-1',
        route: 'browser-export',
        locator: { kind: 'url', uri: 'https://example.test/returned.json' },
        mediaKind: 'json',
        determinism: 'process-dependent',
        boundary: {
          source: 'process',
          target: 'artifact-store',
          route: 'browser-export',
          failureBehavior: 'emit-diagnostic',
        },
        consumedMaterialRefs: [],
      }],
    }),
  });
}

describe('RoundtripResultsPanel', () => {
  it('lists returned materials, sidecars, diagnostics, logs, metadata, and downloads sidecars', () => {
    const onDownloadSidecar = vi.fn();
    render(
      <RoundtripResultsPanel
        result={result()}
        proposalContext={{ baseVersion: 7, targetClipId: 'clip-1' }}
        onCreateProposal={vi.fn()}
        onDownloadSidecar={onDownloadSidecar}
      />,
    );

    expect(screen.getByLabelText('Returned materials')).toHaveTextContent('mat-returned image https://example.test/returned.png');
    expect(screen.getByText('Low confidence')).toBeInTheDocument();
    expect(screen.getByText('info: Process finished')).toBeInTheDocument();
    expect(screen.getByLabelText('Roundtrip metadata')).toHaveTextContent('upscaler');
    expect(screen.queryByLabelText('Process attach provenance')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Download' }));
    expect(onDownloadSidecar).toHaveBeenCalledWith(expect.objectContaining({ filename: 'run.log' }));
  });

  it('renders process.result.attach provenance when supplied without changing actions', () => {
    render(
      <RoundtripResultsPanel
        result={result({
          artifacts: [{
            id: 'artifact-1',
            route: 'browser-export',
            locator: { kind: 'url', uri: 'https://example.test/returned.json' },
            mediaKind: 'json',
            determinism: 'process-dependent',
            boundary: {
              source: 'process',
              target: 'artifact-store',
              route: 'browser-export',
              failureBehavior: 'emit-diagnostic',
            },
            consumedMaterialRefs: [],
          }],
        })}
        processResultAttachRecord={attachRecord()}
        proposalContext={{ baseVersion: 7, targetClipId: 'clip-1' }}
        onCreateProposal={vi.fn()}
      />,
    );

    expect(screen.getByLabelText('Process attach provenance')).toHaveTextContent(
      'process.result.attach via process.upscale',
    );
    expect(screen.getByLabelText('Process attach provenance')).toHaveTextContent(
      'Upscale image · task request-1 · attached 2026-07-04T23:40:00.000Z',
    );
    expect(screen.getByText('Attached logs: 1 · attached diagnostics: 1')).toBeInTheDocument();
    expect(screen.getByText('Attached materials: mat-returned')).toBeInTheDocument();
    expect(screen.getByText('Attached artifacts: artifact-1')).toBeInTheDocument();
    expect(screen.getByText('Attached sidecars: run.log')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Insert as clip' })).toBeInTheDocument();
  });

  it('creates proposal inputs for insert, replace, attach, and create-proposal actions without timeline mutation', () => {
    const onCreateProposal = vi.fn();
    const onDiscard = vi.fn();
    render(
      <RoundtripResultsPanel
        result={result()}
        proposalContext={{ baseVersion: 7, targetClipId: 'clip-1', source: 'host.roundtrip' }}
        onCreateProposal={onCreateProposal}
        onDiscard={onDiscard}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Insert as clip' }));
    fireEvent.click(screen.getByRole('button', { name: 'Replace clip' }));
    fireEvent.click(screen.getByRole('button', { name: 'Attach to clip' }));
    fireEvent.click(screen.getByRole('button', { name: 'Create proposal' }));
    fireEvent.click(screen.getByRole('button', { name: 'Discard' }));

    expect(onCreateProposal).toHaveBeenCalledTimes(4);
    expect(onCreateProposal.mock.calls.map(([proposal]) => proposal.patch.operations[0].op)).toEqual([
      'clip.add',
      'clip.update',
      'project-data.write',
      'clip.add',
    ]);
    expect(onCreateProposal.mock.calls[1][0]).toMatchObject({
      baseVersion: 7,
      source: 'host.roundtrip',
      patch: { operations: [{ target: 'clip-1' }] },
    });
    expect(onDiscard).toHaveBeenCalledWith(expect.objectContaining({ requestId: 'request-1' }));
  });

  it('exports proposal helper used by the panel actions', () => {
    expect(createRoundtripProposalInput('replace-clip', result(), { baseVersion: 3, targetClipId: 'clip-a' }))
      .toMatchObject({
        baseVersion: 3,
        patch: {
          operations: [{
            op: 'clip.update',
            target: 'clip-a',
            payload: { material: expect.objectContaining({ id: 'mat-returned' }) },
          }],
        },
      });
  });
});
