import { describe, expect, it } from 'vitest';
import {
  DETERMINISM_STATUSES,
  RENDER_BLOCKER_REASONS,
  RENDER_ROUTES,
} from '@reigh/editor-sdk';
import type {
  ArtifactBoundary,
  BakeContract,
  CapabilityFinding,
  ContributionRenderability,
  DeterminismStatus,
  RenderArtifact,
  RenderBlocker,
  RenderCapability,
  RenderMaterial,
  RenderMaterialRef,
  RenderRoute,
} from '@reigh/editor-sdk';

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

    const finding: CapabilityFinding = {
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
    expect(finding.detail).toEqual({ effectId: 'glow' });
  });

  it('separates render materials from final artifacts and bake contracts', () => {
    const materialRef: RenderMaterialRef = {
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
      ...materialRef,
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
      consumedMaterialRefs: [materialRef],
      determinism: 'deterministic',
      boundary,
      findings: [],
    };

    const bakeContract: BakeContract = {
      id: 'bake.effect.glow',
      route: 'worker-export',
      inputMaterialRefs: [materialRef],
      outputArtifactKind: 'video',
      determinism: 'deterministic',
      boundary,
      replacementPolicy: 'replace-live-ref',
      blockers: [],
    };

    expect(material.locator.kind).toBe('asset-registry');
    expect(artifact.locator.kind).toBe('artifact-store');
    expect(artifact.consumedMaterialRefs).toEqual([materialRef]);
    expect(bakeContract).toMatchObject({
      route: 'worker-export',
      outputArtifactKind: 'video',
      replacementPolicy: 'replace-live-ref',
    });
  });
});
