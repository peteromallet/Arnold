// @vitest-environment node
import { describe, expect, it } from 'vitest';
import { readFileSync, existsSync } from 'node:fs';
import { resolve } from 'node:path';

const repoRoot = resolve(import.meta.dirname, '..', '..', '..', '..');

const readDoc = (relativePath: string): string =>
  readFileSync(resolve(repoRoot, relativePath), 'utf8');

describe('M5-021: trust-and-security.md', () => {
  const docPath = resolve(repoRoot, 'docs/extensions/trust-and-security.md');
  const trustEnvelopePath = resolve(repoRoot, 'docs/video-editor/extensions-trust-envelope.md');

  it('exists and is readable', () => {
    expect(existsSync(docPath)).toBe(true);
    const content = readFileSync(docPath, 'utf8');
    expect(content.length).toBeGreaterThan(100);
  });

  it('states trusted/unsandboxed posture and non-enforced access disclosures without implying sandbox, broker, marketplace, install, or update enforcement', () => {
    const content = readFileSync(docPath, 'utf8');

    // Key posture statements must be present
    expect(content).toMatch(/trusted/);
    expect(content).toMatch(/unsandboxed/);
    expect(content).toMatch(/same-thread/i);
    expect(content).toMatch(/same-origin/i);

    // Must explicitly deny sandbox/marketplace/install/update enforcement
    expect(content).toMatch(/no sandbox/);
    expect(content).toMatch(/no.*permission.*enforcement/i);
    expect(content).toMatch(/no.*permission broker/i);
    expect(content).toMatch(/no.*marketplace/i);
    expect(content).toMatch(/no.*(?:remote|CDN|dynamic import|fetch)/i);
    expect(content).toMatch(/no.*update/i);
    expect(content).toMatch(/declarative access disclosure/i);
    expect(content).toMatch(/non-enforced/i);
    expect(content).toMatch(/future isolation or brokered-host-API epic/i);

    // Must cover key sections
    expect(content).toMatch(/execution model/i);
    expect(content).toMatch(/access disclosure model/i);
    expect(content).toMatch(/error containment/i);
    expect(content).toMatch(/diagnostic provenance/i);
    expect(content).toMatch(/recovery key/i);
    expect(content).toMatch(/inventory truthfulness/i);
  });

  it('keeps the trust envelope aligned with the declarative disclosure and future-enforcement posture', () => {
    expect(existsSync(trustEnvelopePath)).toBe(true);
    const content = readFileSync(trustEnvelopePath, 'utf8');

    expect(content).toMatch(/trusted-local/i);
    expect(content).toMatch(/full browser-renderer privileges/i);
    expect(content).toMatch(/non-enforced declarative access disclosure/i);
    expect(content).toMatch(/No runtime enforcement/i);
    expect(content).toMatch(/future isolation or brokered-host-API epic/i);
    expect(content).toMatch(/no brokered host API/i);
  });

  it('has at least 130 lines of substantive content', () => {
    const content = readFileSync(docPath, 'utf8');
    const lines = content.split('\n').filter((l) => l.trim().length > 0);
    expect(lines.length).toBeGreaterThanOrEqual(130);
  });
});

