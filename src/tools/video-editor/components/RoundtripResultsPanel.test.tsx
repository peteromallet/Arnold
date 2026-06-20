// @vitest-environment jsdom

import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { ProcessRoundtripResult, RenderMaterial } from '@reigh/editor-sdk';
import { createRoundtripProposalInput, RoundtripResultsPanel } from './RoundtripResultsPanel';

const material: RenderMaterial = {
  id: 'mat-returned',
  mediaKind: 'image',
  locator: { kind: 'url', uri: 'https://example.test/returned.png' },
  producerExtensionId: 'ext.process',
  determinism: 'process-dependent',
  replacementPolicy: 'replace-live-ref',
};

function result(): ProcessRoundtripResult {
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
  };
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
    fireEvent.click(screen.getByRole('button', { name: 'Download' }));
    expect(onDownloadSidecar).toHaveBeenCalledWith(expect.objectContaining({ filename: 'run.log' }));
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
