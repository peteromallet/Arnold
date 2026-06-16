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
import { resolveGenerationAsset } from '@/tools/video-editor/data/generationAssetResolver.ts';
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
const LOCAL_TIMELINES_DIRECTORY_NAME = 'timelines';
const LOCAL_ASSETS_DIRECTORY_NAME = 'assets';
const LOCAL_INCOMING_DIRECTORY_NAME = '.incoming';
const ASSEMBLY_JSON_FILENAME = 'assembly.json';
const REGISTRY_JSON_FILENAME = 'registry.json';

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
  removeEntry?: (name: string, options?: { recursive?: boolean }) => Promise<void>;
};

type FileSystemFileHandleLike = {
  getFile?: () => Promise<File>;
  createWritable: () => Promise<{
    write: (data: BlobPart) => Promise<void>;
    close: () => Promise<void>;
    abort?: () => Promise<void>;
  }>;
};

type ShowDirectoryPicker = () => Promise<FileSystemDirectoryHandleLike>;

type LocalTimelineFiles = {
  projectRootHandle: FileSystemDirectoryHandleLike;
  sourcesHandle: FileSystemDirectoryHandleLike;
  timelineHandle: FileSystemDirectoryHandleLike;
};

export type AssetMaterializationState =
  | { state: 'not-attempted' }
  | { state: 'materialized'; file: string }
  | { state: 'skipped-with-diagnostic'; diagnostic: AssetMaterializationDiagnostic };

export type AssetMaterializationDiagnostic = {
  assetId: string;
  generationId: string;
  reason: 'unresolvable' | 'download-failed' | 'refresh-required';
  message: string;
};

export type AssetMaterializationSummary = {
  states: Record<string, AssetMaterializationState>;
  diagnostics: AssetMaterializationDiagnostic[];
};

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

