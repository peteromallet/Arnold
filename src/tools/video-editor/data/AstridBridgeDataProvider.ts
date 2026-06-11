import type {
  AssetRegistry,
  AssetRegistryEntry,
  TimelineConfig,
} from '@/tools/video-editor/types/index.ts';
import type { Checkpoint } from '@/tools/video-editor/types/history.ts';
import {
  type DataProvider,
  type LoadedTimeline,
  TimelineNotFoundError,
} from '@/tools/video-editor/data/DataProvider.ts';
import type {
  AssetProfile,
  AssetResolveRequest,
  UploadedAssetResult,
  UploadAssetOptions,
} from '@/tools/video-editor/data/AssetResolver.ts';
import { extractAssetRegistryEntry } from '@/tools/video-editor/lib/mediaMetadata.ts';
import {
  ensurePermission,
  getDirectoryHandle,
  saveDirectoryHandle,
  type PersistedLocalDirectoryHandle,
} from '@/shared/lib/media/localHandleStore.ts';
import { generateUUID } from '@/shared/lib/taskCreation/ids.ts';
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
  apiBaseUrl?: string;
  assetBaseUrl?: string;
};

const DEFAULT_API_BASE_URL = '/api/astrid';
const DEFAULT_BRIDGE_PORT = '17333';
const LOCAL_DROP_DIRECTORY_NAME = 'local-drops';
const LOCAL_PROJECT_ROOT_HANDLE_PREFIX = 'astrid-project-root';

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

type FileSystemDirectoryHandleLike = PersistedLocalDirectoryHandle & {
  getDirectoryHandle: (
    name: string,
    options?: { create?: boolean },
  ) => Promise<FileSystemDirectoryHandleLike>;
  getFileHandle: (
    name: string,
    options?: { create?: boolean },
  ) => Promise<FileSystemFileHandleLike>;
};

type FileSystemFileHandleLike = {
  createWritable: () => Promise<{
    write: (data: BlobPart) => Promise<void>;
    close: () => Promise<void>;
    abort?: () => Promise<void>;
  }>;
};

type ShowDirectoryPicker = () => Promise<FileSystemDirectoryHandleLike>;

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

const inferContentType = (file: File): string => {
  if (file.type) {
    return file.type;
  }

  const lowercaseName = file.name.toLowerCase();
  if (/\.(png|jpe?g|gif|webp|bmp|avif|svg)$/.test(lowercaseName)) {
    return 'image/png';
  }
  if (/\.(mp4|mov|webm|m4v|avi)$/.test(lowercaseName)) {
    return 'video/mp4';
  }
  if (/\.(mp3|wav|aac|m4a|ogg|flac)$/.test(lowercaseName)) {
    return 'audio/mpeg';
  }
  return 'application/octet-stream';
};

const sanitizeFilename = (filename: string): string => {
  const trimmed = filename.trim();
  const fallback = trimmed.length > 0 ? trimmed : 'asset';
  const sanitized = fallback
    .replace(/\s+/g, '-')
    .replace(/[^a-zA-Z0-9._-]/g, '-')
    .replace(/-+/g, '-')
    .replace(/^\.+/, '');
  return sanitized.length > 0 ? sanitized : 'asset';
};

const getProjectRootHandleStorageKey = (projectSlug: string): string => {
  return `${LOCAL_PROJECT_ROOT_HANDLE_PREFIX}:${projectSlug}`;
};

const getShowDirectoryPicker = (): ShowDirectoryPicker | null => {
  const picker = (globalThis as typeof globalThis & {
    showDirectoryPicker?: ShowDirectoryPicker;
  }).showDirectoryPicker;
  return typeof picker === 'function' ? picker : null;
};

