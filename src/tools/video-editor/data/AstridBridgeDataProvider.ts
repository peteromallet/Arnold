import type {
  AssetRegistry,
  AssetRegistryEntry,
  TimelineConfig,
} from '@/tools/video-editor/types/index.ts';
import type { Checkpoint } from '@/tools/video-editor/types/history.ts';
import {
  type DataProvider,
  type LoadedTimeline,
} from '@/tools/video-editor/data/DataProvider.ts';
import type {
  AssetProfile,
  AssetResolveRequest,
  UploadedAssetResult,
  UploadAssetOptions,
} from '@/tools/video-editor/data/AssetResolver.ts';
import { withDefaultTimelineOutput } from '@/tools/video-editor/lib/defaults.ts';

type BridgeTimelinePayload = {
  timeline_id?: unknown;
  timeline_ulid?: unknown;
  slug?: unknown;
  name?: unknown;
  config?: unknown;
  config_version?: unknown;
  registry?: unknown;
};

type AstridBridgeDataProviderOptions = {
  projectSlug: string;
  timelineRef: string;
  timelineId?: string;
  persistenceDisabled?: boolean;
  apiBaseUrl?: string;
  assetBaseUrl?: string;
};

const DEFAULT_API_BASE_URL = '/api/astrid';
const DEFAULT_BRIDGE_PORT = '17333';

const clone = <T,>(value: T): T => JSON.parse(JSON.stringify(value)) as T;

const trimTrailingSlash = (value: string): string => value.replace(/\/+$/, '');

const isHttpUrl = (value: string): boolean => /^https?:\/\//.test(value);

const getEnv = (key: string): string | undefined => {
  const meta = import.meta as ImportMeta & { env?: Record<string, string | undefined> };
  return meta.env?.[key];
};

export const defaultAstridBridgeAssetBaseUrl = (): string => {
  const port = getEnv('VITE_ASTRID_BRIDGE_PORT') ?? DEFAULT_BRIDGE_PORT;
  return `http://127.0.0.1:${port}`;
};

export class AstridBridgeReadOnlyError extends Error {
  code = 'astrid_bridge_read_only' as const;

  constructor(action: string) {
    super(`Astrid local bridge is read-only: ${action} is not supported`);
    this.name = 'AstridBridgeReadOnlyError';
  }
}

const normalizeRegistry = (value: unknown): AssetRegistry => {
  if (!value || typeof value !== 'object' || !('assets' in value) || typeof value.assets !== 'object' || value.assets === null) {
    return { assets: {} };
  }
  return clone(value as AssetRegistry);
};

const normalizeConfig = (value: unknown): TimelineConfig => {
  if (!value || typeof value !== 'object') {
    throw new Error('Astrid bridge timeline payload is missing config');
  }
  return withDefaultTimelineOutput(clone(value as TimelineConfig));
};

const normalizeConfigVersion = (value: unknown): number => {
  return typeof value === 'number' ? value : 1;
};

export class AstridBridgeDataProvider implements DataProvider {
  readonly persistenceEnabled = false;
  readonly apiBaseUrl: string;
  readonly assetBaseUrl: string;

  private selectedTimelineRef: string;
  private canonicalTimelineId: string | null;
  private cachedPayload: BridgeTimelinePayload | null = null;
  private assetKeyToFile = new Map<string, string>();
  private fileToAssetKey = new Map<string, string>();

  constructor(options: AstridBridgeDataProviderOptions) {
    this.apiBaseUrl = trimTrailingSlash(options.apiBaseUrl ?? DEFAULT_API_BASE_URL);
    this.assetBaseUrl = trimTrailingSlash(options.assetBaseUrl ?? defaultAstridBridgeAssetBaseUrl());
    this.selectedTimelineRef = options.timelineRef;
    this.canonicalTimelineId = options.timelineId ?? null;
    this.projectSlug = options.projectSlug;
  }

  private readonly projectSlug: string;

  async loadTimeline(timelineId: string): Promise<LoadedTimeline> {
    const payload = await this.fetchTimelinePayload(timelineId);
    return {
      config: normalizeConfig(payload.config),
      configVersion: normalizeConfigVersion(payload.config_version),
    };
  }

  async loadAssetRegistry(timelineId: string): Promise<AssetRegistry> {
    const payload = await this.fetchTimelinePayload(timelineId);
    const registry = normalizeRegistry(payload.registry);
    this.rebuildAssetMaps(registry);
    return registry;
  }

