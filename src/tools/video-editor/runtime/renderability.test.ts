import { readdirSync, readFileSync, statSync } from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';
import {
  DETERMINISM_STATUSES,
  RENDER_BLOCKER_REASONS,
  RENDER_ROUTES,
} from '@reigh/editor-sdk';
import type {
  ArtifactBoundary,
  BakeContract,
  ContributionRenderability,
  DeterminismStatus,
  RenderArtifact,
  RenderBlocker,
  RenderCapability,
  RenderMaterial,
  RenderRoute,
} from '@reigh/editor-sdk';
import type {
  CapabilityFinding,
  RenderArtifactSidecarDescriptor,
  RenderMaterialRef,
} from '@/tools/video-editor/runtime/renderability.ts';
import {
  COMPILE_ONLY_ARTIFACT_ROUTE,
  assertFinalArtifactHasManifest,
  createCompileOnlyArtifact,
  createRenderArtifactManifest,
  createRenderArtifactManifestSidecar,
  normalizeRenderArtifactSidecars,
  serializeRenderArtifactManifest,
} from '@/tools/video-editor/runtime/renderability.ts';

function materialRef(id: string, uri: string): RenderMaterialRef {
  return {
    id,
    mediaKind: 'image',
    locator: {
      kind: 'asset-registry',
      uri,
      contentSha256: `sha256:${id}`,
    },
    producerExtensionId: 'com.example.materials',
    producerVersion: '1.0.0',
    determinism: 'deterministic',
    replacementPolicy: 'preserve-live-ref',
  };
}

function finding(id: string): CapabilityFinding {
  return {
    id,
    severity: 'warning',
    route: 'sidecar-export',
    message: `Finding ${id}`,
  };
}

function sourceFilesUnder(relativeRoot: string): string[] {
  const root = path.join(process.cwd(), relativeRoot);
  const files: string[] = [];
  const visit = (entry: string): void => {
    const stat = statSync(entry);
    if (stat.isDirectory()) {
      for (const child of readdirSync(entry)) {
        visit(path.join(entry, child));
      }
      return;
    }
    if (
      /\.(ts|tsx)$/.test(entry)
      && !entry.endsWith('.test.ts')
      && !entry.endsWith('.test.tsx')
      && !entry.endsWith('.d.ts')
    ) {
      files.push(entry);
    }
  };
  visit(root);
  return files;
}

function workspaceRelative(file: string): string {
  return path.relative(process.cwd(), file);
}

