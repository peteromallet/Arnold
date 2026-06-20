/**
 * Compile-only output format registry and execution.
 *
 * Manages registered compile-only output format handlers and executes them
 * against timeline snapshots and asset registries to produce deterministic
 * {@link RenderArtifact}-compatible artifacts.
 *
 * This module never calls render providers, render planner execution, or
 * media render routes.  Only `requiresRender: false` handlers are executed.
 *
 * @module outputFormatRegistry
 */

import type {
  CompileOnlyOutputResult,
  OutputFormatContribution,
  OutputFormatHandler,
  OutputFormatContext,
  TimelineSnapshot,
  AssetMetadata,
} from '@reigh/editor-sdk';
import {
  assertFinalArtifactHasManifest,
  createCompileOnlyArtifact,
  type RenderArtifact,
} from '@/tools/video-editor/runtime/renderability.ts';

// ---------------------------------------------------------------------------
// Registry types
// ---------------------------------------------------------------------------

/**
 * A registered compile-only output format entry.
 *
 * Associates a handler with its contribution metadata and the extension
 * that registered it.
 */
export interface CompileOnlyOutputFormatEntry {
  /** The contribution descriptor from the extension manifest. */
  readonly contribution: OutputFormatContribution;
  /** The handler registered by the extension. */
  readonly handler: OutputFormatHandler;
  /** The extension ID that owns this format. */
  readonly extensionId: string;
  /** Extension version, if available. */
  readonly extensionVersion?: string;
}

/**
 * Immutable registry of compile-only output format entries keyed by format ID.
 */
export type CompileOnlyOutputFormatRegistry = ReadonlyMap<string, CompileOnlyOutputFormatEntry>;

// ---------------------------------------------------------------------------
// Registry creation
// ---------------------------------------------------------------------------

/**
 * Create a compile-only output format registry from a list of entries.
 *
 * Only entries whose contribution has `requiresRender: false` are admitted.
 * Render-dependent formats (requiresRender: true) are silently skipped
 * because they require the render pipeline, which is not available here.
 *
 * Returns a frozen map keyed by contribution ID.
 */
export function createCompileOnlyOutputFormatRegistry(
  entries: readonly CompileOnlyOutputFormatEntry[],
): CompileOnlyOutputFormatRegistry {
  const map = new Map<string, CompileOnlyOutputFormatEntry>();
  for (const entry of entries) {
    if (entry.contribution.requiresRender) continue;
    map.set(entry.contribution.id as string, entry);
  }
  return Object.freeze(map);
}

// ---------------------------------------------------------------------------
// Execution input types
// ---------------------------------------------------------------------------

/**
 * Options for executing a compile-only output format.
 */
export interface CompileOnlyOutputExecutionOptions {
  /** The output format contribution ID to execute. */
  readonly formatId: string;
  /** Read-only snapshot of the current timeline state. */
  readonly timeline: TimelineSnapshot;
  /** Read-only map of asset key to asset metadata from the registry. */
  readonly assets: ReadonlyMap<string, Readonly<AssetMetadata>>;
  /** The extension that registered the handler (must match the entry). */
  readonly extensionId: string;
  /** Extension version, if available. */
  readonly extensionVersion?: string;
}

/**
 * The result of executing a compile-only output format.
 */
export interface CompileOnlyOutputExecutionResult {
  /** The deterministic artifact produced by the execution. */
  readonly artifact: RenderArtifact;
  /** The raw output data bytes. */
  readonly data: Uint8Array;
  /** Whether the execution had blocking errors. */
  readonly hasBlockingErrors: boolean;
}

// ---------------------------------------------------------------------------
// Execution
// ---------------------------------------------------------------------------

/**
 * Execute a compile-only output format handler.
 *
 * Looks up the handler by formatId in the registry, builds an
 * {@link OutputFormatContext} from the timeline snapshot and asset map,
 * calls the handler, and wraps the result in a deterministic
 * {@link RenderArtifact}.
 *
 * This function never calls render providers, render planner execution,
 * or media render routes.  It only executes `requiresRender: false` handlers
 * that were admitted to the registry.
 *
 * @param registry - The compile-only output format registry.
 * @param options - Execution options (formatId, timeline, assets, etc.).
 * @returns The execution result, or `null` if the format is not in the registry
 *          or is render-dependent.
 */