export class AstridBridgeDataProvider implements DataProvider {
  readonly persistenceEnabled = true;
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
    timelineId: string,
    config: TimelineConfig,
    _expectedVersion: number,
    registry?: AssetRegistry,
  ): Promise<number> {
    const existingPayload = await this.fetchTimelinePayload(timelineId);
    const nextRegistry = registry ?? normalizeRegistry(existingPayload.registry);
    const timelineRef = this.getTimelineRequestRef(timelineId);

    await this.putRegistry(timelineId, nextRegistry, 'save registry');

    const saveResponse = await fetch(
      `${this.apiBaseUrl}/projects/${encodeURIComponent(this.projectSlug)}/timelines/${encodeURIComponent(timelineRef)}/save`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ config }),
      },
    );
    if (!saveResponse.ok) {
      throw await this.toBridgeError(saveResponse, timelineId, 'save timeline');
    }

    const payload = await saveResponse.json() as BridgeTimelinePayload;
    return this.cachePayload(payload, timelineId).configVersion;
  }

  async saveCheckpoint(
    timelineId: string,
    _checkpoint: Omit<Checkpoint, 'id'>,
  ): Promise<string> {
    return `${timelineId}-checkpoint-local-${Date.now()}`;
  }

  async loadCheckpoints(_timelineId: string): Promise<Checkpoint[]> {
    return [];
  }

  async registerAsset(
    timelineId: string,
    assetId: string,
    entry: AssetRegistryEntry,
  ): Promise<void> {
    const existingPayload = await this.fetchTimelinePayload(timelineId);
    const registry = normalizeRegistry(existingPayload.registry);
    await this.putRegistry(timelineId, {
      assets: {
        ...registry.assets,
        [assetId]: clone(entry),
      },
    }, 'register asset');
  }

  async uploadAsset(
    file: File,
    options: UploadAssetOptions,
  ): Promise<UploadedAssetResult> {
    const projectRootHandle = await this.getProjectRootHandle();
    const permission = await ensurePermission(projectRootHandle, 'readwrite');
    if (permission !== 'granted') {
      throw new Error('Astrid local asset drop requires read/write access to the selected project folder');
    }

    const sourcesHandle = await this.requireProjectSourcesDirectory(projectRootHandle);
    const localDropsHandle = await sourcesHandle.getDirectoryHandle(LOCAL_DROP_DIRECTORY_NAME, { create: true });
    const relativePath = await this.writeLocalDropFile(localDropsHandle, file);
    const entry = await extractAssetRegistryEntry(file, relativePath);
    if (!entry.type) {
      entry.type = inferContentType(file);
    }

    const assetId = generateUUID();
    await this.registerAsset(options.timelineId, assetId, entry);
    return { assetId, entry };
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
      `${this.apiBaseUrl}/projects/${encodeURIComponent(this.projectSlug)}/timelines/${encodeURIComponent(this.getTimelineRequestRef(timelineId))}`,
    );

    if (!response.ok) {
      throw await this.toBridgeError(response, timelineId, 'load timeline');
    }

    const payload = await response.json() as BridgeTimelinePayload;
    return this.cachePayload(payload, timelineId).payload;
  }

  private getTimelineRequestRef(timelineId: string): string {
    return this.canonicalTimelineId ?? timelineId ?? this.selectedTimelineRef;
  }

  private cachePayload(
    payload: BridgeTimelinePayload,
    timelineId: string,
  ): {
    payload: BridgeTimelinePayload;
    config: TimelineConfig;
    registry: AssetRegistry;
    configVersion: number;
  } {
    const payloadTimelineId = typeof payload.timeline_id === 'string' ? payload.timeline_id : null;
    if (this.canonicalTimelineId !== null && payloadTimelineId !== null && timelineId !== this.canonicalTimelineId) {
      throw new Error(`Astrid bridge timeline mismatch: expected ${this.canonicalTimelineId}, got ${timelineId}`);
    }

    const normalizedConfig = normalizeConfig(payload.config);
    const normalizedRegistry = normalizeRegistry(payload.registry);
    const normalizedVersion = normalizeConfigVersion(payload.config_version);

    this.canonicalTimelineId = payloadTimelineId ?? this.canonicalTimelineId ?? timelineId;
    this.selectedTimelineRef = this.canonicalTimelineId ?? this.selectedTimelineRef;
    this.cachedPayload = {
      ...payload,
      timeline_id: this.canonicalTimelineId,
      config: normalizedConfig,
      registry: normalizedRegistry,
      config_version: normalizedVersion,
    };
    this.rebuildAssetMaps(normalizedRegistry);

    return {
      payload: this.cachedPayload,
      config: normalizedConfig,
      registry: normalizedRegistry,
      configVersion: normalizedVersion,
    };
  }

  private async toBridgeError(
    response: Response,
    timelineId: string,
    action: string,
  ): Promise<Error> {
    let errorCode: string | undefined;
    let detail: string | undefined;

    try {
      const payload = await response.json() as { error?: unknown; detail?: unknown };
      errorCode = typeof payload.error === 'string' ? payload.error : undefined;
      detail = typeof payload.detail === 'string' ? payload.detail : undefined;
    } catch {
      detail = undefined;
    }

    if (response.status === 404 && errorCode === 'timeline_not_found') {
      return new TimelineNotFoundError(timelineId);
    }

    const description = detail ?? `${response.status} ${response.statusText}`;
    return new Error(`Astrid bridge ${action} failed: ${description}`);
  }

  private async putRegistry(
    timelineId: string,
    registry: AssetRegistry,
    action: string,
  ): Promise<AssetRegistry> {
    const response = await fetch(
      `${this.apiBaseUrl}/projects/${encodeURIComponent(this.projectSlug)}/timelines/${encodeURIComponent(this.getTimelineRequestRef(timelineId))}/registry`,
      {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(registry),
      },
    );
    if (!response.ok) {
      throw await this.toBridgeError(response, timelineId, action);
    }

    let nextRegistry = registry;
    try {
      nextRegistry = normalizeRegistry(await response.json());
    } catch {
      nextRegistry = normalizeRegistry(registry);
    }

    this.updateCachedRegistry(timelineId, nextRegistry);
    return nextRegistry;
  }

  private updateCachedRegistry(timelineId: string, registry: AssetRegistry): void {
    if (this.cachedPayload === null) {
      throw new Error(`Astrid bridge registry update missing cached payload for ${timelineId}`);
    }

    this.cachePayload({
      ...this.cachedPayload,
      registry,
    }, timelineId);
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

  private async getProjectRootHandle(): Promise<FileSystemDirectoryHandleLike> {
    const storageKey = getProjectRootHandleStorageKey(this.projectSlug);
    const persistedHandle = await getDirectoryHandle(storageKey);

    if (persistedHandle && this.isDirectoryHandleLike(persistedHandle)) {
      try {
        await this.requireProjectSourcesDirectory(persistedHandle);
        return persistedHandle;
      } catch {
        // Fall through to re-pick the directory when the persisted handle no longer matches the project layout.
      }
    }

    const showDirectoryPicker = getShowDirectoryPicker();
    if (!showDirectoryPicker) {
      throw new Error('Local asset drop requires a browser with File System Access support');
    }

    const pickedHandle = await showDirectoryPicker();
    await this.requireProjectSourcesDirectory(pickedHandle);
    await saveDirectoryHandle(storageKey, pickedHandle);
    return pickedHandle;
  }

  private isDirectoryHandleLike(handle: PersistedLocalDirectoryHandle): handle is FileSystemDirectoryHandleLike {
    return typeof (handle as FileSystemDirectoryHandleLike).getDirectoryHandle === 'function'
      && typeof (handle as FileSystemDirectoryHandleLike).getFileHandle === 'function';
  }

  private async requireProjectSourcesDirectory(
    projectRootHandle: FileSystemDirectoryHandleLike,
  ): Promise<FileSystemDirectoryHandleLike> {
    try {
      await projectRootHandle.getFileHandle('project.json');
    } catch {
      throw new Error('Select the Astrid project root that contains project.json');
    }

    try {
      return await projectRootHandle.getDirectoryHandle('sources');
    } catch {
      throw new Error('Selected Astrid project root is missing its sources directory');
    }
  }

  private async writeLocalDropFile(
    localDropsHandle: FileSystemDirectoryHandleLike,
    file: File,
  ): Promise<string> {
    const uniqueFilename = await this.getUniqueLocalDropFilename(localDropsHandle, file.name);
    const fileHandle = await localDropsHandle.getFileHandle(uniqueFilename, { create: true });
    const writable = await fileHandle.createWritable();

    try {
      await writable.write(file);
      await writable.close();
    } catch (error) {
      if (typeof writable.abort === 'function') {
        try {
          await writable.abort();
        } catch {
          // Ignore abort failures and surface the original write error.
        }
      }
      throw error;
    }

    return `${LOCAL_DROP_DIRECTORY_NAME}/${uniqueFilename}`;
  }

  private async getUniqueLocalDropFilename(
    localDropsHandle: FileSystemDirectoryHandleLike,
    originalName: string,
  ): Promise<string> {
    const sanitizedName = sanitizeFilename(originalName);
    const extensionIndex = sanitizedName.lastIndexOf('.');
    const baseName = extensionIndex > 0 ? sanitizedName.slice(0, extensionIndex) : sanitizedName;
    const extension = extensionIndex > 0 ? sanitizedName.slice(extensionIndex) : '';

    for (let attempt = 0; attempt < 1000; attempt += 1) {
      const suffix = attempt === 0 ? '' : `-${attempt + 1}`;
      const candidate = `${baseName}${suffix}${extension}`;
      try {
        await localDropsHandle.getFileHandle(candidate);
      } catch {
        return candidate;
      }
    }

    return `${baseName}-${Date.now()}${extension}`;
  }
}