describe('shared renderability contracts', () => {
  it('pins the locked route vocabulary exported through the public SDK', () => {
    expect(RENDER_ROUTES).toEqual([
      'preview',
      'browser-export',
      'worker-export',
      'sidecar-export',
    ]);

    const route: RenderRoute = 'worker-export';
    expect(RENDER_ROUTES).toContain(route);
    expect(Object.isFrozen(RENDER_ROUTES)).toBe(true);
  });

  it('pins the locked determinism vocabulary exported through the public SDK', () => {
    expect(DETERMINISM_STATUSES).toEqual([
      'deterministic',
      'preview-only',
      'live-unbaked',
      'process-dependent',
      'unknown',
    ]);

    const determinism: DeterminismStatus = 'live-unbaked';
    expect(DETERMINISM_STATUSES).toContain(determinism);
    expect(Object.isFrozen(DETERMINISM_STATUSES)).toBe(true);
  });

  it('pins planner-compatible blocker reasons', () => {
    expect(RENDER_BLOCKER_REASONS).toEqual([
      'missing-contribution',
      'route-unsupported',
      'preview-only',
      'live-unbaked',
      'process-dependent',
      'missing-material',
      'materialization-failed',
      'materialization-error',
      'inactive-extension',
      'unknown',
    ]);
    expect(Object.isFrozen(RENDER_BLOCKER_REASONS)).toBe(true);
  });

  it('models capabilities, findings, and blockers with shared route vocabulary', () => {
    const capability: RenderCapability = {
      route: 'browser-export',
      status: 'blocked',
      determinism: 'preview-only',
      blockerReason: 'preview-only',
      message: 'Effect can preview but cannot be exported in-browser.',
    };

    const blocker: RenderBlocker = {
      id: 'blocker.effect.preview-only',
      severity: 'error',
      route: 'browser-export',
      reason: 'preview-only',
      message: 'Effect must be baked before browser export.',
      extensionId: 'com.example.effects',
      contributionId: 'effect.glow',
      clipId: 'clip-1',
    };

    const contractFinding: CapabilityFinding = {
      id: 'finding.effect.preview-only',
      severity: 'warning',
      route: 'preview',
      reason: 'preview-only',
      message: 'Preview route is available, export route is blocked.',
      detail: { effectId: 'glow' },
    };

    const renderability: ContributionRenderability = {
      capabilities: [capability],
      defaultRoute: 'preview',
      determinism: 'preview-only',
      blockers: [blocker],
    };

    expect(renderability).toMatchObject({
      defaultRoute: 'preview',
      determinism: 'preview-only',
      capabilities: [{ route: 'browser-export', status: 'blocked' }],
      blockers: [{ severity: 'error', route: 'browser-export', reason: 'preview-only' }],
    });
    expect(contractFinding.detail).toEqual({ effectId: 'glow' });
  });

  it('separates render materials from final artifacts and bake contracts', () => {
    const contractMaterialRef: RenderMaterialRef = {
      id: 'material.image.1',
      mediaKind: 'image',
      locator: {
        kind: 'asset-registry',
        uri: 'asset://source-image',
        mimeType: 'image/png',
        contentSha256: 'abc123',
      },
      producerExtensionId: 'com.example.materials',
      producerVersion: '1.0.0',
      determinism: 'deterministic',
      replacementPolicy: 'replace-live-ref',
    };

    const material: RenderMaterial = {
      ...contractMaterialRef,
      durationSeconds: 2,
      frameRange: [0, 48],
      inputHash: 'input-hash-1',
      metadata: { pass: 'main' },
    };

    const boundary: ArtifactBoundary = {
      source: 'worker',
      target: 'artifact-store',
      route: 'worker-export',
      failureBehavior: 'block-export',
    };

    const artifact: RenderArtifact = {
      id: 'artifact.video.1',
      route: 'worker-export',
      locator: {
        kind: 'artifact-store',
        uri: 'artifact://video-1.mp4',
        mimeType: 'video/mp4',
      },
      mediaKind: 'video',
      producerExtensionId: 'com.example.materials',
      producerVersion: '1.0.0',
      consumedMaterialRefs: [contractMaterialRef],
      determinism: 'deterministic',
      boundary,
      findings: [],
    };

    const bakeContract: BakeContract = {
      id: 'bake.effect.glow',
      route: 'worker-export',
      inputMaterialRefs: [contractMaterialRef],
      outputArtifactKind: 'video',
      determinism: 'deterministic',
      boundary,
      replacementPolicy: 'replace-live-ref',
      blockers: [],
    };

    expect(material.locator.kind).toBe('asset-registry');
    expect(artifact.locator.kind).toBe('artifact-store');
    expect(artifact.consumedMaterialRefs).toEqual([contractMaterialRef]);
    expect(bakeContract).toMatchObject({
      route: 'worker-export',
      outputArtifactKind: 'video',
      replacementPolicy: 'replace-live-ref',
    });
  });
});

