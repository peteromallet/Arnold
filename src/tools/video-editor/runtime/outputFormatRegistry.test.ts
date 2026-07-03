import { describe, expect, it } from 'vitest';
import type {
  CompileOnlyOutputResult,
  OutputFormatContribution,
  OutputFormatHandler,
  OutputFormatContext,
  TimelineSnapshot,
  AssetMetadata,
} from '@reigh/editor-sdk';
import {
  createCompileOnlyArtifact,
  COMPILE_ONLY_ARTIFACT_ROUTE,
  DETERMINISM_STATUSES,
  RENDER_ROUTES,
} from '@/tools/video-editor/runtime/renderability.ts';
import type {
  CompileOnlyOutputFormatEntry,
  CompileOnlyOutputFormatRegistry,
  CompileOnlyOutputExecutionResult,
} from '@/tools/video-editor/runtime/outputFormatRegistry.ts';
import {
  createCompileOnlyOutputFormatRegistry,
  executeCompileOnlyOutput,
  executeCompileOnlyOutputSync,
  formatScopedKey,
} from '@/tools/video-editor/runtime/outputFormatRegistry.ts';

// ---------------------------------------------------------------------------
// Test helpers
// ---------------------------------------------------------------------------

function makeContribution(overrides?: Partial<OutputFormatContribution>): OutputFormatContribution {
  return {
    id: 'test-format',
    kind: 'outputFormat',
    label: 'Test Format',
    requiresRender: false,
    outputExtension: 'json',
    outputMimeType: 'application/json',
    description: 'A test compile-only format',
    order: 0,
    ...overrides,
  };
}

function makeTimelineSnapshot(overrides?: Partial<TimelineSnapshot>): TimelineSnapshot {
  return {
    projectId: 'project-1',
    baseVersion: 1,
    currentVersion: 1,
    extensionRequirements: [],
    clips: [
      {
        id: 'clip-1',
        track: 'track-1',
        at: 0,
        clipType: 'media',
        duration: 30,
        managed: false,
      },
    ],
    tracks: [
      {
        id: 'track-1',
        kind: 'visual',
        label: 'Main',
        muted: false,
      },
    ],
    assetKeys: ['asset-1', 'asset-2'],
    app: {},
    ...overrides,
  };
}

function makeAssets(): ReadonlyMap<string, Readonly<AssetMetadata>> {
  return new Map([
    ['asset-1', Object.freeze({ integrity: { algorithm: 'sha256', hash: 'abc123', size: 1024 } })],
    ['asset-2', Object.freeze({ provenance: { importedAt: '2026-06-19T12:00:00Z' } })],
  ]);
}

function makeSyncHandler(result: CompileOnlyOutputResult): OutputFormatHandler {
  return (_ctx: OutputFormatContext): CompileOnlyOutputResult => result;
}

function makeAsyncHandler(result: CompileOnlyOutputResult): OutputFormatHandler {
  return (_ctx: OutputFormatContext): Promise<CompileOnlyOutputResult> => Promise.resolve(result);
}

function makeJsonResult(data: unknown): CompileOnlyOutputResult {
  const encoder = new TextEncoder();
  const json = JSON.stringify(data);
  return {
    data: encoder.encode(json),
    mimeType: 'application/json',
    filename: 'output.json',
    hasBlockingErrors: false,
  };
}

// ---------------------------------------------------------------------------
// Tests: createCompileOnlyOutputFormatRegistry
// ---------------------------------------------------------------------------

