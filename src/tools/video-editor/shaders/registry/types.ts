import type {
  DisposeHandle,
  ExtensionDiagnostic,
  ShaderFallbackBehavior,
  ShaderMaterializerDescriptor,
  ShaderPassDescriptor,
  ShaderPassKind,
  ShaderSourceDescriptor,
  ShaderTextureSchema,
  ShaderUniformSchema,
} from '@reigh/editor-sdk';
import type { ContributionRenderability } from '@/tools/video-editor/runtime/renderability.ts';

export type ShaderEffectRegistryProvenance =
  | 'built-in'
  | 'bundled-extension'
  | 'external-catalog'
  | 'local-storage-draft'
  | 'db-resource'
  | 'ai-generated'
  | 'trusted-loader';

export type ShaderEffectRegistryRecordStatus = 'active' | 'inactive' | 'error';

export interface ShaderEffectRegistryLookup {
  readonly shaderId: string;
  readonly ownerExtensionId?: string;
}

export interface ShaderEffectRegistryRecord extends ShaderEffectRegistryLookup {
  readonly contributionId: string;
  readonly label: string;
  readonly description?: string;
  readonly source: ShaderSourceDescriptor;
  readonly pass: ShaderPassKind | ShaderPassDescriptor;
  readonly uniforms?: ShaderUniformSchema;
  readonly textures?: ShaderTextureSchema;
  readonly fallback?: ShaderFallbackBehavior;
  readonly materializer?: ShaderMaterializerDescriptor;
  readonly provenance: ShaderEffectRegistryProvenance;
  readonly renderability: ContributionRenderability;
  readonly status: ShaderEffectRegistryRecordStatus;
  readonly diagnostics?: readonly ExtensionDiagnostic[];
  readonly dispose?: DisposeHandle['dispose'];
}

export interface ShaderEffectRegistrySnapshot {
  readonly records: readonly ShaderEffectRegistryRecord[];
  readonly diagnostics: readonly ExtensionDiagnostic[];
  readonly get: (
    shaderId: string,
    ownerExtensionId?: string,
  ) => ShaderEffectRegistryRecord | undefined;
  readonly getByLookup: (lookup: ShaderEffectRegistryLookup) => ShaderEffectRegistryRecord | undefined;
  readonly has: (shaderId: string, ownerExtensionId?: string) => boolean;
  readonly hasByLookup: (lookup: ShaderEffectRegistryLookup) => boolean;
}

export type ShaderEffectRegistrySubscriber = (snapshot: ShaderEffectRegistrySnapshot) => void;

export interface ShaderEffectRegistry {
  register(record: ShaderEffectRegistryRecord): DisposeHandle;
  updateRecord(
    lookup: ShaderEffectRegistryLookup,
    updater: (current: ShaderEffectRegistryRecord) => ShaderEffectRegistryRecord,
    newDispose?: DisposeHandle['dispose'],
  ): DisposeHandle;
  unregister(shaderId: string, ownerExtensionId?: string): void;
  unregisterByLookup(lookup: ShaderEffectRegistryLookup): void;
  unregisterOwner(ownerExtensionId: string): void;
  resolve(shaderId: string, ownerExtensionId?: string): ShaderEffectRegistryRecord | undefined;
  resolveByLookup(lookup: ShaderEffectRegistryLookup): ShaderEffectRegistryRecord | undefined;
  subscribe(subscriber: ShaderEffectRegistrySubscriber): DisposeHandle;
  getSnapshot(): ShaderEffectRegistrySnapshot;
  dispose(): void;
}
