import type { RenderArtifactSidecarDescriptor } from '@reigh/editor-sdk';

export const SIDECAR_PREVIEW_LIMIT_BYTES = 64 * 1024;

export interface SidecarPreviewProps {
  sidecars: readonly RenderArtifactSidecarDescriptor[];
  onDownload?: (sidecar: RenderArtifactSidecarDescriptor) => void;
  onDownloadAll?: (sidecars: readonly RenderArtifactSidecarDescriptor[]) => void;
}

function decode(sidecar: RenderArtifactSidecarDescriptor): string {
  if (!sidecar.data) return '';
  return new TextDecoder().decode(sidecar.data.slice(0, SIDECAR_PREVIEW_LIMIT_BYTES));
}

function isOversized(sidecar: RenderArtifactSidecarDescriptor): boolean {
  return (sidecar.byteSize ?? sidecar.data?.byteLength ?? 0) > SIDECAR_PREVIEW_LIMIT_BYTES;
}

function safeJson(raw: string): unknown {
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

function preview(sidecar: RenderArtifactSidecarDescriptor): string {
  if (!sidecar.data) return `External sidecar: ${sidecar.locator?.uri ?? 'no inline data'}`;
  const raw = decode(sidecar);
  if (sidecar.kind === 'provenance') return JSON.stringify(sidecar.provenance ?? safeJson(raw) ?? raw, null, 2);
  if (sidecar.kind === 'metadata' || sidecar.kind === 'manifest' || sidecar.mimeType.includes('json')) {
    const parsed = safeJson(raw);
    return parsed === null ? raw : JSON.stringify(parsed, null, 2);
  }
  if (sidecar.kind === 'cue') return raw.split(/\r?\n/).filter(Boolean).slice(0, 20).join('\n');
  if (sidecar.kind === 'thumbnail') return `Thumbnail preview: ${sidecar.mimeType}, ${sidecar.byteSize ?? sidecar.data.byteLength} bytes`;
  return raw.split(/\r?\n/).slice(0, 40).join('\n');
}

export function SidecarPreview({ sidecars, onDownload, onDownloadAll }: SidecarPreviewProps) {
  if (sidecars.length === 0) return <p>No sidecars available.</p>;
  return (
    <section aria-label="Sidecar previews" className="space-y-3">
      <button type="button" onClick={() => onDownloadAll?.(sidecars)}>Download all sidecars</button>
      {sidecars.map((sidecar) => {
        const oversized = isOversized(sidecar);
        const id = sidecar.id ?? `${sidecar.kind}:${sidecar.filename}`;
        return (
          <article key={id} aria-label={`Sidecar ${sidecar.filename}`}>
            <h3>{sidecar.filename}</h3>
            <p>{sidecar.kind} {sidecar.mimeType} {sidecar.byteSize ?? sidecar.data?.byteLength ?? 0} bytes</p>
            {oversized ? <p>Preview withheld because this sidecar exceeds the safe preview limit.</p> : <pre>{preview(sidecar)}</pre>}
            {sidecar.diagnostics?.map((diagnostic) => <p key={diagnostic.id}>{diagnostic.message}</p>)}
            <button type="button" disabled={oversized && !sidecar.locator} onClick={() => onDownload?.(sidecar)}>Download</button>
          </article>
        );
      })}
    </section>
  );
}
