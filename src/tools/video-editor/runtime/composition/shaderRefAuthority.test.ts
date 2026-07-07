import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

const PROJECT_ROOT = process.cwd();

const MIGRATED_READINESS_FILES = [
  'src/tools/video-editor/runtime/renderPlanner.ts',
  'src/tools/video-editor/runtime/exportGuard.ts',
] as const;

const EXPLICIT_OUT_OF_SCOPE_ALLOWLIST = [
  {
    path: 'src/tools/video-editor/lib/timeline-reader.ts',
    reason: 'projector input extraction into snapshot.shaders',
  },
  {
    path: 'src/tools/video-editor/runtime/composition/graphProjector.ts',
    reason: 'projector consumes snapshot.shaders to build graph edges',
  },
  {
    path: 'src/tools/video-editor/lib/timeline-domain.ts',
    reason: 'domain helpers preserve legacy storage and UI mutation/display paths',
  },
  {
    path: 'src/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx',
    reason: 'UI display of clip-local shader metadata',
  },
  {
    path: 'src/tools/video-editor/components/ShaderInspector/ShaderInspector.tsx',
    reason: 'UI mutation of postprocess shader metadata',
  },
] as const;

const FORBIDDEN_READS = [
  {
    label: 'clip.app?.shader',
    pattern: /\bclip\.app\??\.shader\b/,
  },
  {
    label: 'config.app?.shaderPostprocess',
    pattern: /\bconfig\.app\??\.shaderPostprocess\b/,
  },
  {
    label: 'TimelineShaderMetadata',
    pattern: /\bTimelineShaderMetadata\b/,
  },
  {
    label: 'legacyTimelineShaderMetadata',
    pattern: /\blegacyTimelineShaderMetadata\b/,
  },
] as const;

function readProjectFile(projectPath: string): string {
  return readFileSync(path.join(PROJECT_ROOT, projectPath), 'utf8');
}

describe('shader/ref authority guard', () => {
  it('keeps migrated planner/export readiness code off raw legacy shader storage', () => {
    const violations: string[] = [];

    for (const projectPath of MIGRATED_READINESS_FILES) {
      const source = readProjectFile(projectPath);
      source.split(/\r?\n/u).forEach((line, index) => {
        for (const forbidden of FORBIDDEN_READS) {
          if (forbidden.pattern.test(line)) {
            violations.push(`${projectPath}:${index + 1} ${forbidden.label} -> ${line.trim()}`);
          }
        }
      });
    }

    expect(violations).toEqual([]);
  });

  it('documents the projector/UI/domain legacy shader read allowlist', () => {
    const missing = EXPLICIT_OUT_OF_SCOPE_ALLOWLIST
      .filter((entry) => !existsSync(path.join(PROJECT_ROOT, entry.path)))
      .map((entry) => `${entry.path} (${entry.reason})`);

    expect(missing).toEqual([]);
    expect(EXPLICIT_OUT_OF_SCOPE_ALLOWLIST.map((entry) => entry.reason)).toEqual([
      'projector input extraction into snapshot.shaders',
      'projector consumes snapshot.shaders to build graph edges',
      'domain helpers preserve legacy storage and UI mutation/display paths',
      'UI display of clip-local shader metadata',
      'UI mutation of postprocess shader metadata',
    ]);
  });
});