export async function executeCompileOnlyOutput(
  registry: CompileOnlyOutputFormatRegistry,
  options: CompileOnlyOutputExecutionOptions,
): Promise<CompileOnlyOutputExecutionResult | null> {
  const entry = registry.get(options.formatId);
  if (!entry) return null;

  // Safety: render-dependent formats are excluded at registry creation time.
  if (entry.contribution.requiresRender) return null;

  const context: OutputFormatContext = Object.freeze({
    timeline: options.timeline,
    assets: options.assets,
    extensionId: options.extensionId,
    contributionId: options.formatId,
  });

  let result: CompileOnlyOutputResult;

  try {
    const handlerResult = entry.handler(context);
    result = handlerResult instanceof Promise ? await handlerResult : handlerResult;
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : String(err);
    // Produce an artifact with a blocking diagnostic
    const artifact = createCompileOnlyArtifact({
      artifactId: `compile-only.${options.formatId}`,
      data: new Uint8Array(0),
      mimeType: entry.contribution.outputMimeType ?? 'application/octet-stream',
      filename: `error.${entry.contribution.outputExtension}`,
      outputFormatId: options.formatId,
      producerExtensionId: options.extensionId,
      producerVersion: options.extensionVersion,
      consumedAssetKeys: options.timeline.assetKeys as readonly string[],
      diagnostics: [{
        severity: 'error',
        code: 'compile-only/handler-exception',
        message: `Output format handler threw: ${message}`,
        extensionId: options.extensionId,
        contributionId: options.formatId,
        detail: { exception: message },
      }],
      hasBlockingErrors: true,
    });
    assertFinalArtifactHasManifest(artifact, 'outputFormatRegistry.executeCompileOnlyOutput');
    return Object.freeze({
      artifact,
      data: new Uint8Array(0),
      hasBlockingErrors: true,
    });
  }

  // Collect consumed asset keys from the timeline
  const consumedAssetKeys: readonly string[] = options.timeline.assetKeys as readonly string[];

  const artifact = createCompileOnlyArtifact({
    artifactId: `compile-only.${options.formatId}`,
    data: result.data,
    mimeType: result.mimeType,
    filename: result.filename,
    outputFormatId: options.formatId,
    producerExtensionId: options.extensionId,
    producerVersion: options.extensionVersion,
    consumedAssetKeys,
    diagnostics: result.diagnostics?.map((d) => ({
      severity: d.severity,
      code: d.code,
      message: d.message,
      assetKey: d.assetKey,
      extensionId: d.extensionId,
      contributionId: d.contributionId,
      detail: d.detail,
    })),
    hasBlockingErrors: result.hasBlockingErrors,
  });
  assertFinalArtifactHasManifest(artifact, 'outputFormatRegistry.executeCompileOnlyOutput');

  return Object.freeze({
    artifact,
    data: result.data,
    hasBlockingErrors: result.hasBlockingErrors,
  });
}

/**
 * Execute a compile-only output format synchronously.
 *
 * Same as {@link executeCompileOnlyOutput} but only supports synchronous
 * handlers.  Handlers that return a Promise will throw.
 *
 * @throws If the handler returns a Promise (use executeCompileOnlyOutput instead).
 */
export function executeCompileOnlyOutputSync(
  registry: CompileOnlyOutputFormatRegistry,
  options: CompileOnlyOutputExecutionOptions,
): CompileOnlyOutputExecutionResult | null {
  const entry = registry.get(options.formatId);
  if (!entry) return null;

  if (entry.contribution.requiresRender) return null;

  const context: OutputFormatContext = Object.freeze({
    timeline: options.timeline,
    assets: options.assets,
    extensionId: options.extensionId,
    contributionId: options.formatId,
  });

  let handlerResult: CompileOnlyOutputResult | Promise<CompileOnlyOutputResult>;
  try {
    handlerResult = entry.handler(context);
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : String(err);
    const artifact = createCompileOnlyArtifact({
      artifactId: `compile-only.${options.formatId}`,
      data: new Uint8Array(0),
      mimeType: entry.contribution.outputMimeType ?? 'application/octet-stream',
      filename: `error.${entry.contribution.outputExtension}`,
      outputFormatId: options.formatId,
      producerExtensionId: options.extensionId,
      producerVersion: options.extensionVersion,
      consumedAssetKeys: options.timeline.assetKeys as readonly string[],
      diagnostics: [{
        severity: 'error',
        code: 'compile-only/handler-exception',
        message: `Output format handler threw: ${message}`,
        extensionId: options.extensionId,
        contributionId: options.formatId,
        detail: { exception: message },
      }],
      hasBlockingErrors: true,
    });
    assertFinalArtifactHasManifest(artifact, 'outputFormatRegistry.executeCompileOnlyOutputSync');
    return Object.freeze({
      artifact,
      data: new Uint8Array(0),
      hasBlockingErrors: true,
    });
  }

  if (handlerResult instanceof Promise || (handlerResult && typeof (handlerResult as any).then === 'function')) {
    throw new Error(
      `Output format handler for "${options.formatId}" returned a Promise. ` +
      `Use executeCompileOnlyOutput() for async handlers.`,
    );
  }

  const result: CompileOnlyOutputResult = handlerResult as CompileOnlyOutputResult;

  const consumedAssetKeys: readonly string[] = options.timeline.assetKeys as readonly string[];

  const artifact = createCompileOnlyArtifact({
    artifactId: `compile-only.${options.formatId}`,
    data: result.data,
    mimeType: result.mimeType,
    filename: result.filename,
    outputFormatId: options.formatId,
    producerExtensionId: options.extensionId,
    producerVersion: options.extensionVersion,
    consumedAssetKeys,
    diagnostics: result.diagnostics?.map((d) => ({
      severity: d.severity,
      code: d.code,
      message: d.message,
      assetKey: d.assetKey,
      extensionId: d.extensionId,
      contributionId: d.contributionId,
      detail: d.detail,
    })),
    hasBlockingErrors: result.hasBlockingErrors,
  });
  assertFinalArtifactHasManifest(artifact, 'outputFormatRegistry.executeCompileOnlyOutputSync');

  return Object.freeze({
    artifact,
    data: result.data,
    hasBlockingErrors: result.hasBlockingErrors,
  });
}