const filenameFromUrl = (url: string, fallback: string): string => {
  try {
    const parsed = new URL(url);
    const lastSegment = parsed.pathname.split('/').filter(Boolean).pop();
    if (lastSegment) {
      return sanitizeFilename(decodeURIComponent(lastSegment));
    }
  } catch {
    // Fall through to the deterministic fallback.
  }
  return sanitizeFilename(fallback);
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
  private localObjectUrls = new Map<string, string>();
  private materializationStates = new Map<string, AssetMaterializationState>();
  private localTimelineFiles: LocalTimelineFiles | null = null;

  constructor(options: AstridBridgeDataProviderOptions) {
    this.apiBaseUrl = trimTrailingSlash(options.apiBaseUrl ?? DEFAULT_API_BASE_URL);
    // Media asset URLs must travel the same (proxied) base as config/registry
    // requests so <video>/<img>/<audio> fetches are same-origin and reach the
    // bridge the dev proxy targets. A direct cross-origin default port (17333)
    // 404s in the browser. Fall back to the resolved apiBaseUrl unless an
    // explicit assetBaseUrl is supplied.
    this.assetBaseUrl = trimTrailingSlash(options.assetBaseUrl ?? this.apiBaseUrl);
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

  getMaterializationSummary(): AssetMaterializationSummary {
    const states: Record<string, AssetMaterializationState> = {};
    const diagnostics: AssetMaterializationDiagnostic[] = [];
    for (const [assetId, state] of this.materializationStates) {
      states[assetId] = clone(state);
      if (state.state === 'skipped-with-diagnostic') {
        diagnostics.push(clone(state.diagnostic));
      }
    }
    return { states, diagnostics };
  }

  async resolveAssetUrl(file: string): Promise<string> {
    const candidate = file.trim();
    console.log('[AstridBridgeDataProvider.resolveAssetUrl] input:', file, 'localTimelineFiles:', this.localTimelineFiles !== null);
    if (!candidate) {
      throw new Error('Cannot resolve asset URL for an empty file path');
    }
    if (isHttpUrl(candidate)) {
      console.log('[AstridBridgeDataProvider.resolveAssetUrl] returning HTTP URL:', candidate);
      return candidate;
    }

    if (this.localTimelineFiles !== null) {
      const resolved = await this.resolveLocalAssetUrl(candidate);
      console.log('[AstridBridgeDataProvider.resolveAssetUrl] resolved local URL:', resolved);
      return resolved;
    }

    const assetKey = this.fileToAssetKey.get(candidate);
    if (!assetKey) {
      console.log('[AstridBridgeDataProvider.resolveAssetUrl] no assetKey, returning raw:', candidate);
      return candidate;
    }
    const url = this.buildAssetUrl(assetKey);
    console.log('[AstridBridgeDataProvider.resolveAssetUrl] returning bridge URL:', url);
    return url;
  }

  async onResolve(request: AssetResolveRequest): Promise<string> {
    console.log('[AstridBridgeDataProvider.onResolve] request:', request);
    const assetKey = this.getPreferredAssetKey(request);
    if (this.localTimelineFiles !== null) {
      const file = request.entry?.file ?? (assetKey ? this.assetKeyToFile.get(assetKey) : undefined) ?? request.file;
      if (file && !isHttpUrl(file)) {
        const resolved = await this.resolveLocalAssetUrl(file);
        console.log('[AstridBridgeDataProvider.onResolve] resolved local URL:', resolved);
        return resolved;
      }
    }
    if (assetKey) {
      const url = this.buildAssetUrl(assetKey);
      console.log('[AstridBridgeDataProvider.onResolve] returning bridge URL:', url);
      return url;
    }
    const resolved = await this.resolveAssetUrl(request.file);
    console.log('[AstridBridgeDataProvider.onResolve] falling back to resolveAssetUrl:', resolved);
    return resolved;
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

    if (this.localTimelineFiles !== null) {
      const materializedRegistry = await this.materializeGenerationAssets(timelineId, nextRegistry);
      await this.writeLocalJson(this.localTimelineFiles.timelineHandle, REGISTRY_JSON_FILENAME, materializedRegistry);
      await this.writeLocalJson(this.localTimelineFiles.timelineHandle, ASSEMBLY_JSON_FILENAME, config);
      this.cachePayload({
        ...existingPayload,
        config,
        registry: materializedRegistry,
        config_version: normalizeConfigVersion(existingPayload.config_version) + 1,
      }, timelineId);
      return normalizeConfigVersion(this.cachedPayload?.config_version);
    }

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

    const localPayload = await this.fetchLocalTimelinePayload(timelineId);
    if (localPayload !== null) {
      return this.cachePayload(localPayload, timelineId).payload;
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

  private async fetchLocalTimelinePayload(timelineId: string): Promise<BridgeTimelinePayload | null> {
    const localFiles = await this.getLocalTimelineFiles(timelineId, { prompt: false });
    if (localFiles === null) {
      return null;
    }

    this.localTimelineFiles = localFiles;
    const config = await this.readLocalJson(localFiles.timelineHandle, ASSEMBLY_JSON_FILENAME);
    const registry = await this.readOptionalLocalJson(localFiles.timelineHandle, REGISTRY_JSON_FILENAME) ?? { assets: {} };
    const normalizedRegistry = normalizeRegistry(registry);
    const beforeMaterialization = JSON.stringify(normalizedRegistry);
    const materializedRegistry = await this.materializeGenerationAssets(timelineId, normalizedRegistry);
    if (JSON.stringify(materializedRegistry) !== beforeMaterialization) {
      await this.writeLocalJson(localFiles.timelineHandle, REGISTRY_JSON_FILENAME, materializedRegistry);
    }

    return {
      timeline_id: timelineId,
      timeline_ulid: timelineId,
      slug: this.selectedTimelineRef,
      name: this.selectedTimelineRef,
      config,
      registry: materializedRegistry,
      config_version: 1,
    };
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

  private async resolveLocalAssetUrl(file: string): Promise<string> {
    if (this.localTimelineFiles === null) {
      return file;
    }

    const cached = this.localObjectUrls.get(file);
    if (cached) {
      return cached;
    }

    const fileHandle = await this.resolveLocalAssetFileHandle(file);
    if (!fileHandle || typeof fileHandle.getFile !== 'function') {
      return file;
    }

    const blob = await fileHandle.getFile();
    const url = URL.createObjectURL(blob);
    this.localObjectUrls.set(file, url);
    return url;
  }

  private async resolveLocalAssetFileHandle(file: string): Promise<FileSystemFileHandleLike | null> {
    if (this.localTimelineFiles === null) {
      return null;
    }

    const segments = file.split('/').filter(Boolean);
    if (
      segments.length === 0
      || file.startsWith('/')
      || segments.some((segment) => segment === '.' || segment === '..')
    ) {
      return null;
    }

    let directoryHandle = this.localTimelineFiles.sourcesHandle;
    for (const segment of segments.slice(0, -1)) {
      try {
        directoryHandle = await directoryHandle.getDirectoryHandle(segment);
      } catch {
        return null;
      }
    }

    try {
      return await directoryHandle.getFileHandle(segments[segments.length - 1]);
    } catch {
      return null;
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
    const handle = await this.getProjectRootHandleOptional({ prompt: true });
    if (handle === null) {
      throw new Error('Local asset drop requires a browser with File System Access support');
    }
    return handle;
  }

  private async getProjectRootHandleOptional({
    prompt,
  }: {
    prompt: boolean;
  }): Promise<FileSystemDirectoryHandleLike | null> {
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

    if (!prompt) {
      return null;
    }

    const showDirectoryPicker = getShowDirectoryPicker();
    if (!showDirectoryPicker) {
      return null;
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

  private async getLocalTimelineFiles(
    timelineId: string,
    options: { prompt: boolean },
  ): Promise<LocalTimelineFiles | null> {
    const projectRootHandle = await this.getProjectRootHandleOptional(options);
    if (projectRootHandle === null) {
      return null;
    }

    const sourcesHandle = await this.requireProjectSourcesDirectory(projectRootHandle);
    const timelinesHandle = await projectRootHandle.getDirectoryHandle(LOCAL_TIMELINES_DIRECTORY_NAME);
    const timelineHandle = await timelinesHandle.getDirectoryHandle(this.getTimelineRequestRef(timelineId));
    return { projectRootHandle, sourcesHandle, timelineHandle };
  }

  private async readLocalJson(
    directoryHandle: FileSystemDirectoryHandleLike,
    filename: string,
  ): Promise<unknown> {
    const fileHandle = await directoryHandle.getFileHandle(filename);
    if (typeof fileHandle.getFile !== 'function') {
      throw new Error(`Local timeline file ${filename} cannot be read in this browser`);
    }

    const file = await fileHandle.getFile();
    return JSON.parse(await file.text());
  }

  private async readOptionalLocalJson(
    directoryHandle: FileSystemDirectoryHandleLike,
    filename: string,
  ): Promise<unknown | null> {
    try {
      return await this.readLocalJson(directoryHandle, filename);
    } catch {
      return null;
    }
  }

  private async writeLocalJson(
    directoryHandle: FileSystemDirectoryHandleLike,
    filename: string,
    value: unknown,
  ): Promise<void> {
    const tempFilename = `.${filename}.${Date.now()}.${Math.random().toString(36).slice(2)}.tmp`;
    const bytes = JSON.stringify(value, null, 2);

    await this.writeFile(directoryHandle, tempFilename, bytes);
    try {
      await this.writeFile(directoryHandle, filename, bytes);
    } catch (error) {
      await this.removeEntryBestEffort(directoryHandle, tempFilename);
      throw error;
    }
    await this.removeEntryBestEffort(directoryHandle, tempFilename);
  }

  private async writeFile(
    directoryHandle: FileSystemDirectoryHandleLike,
    filename: string,
    data: BlobPart,
  ): Promise<void> {
    const fileHandle = await directoryHandle.getFileHandle(filename, { create: true });
    const writable = await fileHandle.createWritable();
    try {
      await writable.write(data);
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
  }

  private async removeEntryBestEffort(
    directoryHandle: FileSystemDirectoryHandleLike,
    name: string,
  ): Promise<void> {
    if (typeof directoryHandle.removeEntry !== 'function') {
      return;
    }
    try {
      await directoryHandle.removeEntry(name, { recursive: true });
    } catch {
      // Temp cleanup is best effort.
    }
  }

  private async materializeGenerationAssets(
    timelineId: string,
    registry: AssetRegistry,
  ): Promise<AssetRegistry> {
    if (this.localTimelineFiles === null) {
      return registry;
    }

    const nextRegistry = clone(registry);
    let changed = false;

    for (const [assetId, entry] of Object.entries(nextRegistry.assets ?? {})) {
      if (!entry?.generationId || this.hasLocalFile(entry) || this.materializationStates.get(assetId)?.state === 'skipped-with-diagnostic') {
        if (!this.materializationStates.has(assetId)) {
          this.materializationStates.set(assetId, { state: 'not-attempted' });
        }
        continue;
      }

      this.materializationStates.set(assetId, { state: 'not-attempted' });
      const result = await this.materializeGenerationAsset(timelineId, assetId, entry);
      if (result.ok) {
        nextRegistry.assets[assetId] = result.entry;
        this.materializationStates.set(assetId, { state: 'materialized', file: result.entry.file });
        changed = true;
      } else {
        this.materializationStates.set(assetId, {
          state: 'skipped-with-diagnostic',
          diagnostic: result.diagnostic,
        });
      }
    }

    return changed ? nextRegistry : registry;
  }

  private hasLocalFile(entry: AssetRegistryEntry): boolean {
    const file = entry.file?.trim();
    return Boolean(file && !isHttpUrl(file));
  }

  private async materializeGenerationAsset(
    timelineId: string,
    assetId: string,
    entry: AssetRegistryEntry,
  ): Promise<
    | { ok: true; entry: AssetRegistryEntry }
    | { ok: false; diagnostic: AssetMaterializationDiagnostic }
  > {
    if (this.localTimelineFiles === null || !entry.generationId) {
      throw new Error('Generation materialization requires local timeline files and a generationId');
    }

    const resolved = await resolveGenerationAsset({
      generationId: entry.generationId,
      assetId,
      entry,
      refresh: 'if-stale',
    });

    if (!resolved.ok) {
      return {
        ok: false,
        diagnostic: {
          assetId,
          generationId: entry.generationId,
          reason: resolved.diagnostic.code === 'refresh-required' ? 'refresh-required' : 'unresolvable',
          message: resolved.diagnostic.message,
        },
      };
    }

    let response: Response;
    try {
      response = await fetch(resolved.asset.url);
    } catch (error) {
      return {
        ok: false,
        diagnostic: {
          assetId,
          generationId: entry.generationId,
          reason: 'download-failed',
          message: error instanceof Error ? error.message : `Failed to download generation ${entry.generationId}`,
        },
      };
    }

    if (!response.ok) {
      return {
        ok: false,
        diagnostic: {
          assetId,
          generationId: entry.generationId,
          reason: 'download-failed',
          message: `Generation download failed with ${response.status} ${response.statusText}`,
        },
      };
    }

    const blob = await response.blob();
    if (blob.size <= 0) {
      return {
        ok: false,
        diagnostic: {
          assetId,
          generationId: entry.generationId,
          reason: 'download-failed',
          message: 'Generation download returned an empty file',
        },
      };
    }

    const assetsHandle = await this.localTimelineFiles.sourcesHandle.getDirectoryHandle(LOCAL_ASSETS_DIRECTORY_NAME, { create: true });
    const incomingHandle = await assetsHandle.getDirectoryHandle(LOCAL_INCOMING_DIRECTORY_NAME, { create: true });
    const nonce = `${Date.now()}-${Math.random().toString(36).slice(2)}`;
    const stageHandle = await incomingHandle.getDirectoryHandle(nonce, { create: true });
    const filename = await this.getUniqueLocalDropFilename(
      assetsHandle,
      filenameFromUrl(resolved.asset.url, `${assetId}.bin`),
    );

    await this.writeFile(stageHandle, filename, blob);
    await this.writeFile(assetsHandle, filename, blob);
    await this.removeEntryBestEffort(incomingHandle, nonce);

    return {
      ok: true,
      entry: {
        ...resolved.asset.entry,
        file: `${LOCAL_ASSETS_DIRECTORY_NAME}/${filename}`,
        url: resolved.asset.url,
      },
    };
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
