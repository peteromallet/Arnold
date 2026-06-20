import { AbsoluteFill } from 'remotion';
import type { CapabilityFinding, RenderMaterialRef } from '@reigh/editor-sdk';
import type { RenderPlannerMaterialStatus } from '@/tools/video-editor/runtime/renderPlanner.ts';

export interface PendingMaterialPlaceholderProps {
  clipId: string;
  material: RenderMaterialRef;
  status: RenderPlannerMaterialStatus;
  diagnostics?: readonly CapabilityFinding[];
}

const STATE_COPY: Record<RenderPlannerMaterialStatus['state'], { label: string; background: string; border: string; color: string }> = {
  missing: {
    label: 'pending material missing',
    background: '#3B0A0A',
    border: '#F87171',
    color: '#FEE2E2',
  },
  stale: {
    label: 'materializing updated material',
    background: '#342400',
    border: '#F59E0B',
    color: '#FEF3C7',
  },
  unbaked: {
    label: 'pending materialization',
    background: '#13213A',
    border: '#60A5FA',
    color: '#DBEAFE',
  },
  resolved: {
    label: 'material ready',
    background: '#052E1A',
    border: '#34D399',
    color: '#D1FAE5',
  },
};

function diagnosticText(
  status: RenderPlannerMaterialStatus,
  diagnostics: readonly CapabilityFinding[] | undefined,
): string | undefined {
  return status.message ?? diagnostics?.find((diagnostic) => diagnostic.severity === 'error')?.message ?? diagnostics?.[0]?.message;
}

export function PendingMaterialPlaceholder({
  clipId,
  material,
  status,
  diagnostics,
}: PendingMaterialPlaceholderProps) {
  const copy = STATE_COPY[status.state];
  const detail = diagnosticText(status, diagnostics);
  return (
    <AbsoluteFill
      data-testid="pending-material-placeholder"
      data-clip-id={clipId}
      data-material-ref-id={material.id}
      data-material-state={status.state}
      style={{
        backgroundColor: copy.background,
        borderTop: `2px solid ${copy.border}`,
        borderBottom: `2px solid ${copy.border}`,
        color: copy.color,
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
        <div>{copy.label}: {material.id}</div>
        {detail ? <div>{detail}</div> : null}
      </div>
    </AbsoluteFill>
  );
}
