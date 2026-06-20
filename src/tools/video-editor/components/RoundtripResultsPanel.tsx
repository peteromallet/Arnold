import type {
  ProcessRoundtripAction,
  ProcessRoundtripResult,
  RenderArtifact,
  RenderArtifactSidecarDescriptor,
  RenderMaterial,
  TimelinePatch,
  TimelineProposalInput,
} from '@reigh/editor-sdk';
import { SidecarPreview } from '@/tools/video-editor/components/SidecarPreview.tsx';

export interface RoundtripProposalContext {
  baseVersion: number;
  source?: string;
  targetClipId?: string;
}

export interface RoundtripResultsPanelProps {
  result: ProcessRoundtripResult;
  proposalContext: RoundtripProposalContext;
  onCreateProposal: (proposal: TimelineProposalInput) => void;
  onDownloadSidecar?: (sidecar: RenderArtifactSidecarDescriptor) => void;
  onDiscard?: (result: ProcessRoundtripResult) => void;
}

function firstMaterial(result: ProcessRoundtripResult): RenderMaterial | undefined {
  return result.returnedMaterials[0];
}

function materialPayload(material: RenderMaterial | undefined, artifact: RenderArtifact | undefined) {
  return {
    material,
    artifact,
    locator: material?.locator ?? artifact?.locator,
    mediaKind: material?.mediaKind ?? artifact?.mediaKind,
  };
}

function patchForAction(
  action: Extract<ProcessRoundtripAction, 'insert-as-clip' | 'replace-clip' | 'attach-to-clip' | 'create-proposal'>,
  result: ProcessRoundtripResult,
  context: RoundtripProposalContext,
): TimelinePatch {
  const material = firstMaterial(result);
  const artifact = result.artifacts?.[0];
  const payload = {
    ...materialPayload(material, artifact),
    requestId: result.requestId,
    processId: result.processId,
    operationId: result.operationId,
    metadata: result.metadata,
  };
  if (action === 'insert-as-clip' || action === 'create-proposal') {
    return {
      version: 1,
      source: context.source ?? `process:${result.processId}`,
      operations: [{
        op: 'clip.add',
        target: material?.id ?? artifact?.id ?? result.requestId,
        payload,
      }],
    };
  }
  if (action === 'replace-clip') {
    return {
      version: 1,
      source: context.source ?? `process:${result.processId}`,
      operations: [{
        op: 'clip.update',
        target: context.targetClipId ?? '',
        payload,
      }],
    };
  }
  return {
    version: 1,
    source: context.source ?? `process:${result.processId}`,
    operations: [{
      op: 'project-data.write',
      target: context.targetClipId ?? material?.id ?? result.requestId,
      payload: {
        namespace: 'process-roundtrip-attachments',
        value: payload,
      },
    }],
  };
}

export function createRoundtripProposalInput(
  action: Extract<ProcessRoundtripAction, 'insert-as-clip' | 'replace-clip' | 'attach-to-clip' | 'create-proposal'>,
  result: ProcessRoundtripResult,
  context: RoundtripProposalContext,
): TimelineProposalInput {
  return {
    source: context.source ?? `process:${result.processId}:${result.operationId}`,
    rationale: `${action} from ${result.processId}/${result.operationId}`,
    baseVersion: context.baseVersion,
    patch: patchForAction(action, result, context),
  };
}

function hasAction(result: ProcessRoundtripResult, action: ProcessRoundtripAction): boolean {
  return (result.availableActions ?? ['insert-as-clip', 'replace-clip', 'attach-to-clip', 'download-sidecar', 'discard', 'create-proposal']).includes(action);
}

export function RoundtripResultsPanel({
  result,
  proposalContext,
  onCreateProposal,
  onDownloadSidecar,
  onDiscard,
}: RoundtripResultsPanelProps) {
  const proposalAction = (action: Extract<ProcessRoundtripAction, 'insert-as-clip' | 'replace-clip' | 'attach-to-clip' | 'create-proposal'>) => {
    onCreateProposal(createRoundtripProposalInput(action, result, proposalContext));
  };
  return (
    <section aria-label="Roundtrip results">
      <h3>{result.processId} {result.operationId}</h3>
      <p>{result.status}</p>
      {result.metadata ? <pre aria-label="Roundtrip metadata">{JSON.stringify(result.metadata, null, 2)}</pre> : null}
      {result.logs?.map((log) => <p key={`${log.level}:${log.message}`}>{log.level}: {log.message}</p>)}
      {result.diagnostics?.map((diagnostic) => <p key={diagnostic.id}>{diagnostic.message}</p>)}
      <ul aria-label="Returned materials">
        {result.returnedMaterials.map((material) => (
          <li key={material.id}>{material.id} {material.mediaKind} {material.locator.uri}</li>
        ))}
      </ul>
      <ul aria-label="Returned artifacts">
        {(result.artifacts ?? []).map((artifact) => (
          <li key={artifact.id}>{artifact.id} {artifact.mediaKind} {artifact.locator.uri}</li>
        ))}
      </ul>
      <SidecarPreview sidecars={result.sidecars ?? []} onDownload={onDownloadSidecar} />
      {hasAction(result, 'insert-as-clip') ? <button type="button" onClick={() => proposalAction('insert-as-clip')}>Insert as clip</button> : null}
      {hasAction(result, 'replace-clip') ? <button type="button" onClick={() => proposalAction('replace-clip')}>Replace clip</button> : null}
      {hasAction(result, 'attach-to-clip') ? <button type="button" onClick={() => proposalAction('attach-to-clip')}>Attach to clip</button> : null}
      {hasAction(result, 'create-proposal') ? <button type="button" onClick={() => proposalAction('create-proposal')}>Create proposal</button> : null}
      {hasAction(result, 'discard') ? <button type="button" onClick={() => onDiscard?.(result)}>Discard</button> : null}
    </section>
  );
}