describe('M3 export readiness documentation contracts', () => {
  const readinessDocs = [
    'docs/extensions/composition-spine/m1b-composition-graph.md',
    'docs/extensions/composition-spine/m3b-live-binding-and-deterministic-capture.md',
    'docs/extensions/composition-spine/v8-architecture-baseline.md',
    'docs/extensions/phase4-readiness.md',
  ];

  const readAllReadinessDocs = (): string =>
    readinessDocs.map((docPath) => readDoc(docPath)).join('\n\n');

  it('keeps guard scans as planner inputs and planner blockers as the user-facing readiness vocabulary', () => {
    const content = readAllReadinessDocs();

    expect(content).toMatch(/The scan payload is planner input/i);
    expect(content).toMatch(/scanner diagnostics are planner\s+input/i);
    expect(content).toMatch(/buildExportReadinessPlan\(\).*planRender\(\)/s);
    expect(content).toMatch(/planner `RenderBlocker` records are the canonical\s+user-facing readiness vocabulary/i);
    expect(content).toMatch(/user-facing readiness blockers must be planner\s+blockers/i);
    expect(content).toMatch(/`export\/\*` diagnostic codes?.*diagnostic metadata/is);
  });

  it('does not reintroduce guard-as-authority readiness wording', () => {
    const content = readAllReadinessDocs();

    expect(content).not.toMatch(/scanExportConfig[^.\n]*(?:authoritative|authority)/i);
    expect(content).not.toMatch(/(?:authoritative|authority)[^.\n]*scanExportConfig/i);
    expect(content).not.toMatch(/export guard[^.\n]*(?:authoritative|authority)/i);
    expect(content).not.toMatch(/(?:authoritative|authority)[^.\n]*export guard/i);
    expect(content).not.toMatch(/authoritative export guard/i);
    expect(content).not.toMatch(/Graph-first export authority/i);
    expect(content).not.toMatch(/exportGuard[^.\n]*authority/i);
  });

  it('keeps broader trust and release gate prohibitions in the readiness docs', () => {
    const baselineContent = readDoc(
      'docs/extensions/composition-spine/v8-architecture-baseline.md',
    );
    const phase4Content = readDoc('docs/extensions/phase4-readiness.md');

    expect(baselineContent).toMatch(/No sandbox, marketplace/i);
    expect(baselineContent).toMatch(/trusted, unsandboxed code/i);
    expect(baselineContent).toMatch(/not runtime enforcement, sandbox isolation, code signing, or a permission broker/i);
    expect(baselineContent).toMatch(/No marketplace, remote install, or signing claims/i);
    expect(phase4Content).toMatch(/`npm run test:readiness` command validates/i);
    expect(phase4Content).toMatch(/A missing or renamed anchor causes the\s+command to fail/i);
  });
});

describe('M5-022: foundation-contracts.md', () => {
  const docPath = resolve(repoRoot, 'docs/extensions/foundation-contracts.md');

  it('exists and is readable', () => {
    expect(existsSync(docPath)).toBe(true);
    const content = readFileSync(docPath, 'utf8');
    expect(content.length).toBeGreaterThan(100);
  });

  it('covers canonical foundation contract paths', () => {
    const content = readFileSync(docPath, 'utf8');

    // Must cover each required contract section
    expect(content).toMatch(/extension definition/i);
    expect(content).toMatch(/lifecycle state machine/i);
    expect(content).toMatch(/contribution surfaces/i);
    expect(content).toMatch(/runtime normalization/i);
    expect(content).toMatch(/diagnostic contract/i);
    expect(content).toMatch(/error boundary/i);
    expect(content).toMatch(/recovery key/i);
    expect(content).toMatch(/package inventory/i);
    expect(content).toMatch(/settings contract/i);
    expect(content).toMatch(/export guard/i);
    expect(content).toMatch(/provider compatibility/i);
  });

  it('includes code path index covering at least 16 files', () => {
    const content = readFileSync(docPath, 'utf8');

    // Section 13 code path index must exist
    expect(content).toMatch(/code path index/i);

    // Count file references in the index
    const indexStart = content.indexOf('## 13. Code Path Index');
    expect(indexStart).toBeGreaterThan(-1);
    const indexSection = content.substring(indexStart);

    // Count unique file paths referenced (backtick-wrapped paths containing .ts/.tsx/.json/.md)
    const fileRefs = indexSection.match(/`[^`]+\.(?:ts|tsx|json|md)[^`]*`/g) || [];
    const uniqueFiles = new Set(fileRefs);
    expect(uniqueFiles.size).toBeGreaterThanOrEqual(16);
  });

  it('has at least 290 lines of substantive content', () => {
    const content = readFileSync(docPath, 'utf8');
    const lines = content.split('\n').filter((l) => l.trim().length > 0);
    expect(lines.length).toBeGreaterThanOrEqual(290);
  });
});
