import type { FC } from 'react';
import type { DisposeHandle, ExtensionDiagnostic } from '@reigh/editor-sdk';
import type { EffectComponentProps } from '@/tools/video-editor/effects/entrances.tsx';
import type { ContributionRenderability } from '@/tools/video-editor/runtime/renderability.ts';
import type { ParameterSchema } from '@/tools/video-editor/types/index.ts';

export type EffectRegistryProvenance =
  | 'built-in'
  | 'bundled-extension'
  | 'external-catalog'
  | 'local-storage-draft'
  | 'legacy-db-effect'
  | 'db-resource'
  | 'ai-generated'
  | 'trusted-loader';

export type EffectRegistryRecordStatus = 'active' | 'inactive' | 'error';

export interface EffectRegistryRecord {
  readonly effectId: string;
  readonly contributionId: string;
  readonly component: FC<EffectComponentProps>;
  readonly schema?: ParameterSchema;
  readonly code?: string;
  readonly provenance: EffectRegistryProvenance;
  readonly ownerExtensionId?: string;
  readonly renderability: ContributionRenderability;
  readonly status: EffectRegistryRecordStatus;
  readonly diagnostics?: readonly ExtensionDiagnostic[];
  readonly dispose?: DisposeHandle['dispose'];
}

export interface EffectRegistrySnapshot {
  readonly records: readonly EffectRegistryRecord[];
  readonly diagnostics: readonly ExtensionDiagnostic[];
  readonly get: (effectId: string) => EffectRegistryRecord | undefined;
  readonly has: (effectId: string) => boolean;
}

export type EffectRegistrySubscriber = (snapshot: EffectRegistrySnapshot) => void;

export interface EffectRegistry {
  register(record: EffectRegistryRecord): DisposeHandle;
  updateRecord(
    effectId: string,
    updater: (current: EffectRegistryRecord) => EffectRegistryRecord,
    newDispose?: DisposeHandle['dispose'],
  ): DisposeHandle;
  unregister(effectId: string): void;
  unregisterOwner(ownerExtensionId: string): void;
  resolve(effectId: string): EffectRegistryRecord | undefined;
  subscribe(subscriber: EffectRegistrySubscriber): DisposeHandle;
  getSnapshot(): EffectRegistrySnapshot;
  dispose(): void;
}
