import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { SidecarPreview, SIDECAR_PREVIEW_LIMIT_BYTES } from './SidecarPreview';
import type { RenderArtifactSidecarDescriptor } from '@reigh/editor-sdk';

const enc = new TextEncoder();

function sidecar(kind: RenderArtifactSidecarDescriptor['kind'], filename: string, value: string, extra: Partial<RenderArtifactSidecarDescriptor> = {}): RenderArtifactSidecarDescriptor {
  const data = enc.encode(value);
  return { kind, filename, mimeType: filename.endsWith('.json') ? 'application/json' : 'text/plain', data, byteSize: data.byteLength, ...extra };
}

describe('SidecarPreview', () => {
  it('renders JSON/tree, text/log, cue, thumbnail, and provenance previews safely', () => {
    render(
      <SidecarPreview
        sidecars={[
          sidecar('metadata', 'meta.json', '{"b":2,"a":1}'),
          sidecar('log', 'run.log', '<script>alert(1)</script>\nline 2'),
          sidecar('cue', 'markers.vtt', 'cue 1\ncue 2\n'),
          sidecar('thumbnail', 'thumb.png', 'not rendered bytes', { mimeType: 'image/png' }),
          sidecar('provenance', 'prov.json', '{}', { provenance: { producer: 'ext.proc' } }),
        ]}
      />,
    );

    expect(screen.getByText(/"a": 1/)).toBeInTheDocument();
    expect(screen.getByText(/<script>alert\(1\)<\/script>/)).toBeInTheDocument();
    expect(screen.getByText(/cue 1/)).toBeInTheDocument();
    expect(screen.getByText(/Thumbnail preview: image\/png/)).toBeInTheDocument();
    expect(screen.getByText(/ext.proc/)).toBeInTheDocument();
  });

  it('enforces preview limits before download and supports download-all integration', () => {
    const onDownload = vi.fn();
    const onDownloadAll = vi.fn();
    const oversized = new Uint8Array(SIDECAR_PREVIEW_LIMIT_BYTES + 1);
    render(
      <SidecarPreview
        sidecars={[
          { kind: 'log', filename: 'huge.log', mimeType: 'text/plain', data: oversized, byteSize: oversized.byteLength },
        ]}
        onDownload={onDownload}
        onDownloadAll={onDownloadAll}
      />,
    );

    expect(screen.getByText('Preview withheld because this sidecar exceeds the safe preview limit.')).toBeInTheDocument();
    expect(screen.getByText('Download')).toBeDisabled();
    fireEvent.click(screen.getByText('Download all sidecars'));
    expect(onDownloadAll).toHaveBeenCalledWith([expect.objectContaining({ filename: 'huge.log' })]);
    expect(onDownload).not.toHaveBeenCalled();
  });
});
