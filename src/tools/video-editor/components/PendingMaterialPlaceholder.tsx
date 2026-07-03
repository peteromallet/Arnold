import { AbsoluteFill } from 'remotion';
import type { CapabilityFinding, RenderMaterialRef } from '@reigh/editor-sdk';
import type { RenderPlannerMaterialStatus } from '@/tools/video-editor/runtime/renderPlanner.ts';

export interface PendingMaterialPlaceholderProps {
  clipId: string;
  material: RenderMaterialRef;
  status: RenderPlannerMaterialStatus;
  diagnostics?: readonly CapabilityFinding[];
}

interface StatusStyle {
  background: string;
  border: string;
  color: string;
}

const STATE_STYLES: Record<RenderPlannerMaterialStatus['state'], StatusStyle> = {
  missing: {
    background: '#3B0A0A',
    border: '#F87171',
    color: '#FEE2E2',
  },
  stale: {
    background: '#342400',
    border: '#F59E0B',
    color: '#FEF3C7',
  },
  pending: {
    background: '#13213A',
    border: '#60A5FA',
    color: '#DBEAFE',
  },
  failed: {
    background: '#2E1065',
    border: '#C084FC',
    color: '#F3E8FF',
  },
  resolved: {
    background: '#052E1A',
    border: '#34D399',
    color: '#D1FAE5',
  },
};

function statusLabel(status: RenderPlannerMaterialStatus): string {
  const phase = status.detail?.phase;
  switch (status.state) {
    case 'pending':
      if (phase === 'active') return 'materializing…';
      if (phase === 'live-only') return 'live-only preview';
      return 'pending materialization';
    case 'stale':
      return 'stale material';
    case 'missing':
      return 'material missing';
    case 'failed':
      return 'materialization failed';
    case 'resolved':
      return 'material ready';
    default:
      return status.state;
  }
}

function statusSubtitle(
  status: RenderPlannerMaterialStatus,
  diagnostics: readonly CapabilityFinding[] | undefined,
): string | undefined {
  // Prefer explicit message, then diagnostic error, then phase/quality context
  const diagnosticMsg =
    diagnostics?.find((d) => d.severity === 'error')?.message
    ?? diagnostics?.[0]?.message;

  const phaseStr = status.detail?.phase ? `phase: ${status.detail.phase}` : undefined;
  const qualityStr = status.detail?.quality ? `quality: ${status.detail.quality}` : undefined;
  const detailParts = [phaseStr, qualityStr].filter(Boolean) as string[];
  const detailStr = detailParts.length > 0 ? detailParts.join(', ') : undefined;

  return status.message ?? diagnosticMsg ?? detailStr;
}

export function PendingMaterialPlaceholder({
  clipId,
  material,
  status,
  diagnostics,
}: PendingMaterialPlaceholderProps) {
  const style = STATE_STYLES[status.state];
  const label = statusLabel(status);
  const subtitle = statusSubtitle(status, diagnostics);
  return (
    <AbsoluteFill
      data-testid="pending-material-placeholder"
      data-clip-id={clipId}
      data-material-ref-id={material.id}
      data-material-state={status.state}
      data-material-phase={status.detail?.phase}
      data-material-quality={status.detail?.quality}
      style={{
        backgroundColor: style.background,
        borderTop: `2px solid ${style.border}`,
        borderBottom: `2px solid ${style.border}`,
        color: style.color,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '12px 24px',
        textAlign: 'center',
        fontFamily: 'ui-monospace, SFMono-Regular, "Roboto Mono", Menlo, Consolas, monospace',
        fontSize: 13,
        lineHeight: 1.4,
      }}
    >
      <div style={{ maxWidth: '80%', padding: '8px 16px', borderRadius: 4, background: 'rgba(0, 0, 0, 0.45)' }}>
        <div>{label}: {material.id}</div>
        {subtitle ? <div>{subtitle}</div> : null}
      </div>
    </AbsoluteFill>
  );
}