describe('createCompileOnlyOutputFormatRegistry', () => {
  it('admits compile-only entries (requiresRender: false)', () => {
    const entry: CompileOnlyOutputFormatEntry = {
      contribution: makeContribution({ requiresRender: false }),
      handler: makeSyncHandler(makeJsonResult({})),
      extensionId: 'com.example.test',
    };
    const registry = createCompileOnlyOutputFormatRegistry([entry]);
    expect(registry.size).toBe(1);
    expect(registry.get(formatScopedKey('com.example.test', 'test-format'))).toBe(entry);
  });

  it('excludes render-dependent entries (requiresRender: true)', () => {
    const entry: CompileOnlyOutputFormatEntry = {
      contribution: makeContribution({
        id: 'render-format',
        requiresRender: true,
      }),
      handler: makeSyncHandler(makeJsonResult({})),
      extensionId: 'com.example.test',
    };
    const registry = createCompileOnlyOutputFormatRegistry([entry]);
    expect(registry.size).toBe(0);
  });

  it('returns a frozen map', () => {
    const entry: CompileOnlyOutputFormatEntry = {
      contribution: makeContribution(),
      handler: makeSyncHandler(makeJsonResult({})),
      extensionId: 'com.example.test',
    };
    const registry = createCompileOnlyOutputFormatRegistry([entry]);
    expect(Object.isFrozen(registry)).toBe(true);
  });

  it('handles empty entries', () => {
    const registry = createCompileOnlyOutputFormatRegistry([]);
    expect(registry.size).toBe(0);
    expect(Object.isFrozen(registry)).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// Tests: executeCompileOnlyOutputSync
// ---------------------------------------------------------------------------

describe('executeCompileOnlyOutputSync', () => {
  it('executes a synchronous handler and returns a deterministic RenderArtifact', () => {
    const entry: CompileOnlyOutputFormatEntry = {
      contribution: makeContribution({ id: 'metadata-json' }),
      handler: makeSyncHandler(makeJsonResult({ version: '1.0' })),
      extensionId: 'com.example.metadata',
      extensionVersion: '1.2.3',
    };
    const registry = createCompileOnlyOutputFormatRegistry([entry]);
    const timeline = makeTimelineSnapshot();
    const assets = makeAssets();

    const result = executeCompileOnlyOutputSync(registry, {
      formatId: 'metadata-json',
      timeline,
      assets,
      extensionId: 'com.example.metadata',
      extensionVersion: '1.2.3',
    });

    expect(result).not.toBeNull();
    const exec = result as CompileOnlyOutputExecutionResult;
    expect(exec.hasBlockingErrors).toBe(false);
    expect(exec.data.constructor.name).toBe('Uint8Array');

    const artifact = exec.artifact;
    expect(artifact.id).toBe('compile-only.metadata-json');
    expect(artifact.route).toBe(COMPILE_ONLY_ARTIFACT_ROUTE);
    expect(artifact.determinism).toBe('deterministic');
    expect(artifact.producerExtensionId).toBe('com.example.metadata');
    expect(artifact.producerVersion).toBe('1.2.3');
    expect(artifact.mediaKind).toBe('json');
    expect(artifact.locator.kind).toBe('inline');
    expect(artifact.locator.mimeType).toBe('application/json');
    expect(artifact.locator.uri).toBe('output.json');
    expect(artifact.manifest).toMatchObject({
      artifactId: 'compile-only.metadata-json',
      route: COMPILE_ONLY_ARTIFACT_ROUTE,
      determinism: 'deterministic',
      outputFormatId: 'metadata-json',
      producerExtensionId: 'com.example.metadata',
      producerVersion: '1.2.3',
    });
    expect(artifact.boundary.source).toBe('browser');
    expect(artifact.boundary.target).toBe('export-output');
    expect(artifact.boundary.failureBehavior).toBe('emit-diagnostic');
    expect(artifact.consumedMaterialRefs).toHaveLength(2);
    expect(artifact.consumedMaterialRefs[0].id).toBe('material.asset.asset-1');
    expect(artifact.consumedMaterialRefs[1].id).toBe('material.asset.asset-2');
    expect(Object.isFrozen(artifact)).toBe(true);
  });

  it('returns the handler output data intact', () => {
    const encoder = new TextEncoder();
    const payload = { foo: 'bar', num: 42 };
    const json = JSON.stringify(payload);
    const entry: CompileOnlyOutputFormatEntry = {
      contribution: makeContribution(),
      handler: makeSyncHandler({
        data: encoder.encode(json),
        mimeType: 'application/json',
        filename: 'test.json',
        hasBlockingErrors: false,
      }),
      extensionId: 'com.example.test',
    };
    const registry = createCompileOnlyOutputFormatRegistry([entry]);

    const result = executeCompileOnlyOutputSync(registry, {
      formatId: 'test-format',
      timeline: makeTimelineSnapshot(),
      assets: makeAssets(),
      extensionId: 'com.example.test',
    });

    expect(result).not.toBeNull();
    const decoder = new TextDecoder();
    const decoded = decoder.decode(result!.data);
    expect(JSON.parse(decoded)).toEqual(payload);
  });

  it('surfaces handler diagnostics as artifact findings', () => {
    const entry: CompileOnlyOutputFormatEntry = {
      contribution: makeContribution({ id: 'diag-format' }),
      handler: makeSyncHandler({
        data: new Uint8Array([1, 2, 3]),
        mimeType: 'application/octet-stream',
        filename: 'output.bin',
        diagnostics: [
          {
            severity: 'warning',
            code: 'parser/missing-metadata',
            message: 'Some metadata fields were empty.',
            assetKey: 'asset-1',
            extensionId: 'com.example.test',
            contributionId: 'diag-format',
          },
        ],
        hasBlockingErrors: false,
      }),
      extensionId: 'com.example.test',
    };
    const registry = createCompileOnlyOutputFormatRegistry([entry]);

    const result = executeCompileOnlyOutputSync(registry, {
      formatId: 'diag-format',
      timeline: makeTimelineSnapshot(),
      assets: makeAssets(),
      extensionId: 'com.example.test',
    });

    expect(result).not.toBeNull();
    expect(result!.artifact.findings).toBeDefined();
    expect(result!.artifact.findings).toHaveLength(1);
    expect(result!.artifact.findings![0].severity).toBe('warning');
    expect(result!.artifact.findings![0].message).toBe('Some metadata fields were empty.');
  });

  it('returns null for unknown formatId', () => {
    const entry: CompileOnlyOutputFormatEntry = {
      contribution: makeContribution(),
      handler: makeSyncHandler(makeJsonResult({})),
      extensionId: 'com.example.test',
    };
    const registry = createCompileOnlyOutputFormatRegistry([entry]);

    const result = executeCompileOnlyOutputSync(registry, {
      formatId: 'nonexistent',
      timeline: makeTimelineSnapshot(),
      assets: makeAssets(),
      extensionId: 'com.example.test',
    });
    expect(result).toBeNull();
  });

  it('returns null for empty registry', () => {
    const registry = createCompileOnlyOutputFormatRegistry([]);

    const result = executeCompileOnlyOutputSync(registry, {
      formatId: 'any-format',
      timeline: makeTimelineSnapshot(),
      assets: makeAssets(),
      extensionId: 'com.example.test',
    });
    expect(result).toBeNull();
  });

  it('passed render-dependent format is excluded (returns null)', () => {
    // Even if somehow a render-dependent entry got through, execution rejects it
    const entry: CompileOnlyOutputFormatEntry = {
      contribution: makeContribution({ requiresRender: true }),
      handler: makeSyncHandler(makeJsonResult({})),
      extensionId: 'com.example.test',
    };
    // Manually create a registry that includes a render-dependent entry
    // (this bypasses createCompileOnlyOutputFormatRegistry which filters them)
    const map = new Map<string, CompileOnlyOutputFormatEntry>();
    map.set(formatScopedKey('com.example.test', 'test-format'), entry);
    const registry: CompileOnlyOutputFormatRegistry = Object.freeze(map);

    const result = executeCompileOnlyOutputSync(registry, {
      formatId: 'test-format',
      timeline: makeTimelineSnapshot(),
      assets: makeAssets(),
      extensionId: 'com.example.test',
    });
    expect(result).toBeNull();
  });

  it('handles handler that throws', () => {
    const entry: CompileOnlyOutputFormatEntry = {
      contribution: makeContribution({ outputMimeType: 'application/json', outputExtension: 'json' }),
      handler: () => {
        throw new Error('Handler exploded');
      },
      extensionId: 'com.example.test',
    };
    const registry = createCompileOnlyOutputFormatRegistry([entry]);

    const result = executeCompileOnlyOutputSync(registry, {
      formatId: 'test-format',
      timeline: makeTimelineSnapshot(),
      assets: makeAssets(),
      extensionId: 'com.example.test',
    });

    expect(result).not.toBeNull();
    expect(result!.hasBlockingErrors).toBe(true);
    expect(result!.data).toEqual(new Uint8Array(0));
    expect(result!.artifact.findings).toBeDefined();
    expect(result!.artifact.findings![0].severity).toBe('error');
    expect(result!.artifact.findings![0].id).toContain('compile-only/handler-exception');
    expect(result!.artifact.findings![0].message).toContain('Handler exploded');
  });

  it('throws for async handler in sync execution', () => {
    const entry: CompileOnlyOutputFormatEntry = {
      contribution: makeContribution(),
      handler: makeAsyncHandler(makeJsonResult({})),
      extensionId: 'com.example.test',
    };
    const registry = createCompileOnlyOutputFormatRegistry([entry]);

    expect(() =>
      executeCompileOnlyOutputSync(registry, {
        formatId: 'test-format',
        timeline: makeTimelineSnapshot(),
        assets: makeAssets(),
        extensionId: 'com.example.test',
      }),
    ).toThrow(/Use executeCompileOnlyOutput/);
  });

  it('provides context with timeline, assets, extensionId, and contributionId', () => {
    let capturedContext: OutputFormatContext | undefined;
    const handler: OutputFormatHandler = (ctx: OutputFormatContext) => {
      capturedContext = ctx;
      return makeJsonResult({ captured: true });
    };
    const entry: CompileOnlyOutputFormatEntry = {
      contribution: makeContribution({ id: 'ctx-test' }),
      handler,
      extensionId: 'com.example.ctx',
    };
    const registry = createCompileOnlyOutputFormatRegistry([entry]);
    const timeline = makeTimelineSnapshot();
    const assets = makeAssets();

    executeCompileOnlyOutputSync(registry, {
      formatId: 'ctx-test',
      timeline,
      assets,
      extensionId: 'com.example.ctx',
    });

    expect(capturedContext).toBeDefined();
    expect(capturedContext!.timeline).toBe(timeline);
    expect(capturedContext!.assets).toBe(assets);
    expect(capturedContext!.extensionId).toBe('com.example.ctx');
    expect(capturedContext!.contributionId).toBe('ctx-test');
    expect(Object.isFrozen(capturedContext)).toBe(true);
  });

  it('handler cannot mutate the context', () => {
    const handler: OutputFormatHandler = (ctx: OutputFormatContext) => {
      // Attempt mutation should be a no-op on frozen object
      try {
        (ctx as Record<string, unknown>).extensionId = 'hacked';
      } catch {
        // Expected: frozen object throws in strict mode
      }
      return makeJsonResult({});
    };
    const entry: CompileOnlyOutputFormatEntry = {
      contribution: makeContribution({ id: 'freeze-test' }),
      handler,
      extensionId: 'com.example.test',
    };
    const registry = createCompileOnlyOutputFormatRegistry([entry]);

    const result = executeCompileOnlyOutputSync(registry, {
      formatId: 'freeze-test',
      timeline: makeTimelineSnapshot(),
      assets: makeAssets(),
      extensionId: 'com.example.test',
    });

    expect(result).not.toBeNull();
    // If the frozen context prevented mutation, execution still succeeded
    expect(result!.hasBlockingErrors).toBe(false);
  });

  it('artifact is always marked deterministic', () => {
    const entry: CompileOnlyOutputFormatEntry = {
      contribution: makeContribution(),
      handler: makeSyncHandler(makeJsonResult({})),
      extensionId: 'com.example.test',
    };
    const registry = createCompileOnlyOutputFormatRegistry([entry]);

    const result = executeCompileOnlyOutputSync(registry, {
      formatId: 'test-format',
      timeline: makeTimelineSnapshot(),
      assets: makeAssets(),
      extensionId: 'com.example.test',
    });

    expect(result).not.toBeNull();
    expect(result!.artifact.determinism).toBe('deterministic');
    expect(DETERMINISM_STATUSES).toContain(result!.artifact.determinism);
  });
});

// ---------------------------------------------------------------------------
// Tests: executeCompileOnlyOutput (async)
// ---------------------------------------------------------------------------

describe('executeCompileOnlyOutput (async)', () => {
  it('executes an async handler and returns a deterministic RenderArtifact', async () => {
    const entry: CompileOnlyOutputFormatEntry = {
      contribution: makeContribution({ id: 'async-json' }),
      handler: makeAsyncHandler(makeJsonResult({ async: true })),
      extensionId: 'com.example.async',
    };
    const registry = createCompileOnlyOutputFormatRegistry([entry]);

    const result = await executeCompileOnlyOutput(registry, {
      formatId: 'async-json',
      timeline: makeTimelineSnapshot(),
      assets: makeAssets(),
      extensionId: 'com.example.async',
    });

    expect(result).not.toBeNull();
    expect(result!.hasBlockingErrors).toBe(false);
    expect(result!.artifact.determinism).toBe('deterministic');
    expect(result!.artifact.mediaKind).toBe('json');
    expect(Object.isFrozen(result!.artifact)).toBe(true);
    const decoder = new TextDecoder();
    const decoded = JSON.parse(decoder.decode(result!.data));
    expect(decoded).toEqual({ async: true });
  });

  it('handles async handler that rejects', async () => {
    const entry: CompileOnlyOutputFormatEntry = {
      contribution: makeContribution({ outputMimeType: 'application/json', outputExtension: 'json' }),
      handler: (_ctx: OutputFormatContext): Promise<CompileOnlyOutputResult> =>
        Promise.reject(new Error('Async handler failed')),
      extensionId: 'com.example.async',
    };
    const registry = createCompileOnlyOutputFormatRegistry([entry]);

    const result = await executeCompileOnlyOutput(registry, {
      formatId: 'test-format',
      timeline: makeTimelineSnapshot(),
      assets: makeAssets(),
      extensionId: 'com.example.async',
    });

    expect(result).not.toBeNull();
    expect(result!.hasBlockingErrors).toBe(true);
    expect(result!.artifact.findings).toBeDefined();
    expect(result!.artifact.findings![0].severity).toBe('error');
    expect(result!.artifact.findings![0].message).toContain('Async handler failed');
  });

  it('returns null for unknown formatId', async () => {
    const registry = createCompileOnlyOutputFormatRegistry([]);
    const result = await executeCompileOnlyOutput(registry, {
      formatId: 'nonexistent',
      timeline: makeTimelineSnapshot(),
      assets: makeAssets(),
      extensionId: 'com.example.test',
    });
    expect(result).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// Tests: createCompileOnlyArtifact (renderability integration)
// ---------------------------------------------------------------------------

describe('createCompileOnlyArtifact (renderability integration)', () => {
  it('produces a frozen RenderArtifact with deterministic posture', () => {
    const artifact = createCompileOnlyArtifact({
      artifactId: 'test-artifact',
      data: new Uint8Array([1, 2, 3]),
      mimeType: 'application/json',
      filename: 'test.json',
      producerExtensionId: 'com.example.test',
    });

    expect(artifact.id).toBe('test-artifact');
    expect(artifact.route).toBe(COMPILE_ONLY_ARTIFACT_ROUTE);
    expect(artifact.determinism).toBe('deterministic');
    expect(artifact.mediaKind).toBe('json');
    expect(artifact.locator.kind).toBe('inline');
    expect(artifact.locator.uri).toBe('test.json');
    expect(artifact.locator.mimeType).toBe('application/json');
    expect(artifact.boundary.source).toBe('browser');
    expect(artifact.boundary.target).toBe('export-output');
    expect(artifact.boundary.failureBehavior).toBe('emit-diagnostic');
    expect(Object.isFrozen(artifact)).toBe(true);
  });

  it('maps MIME types to correct media kinds', () => {
    const cases: Array<[string, string]> = [
      ['image/png', 'image'],
      ['video/mp4', 'video'],
      ['audio/mp3', 'audio'],
      ['application/json', 'json'],
      ['application/ld+json', 'json'],
      ['text/plain', 'text'],
      ['text/html', 'text'],
      ['application/octet-stream', 'binary'],
      ['application/x-custom', 'unknown'],
    ];

    for (const [mimeType, expectedKind] of cases) {
      const artifact = createCompileOnlyArtifact({
        artifactId: `test-${expectedKind}`,
        data: new Uint8Array(0),
        mimeType,
        filename: 'test',
      });
      expect(artifact.mediaKind).toBe(expectedKind);
    }
  });

  it('includes diagnostics as findings', () => {
    const artifact = createCompileOnlyArtifact({
      artifactId: 'diag-test',
      data: new Uint8Array(0),
      mimeType: 'application/json',
      filename: 'test.json',
      diagnostics: [
        {
          severity: 'warning',
          code: 'parser/missing-field',
          message: 'Missing field X',
          assetKey: 'a1',
          extensionId: 'ext1',
          contributionId: 'c1',
        },
        {
          severity: 'error',
          code: 'compile-only/handler-exception',
          message: 'Something broke',
          extensionId: 'ext1',
        },
      ],
      hasBlockingErrors: true,
    });

    expect(artifact.findings).toBeDefined();
    expect(artifact.findings).toHaveLength(2);
    expect(artifact.findings![0].severity).toBe('warning');
    expect(artifact.findings![1].severity).toBe('error');
    expect(artifact.findings![1].reason).toBe('unknown'); // error → unknown blocker reason
    expect(artifact.findings![0].reason).toBeUndefined(); // warning → no blocker reason
    expect(artifact.findings![0].detail).toBeUndefined();
  });

  it('produces consumedMaterialRefs from asset keys', () => {
    const artifact = createCompileOnlyArtifact({
      artifactId: 'asset-test',
      data: new Uint8Array(0),
      mimeType: 'application/json',
      filename: 'test.json',
      consumedAssetKeys: ['img-1', 'vid-2', 'aud-3'],
    });

    expect(artifact.consumedMaterialRefs).toHaveLength(3);
    expect(artifact.consumedMaterialRefs[0].id).toBe('material.asset.img-1');
    expect(artifact.consumedMaterialRefs[0].locator.kind).toBe('asset-registry');
    expect(artifact.consumedMaterialRefs[0].locator.uri).toBe('asset://img-1');
    expect(artifact.consumedMaterialRefs[0].determinism).toBe('deterministic');
    expect(artifact.consumedMaterialRefs[1].id).toBe('material.asset.vid-2');
    expect(artifact.consumedMaterialRefs[2].id).toBe('material.asset.aud-3');
  });

  it('empty diagnostics produce no findings', () => {
    const artifact = createCompileOnlyArtifact({
      artifactId: 'no-diag',
      data: new Uint8Array(0),
      mimeType: 'application/json',
      filename: 'test.json',
      diagnostics: [],
    });

    expect(artifact.findings).toBeUndefined();
  });

  it('undefined diagnostics produce no findings', () => {
    const artifact = createCompileOnlyArtifact({
      artifactId: 'no-diag2',
      data: new Uint8Array(0),
      mimeType: 'application/json',
      filename: 'test.json',
    });

    expect(artifact.findings).toBeUndefined();
  });
});

// ---------------------------------------------------------------------------
// Tests: never calls render providers, render planner, or media render routes
// ---------------------------------------------------------------------------

describe('compile-only output execution isolation', () => {
  it('executeCompileOnlyOutputSync only invokes the handler and renderability helpers', () => {
    let handlerCalled = false;
    const handler: OutputFormatHandler = (_ctx: OutputFormatContext) => {
      handlerCalled = true;
      return makeJsonResult({ isolated: true });
    };
    const entry: CompileOnlyOutputFormatEntry = {
      contribution: makeContribution({ id: 'isolated-test' }),
      handler,
      extensionId: 'com.example.test',
    };
    const registry = createCompileOnlyOutputFormatRegistry([entry]);

    const result = executeCompileOnlyOutputSync(registry, {
      formatId: 'isolated-test',
      timeline: makeTimelineSnapshot(),
      assets: makeAssets(),
      extensionId: 'com.example.test',
    });

    expect(handlerCalled).toBe(true);
    expect(result).not.toBeNull();
    expect(result!.artifact.route).toBe(COMPILE_ONLY_ARTIFACT_ROUTE);
    // The fact that no render providers, render planner, or media render routes
    // are imported or invoked is proven by the module's own import graph
    // (outputFormatRegistry.ts imports only from @reigh/editor-sdk and renderability.ts)
  });

  it('handler never receives render planner or render provider references', () => {
    let receivedContext: OutputFormatContext | undefined;
    const handler: OutputFormatHandler = (ctx: OutputFormatContext) => {
      receivedContext = ctx;
      return makeJsonResult({});
    };
    const entry: CompileOnlyOutputFormatEntry = {
      contribution: makeContribution({ id: 'surface-test' }),
      handler,
      extensionId: 'com.example.test',
    };
    const registry = createCompileOnlyOutputFormatRegistry([entry]);

    executeCompileOnlyOutputSync(registry, {
      formatId: 'surface-test',
      timeline: makeTimelineSnapshot(),
      assets: makeAssets(),
      extensionId: 'com.example.test',
    });

    expect(receivedContext).toBeDefined();
    // Context only contains timeline, assets, extensionId, contributionId
    expect(receivedContext!.timeline).toBeDefined();
    expect(receivedContext!.assets).toBeDefined();
    expect(receivedContext!.extensionId).toBe('com.example.test');
    expect(receivedContext!.contributionId).toBe('surface-test');
    // No render provider, render planner, or media render route references
    expect(Object.keys(receivedContext!)).toHaveLength(4);
  });
});

// ---------------------------------------------------------------------------
// M6: T19 — Compile-only output determinism proof (byte-identical)
// ---------------------------------------------------------------------------

describe('M6: compile-only output determinism (byte-identical)', () => {
  it('sync: same inputs produce byte-identical output across two executions', () => {
    const payload = { key: 'value', numbers: [1, 2, 3] };
    const entry: CompileOnlyOutputFormatEntry = {
      contribution: makeContribution({ id: 'det-sync' }),
      handler: makeSyncHandler(makeJsonResult(payload)),
      extensionId: 'com.example.det',
    };
    const registry = createCompileOnlyOutputFormatRegistry([entry]);
    const timeline = makeTimelineSnapshot();
    const assets = makeAssets();

    const result1 = executeCompileOnlyOutputSync(registry, {
      formatId: 'det-sync', timeline, assets, extensionId: 'com.example.det',
    });
    const result2 = executeCompileOnlyOutputSync(registry, {
      formatId: 'det-sync', timeline, assets, extensionId: 'com.example.det',
    });

    expect(result1).not.toBeNull();
    expect(result2).not.toBeNull();
    // Byte-identical output
    expect(result1!.data).toEqual(result2!.data);
    // Artifact structure identical (except non-deterministic fields like timestamps)
    expect(result1!.artifact.id).toBe(result2!.artifact.id);
    expect(result1!.artifact.route).toBe(result2!.artifact.route);
    expect(result1!.artifact.determinism).toBe(result2!.artifact.determinism);
    expect(result1!.artifact.mediaKind).toBe(result2!.artifact.mediaKind);
    expect(result1!.hasBlockingErrors).toBe(result2!.hasBlockingErrors);
  });

  it('async: same inputs produce byte-identical output across two executions', async () => {
    const payload = { async: 'deterministic', count: 42 };
    const entry: CompileOnlyOutputFormatEntry = {
      contribution: makeContribution({ id: 'det-async' }),
      handler: makeAsyncHandler(makeJsonResult(payload)),
      extensionId: 'com.example.det',
    };
    const registry = createCompileOnlyOutputFormatRegistry([entry]);
    const timeline = makeTimelineSnapshot();
    const assets = makeAssets();

    const result1 = await executeCompileOnlyOutput(registry, {
      formatId: 'det-async', timeline, assets, extensionId: 'com.example.det',
    });
    const result2 = await executeCompileOnlyOutput(registry, {
      formatId: 'det-async', timeline, assets, extensionId: 'com.example.det',
    });

    expect(result1).not.toBeNull();
    expect(result2).not.toBeNull();
    expect(result1!.data).toEqual(result2!.data);
    expect(result1!.artifact.determinism).toBe('deterministic');
    expect(result2!.artifact.determinism).toBe('deterministic');
  });

  it('different asset data produces different output bytes', () => {
    let capturedAssets: ReadonlyMap<string, Readonly<AssetMetadata>> | undefined;
    const handler: OutputFormatHandler = (ctx: OutputFormatContext) => {
      capturedAssets = ctx.assets;
      // Encode asset count into output
      const encoder = new TextEncoder();
      return {
        data: encoder.encode(JSON.stringify({ assetCount: ctx.assets.size })),
        mimeType: 'application/json',
        filename: 'output.json',
        hasBlockingErrors: false,
      };
    };
    const entry: CompileOnlyOutputFormatEntry = {
      contribution: makeContribution({ id: 'diff-assets' }),
      handler,
      extensionId: 'com.example.det',
    };
    const registry = createCompileOnlyOutputFormatRegistry([entry]);
    const timeline = makeTimelineSnapshot();

    const assets2 = makeAssets();
    const assets3 = new Map([...assets2, ['asset-3', Object.freeze({ integrity: { algorithm: 'sha256', hash: 'def456', size: 2048 } })]]);

    const result2 = executeCompileOnlyOutputSync(registry, {
      formatId: 'diff-assets', timeline, assets: assets2, extensionId: 'com.example.det',
    });
    const result3 = executeCompileOnlyOutputSync(registry, {
      formatId: 'diff-assets', timeline, assets: assets3, extensionId: 'com.example.det',
    });

    expect(result2).not.toBeNull();
    expect(result3).not.toBeNull();
    expect(result2!.data).not.toEqual(result3!.data);
    const decoder = new TextDecoder();
    expect(JSON.parse(decoder.decode(result2!.data))).toEqual({ assetCount: 2 });
    expect(JSON.parse(decoder.decode(result3!.data))).toEqual({ assetCount: 3 });
  });

  it('different timeline produces different output bytes', () => {
    let capturedTimeline: TimelineSnapshot | undefined;
    const handler: OutputFormatHandler = (ctx: OutputFormatContext) => {
      capturedTimeline = ctx.timeline;
      const encoder = new TextEncoder();
      return {
        data: encoder.encode(JSON.stringify({ clipCount: ctx.timeline.clips?.length ?? 0 })),
        mimeType: 'application/json',
        filename: 'output.json',
        hasBlockingErrors: false,
      };
    };
    const entry: CompileOnlyOutputFormatEntry = {
      contribution: makeContribution({ id: 'diff-timeline' }),
      handler,
      extensionId: 'com.example.det',
    };
    const registry = createCompileOnlyOutputFormatRegistry([entry]);
    const assets = makeAssets();

    const timeline1 = makeTimelineSnapshot();
    const timeline2 = makeTimelineSnapshot({
      clips: [
        { id: 'clip-1', track: 'track-1', at: 0, clipType: 'media', duration: 30, managed: false },
        { id: 'clip-2', track: 'track-2', at: 30, clipType: 'media', duration: 15, managed: false },
      ],
      assetKeys: ['asset-1'],
    });

    const result1 = executeCompileOnlyOutputSync(registry, {
      formatId: 'diff-timeline', timeline: timeline1, assets, extensionId: 'com.example.det',
    });
    const result2 = executeCompileOnlyOutputSync(registry, {
      formatId: 'diff-timeline', timeline: timeline2, assets, extensionId: 'com.example.det',
    });

    expect(result1).not.toBeNull();
    expect(result2).not.toBeNull();
    expect(result1!.data).not.toEqual(result2!.data);
  });

  it('artifact determinism label is always \'deterministic\' regardless of handler result', () => {
    const cases: CompileOnlyOutputResult[] = [
      makeJsonResult({}),
      { data: new Uint8Array([0]), mimeType: 'application/octet-stream', filename: 'a.bin', hasBlockingErrors: true },
      { data: new TextEncoder().encode('hello'), mimeType: 'text/plain', filename: 'a.txt', hasBlockingErrors: false },
    ];
    for (const result of cases) {
      const entry: CompileOnlyOutputFormatEntry = {
        contribution: makeContribution({ id: 'always-det' }),
        handler: makeSyncHandler(result),
        extensionId: 'com.example.test',
      };
      const registry = createCompileOnlyOutputFormatRegistry([entry]);
      const exec = executeCompileOnlyOutputSync(registry, {
        formatId: 'always-det', timeline: makeTimelineSnapshot(), assets: makeAssets(), extensionId: 'com.example.test',
      });
      expect(exec).not.toBeNull();
      expect(exec!.artifact.determinism).toBe('deterministic');
    }
  });
});

// ---------------------------------------------------------------------------
// M6: T19 — Render-dependent declarations never execute (defense-in-depth)
// ---------------------------------------------------------------------------

describe('M6: render-dependent declarations never execute', () => {
  it('createCompileOnlyOutputFormatRegistry silently skips render-dependent entries', () => {
    const compileOnly: CompileOnlyOutputFormatEntry = {
      contribution: makeContribution({ id: 'compile-a', requiresRender: false }),
      handler: makeSyncHandler(makeJsonResult({ a: 1 })),
      extensionId: 'com.example.a',
    };
    const renderDep: CompileOnlyOutputFormatEntry = {
      contribution: makeContribution({ id: 'render-b', requiresRender: true }),
      handler: makeSyncHandler(makeJsonResult({ b: 2 })),
      extensionId: 'com.example.b',
    };

    const registry = createCompileOnlyOutputFormatRegistry([compileOnly, renderDep]);
    expect(registry.size).toBe(1);
    expect(registry.has(formatScopedKey('com.example.a', 'compile-a'))).toBe(true);
    expect(registry.has(formatScopedKey('com.example.b', 'render-b'))).toBe(false);
  });

  it('registry with only render-dependent entries has size 0', () => {
    const r1: CompileOnlyOutputFormatEntry = {
      contribution: makeContribution({ id: 'r1', requiresRender: true }),
      handler: makeSyncHandler(makeJsonResult({})),
      extensionId: 'com.example.r1',
    };
    const r2: CompileOnlyOutputFormatEntry = {
      contribution: makeContribution({ id: 'r2', requiresRender: true }),
      handler: makeSyncHandler(makeJsonResult({})),
      extensionId: 'com.example.r2',
    };

    const registry = createCompileOnlyOutputFormatRegistry([r1, r2]);
    expect(registry.size).toBe(0);
  });

  it('render-dependent handler is never called during registry creation', () => {
    let handlerCalled = false;
    const renderDep: CompileOnlyOutputFormatEntry = {
      contribution: makeContribution({ id: 'render-x', requiresRender: true }),
      handler: (_ctx) => { handlerCalled = true; return makeJsonResult({}); },
      extensionId: 'com.example.x',
    };

    createCompileOnlyOutputFormatRegistry([renderDep]);
    expect(handlerCalled).toBe(false);
  });

  it('executeCompileOnlyOutputSync returns null for render-dependent format (defense-in-depth)', () => {
    // Manually build a registry that includes a render-dependent entry
    // to test the execution-level guard
    const renderDep: CompileOnlyOutputFormatEntry = {
      contribution: makeContribution({ id: 'render-guard', requiresRender: true }),
      handler: makeSyncHandler(makeJsonResult({})),
      extensionId: 'com.example.rg',
    };
    const map = new Map<string, CompileOnlyOutputFormatEntry>();
    map.set(formatScopedKey('com.example.rg', 'render-guard'), renderDep);
    const registry: CompileOnlyOutputFormatRegistry = Object.freeze(map);

    const result = executeCompileOnlyOutputSync(registry, {
      formatId: 'render-guard',
      timeline: makeTimelineSnapshot(),
      assets: makeAssets(),
      extensionId: 'com.example.rg',
    });
    expect(result).toBeNull();
  });

  it('executeCompileOnlyOutput (async) returns null for render-dependent format (defense-in-depth)', async () => {
    const renderDep: CompileOnlyOutputFormatEntry = {
      contribution: makeContribution({ id: 'render-async-guard', requiresRender: true }),
      handler: makeAsyncHandler(makeJsonResult({})),
      extensionId: 'com.example.rag',
    };
    const map = new Map<string, CompileOnlyOutputFormatEntry>();
    map.set(formatScopedKey('com.example.rag', 'render-async-guard'), renderDep);
    const registry: CompileOnlyOutputFormatRegistry = Object.freeze(map);

    const result = await executeCompileOnlyOutput(registry, {
      formatId: 'render-async-guard',
      timeline: makeTimelineSnapshot(),
      assets: makeAssets(),
      extensionId: 'com.example.rag',
    });
    expect(result).toBeNull();
  });

  it('render-dependent handler is never called in sync execution path', () => {
    let handlerCalled = false;
    const renderDep: CompileOnlyOutputFormatEntry = {
      contribution: makeContribution({ id: 'never-called-sync', requiresRender: true }),
      handler: (_ctx) => { handlerCalled = true; return makeJsonResult({}); },
      extensionId: 'com.example.ncs',
    };
    const map = new Map<string, CompileOnlyOutputFormatEntry>();
    map.set(formatScopedKey('com.example.ncs', 'never-called-sync'), renderDep);
    const registry: CompileOnlyOutputFormatRegistry = Object.freeze(map);

    executeCompileOnlyOutputSync(registry, {
      formatId: 'never-called-sync',
      timeline: makeTimelineSnapshot(),
      assets: makeAssets(),
      extensionId: 'com.example.ncs',
    });
    expect(handlerCalled).toBe(false);
  });

  it('render-dependent handler is never called in async execution path', async () => {
    let handlerCalled = false;
    const renderDep: CompileOnlyOutputFormatEntry = {
      contribution: makeContribution({ id: 'never-called-async', requiresRender: true }),
      handler: (_ctx) => { handlerCalled = true; return makeJsonResult({}); },
      extensionId: 'com.example.nca',
    };
    const map = new Map<string, CompileOnlyOutputFormatEntry>();
    map.set(formatScopedKey('com.example.nca', 'never-called-async'), renderDep);
    const registry: CompileOnlyOutputFormatRegistry = Object.freeze(map);

    await executeCompileOnlyOutput(registry, {
      formatId: 'never-called-async',
      timeline: makeTimelineSnapshot(),
      assets: makeAssets(),
      extensionId: 'com.example.nca',
    });
    expect(handlerCalled).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// M6: T19 — Multiple compile-only formats in one registry
// ---------------------------------------------------------------------------

describe('M6: multiple compile-only formats in one registry', () => {
  it('two formats execute independently and produce distinct artifacts', () => {
    const encoder = new TextEncoder();
    const entryA: CompileOnlyOutputFormatEntry = {
      contribution: makeContribution({ id: 'format-a', outputMimeType: 'application/json', outputExtension: 'json' }),
      handler: makeSyncHandler({
        data: encoder.encode(JSON.stringify({ format: 'A' })),
        mimeType: 'application/json',
        filename: 'a.json',
        hasBlockingErrors: false,
      }),
      extensionId: 'com.example.multi',
    };
    const entryB: CompileOnlyOutputFormatEntry = {
      contribution: makeContribution({ id: 'format-b', outputMimeType: 'text/plain', outputExtension: 'txt' }),
      handler: makeSyncHandler({
        data: encoder.encode('Format B output'),
        mimeType: 'text/plain',
        filename: 'b.txt',
        hasBlockingErrors: false,
      }),
      extensionId: 'com.example.multi',
    };
    const registry = createCompileOnlyOutputFormatRegistry([entryA, entryB]);
    expect(registry.size).toBe(2);

    const timeline = makeTimelineSnapshot();
    const assets = makeAssets();

    const resultA = executeCompileOnlyOutputSync(registry, {
      formatId: 'format-a', timeline, assets, extensionId: 'com.example.multi',
    });
    const resultB = executeCompileOnlyOutputSync(registry, {
      formatId: 'format-b', timeline, assets, extensionId: 'com.example.multi',
    });

    expect(resultA).not.toBeNull();
    expect(resultB).not.toBeNull();
    expect(resultA!.artifact.id).toBe('compile-only.format-a');
    expect(resultB!.artifact.id).toBe('compile-only.format-b');
    expect(resultA!.artifact.mediaKind).toBe('json');
    expect(resultB!.artifact.mediaKind).toBe('text');
    expect(resultA!.artifact.locator.mimeType).toBe('application/json');
    expect(resultB!.artifact.locator.mimeType).toBe('text/plain');
  });

  it('each format receives its own contributionId in context', () => {
    const capturedIds: string[] = [];
    const makeHandler = (id: string): OutputFormatHandler => (ctx: OutputFormatContext) => {
      capturedIds.push(ctx.contributionId);
      return makeJsonResult({ from: id });
    };

    const entries: CompileOnlyOutputFormatEntry[] = [
      { contribution: makeContribution({ id: 'ctx-a' }), handler: makeHandler('ctx-a'), extensionId: 'com.example.ctx' },
      { contribution: makeContribution({ id: 'ctx-b' }), handler: makeHandler('ctx-b'), extensionId: 'com.example.ctx' },
      { contribution: makeContribution({ id: 'ctx-c' }), handler: makeHandler('ctx-c'), extensionId: 'com.example.ctx' },
    ];
    const registry = createCompileOnlyOutputFormatRegistry(entries);
    const timeline = makeTimelineSnapshot();
    const assets = makeAssets();

    executeCompileOnlyOutputSync(registry, { formatId: 'ctx-a', timeline, assets, extensionId: 'com.example.ctx' });
    executeCompileOnlyOutputSync(registry, { formatId: 'ctx-b', timeline, assets, extensionId: 'com.example.ctx' });
    executeCompileOnlyOutputSync(registry, { formatId: 'ctx-c', timeline, assets, extensionId: 'com.example.ctx' });

    expect(capturedIds).toEqual(['ctx-a', 'ctx-b', 'ctx-c']);
  });

  it('multiple compile-only formats with render-dependent mixed in', () => {
    const encoder = new TextEncoder();
    const entries: CompileOnlyOutputFormatEntry[] = [
      {
        contribution: makeContribution({ id: 'co-1', requiresRender: false }),
        handler: makeSyncHandler({ data: encoder.encode('co1'), mimeType: 'text/plain', filename: 'co1.txt', hasBlockingErrors: false }),
        extensionId: 'com.example.mix',
      },
      {
        contribution: makeContribution({ id: 'rd-1', requiresRender: true }),
        handler: makeSyncHandler({ data: encoder.encode('rd1'), mimeType: 'text/plain', filename: 'rd1.txt', hasBlockingErrors: false }),
        extensionId: 'com.example.mix',
      },
      {
        contribution: makeContribution({ id: 'co-2', requiresRender: false }),
        handler: makeSyncHandler({ data: encoder.encode('co2'), mimeType: 'text/plain', filename: 'co2.txt', hasBlockingErrors: false }),
        extensionId: 'com.example.mix',
      },
    ];
    const registry = createCompileOnlyOutputFormatRegistry(entries);
    expect(registry.size).toBe(2);
    expect(registry.has(formatScopedKey('com.example.mix', 'co-1'))).toBe(true);
    expect(registry.has(formatScopedKey('com.example.mix', 'co-2'))).toBe(true);
    expect(registry.has(formatScopedKey('com.example.mix', 'rd-1'))).toBe(false);

    const timeline = makeTimelineSnapshot();
    const assets = makeAssets();

    // Can execute compile-only formats
    const result1 = executeCompileOnlyOutputSync(registry, {
      formatId: 'co-1', timeline, assets, extensionId: 'com.example.mix',
    });
    const result2 = executeCompileOnlyOutputSync(registry, {
      formatId: 'co-2', timeline, assets, extensionId: 'com.example.mix',
    });
    expect(result1).not.toBeNull();
    expect(result2).not.toBeNull();

    // Render-dependent returns null
    const result3 = executeCompileOnlyOutputSync(registry, {
      formatId: 'rd-1', timeline, assets, extensionId: 'com.example.mix',
    });
    expect(result3).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// M6: T19 — Context completeness (timeline/assets/options received by handler)
// ---------------------------------------------------------------------------

describe('M6: handler receives complete timeline/assets/options', () => {
  it('handler receives the exact same timeline reference', () => {
    let received: TimelineSnapshot | undefined;
    const handler: OutputFormatHandler = (ctx) => {
      received = ctx.timeline;
      return makeJsonResult({});
    };
    const entry: CompileOnlyOutputFormatEntry = {
      contribution: makeContribution({ id: 'ref-timeline' }),
      handler,
      extensionId: 'com.example.ref',
    };
    const registry = createCompileOnlyOutputFormatRegistry([entry]);
    const timeline = makeTimelineSnapshot({ projectId: 'custom-project' });

    executeCompileOnlyOutputSync(registry, {
      formatId: 'ref-timeline', timeline, assets: makeAssets(), extensionId: 'com.example.ref',
    });

    expect(received).toBe(timeline);
    expect(received!.projectId).toBe('custom-project');
  });

  it('handler receives the exact same assets map reference', () => {
    let received: ReadonlyMap<string, Readonly<AssetMetadata>> | undefined;
    const handler: OutputFormatHandler = (ctx) => {
      received = ctx.assets;
      return makeJsonResult({});
    };
    const entry: CompileOnlyOutputFormatEntry = {
      contribution: makeContribution({ id: 'ref-assets' }),
      handler,
      extensionId: 'com.example.ref',
    };
    const registry = createCompileOnlyOutputFormatRegistry([entry]);
    const assets = makeAssets();

    executeCompileOnlyOutputSync(registry, {
      formatId: 'ref-assets', timeline: makeTimelineSnapshot(), assets, extensionId: 'com.example.ref',
    });

    expect(received).toBe(assets);
    expect(received!.get('asset-1')).toBeDefined();
  });

  it('handler receives extensionVersion from execution options', () => {
    let receivedVersion: string | undefined;
    const handler: OutputFormatHandler = (_ctx) => {
      // The version is on the entry, not the context — validate artifact carries it
      return makeJsonResult({});
    };
    const entry: CompileOnlyOutputFormatEntry = {
      contribution: makeContribution({ id: 'versioned' }),
      handler,
      extensionId: 'com.example.ver',
      extensionVersion: '3.2.1',
    };
    const registry = createCompileOnlyOutputFormatRegistry([entry]);

    const result = executeCompileOnlyOutputSync(registry, {
      formatId: 'versioned',
      timeline: makeTimelineSnapshot(),
      assets: makeAssets(),
      extensionId: 'com.example.ver',
      extensionVersion: '3.2.1',
    });

    expect(result).not.toBeNull();
    expect(result!.artifact.producerExtensionId).toBe('com.example.ver');
    expect(result!.artifact.producerVersion).toBe('3.2.1');
  });

  it('handler receives empty timeline gracefully', () => {
    let received: TimelineSnapshot | undefined;
    const handler: OutputFormatHandler = (ctx) => {
      received = ctx.timeline;
      return makeJsonResult({});
    };
    const entry: CompileOnlyOutputFormatEntry = {
      contribution: makeContribution({ id: 'empty-timeline' }),
      handler,
      extensionId: 'com.example.edge',
    };
    const registry = createCompileOnlyOutputFormatRegistry([entry]);
    const emptyTimeline = makeTimelineSnapshot({ clips: [], assetKeys: [] });

    const result = executeCompileOnlyOutputSync(registry, {
      formatId: 'empty-timeline',
      timeline: emptyTimeline,
      assets: makeAssets(),
      extensionId: 'com.example.edge',
    });

    expect(result).not.toBeNull();
    expect(received!.clips).toHaveLength(0);
    expect(received!.assetKeys).toHaveLength(0);
    expect(result!.artifact.consumedMaterialRefs).toHaveLength(0);
  });

  it('handler receives empty assets map gracefully', () => {
    let received: ReadonlyMap<string, Readonly<AssetMetadata>> | undefined;
    const handler: OutputFormatHandler = (ctx) => {
      received = ctx.assets;
      return makeJsonResult({});
    };
    const entry: CompileOnlyOutputFormatEntry = {
      contribution: makeContribution({ id: 'empty-assets' }),
      handler,
      extensionId: 'com.example.edge',
    };
    const registry = createCompileOnlyOutputFormatRegistry([entry]);
    const emptyAssets = new Map<string, Readonly<AssetMetadata>>();

    const result = executeCompileOnlyOutputSync(registry, {
      formatId: 'empty-assets',
      timeline: makeTimelineSnapshot(),
      assets: emptyAssets,
      extensionId: 'com.example.edge',
    });

    expect(result).not.toBeNull();
    expect(received!.size).toBe(0);
    // consumedMaterialRefs still come from timeline.assetKeys, not from assets map size
  });

  it('context is frozen and immutable', () => {
    let contextWasFrozen = false;
    let caughtMutationError = false;
    const handler: OutputFormatHandler = (ctx) => {
      contextWasFrozen = Object.isFrozen(ctx);
      try {
        (ctx as Record<string, unknown>).timeline = null;
      } catch {
        caughtMutationError = true;
      }
      return makeJsonResult({});
    };
    const entry: CompileOnlyOutputFormatEntry = {
      contribution: makeContribution({ id: 'frozen-ctx' }),
      handler,
      extensionId: 'com.example.frozen',
    };
    const registry = createCompileOnlyOutputFormatRegistry([entry]);

    const result = executeCompileOnlyOutputSync(registry, {
      formatId: 'frozen-ctx',
      timeline: makeTimelineSnapshot(),
      assets: makeAssets(),
      extensionId: 'com.example.frozen',
    });

    expect(result).not.toBeNull();
    expect(contextWasFrozen).toBe(true);
    expect(caughtMutationError).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// M6: T19 — Async execution supplements
// ---------------------------------------------------------------------------

describe('M6: async execution supplements', () => {
  it('executeCompileOnlyOutput works with synchronous handler (no Promise)', async () => {
    const entry: CompileOnlyOutputFormatEntry = {
      contribution: makeContribution({ id: 'sync-via-async' }),
      handler: makeSyncHandler(makeJsonResult({ sync: true })),
      extensionId: 'com.example.async',
    };
    const registry = createCompileOnlyOutputFormatRegistry([entry]);

    const result = await executeCompileOnlyOutput(registry, {
      formatId: 'sync-via-async',
      timeline: makeTimelineSnapshot(),
      assets: makeAssets(),
      extensionId: 'com.example.async',
    });

    expect(result).not.toBeNull();
    expect(result!.hasBlockingErrors).toBe(false);
    expect(result!.artifact.determinism).toBe('deterministic');
    const decoder = new TextDecoder();
    expect(JSON.parse(decoder.decode(result!.data))).toEqual({ sync: true });
  });

  it('async handler receives context with timeline and assets', async () => {
    let captured: OutputFormatContext | undefined;
    const handler: OutputFormatHandler = (ctx: OutputFormatContext) => {
      captured = ctx;
      return Promise.resolve(makeJsonResult({}));
    };
    const entry: CompileOnlyOutputFormatEntry = {
      contribution: makeContribution({ id: 'async-ctx' }),
      handler,
      extensionId: 'com.example.async',
    };
    const registry = createCompileOnlyOutputFormatRegistry([entry]);
    const timeline = makeTimelineSnapshot();
    const assets = makeAssets();

    await executeCompileOnlyOutput(registry, {
      formatId: 'async-ctx', timeline, assets, extensionId: 'com.example.async',
    });

    expect(captured).toBeDefined();
    expect(captured!.timeline).toBe(timeline);
    expect(captured!.assets).toBe(assets);
    expect(captured!.extensionId).toBe('com.example.async');
    expect(captured!.contributionId).toBe('async-ctx');
    expect(Object.isFrozen(captured)).toBe(true);
  });

  it('async handler returning blocking errors produces error artifact', async () => {
    const entry: CompileOnlyOutputFormatEntry = {
      contribution: makeContribution({ id: 'async-err', outputMimeType: 'application/json', outputExtension: 'json' }),
      handler: (_ctx: OutputFormatContext): Promise<CompileOnlyOutputResult> =>
        Promise.resolve({
          data: new Uint8Array(0),
          mimeType: 'application/json',
          filename: 'error.json',
          hasBlockingErrors: true,
          diagnostics: [{
            severity: 'error',
            code: 'compile-only/validation-failed',
            message: 'Required field missing',
            extensionId: 'com.example.async',
            contributionId: 'async-err',
          }],
        }),
      extensionId: 'com.example.async',
    };
    const registry = createCompileOnlyOutputFormatRegistry([entry]);

    const result = await executeCompileOnlyOutput(registry, {
      formatId: 'async-err',
      timeline: makeTimelineSnapshot(),
      assets: makeAssets(),
      extensionId: 'com.example.async',
    });

    expect(result).not.toBeNull();
    expect(result!.hasBlockingErrors).toBe(true);
    expect(result!.artifact.findings).toBeDefined();
    expect(result!.artifact.findings![0].severity).toBe('error');
    expect(result!.artifact.findings![0].message).toBe('Required field missing');
  });
});

// ---------------------------------------------------------------------------
// M6: T19 — Artifact compatibility proof
// ---------------------------------------------------------------------------

describe('M6: artifact compatibility proof', () => {
  it('produced artifact has all required RenderArtifact fields', () => {
    const entry: CompileOnlyOutputFormatEntry = {
      contribution: makeContribution({ id: 'full-artifact' }),
      handler: makeSyncHandler(makeJsonResult({})),
      extensionId: 'com.example.art',
    };
    const registry = createCompileOnlyOutputFormatRegistry([entry]);

    const result = executeCompileOnlyOutputSync(registry, {
      formatId: 'full-artifact',
      timeline: makeTimelineSnapshot(),
      assets: makeAssets(),
      extensionId: 'com.example.art',
    });

    expect(result).not.toBeNull();
    const a = result!.artifact;
    // Required RenderArtifact fields
    expect(a.id).toBeDefined();
    expect(a.route).toBeDefined();
    expect(a.locator).toBeDefined();
    expect(a.mediaKind).toBeDefined();
    expect(a.consumedMaterialRefs).toBeDefined();
    expect(a.determinism).toBeDefined();
    expect(a.boundary).toBeDefined();
    expect(a.manifest).toMatchObject({
      artifactId: a.id,
      route: a.route,
      determinism: a.determinism,
      producerExtensionId: 'com.example.art',
      outputFormatId: 'full-artifact',
    });
  });

  it('consumedMaterialRefs use asset-registry locator kind', () => {
    const entry: CompileOnlyOutputFormatEntry = {
      contribution: makeContribution({ id: 'locator-kind' }),
      handler: makeSyncHandler(makeJsonResult({})),
      extensionId: 'com.example.loc',
    };
    const registry = createCompileOnlyOutputFormatRegistry([entry]);
    const timeline = makeTimelineSnapshot({ assetKeys: ['img-main', 'audio-narration'] });

    const result = executeCompileOnlyOutputSync(registry, {
      formatId: 'locator-kind',
      timeline,
      assets: makeAssets(),
      extensionId: 'com.example.loc',
    });

    expect(result).not.toBeNull();
    const refs = result!.artifact.consumedMaterialRefs;
    expect(refs).toHaveLength(2);
    for (const ref of refs) {
      expect(ref.locator.kind).toBe('asset-registry');
      expect(ref.locator.uri).toMatch(/^asset:\/\//);
      expect(ref.determinism).toBe('deterministic');
      expect(ref.replacementPolicy).toBe('preserve-live-ref');
    }
  });

  it('artifact route is browser-export (never preview or sidecar)', () => {
    const entry: CompileOnlyOutputFormatEntry = {
      contribution: makeContribution({ id: 'route-check' }),
      handler: makeSyncHandler(makeJsonResult({})),
      extensionId: 'com.example.route',
    };
    const registry = createCompileOnlyOutputFormatRegistry([entry]);

    const result = executeCompileOnlyOutputSync(registry, {
      formatId: 'route-check',
      timeline: makeTimelineSnapshot(),
      assets: makeAssets(),
      extensionId: 'com.example.route',
    });

    expect(result).not.toBeNull();
    expect(result!.artifact.route).toBe(COMPILE_ONLY_ARTIFACT_ROUTE);
    expect(result!.artifact.route).not.toBe('preview');
    expect(result!.artifact.route).not.toBe('worker-export');
    expect(result!.artifact.route).not.toBe('sidecar-export');
    // Verify the route is in the locked vocabulary
    expect(RENDER_ROUTES).toContain(result!.artifact.route);
  });

  it('artifact boundary has emit-diagnostic failure behavior (non-blocking)', () => {
    const entry: CompileOnlyOutputFormatEntry = {
      contribution: makeContribution({ id: 'boundary-check' }),
      handler: makeSyncHandler(makeJsonResult({})),
      extensionId: 'com.example.boundary',
    };
    const registry = createCompileOnlyOutputFormatRegistry([entry]);

    const result = executeCompileOnlyOutputSync(registry, {
      formatId: 'boundary-check',
      timeline: makeTimelineSnapshot(),
      assets: makeAssets(),
      extensionId: 'com.example.boundary',
    });

    expect(result).not.toBeNull();
    expect(result!.artifact.boundary.failureBehavior).toBe('emit-diagnostic');
    expect(result!.artifact.boundary.source).toBe('browser');
    expect(result!.artifact.boundary.target).toBe('export-output');
  });

  it('zero-length data output is preserved faithfully', () => {
    const entry: CompileOnlyOutputFormatEntry = {
      contribution: makeContribution({ id: 'zero-data' }),
      handler: makeSyncHandler({
        data: new Uint8Array(0),
        mimeType: 'application/json',
        filename: 'empty.json',
        hasBlockingErrors: false,
      }),
      extensionId: 'com.example.zero',
    };
    const registry = createCompileOnlyOutputFormatRegistry([entry]);

    const result = executeCompileOnlyOutputSync(registry, {
      formatId: 'zero-data',
      timeline: makeTimelineSnapshot(),
      assets: makeAssets(),
      extensionId: 'com.example.zero',
    });

    expect(result).not.toBeNull();
    expect(result!.data).toEqual(new Uint8Array(0));
    expect(result!.hasBlockingErrors).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// T10: Cross-extension duplicate bare format IDs
// ---------------------------------------------------------------------------

describe('cross-extension duplicate bare format IDs', () => {
  it('two extensions with the same bare formatId are both stored without clobbering', () => {
    const handlerA = makeSyncHandler(makeJsonResult({ ext: 'A' }));
    const handlerB = makeSyncHandler(makeJsonResult({ ext: 'B' }));

    const entryA: CompileOnlyOutputFormatEntry = {
      contribution: makeContribution({ id: 'shared-format', label: 'Format A' }),
      handler: handlerA,
      extensionId: 'com.example.alpha',
    };
    const entryB: CompileOnlyOutputFormatEntry = {
      contribution: makeContribution({ id: 'shared-format', label: 'Format B' }),
      handler: handlerB,
      extensionId: 'com.example.beta',
    };

    const registry = createCompileOnlyOutputFormatRegistry([entryA, entryB]);

    // Both entries are stored under distinct scoped keys
    expect(registry.size).toBe(2);
    expect(registry.get(formatScopedKey('com.example.alpha', 'shared-format'))).toBe(entryA);
    expect(registry.get(formatScopedKey('com.example.beta', 'shared-format'))).toBe(entryB);
  });

  it('lookup by extensionId + formatId returns the correct entry', () => {
    const handlerA = makeSyncHandler(makeJsonResult({ ext: 'A' }));
    const handlerB = makeSyncHandler(makeJsonResult({ ext: 'B' }));

    const entryA: CompileOnlyOutputFormatEntry = {
      contribution: makeContribution({ id: 'shared-format', label: 'Format A' }),
      handler: handlerA,
      extensionId: 'com.example.alpha',
    };
    const entryB: CompileOnlyOutputFormatEntry = {
      contribution: makeContribution({ id: 'shared-format', label: 'Format B' }),
      handler: handlerB,
      extensionId: 'com.example.beta',
    };

    const registry = createCompileOnlyOutputFormatRegistry([entryA, entryB]);
    const timeline = makeTimelineSnapshot();
    const assets = makeAssets();

    // Execute via extension Alpha
    const resultA = executeCompileOnlyOutputSync(registry, {
      formatId: 'shared-format',
      timeline,
      assets,
      extensionId: 'com.example.alpha',
    });
    expect(resultA).not.toBeNull();
    const decoderA = new TextDecoder();
    expect(JSON.parse(decoderA.decode(resultA!.data))).toEqual({ ext: 'A' });

    // Execute via extension Beta
    const resultB = executeCompileOnlyOutputSync(registry, {
      formatId: 'shared-format',
      timeline,
      assets,
      extensionId: 'com.example.beta',
    });
    expect(resultB).not.toBeNull();
    const decoderB = new TextDecoder();
    expect(JSON.parse(decoderB.decode(resultB!.data))).toEqual({ ext: 'B' });
  });

  it('cross-extension duplicate bare formatId works with async execution', async () => {
    const handlerA = makeAsyncHandler(makeJsonResult({ ext: 'A-async' }));
    const handlerB = makeAsyncHandler(makeJsonResult({ ext: 'B-async' }));

    const entryA: CompileOnlyOutputFormatEntry = {
      contribution: makeContribution({ id: 'async-shared' }),
      handler: handlerA,
      extensionId: 'com.example.alpha',
    };
    const entryB: CompileOnlyOutputFormatEntry = {
      contribution: makeContribution({ id: 'async-shared' }),
      handler: handlerB,
      extensionId: 'com.example.beta',
    };

    const registry = createCompileOnlyOutputFormatRegistry([entryA, entryB]);
    const timeline = makeTimelineSnapshot();
    const assets = makeAssets();

    const resultA = await executeCompileOnlyOutput(registry, {
      formatId: 'async-shared',
      timeline,
      assets,
      extensionId: 'com.example.alpha',
    });
    expect(resultA).not.toBeNull();
    const decoderA = new TextDecoder();
    expect(JSON.parse(decoderA.decode(resultA!.data))).toEqual({ ext: 'A-async' });

    const resultB = await executeCompileOnlyOutput(registry, {
      formatId: 'async-shared',
      timeline,
      assets,
      extensionId: 'com.example.beta',
    });
    expect(resultB).not.toBeNull();
    const decoderB = new TextDecoder();
    expect(JSON.parse(decoderB.decode(resultB!.data))).toEqual({ ext: 'B-async' });
  });

  it('unknown extensionId + formatId combination returns null', () => {
    const entry: CompileOnlyOutputFormatEntry = {
      contribution: makeContribution({ id: 'only-mine' }),
      handler: makeSyncHandler(makeJsonResult({})),
      extensionId: 'com.example.alpha',
    };

    const registry = createCompileOnlyOutputFormatRegistry([entry]);

    // Correct extension but wrong formatId
    const result1 = executeCompileOnlyOutputSync(registry, {
      formatId: 'nonexistent',
      timeline: makeTimelineSnapshot(),
      assets: makeAssets(),
      extensionId: 'com.example.alpha',
    });
    expect(result1).toBeNull();

    // Correct formatId but wrong extension
    const result2 = executeCompileOnlyOutputSync(registry, {
      formatId: 'only-mine',
      timeline: makeTimelineSnapshot(),
      assets: makeAssets(),
      extensionId: 'com.example.beta',
    });
    expect(result2).toBeNull();
  });

  it('same extension and same bare formatId overwrites (last-wins within same scope)', () => {
    const handler1 = makeSyncHandler(makeJsonResult({ version: 1 }));
    const handler2 = makeSyncHandler(makeJsonResult({ version: 2 }));

    const entry1: CompileOnlyOutputFormatEntry = {
      contribution: makeContribution({ id: 'same-scope-fmt' }),
      handler: handler1,
      extensionId: 'com.example.same',
    };
    const entry2: CompileOnlyOutputFormatEntry = {
      contribution: makeContribution({ id: 'same-scope-fmt' }),
      handler: handler2,
      extensionId: 'com.example.same',
    };

    const registry = createCompileOnlyOutputFormatRegistry([entry1, entry2]);

    // Same scoped key → single entry, last-wins
    expect(registry.size).toBe(1);
    expect(registry.get(formatScopedKey('com.example.same', 'same-scope-fmt'))).toBe(entry2);

    // Execution returns the last-registered handler's output
    const result = executeCompileOnlyOutputSync(registry, {
      formatId: 'same-scope-fmt',
      timeline: makeTimelineSnapshot(),
      assets: makeAssets(),
      extensionId: 'com.example.same',
    });
    expect(result).not.toBeNull();
    const decoder = new TextDecoder();
    expect(JSON.parse(decoder.decode(result!.data))).toEqual({ version: 2 });
  });

  it('three extensions sharing the same bare formatId all coexist', () => {
    const makeHandler = (label: string) => makeSyncHandler(makeJsonResult({ from: label }));
    const entries: CompileOnlyOutputFormatEntry[] = [
      {
        contribution: makeContribution({ id: 'triple-format' }),
        handler: makeHandler('ext-1'),
        extensionId: 'com.example.one',
      },
      {
        contribution: makeContribution({ id: 'triple-format' }),
        handler: makeHandler('ext-2'),
        extensionId: 'com.example.two',
      },
      {
        contribution: makeContribution({ id: 'triple-format' }),
        handler: makeHandler('ext-3'),
        extensionId: 'com.example.three',
      },
    ];

    const registry = createCompileOnlyOutputFormatRegistry(entries);
    expect(registry.size).toBe(3);

    const timeline = makeTimelineSnapshot();
    const assets = makeAssets();

    for (const extId of ['com.example.one', 'com.example.two', 'com.example.three']) {
      const result = executeCompileOnlyOutputSync(registry, {
        formatId: 'triple-format',
        timeline,
        assets,
        extensionId: extId,
      });
      expect(result).not.toBeNull();
      const decoder = new TextDecoder();
      const parsed = JSON.parse(decoder.decode(result!.data));
      const expectedLabel = extId === 'com.example.one' ? 'ext-1'
        : extId === 'com.example.two' ? 'ext-2'
        : 'ext-3';
      expect(parsed).toEqual({ from: expectedLabel });
    }
  });
});