  async resolveAssetUrl(file: string): Promise<string> {
    const candidate = file.trim();
    if (!candidate) {
      throw new Error('Cannot resolve asset URL for an empty file path');
    }
    if (isHttpUrl(candidate)) {
      return candidate;
    }

    const assetKey = this.fileToAssetKey.get(candidate);
    if (!assetKey) {
      return candidate;
    }
    return this.buildAssetUrl(assetKey);
  }

  async onResolve(request: AssetResolveRequest): Promise<string> {
    const assetKey = this.getPreferredAssetKey(request);
    if (assetKey) {
      return this.buildAssetUrl(assetKey);
    }
    return this.resolveAssetUrl(request.file);
  }

  async saveTimeline(
    _timelineId: string,
    _config: TimelineConfig,
    _expectedVersion: number,
    _registry?: AssetRegistry,
  ): Promise<number> {
    throw new AstridBridgeReadOnlyError('saveTimeline');
  }

  async saveCheckpoint(
    _timelineId: string,
    _checkpoint: Omit<Checkpoint, 'id'>,
  ): Promise<string> {
    throw new AstridBridgeReadOnlyError('saveCheckpoint');
  }

  async registerAsset(
    _timelineId: string,
    _assetId: string,
    _entry: AssetRegistryEntry,
  ): Promise<void> {
    throw new AstridBridgeReadOnlyError('registerAsset');
  }

  async uploadAsset(
    _file: File,
    _options: UploadAssetOptions,
  ): Promise<UploadedAssetResult> {
    throw new AstridBridgeReadOnlyError('uploadAsset');
  }

  async onUpload(): Promise<UploadedAssetResult> {
    throw new AstridBridgeReadOnlyError('onUpload');
  }

  async loadWaveform(): Promise<null> {
    return null;
  }

  async loadAssetProfile(): Promise<AssetProfile | null> {
    return null;
  }

  private async fetchTimelinePayload(timelineId: string): Promise<BridgeTimelinePayload> {
    if (this.cachedPayload !== null && (this.canonicalTimelineId === null || timelineId === this.canonicalTimelineId)) {
      return this.cachedPayload;
    }

    const response = await fetch(
      `${this.apiBaseUrl}/projects/${encodeURIComponent(this.projectSlug)}/timelines/${encodeURIComponent(this.selectedTimelineRef)}`,
    );

    if (!response.ok) {
      throw new Error(`Astrid bridge request failed: ${response.status} ${response.statusText}`);
    }

    const payload = await response.json() as BridgeTimelinePayload;
    const payloadTimelineId = typeof payload.timeline_id === 'string' ? payload.timeline_id : null;
    if (this.canonicalTimelineId !== null && payloadTimelineId !== null && timelineId !== this.canonicalTimelineId) {
      throw new Error(`Astrid bridge timeline mismatch: expected ${this.canonicalTimelineId}, got ${timelineId}`);
    }

    this.canonicalTimelineId = payloadTimelineId ?? this.canonicalTimelineId ?? timelineId;
    this.selectedTimelineRef = payloadTimelineId ?? this.selectedTimelineRef;
    this.cachedPayload = payload;
    this.rebuildAssetMaps(normalizeRegistry(payload.registry));
    return payload;
  }

  private rebuildAssetMaps(registry: AssetRegistry): void {
    this.assetKeyToFile.clear();
    this.fileToAssetKey.clear();
    for (const [assetKey, entry] of Object.entries(registry.assets ?? {})) {
      if (!entry || typeof entry.file !== 'string' || entry.file.length === 0) {
        continue;
      }
      this.assetKeyToFile.set(assetKey, entry.file);
      if (!this.fileToAssetKey.has(entry.file)) {
        this.fileToAssetKey.set(entry.file, assetKey);
      }
    }
  }

  private getPreferredAssetKey(request: AssetResolveRequest): string | null {
    if (request.assetId && this.assetKeyToFile.has(request.assetId)) {
      return request.assetId;
    }
    if (request.entry?.file) {
      const assetKey = this.fileToAssetKey.get(request.entry.file);
      if (assetKey) {
        return assetKey;
      }
    }
    if (request.file) {
      const assetKey = this.fileToAssetKey.get(request.file);
      if (assetKey) {
        return assetKey;
      }
    }
    return null;
  }

  private buildAssetUrl(assetKey: string): string {
    return `${this.assetBaseUrl}/projects/${encodeURIComponent(this.projectSlug)}/timelines/${encodeURIComponent(this.selectedTimelineRef)}/assets/${encodeURIComponent(assetKey)}`;
  }
}