describe('render artifact manifest helpers', () => {
  it('serializes manifests stably across object key, material, sidecar, and diagnostic order', () => {
    const sidecarA: RenderArtifactSidecarDescriptor = {
      filename: 'labels.json',
      mimeType: 'application/json',
      kind: 'label',
      data: new Uint8Array([2, 1]),
      provenance: { z: true, a: 'first' },
    };
    const sidecarB: RenderArtifactSidecarDescriptor = {
      id: 'sidecar.cue.timeline',
      filename: 'timeline.cue',
      mimeType: 'text/plain',
      kind: 'cue',
      data: new Uint8Array([1, 2]),
    };

    const base = {
      artifactId: 'artifact.dataset',
      route: 'sidecar-export' as const,
      determinism: 'process-dependent' as const,
      producerExtensionId: 'com.example.dataset',
      producerVersion: '2.0.0',
      outputFormatId: 'dataset-show-control',
      inputHashes: {
        'asset://z': 'sha256:z',
        'asset://a': 'sha256:a',
      },
      provenance: {
        z: 1,
        a: 2,
      },
      metadata: {
        sampleCount: 2,
      },
      createdAt: '2026-06-20T00:00:00.000Z',
    };

    const first = createRenderArtifactManifest({
      ...base,
      consumedMaterialRefs: [materialRef('mat-z', 'asset://z'), materialRef('mat-a', 'asset://a')],
      sidecars: [sidecarA, sidecarB],
      diagnostics: [finding('diag-z'), finding('diag-a')],
    });
    const second = createRenderArtifactManifest({
      ...base,
      consumedMaterialRefs: [materialRef('mat-a', 'asset://a'), materialRef('mat-z', 'asset://z')],
      sidecars: [sidecarB, sidecarA],
      diagnostics: [finding('diag-a'), finding('diag-z')],
    });

    expect(serializeRenderArtifactManifest(first)).toBe(serializeRenderArtifactManifest(second));
    expect(first.consumedMaterialRefs.map((ref) => ref.id)).toEqual(['mat-a', 'mat-z']);
    expect(first.sidecars.map((sidecar) => sidecar.id)).toEqual([
      'sidecar.cue.timeline',
      'sidecar.label.labels.json',
    ]);
    expect(first.diagnostics?.map((diag) => diag.id)).toEqual(['diag-a', 'diag-z']);
  });

  it('creates a manifest sidecar whose bytes match stable manifest serialization', () => {
    const manifest = createRenderArtifactManifest({
      artifactId: 'artifact.primary',
      route: 'browser-export',
      determinism: 'deterministic',
      producerExtensionId: 'com.example.export',
      producerVersion: '1.4.0',
      outputFormatId: 'metadata-json',
      consumedMaterialRefs: [materialRef('mat-main', 'asset://main')],
      sidecars: [{
        filename: 'provenance.json',
        mimeType: 'application/json',
        kind: 'provenance',
      }],
    });

    const sidecar = createRenderArtifactManifestSidecar(manifest, 'manifest.json');
    const serialized = serializeRenderArtifactManifest(manifest);

    expect(sidecar.kind).toBe('manifest');
    expect(sidecar.filename).toBe('manifest.json');
    expect(sidecar.mimeType).toBe('application/json');
    expect(sidecar.byteSize).toBe(sidecar.data?.byteLength);
    expect(new TextDecoder().decode(sidecar.data)).toBe(serialized);
  });

  it('fails final artifact assertions when a producer omits or mismatches a manifest', () => {
    const baseArtifact: RenderArtifact = {
      id: 'artifact.without-manifest',
      route: 'browser-export',
      locator: {
        kind: 'inline',
        uri: 'artifact.json',
        mimeType: 'application/json',
      },
      mediaKind: 'json',
      consumedMaterialRefs: [],
      determinism: 'deterministic',
      boundary: {
        source: 'browser',
        target: 'export-output',
        route: 'browser-export',
        failureBehavior: 'emit-diagnostic',
      },
    };

    expect(() => assertFinalArtifactHasManifest(baseArtifact, 'regression-test')).toThrow(
      /missing a render artifact manifest/,
    );

    const mismatched = {
      ...baseArtifact,
      manifest: createRenderArtifactManifest({
        artifactId: 'different-artifact',
        route: 'browser-export',
        determinism: 'deterministic',
      }),
    };

    expect(() => assertFinalArtifactHasManifest(mismatched, 'regression-test')).toThrow(
      /has manifest artifactId/,
    );
  });

  it('preserves route metadata, determinism status, producer fields, and consumed materials', () => {
    const manifest = createRenderArtifactManifest({
      artifactId: 'artifact.rendered-pass',
      route: 'sidecar-export',
      determinism: 'process-dependent',
      producerExtensionId: 'com.example.blender',
      producerVersion: '3.6.1',
      processId: 'blender-mcp',
      processVersion: { semver: '4.0.0', declaredBy: 'com.example.blender' },
      operationId: 'render.preview',
      renderGroupId: 'group-hero',
      passName: 'beauty',
      mediaKind: 'video',
      locator: {
        kind: 'artifact-store',
        uri: 'artifact://artifact.rendered-pass',
        mimeType: 'video/mp4',
      },
      consumedMaterialRefs: [
        materialRef('mat-background', 'asset://background'),
        materialRef('mat-foreground', 'asset://foreground'),
      ],
    });

    expect(manifest.route).toBe('sidecar-export');
    expect(manifest.determinism).toBe('process-dependent');
    expect(manifest.producerExtensionId).toBe('com.example.blender');
    expect(manifest.producerVersion).toBe('3.6.1');
    expect(manifest.processId).toBe('blender-mcp');
    expect(manifest.processVersion).toEqual({ semver: '4.0.0', declaredBy: 'com.example.blender' });
    expect(manifest.operationId).toBe('render.preview');
    expect(manifest.renderGroupId).toBe('group-hero');
    expect(manifest.passName).toBe('beauty');
    expect(manifest.mediaKind).toBe('video');
    expect(manifest.consumedMaterialRefs.map((ref) => ref.id)).toEqual([
      'mat-background',
      'mat-foreground',
    ]);
  });

  it('normalizes sidecar descriptors with stable IDs, byte sizes, and frozen output', () => {
    const normalized = normalizeRenderArtifactSidecars([
      {
        filename: 'report.log',
        mimeType: 'text/plain',
        kind: 'log',
        data: new Uint8Array([1, 2, 3]),
      },
    ]);

    expect(normalized).toHaveLength(1);
    expect(normalized[0].id).toBe('sidecar.log.report.log');
    expect(normalized[0].byteSize).toBe(3);
    expect(Object.isFrozen(normalized)).toBe(true);
    expect(Object.isFrozen(normalized[0])).toBe(true);
  });

  it('keeps compile-only artifacts compatible while adding a deterministic manifest', () => {
    const artifact = createCompileOnlyArtifact({
      artifactId: 'compile-only.metadata-json',
      data: new TextEncoder().encode('{"ok":true}'),
      mimeType: 'application/json',
      filename: 'metadata.json',
      outputFormatId: 'metadata-json',
      producerExtensionId: 'com.example.metadata',
      producerVersion: '1.2.3',
      consumedAssetKeys: ['asset-b', 'asset-a'],
    });

    expect(artifact.route).toBe(COMPILE_ONLY_ARTIFACT_ROUTE);
    expect(artifact.determinism).toBe('deterministic');
    expect(artifact.locator.uri).toBe('metadata.json');
    expect(artifact.consumedMaterialRefs.map((ref) => ref.id)).toEqual([
      'material.asset.asset-b',
      'material.asset.asset-a',
    ]);
    expect(artifact.manifest).toMatchObject({
      artifactId: 'compile-only.metadata-json',
      route: COMPILE_ONLY_ARTIFACT_ROUTE,
      determinism: 'deterministic',
      producerExtensionId: 'com.example.metadata',
      producerVersion: '1.2.3',
      outputFormatId: 'metadata-json',
      mediaKind: 'json',
    });
    expect(artifact.manifest?.consumedMaterialRefs.map((ref) => ref.id)).toEqual([
      'material.asset.asset-a',
      'material.asset.asset-b',
    ]);
    expect(artifact.sidecars).toEqual([]);
    expect(artifact.manifest?.sidecars).toEqual([]);
  });

  it('sweeps runtime and lib artifact producers for manifest-helper coverage', () => {
    const files = [
      ...sourceFilesUnder('src/tools/video-editor/runtime'),
      ...sourceFilesUnder('src/tools/video-editor/lib'),
    ].map((file) => ({
      file,
      relative: workspaceRelative(file),
      source: readFileSync(file, 'utf8'),
    }));

    const producerFiles = files
      .filter(({ source }) => (
        /\bRenderArtifact\b/.test(source)
        || /\bCompileOnlyOutputExecutionResult\b/.test(source)
        || /\bcreateCompileOnlyArtifact\s*\(/.test(source)
        || /\bcreateRenderArtifactManifest\s*\(/.test(source)
      ))
      .map(({ relative }) => relative)
      .sort();

    expect(producerFiles).toEqual(expect.arrayContaining([
      'src/tools/video-editor/runtime/outputFormatRegistry.ts',
      'src/tools/video-editor/runtime/renderability.ts',
    ]));

    const offenders = files.flatMap(({ relative, source }) => {
      if (relative === 'src/tools/video-editor/runtime/renderability.ts') return [];

      const directlyBuildsRenderArtifact = (
        /:\s*RenderArtifact\s*=\s*\{/.test(source)
        || /\bas\s+RenderArtifact\b/.test(source)
        || /\bsatisfies\s+RenderArtifact\b/.test(source)
      );
      const returnsFinalArtifact = (
        /\bCompileOnlyOutputExecutionResult\b/.test(source)
        || /readonly\s+artifact:\s*RenderArtifact\b/.test(source)
      );
      const usesManifestPath = (
        /\bcreateCompileOnlyArtifact\s*\(/.test(source)
        || /\bcreateRenderArtifactManifest\s*\(/.test(source)
        || /\bassertFinalArtifactHasManifest\s*\(/.test(source)
      );
      const assertsBeforeReturn = !returnsFinalArtifact || /\bassertFinalArtifactHasManifest\s*\(/.test(source);

      if ((directlyBuildsRenderArtifact && !usesManifestPath) || !assertsBeforeReturn) {
        return [relative];
      }
      return [];
    });

    expect(offenders).toEqual([]);
  });
});
