/**
 * Process family module.
 *
 * Houses the process family contracts extracted from the public barrel
 * (src/sdk/index.ts): ProcessSpawnConfig, ProcessManifestEntry,
 * ProcessEnvFieldSpec, ProcessOperationSpec, ProcessSpec,
 * ProcessContribution, ProcessLifecycleState, ProcessStatusBase,
 * and ProcessStatus.
 *
 * This module contains only data-only types and read-only surfaces; no
 * registry, provider, resolver, or DOM behaviour lives here.
 *
 * @publicContract
 */

import type { ContributionId } from '../../ids';
import type { ExtensionDiagnostic } from '../../diagnostics';
import type { AgentToolInputSchema } from './agentTools';
import type {
  IntegrationCapabilities,
  CapabilitySourceRef,
  CapabilityVersion,
  ProcessProgressEvent,
} from '../../capabilities';
import type { DeterminismStatus, RenderRoute } from '../rendering/renderability';

// ---------------------------------------------------------------------------
// M12: Process spawn configuration
// ---------------------------------------------------------------------------

export interface ProcessSpawnConfig {
  command: string;
  args?: readonly string[];
  env?: Record<string, string>;
  cwd?: string;
}

export type ProcessManifestEntry = ProcessSpec;

// ---------------------------------------------------------------------------
// M12: Process environment / operation / spec types
// ---------------------------------------------------------------------------

/** M12: Declarative environment field for trusted local process configuration. */
export interface ProcessEnvFieldSpec {
  readonly key: string;
  readonly label?: string;
  readonly description?: string;
  readonly required?: boolean;
  readonly secret?: boolean;
  readonly defaultValue?: string;
  readonly platformDefaults?: Partial<Record<'darwin' | 'linux' | 'win32', string>>;
}

/** Data-only output kinds a trusted local process operation may advertise. */
export type ProcessOutputKind =
  | 'artifact'
  | 'material'
  | 'sidecar'
  | 'diagnostic'
  | 'planner-result'
  | 'tool-result'
  | 'live-source-scalar'
  | 'live-source-vector'
  | 'live-source-structured';

/** Value-shape metadata for process-backed live data exposed through LiveSourceRef. */
export type ProcessLiveSourceValueShape = 'scalar' | 'vector' | 'structured';

/** Declarative, data-only live source advertised by a trusted local process. */
export interface ProcessLiveSourceDeclaration {
  readonly sourceId: string;
  readonly valueShape: ProcessLiveSourceValueShape;
  readonly label?: string;
  readonly description?: string;
  readonly sourceKind?: string;
}

/** Optional data-only process binding carried by a LiveSourceRef. */
export interface ProcessLiveSourceBinding {
  readonly processId: string;
}

/** M12: Operation a trusted local process exposes to tools, render routes, or export formats. */
export interface ProcessOperationSpec {
  readonly id: string;
  readonly label: string;
  readonly description?: string;
  readonly inputSchema?: AgentToolInputSchema;
  readonly outputKinds?: readonly ProcessOutputKind[];
  readonly requiredCapabilities?: readonly string[];
  readonly routes?: readonly RenderRoute[];
  readonly determinism?: DeterminismStatus;
}

/** M12: Declarative trusted-local process specification. */
export interface ProcessSpec {
  id: string;
  label: string;
  description?: string;
  spawn: ProcessSpawnConfig;
  protocol: 'stdio-jsonrpc';
  healthCheck?: string;
  shutdown?: string;
  restartPolicy?: 'never' | 'always' | 'on-failure';
  version?: CapabilityVersion;
  env?: readonly ProcessEnvFieldSpec[];
  operations?: readonly ProcessOperationSpec[];
  liveSources?: readonly ProcessLiveSourceDeclaration[];
  capabilities?: IntegrationCapabilities;
  requiredBy?: readonly CapabilitySourceRef[];
}

// ---------------------------------------------------------------------------
// M12: Process contribution (manifest)
// ---------------------------------------------------------------------------

/** M12: Process contribution declared in an extension manifest. */
export interface ProcessContribution {
  readonly id: ContributionId;
  readonly kind: 'process';
  readonly label?: string;
  readonly order?: number;
  readonly spec: ProcessSpec;
}

// ---------------------------------------------------------------------------
// M12: Process lifecycle state / status types
// ---------------------------------------------------------------------------

export type ProcessLifecycleState =
  | 'not-installed'
  | 'stopped'
  | 'starting'
  | 'ready'
  | 'busy'
  | 'degraded'
  | 'failed'
  | 'stopping';

export interface ProcessStatusBase {
  readonly processId: string;
  readonly state: ProcessLifecycleState;
  readonly label?: string;
  readonly message?: string;
  readonly updatedAt?: string;
  readonly blockingOperations?: readonly string[];
  readonly diagnostics?: readonly ExtensionDiagnostic[];
}

export type ProcessStatus =
  | (ProcessStatusBase & { readonly state: 'not-installed'; readonly installHint?: string })
  | (ProcessStatusBase & { readonly state: 'stopped' })
  | (ProcessStatusBase & { readonly state: 'starting'; readonly startedAt?: string })
  | (ProcessStatusBase & { readonly state: 'ready'; readonly pid?: number; readonly version?: CapabilityVersion })
  | (ProcessStatusBase & { readonly state: 'busy'; readonly operationId?: string; readonly progress?: ProcessProgressEvent })
  | (ProcessStatusBase & { readonly state: 'degraded'; readonly healthCheck?: string })
  | (ProcessStatusBase & { readonly state: 'failed'; readonly errorCode?: string; readonly recoverable?: boolean })
  | (ProcessStatusBase & { readonly state: 'stopping'; readonly reason?: string });
