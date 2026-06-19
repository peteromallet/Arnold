import type { DisposeHandle, ExtensionDiagnostic, TransitionRenderer } from '@reigh/editor-sdk';
import type { ContributionRenderability } from '@/tools/video-editor/runtime/renderability.ts';
import type { ParameterSchema } from '@/tools/video-editor/types/index.ts';

export type TransitionRegistryProvenance =
  | 'built-in'
  | 'bundled-extension'
  | 'external-catalog'
  | 'local-storage-draft'
  | 'legacy-db-transition'
  | 'db-resource'
  | 'ai-generated'
  | 'trusted-loader';

export type TransitionRegistryRecordStatus = 'active' | 'inactive' | 'error';

export interface TransitionRegistryRecord {
  readonly transitionId: string;
  readonly contributionId: string;
  readonly renderer: TransitionRenderer;
  readonly schema?: ParameterSchema;
  readonly code?: string;
  readonly provenance: TransitionRegistryProvenance;
  readonly ownerExtensionId?: string;
  readonly renderability: ContributionRenderability;
  readonly status: TransitionRegistryRecordStatus;
  readonly diagnostics?: readonly ExtensionDiagnostic[];
  readonly dispose?: DisposeHandle['dispose'];
}

export interface TransitionRegistrySnapshot {
  readonly records: readonly TransitionRegistryRecord[];
  readonly diagnostics: readonly ExtensionDiagnostic[];
  readonly get: (transitionId: string) => TransitionRegistryRecord | undefined;
  readonly has: (transitionId: string) => boolean;
}

export type TransitionRegistrySubscriber = (snapshot: TransitionRegistrySnapshot) => void;

export interface TransitionRegistry {
  register(record: TransitionRegistryRecord): DisposeHandle;
  updateRecord(
    transitionId: string,
    updater: (current: TransitionRegistryRecord) => TransitionRegistryRecord,
    newDispose?: DisposeHandle['dispose'],
  ): DisposeHandle;
  unregister(transitionId: string): void;
  unregisterOwner(ownerExtensionId: string): void;
  resolve(transitionId: string): TransitionRegistryRecord | undefined;
  subscribe(subscriber: TransitionRegistrySubscriber): DisposeHandle;
  getSnapshot(): TransitionRegistrySnapshot;
  dispose(): void;
}
