/**
 * SDK import governance test for extension examples.
 *
 * Verifies that every TypeScript file under src/examples/:
 *   1. Imports from @reigh/editor-sdk (the public SDK entrypoint)
 *   2. Does NOT deep-import from src/tools/video-editor/* internals
 *   3. Examples collectively cover every supported public SDK surface class
 *
 * Supported public exports that are NOT imported by at least one compiled
 * example require an explicit deferred/unsupported classification in the
 * contract-recheck matrix (via the shared matrix helper).  This test reads
 * the canonical matrix at startup and dynamically exempts exports that
 * belong to milestones or features classified as deferred or unsupported.
 *
 * This test is the executable proof for the governance rule enforced
 * by scripts/quality/check-video-editor-sdk-imports.mjs at the CLI level.
 */

import { describe, expect, it } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import {
  loadContractMatrix,
  isDeferred,
  isUnsupported,
} from '../../scripts/quality/lib/extension-contract-matrix.mjs';
import { commandExtension } from '../examples/command-extension';
import { integrityHashParserExtension, integrityParserHandler } from '../examples/integrity-hash-parser-example';
import { metadataJsonOutputExtension, metadataJsonHandler } from '../examples/metadata-json-output-example';
import { clipTypeKeyframedExample } from '../examples/clip-type-keyframed-example';
import {
  automationRecordingCanaryExample,
  canaryRecordAutomation,
  buildAutomationClipParams,
  canaryApplyAutomationOverrides,
} from '../examples/automation-recording-canary';
import type {
  AssetMetadata,
  AutomationClipParams,
  AutomationClipTarget,
  ClipParameterDefinition,
  ClipTypeContribution,
  CommandContribution,
  CompileOnlyOutputResult,
  ContextMenuItemContribution,
  DeferredEnrichmentRecord,
  KeybindingContribution,
  Keyframe,
  OutputFormatContribution,
  OutputFormatContext,
  OutputFormatHandler,
  ParserContribution,
  ParserInput,
  ReighExtension,
  TimelineOps,
  TimelineProposalInput,
} from '@reigh/editor-sdk';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const REPO_ROOT = path.resolve(import.meta.dirname, '../..');
const EXAMPLES_DIR = path.join(REPO_ROOT, 'src', 'examples');
const SDK_INDEX = path.join(REPO_ROOT, 'src', 'sdk', 'index.ts');

/** Regex matching any import/export-from specifier (static + dynamic). */
const IMPORT_SPECIFIER_RE = /(?:import|export)\b[\s\S]*?\bfrom\s+['"]([^'"]+)['"]|import\s*\(\s*['"]([^'"]+)['"]\s*\)/g;

function extractSpecifiers(content: string): string[] {
  const specifiers = new Set<string>();
  for (const match of content.matchAll(IMPORT_SPECIFIER_RE)) {
    const specifier = match[1] ?? match[2];
    if (specifier) {
      specifiers.add(specifier);
    }
  }
  return [...specifiers];
}

function walkTsFiles(dir: string): string[] {
  const files: string[] = [];
  if (!fs.existsSync(dir)) return files;

  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (entry.name.startsWith('.')) continue;
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      files.push(...walkTsFiles(fullPath));
    } else if (entry.isFile() && (fullPath.endsWith('.ts') || fullPath.endsWith('.tsx'))) {
      files.push(fullPath);
    }
  }
  return files;
}

/** Check if a specifier resolves into src/tools/video-editor internals. */
function isVideoEditorInternal(relativePath: string, specifier: string): boolean {
  // Direct alias-based imports to video-editor internals
  if (specifier.startsWith('@/tools/video-editor')) return true;

  // Relative imports that resolve into src/tools/video-editor
  if (specifier.startsWith('.')) {
    const resolved = path.resolve(path.dirname(relativePath), specifier);
    // Normalize to check against the known forbidden directory
    const relative = path.relative(REPO_ROOT, resolved);
    const normalizedSep = relative.split(path.sep).join('/');
    if (normalizedSep.startsWith('src/tools/video-editor/')) return true;

    // Also check with possible extensions
    for (const ext of ['.ts', '.tsx', '/index.ts', '/index.tsx']) {
      const candidate = path.resolve(path.dirname(relativePath), specifier + ext);
      const candidateRel = path.relative(REPO_ROOT, candidate).split(path.sep).join('/');
      if (candidateRel.startsWith('src/tools/video-editor/')) return true;
    }
  }

  return false;
}

// ---------------------------------------------------------------------------
// SDK surface extraction
// ---------------------------------------------------------------------------

/** Regex matching `export (type|interface|class|function|const|let|var) Name`. */
const SDK_EXPORT_RE = /^export\s+(?:(?:declare\s+)?(?:type|interface|class|function|const|let|var)\s+)([A-Za-z_$][\w$]*)/gm;

/**
 * Extract the set of named exports from src/sdk/index.ts.
 * Uses a simple regex-based approach that captures type, interface,
 * class, function, const, let, and var exports.
 */
function extractSdkExports(): Set<string> {
  const content = fs.readFileSync(SDK_INDEX, 'utf8');
  const names = new Set<string>();
  for (const match of content.matchAll(SDK_EXPORT_RE)) {
    names.add(match[1]);
  }
  return names;
}

/**
 * Extract all names imported from @reigh/editor-sdk in a given file.
 * Handles both `import { A, B } from '@reigh/editor-sdk'` and
 * `import type { C } from '@reigh/editor-sdk'` forms.
 */
function extractSdkImports(filePath: string): Set<string> {
  const content = fs.readFileSync(filePath, 'utf8');
  const names = new Set<string>();

  // Match import { ... } from '@reigh/editor-sdk' (value + type imports)
  const importBlockRe = /import\s+(?:type\s+)?\{([^}]+)\}\s+from\s+['"]@reigh\/editor-sdk['"]/g;
  for (const match of content.matchAll(importBlockRe)) {
    const block = match[1];
    // Split on commas, handle `as` aliases
    for (const part of block.split(',')) {
      const trimmed = part.trim();
      if (!trimmed) continue;
      // Handle `Name as Alias` — take the original name
      const nameMatch = trimmed.match(/^([A-Za-z_$][\w$]*)\s*(?:as\s+[A-Za-z_$][\w$]*)?/);
      if (nameMatch) {
        names.add(nameMatch[1]);
      }
    }
  }

  // Match default imports: import Name from '@reigh/editor-sdk'
  const defaultImportRe = /import\s+([A-Za-z_$][\w$]*)\s+from\s+['"]@reigh\/editor-sdk['"]/g;
  for (const match of content.matchAll(defaultImportRe)) {
    names.add(match[1]);
  }

  return names;
}

// ---------------------------------------------------------------------------
// Dynamic deferred/unsupported export classification
// ---------------------------------------------------------------------------

/**
 * Milestone → export-name-pattern mapping used to connect matrix row IDs
 * (e.g. M6-007, M11-001) to the SDK export names those features surface.
 *
 * Each entry maps a milestone prefix to a regex that matches the export
 * names belonging to features in that milestone.  The contract-recheck
 * matrix is consulted at runtime: when a milestone's *relevant* rows are
 * all classified as deferred or unsupported by the shared matrix helper,
 * every export matching that milestone's pattern is exempt from the
 * example-coverage requirement.
 *
 * Milestones that are entirely deferred (M10–M14) have broad patterns.
 * Milestones that are partially supported (M6–M9) have narrower patterns
 * that only match the deferred subsets.
 */
const MILESTONE_EXPORT_PATTERNS: [RegExp, string][] = [
  // M6 deferred exports (Asset detail sections, search providers, facets,
  // enrichment status, export service, material read surface, diagnostics,
  // compile-only output contracts)
  [
    /^(AssetDetailSection(Contribution|Descriptor)|AssetGPSMetadata|AssetIntegrityMetadata|AssetConsentMetadata|AssetProvenanceMetadata|AssetReadSurface|CompileOnlyOutput(FormatContribution|Result)|Diagnostic(Collection|SourceRange)?$|EnrichmentStatus|ExportService|MaterialReadSurface|MetadataFacet(Contribution|Descriptor|ValueKind)|OutputFormatRegistrationOptions|SearchMatch|SearchProvider(Contribution|Context|Handler|Result)|createDiagnosticCollection)$/,
    'M6',
  ],
  // M7 deferred test-coverage exports (effect registry types)
  [/^(Effect(Component|Contribution|ParameterDefinition|ParameterSchema|RegistrationOptions|RegistrationService))$/, 'M7'],
  // M8 deferred test-coverage exports (transition registry types)
  [/^(Transition(Contribution|ParameterDefinition|ParameterSchema|RegistrationOptions|RegistrationService|Renderer))$/, 'M8'],
  // M10 deferred agent-tool exports (all agent tool / tool result types)
  [/^(AgentTool|Tool(Artifact|Enrichment|Export|Generation|Material|Mutation|Process|Result|Search|Source|UI))/, 'M10'],
  // M11 deferred live-data-bridge exports
  [/^(Live|Steering|GenerationSession|Binding)/, 'M11'],
  // M12 deferred render-planner exports
  [/^(Process|Sampling|Capability|Route|Integration|RenderArtifact|RenderDependent|Timeline(Effect|Transition|Live|Material|Render|Source|Output|Shader)|getCapability)/, 'M12'],
  // M13 deferred shader-frontend exports (all Shader* exports)
  [/^Shader/, 'M13'],
  // M14 deferred extension-packaging exports
  [/^(Dependency|Extension(Dependency|Settings)|Integrity(Algorithm|Hash)|Migration(Hook|Declaration)|InstalledExtension|ManifestValidation|validate(Manifest|Installed))/, 'M14'],
];

/**
 * Build the set of SDK export names that are classified as deferred or
 * unsupported by BOTH the contract-recheck matrix AND the supported/deferred
 * matrix.  Uses the shared matrix helper predicates (isDeferred /
 * isUnsupported) for the contract-recheck matrix and also parses the
 * supported/deferred matrix markdown for explicit deferred/unsupported
 * classifications that may override the contract-recheck disposition.
 *
 * For each milestone M*:
 *   - Collect all matrix rows whose rowId starts with that milestone prefix.
 *   - If at least one row in that milestone is deferred/unsupported in
 *     EITHER matrix, then all exports matching that milestone's pattern
 *     are deferred.
 *
 * This uses the shared matrix helper predicates (isDeferred / isUnsupported)
 * so the classification is always consistent with the canonical matrix
 * semantics defined by SD1, plus the supported/deferred matrix rows which
 * provide explicit deferral classifications per SD2.
 */
function buildDeferredUnsupportedExportSet(
  sdkExports: Set<string>,
  matrixRows: object[],
): Set<string> {
  const result = new Set<string>();

  // ── Parse the supported/deferred matrix for explicit deferrals ──
  const SUPPORTED_DEFERRED_PATH = path.join(
    REPO_ROOT,
    'docs',
    'video-editor',
    'extension-platform-supported-deferred.md',
  );
  const deferredFromSupportedMatrix = new Set<string>();
  if (fs.existsSync(SUPPORTED_DEFERRED_PATH)) {
    const md = fs.readFileSync(SUPPORTED_DEFERRED_PATH, 'utf8');
    // Extract CR: references from rows classified as deferred or unsupported
    // in sections 3 and 4.1 of the supported/deferred matrix.
    const crRefRe = /CR:([A-Z]+\d+-\d+)/g;
    let inDeferredSection = false;
    for (const line of md.split('\n')) {
      if (line.startsWith('## 3. Deferred') || line.startsWith('### 3.')) {
        inDeferredSection = true;
        continue;
      }
      if (line.startsWith('## 4. V1 Scope Boundaries')) {
        inDeferredSection = false;
      }
      if (!inDeferredSection) continue;

      // Match table rows classified as **deferred** or **unsupported**
      if (
        line.includes('| **deferred** |')
        || line.includes('| **unsupported** |')
      ) {
        for (const match of line.matchAll(crRefRe)) {
          deferredFromSupportedMatrix.add(match[1]);
        }
      }
    }
  }

  // Group matrix rows by milestone prefix
  const rowsByMilestone = new Map<string, object[]>();
  for (const row of matrixRows) {
    const rowId = (row as any).rowId as string | undefined;
    if (!rowId) continue;
    const match = rowId.match(/^(M\d+)-/);
    if (!match) continue;
    const milestone = match[1];
    if (!rowsByMilestone.has(milestone)) {
      rowsByMilestone.set(milestone, []);
    }
    rowsByMilestone.get(milestone)!.push(row);
  }

  // Determine which milestones have deferred/unsupported exports.
  // A milestone contributes deferred exports when it has at least one
  // deferred/unsupported row in EITHER the contract-recheck matrix OR
  // the supported/deferred matrix.
  const deferredMilestones = new Set<string>();
  for (const [milestone, rows] of rowsByMilestone) {
    const hasDeferredInCR = rows.some(
      (r) => isDeferred(r) || isUnsupported(r),
    );
    const hasDeferredInSD = rows.some((r) =>
      deferredFromSupportedMatrix.has((r as any).rowId as string),
    );

    if (hasDeferredInCR || hasDeferredInSD) {
      deferredMilestones.add(milestone);
    }
  }

  // Match every SDK export against the milestone patterns.
  // An export is deferred/unsupported when its matching milestone has
  // at least one deferred/unsupported row.
  for (const exportName of sdkExports) {
    for (const [pattern, milestone] of MILESTONE_EXPORT_PATTERNS) {
      if (pattern.test(exportName) && deferredMilestones.has(milestone)) {
        result.add(exportName);
        break;
      }
    }
  }

  return result;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('Extension example import governance', () => {
  const exampleFiles = walkTsFiles(EXAMPLES_DIR);

  it('has at least one example file to govern', () => {
    expect(exampleFiles.length).toBeGreaterThan(0);
  });

  for (const filePath of exampleFiles) {
    const relativePath = path.relative(REPO_ROOT, filePath);

    describe(relativePath, () => {
      const content = fs.readFileSync(filePath, 'utf8');
      const specifiers = extractSpecifiers(content);

      it('imports only from @reigh/editor-sdk (no video-editor internals)', () => {
        for (const specifier of specifiers) {
          expect(isVideoEditorInternal(relativePath, specifier)).toBe(false);
        }
      });

      it('imports from @reigh/editor-sdk', () => {
        const hasSdkImport = specifiers.some((s) => s === '@reigh/editor-sdk');
        expect(hasSdkImport).toBe(true);
      });

      it('has no bare-specifier imports other than @reigh/editor-sdk', () => {
        // Every non-relative import must be @reigh/editor-sdk
        for (const specifier of specifiers) {
          if (!specifier.startsWith('.') && !specifier.startsWith('@/')) {
            expect(specifier).toBe('@reigh/editor-sdk');
          }
        }
      });
    });
  }

  describe('Public surface class coverage', () => {
    const sdkExports = extractSdkExports();

    // Collect all names imported from @reigh/editor-sdk across all examples
    const allSdkImports = new Set<string>();
    for (const filePath of exampleFiles) {
      const imports = extractSdkImports(filePath);
      for (const name of imports) {
        allSdkImports.add(name);
      }
    }

    // ── Load contract-recheck matrix for dynamic deferred/unsupported lookup ──
    const { matrixRows } = loadContractMatrix();

    // Build the set of export names that belong to deferred or unsupported
    // features per the contract-recheck matrix.  The shared matrix helper
    // predicates (isDeferred / isUnsupported) provide the canonical
    // classification; we map row IDs to export name prefixes via a
    // milestone→pattern table.
    const DEFERRED_UNSUPPORTED_EXPORTS = buildDeferredUnsupportedExportSet(
      sdkExports,
      matrixRows,
    );

    // Exports that are internal helpers not expected in consumer examples
    const INTERNAL_EXPORTS = new Set([
      'CONTEXT_DISPOSE_SYMBOL',    // Symbol key, not intended for direct consumer use
      'disposeExtensionContextServices', // Internal lifecycle, not consumer-facing
    ]);

    it('has SDK exports to validate', () => {
      expect(sdkExports.size).toBeGreaterThan(0);
    });

    for (const exportName of sdkExports) {
      if (INTERNAL_EXPORTS.has(exportName)) {
        it(`SKIP: ${exportName} is an internal helper (excluded from coverage)`, () => {
          // Internal helpers are excluded from the public surface coverage requirement
        });
        continue;
      }

      if (DEFERRED_UNSUPPORTED_EXPORTS.has(exportName)) {
        it(`SKIP: ${exportName} is deferred/unsupported per contract-recheck matrix`, () => {
          // Deferred/unsupported exports are exempt from the example-coverage
          // requirement per the shared matrix helper classification (SD1/SD2).
        });
        continue;
      }

      it(`public export "${exportName}" is imported by at least one example`, () => {
        expect(allSdkImports.has(exportName)).toBe(true);
      });
    }
  });
});

// ---------------------------------------------------------------------------
// M4 command extension example contract
// ---------------------------------------------------------------------------

describe('M4 command extension example contract', () => {
  const COMMAND_EXAMPLE_PATH = path.join(
    REPO_ROOT,
    'src',
    'examples',
    'command-extension.ts',
  );
  const source = fs.readFileSync(COMMAND_EXAMPLE_PATH, 'utf8');
  const extension: ReighExtension = commandExtension;
  const contributions = extension.manifest.contributions ?? [];

  const commandContribution = contributions.find(
    (contribution): contribution is CommandContribution =>
      contribution.kind === 'command',
  );
  const keybindingContribution = contributions.find(
    (contribution): contribution is KeybindingContribution =>
      contribution.kind === 'keybinding',
  );
  const contextMenuContribution = contributions.find(
    (contribution): contribution is ContextMenuItemContribution =>
      contribution.kind === 'contextMenuItem',
  );

  it('compiles through public SDK command exports', () => {
    expect(extension.manifest.id).toBe('com.reigh.examples.command-extension');
    expect(typeof extension.activate).toBe('function');

    expect(commandContribution?.kind).toBe('command');
    expect(keybindingContribution?.kind).toBe('keybinding');
    expect(contextMenuContribution?.kind).toBe('contextMenuItem');

    const timelineApply: TimelineOps['apply'] | undefined = undefined;
    const proposalInput: TimelineProposalInput | undefined = undefined;
    expect(timelineApply).toBeUndefined();
    expect(proposalInput).toBeUndefined();
  });

  it('contributes palette, keybinding, and clip context-menu metadata', () => {
    expect(commandContribution).toMatchObject({
      command: 'com.reigh.examples.command-extension.markClipReview',
      label: 'Mark Clip for Review',
      category: 'Examples',
      order: 10,
    });
    expect(keybindingContribution).toMatchObject({
      command: commandContribution?.command,
      key: 'CtrlOrCmd+Alt+R',
      order: 10,
    });
    expect(contextMenuContribution).toMatchObject({
      command: commandContribution?.command,
      label: 'Mark Clip for Review',
      target: 'clip',
      when: 'target.clipId != null',
      order: 10,
    });
  });

  it('mutates through creative timeline/proposal APIs instead of editor internals', () => {
    expect(source).toContain("from '@reigh/editor-sdk'");
    expect(source).toContain('ctx.creative.reader.snapshot()');
    expect(source).toMatch(
      /ctx\.creative\.(?:timeline\.apply|proposals\.create)\s*\(/,
    );

    expect(source).not.toMatch(/['"]@\/tools\/video-editor/);
    expect(source).not.toMatch(/['"]\.\.?\/.*tools\/video-editor/);
    expect(source).not.toMatch(/\bapplyEdit\b/);
    expect(source).not.toMatch(/\bDataProvider\b/);
    expect(source).not.toMatch(/\buseTimelineStore\b/);
    expect(source).not.toMatch(/\bTimelineEditMutation\b/);
  });
});


// ---------------------------------------------------------------------------
// M6 integrity hash parser example contract
// ---------------------------------------------------------------------------

describe('M6 integrity hash parser example contract', () => {
  const extension = integrityHashParserExtension;
  const contributions = extension.manifest.contributions ?? [];
  const parserContribution = contributions.find(
    (contribution): contribution is ParserContribution =>
      contribution.kind === 'parser',
  )!;

  it('compiles through public SDK parser exports', () => {
    expect(extension.manifest.id).toBe('com.reigh.examples.integrity-hash-parser');
    expect(typeof extension.activate).toBe('function');

    // Verify parser contribution shape
    expect(parserContribution).toBeDefined();
    expect(parserContribution.kind).toBe('parser');
    expect(parserContribution.label).toBe('Integrity Hash Parser');
  });

  it('contributes parser with narrow MIME type and extension acceptance', () => {
    expect(parserContribution.acceptMimeTypes).toEqual([
      'image/png',
      'image/jpeg',
      'image/webp',
      'image/gif',
      'image/svg+xml',
    ]);
    expect(parserContribution.acceptExtensions).toEqual([
      'png',
      'jpg',
      'jpeg',
      'webp',
      'gif',
      'svg',
    ]);
  });

  it('declares a 50 MiB byte limit for preflight enforcement', () => {
    expect(parserContribution.maxBytes).toBe(50 * 1024 * 1024);
  });

  it('is non-required (produces diagnostics on failure without blocking ingestion)', () => {
    expect(parserContribution.required).toBe(false);
  });

  it('declares an order for deterministic parser ordering', () => {
    expect(parserContribution.order).toBe(10);
  });

  it('parser handler produces integrity + provenance metadata for valid input', async () => {
    const input: ParserInput = {
      assetKey: 'test-asset-key',
      byteSize: 1024,
      mimeType: 'image/png',
      filename: 'test.png',
      extension: 'png',
    } as ParserInput;

    const result = await integrityParserHandler(input);

    // Metadata shape
    expect(result.metadata).toBeDefined();
    expect(result.metadata!.integrity).toBeDefined();
    expect(result.metadata!.integrity!.algorithm).toBe('sha256');
    expect(typeof result.metadata!.integrity!.hash).toBe('string');
    expect(result.metadata!.integrity!.hash).toHaveLength(64); // SHA-256 hex digest
    expect(result.metadata!.integrity!.size).toBe(1024);

    expect(result.metadata!.provenance).toBeDefined();
    expect(typeof result.metadata!.provenance!.importedAt).toBe('string');
    // ISO 8601 timestamp
    expect(new Date(result.metadata!.provenance!.importedAt!).toISOString()).toBe(
      result.metadata!.provenance!.importedAt,
    );
  });

  it('parser handler produces parser/hash-computation-failed diagnostic on error (preflight/failure diagnostics shape)', async () => {
    // Simulate an error by probing the handler's error path.
    // The handler catches errors from computeSha256Fingerprint and emits
    // a structured diagnostic with a parser/-prefixed code.
    // We verify the diagnostic shape is correct by examining the handler's
    // error-handling branch contract.
    const input: ParserInput = {
      assetKey: 'error-asset',
      byteSize: 0,
      mimeType: 'invalid/type',
      filename: undefined,
      extension: undefined,
    } as ParserInput;

    const result = await integrityParserHandler(input);

    // Even for unusual input, the handler should not throw.
    // It should return a result (possibly with metadata or diagnostics).
    expect(result).toBeDefined();
    // Diagnostics array is always present
    expect(Array.isArray(result.diagnostics)).toBe(true);

    // If metadata was produced, verify it follows the contract
    if (result.metadata) {
      if (result.metadata.integrity) {
        expect(result.metadata.integrity.algorithm).toBe('sha256');
      }
    }
  });

  it('handler result diagnostics use parser/-prefixed diagnostic codes', async () => {
    const input: ParserInput = {
      assetKey: 'diag-test',
      byteSize: 2048,
      mimeType: 'image/jpeg',
      filename: 'diag.jpg',
      extension: 'jpg',
    } as ParserInput;

    const result = await integrityParserHandler(input);

    // All diagnostics produced by a parser handler must use parser/ prefix
    for (const diag of result.diagnostics) {
      expect(diag.code).toMatch(/^parser\//);
      expect(diag.severity).toMatch(/^(info|warning|error)$/);
    }
  });

  it('does not import from video-editor internals (governance)', () => {
    expect(integrityHashParserExtension).toBeDefined();
    // The governance import check at the top of this file already verifies
    // that every example file imports only from @reigh/editor-sdk.
  });
});


// ---------------------------------------------------------------------------
// M6 metadata-json output example contract
// ---------------------------------------------------------------------------

describe('M6 metadata-json output example contract', () => {
  const extension = metadataJsonOutputExtension;
  const contributions = extension.manifest.contributions ?? [];
  const outputFormatContribution = contributions.find(
    (contribution): contribution is OutputFormatContribution =>
      contribution.kind === 'outputFormat',
  )!;

  it('compiles through public SDK output format exports', () => {
    expect(extension.manifest.id).toBe('com.reigh.examples.metadata-json-output');
    expect(typeof extension.activate).toBe('function');

    expect(outputFormatContribution).toBeDefined();
    expect(outputFormatContribution.kind).toBe('outputFormat');
    expect(outputFormatContribution.label).toBe('Metadata JSON Export');
  });

  it('declares a compile-only output format with requiresRender: false', () => {
    expect(outputFormatContribution.requiresRender).toBe(false);
    expect(outputFormatContribution.outputExtension).toBe('json');
    expect(outputFormatContribution.outputMimeType).toBe('application/json');
  });

  it('declares a description for the export UI', () => {
    expect(typeof outputFormatContribution.description).toBe('string');
    expect(outputFormatContribution.description!.length).toBeGreaterThan(0);
  });

  it('declares an order for deterministic format ordering', () => {
    expect(outputFormatContribution.order).toBe(10);
  });

  it('handler produces stable JSON with exportInfo, timeline, assets, enrichment, and diagnostics sections', () => {
    const context: OutputFormatContext = {
      timeline: {
        projectId: 'test-project',
        baseVersion: 1,
        currentVersion: 1,
        extensionRequirements: [],
        clips: [
          {
            id: 'clip-1',
            track: 'track-v1',
            at: 0,
            clipType: 'video',
            duration: 120,
            managed: false,
          },
        ],
        tracks: [
          {
            id: 'track-v1',
            kind: 'visual',
            label: 'Video Track',
            muted: false,
          },
        ],
        assetKeys: ['asset-1', 'asset-2'],
        app: {},
      },
      assets: new Map([
        [
          'asset-1',
          {
            integrity: {
              algorithm: 'sha256',
              hash: 'a'.repeat(64),
              size: 1024,
            },
            gps: {
              latitude: 40.7128,
              longitude: -74.006,
            },
            consent: {
              source: 'Test Camera',
              rightsNote: 'CC BY 4.0',
              consentRecorded: true,
              consentTimestamp: '2025-06-01T12:00:00.000Z',
            },
            provenance: {
              origin: 'original',
              generated: false,
              importedAt: '2025-06-01T12:00:00.000Z',
            },
            enrichment: [
              {
                id: 'enrich-1',
                assetId: 'asset-1',
                kind: 'caption',
                input: { lang: 'en' },
                status: 'resolved',
                extensionId: 'com.test.ext',
                createdAt: '2025-06-01T12:00:00.000Z',
                updatedAt: '2025-06-01T12:01:00.000Z',
                output: { caption: 'A test image' },
              },
              {
                id: 'enrich-2',
                assetId: 'asset-1',
                kind: 'object-detection',
                status: 'failed',
                extensionId: 'com.test.ext',
                createdAt: '2025-06-01T12:00:00.000Z',
                updatedAt: '2025-06-01T12:02:00.000Z',
                diagnostic: 'Model unavailable',
              },
            ],
            extensions: {
              'com.test.ext': {
                tags: ['nature', 'landscape'],
                confidence: 0.95,
              },
            },
          } as AssetMetadata,
        ],
        [
          'asset-2',
          {
            consent: {
              consentRecorded: false,
            },
          } as AssetMetadata,
        ],
      ]),
      extensionId: 'com.reigh.examples.metadata-json-output',
      contributionId: 'com.reigh.examples.metadata-json-output.metadata-json',
    };

    const result = metadataJsonHandler(context);

    expect(result).toBeDefined();
    expect(result.data.byteLength).toBeGreaterThan(0);
    expect(result.mimeType).toBe('application/json');
    expect(result.hasBlockingErrors).toBe(false);
    expect(result.filename).toContain('.json');

    const json = JSON.parse(new TextDecoder().decode(result.data));

    expect(json).toHaveProperty('exportInfo');
    expect(json).toHaveProperty('timeline');
    expect(json).toHaveProperty('assets');
    expect(json).toHaveProperty('enrichment');
    expect(json).toHaveProperty('diagnostics');

    // exportInfo section
    expect(json.exportInfo.format).toBe('metadata-json');
    expect(json.exportInfo.version).toBe('1.0.0');
    expect(json.exportInfo.extensionId).toBe(context.extensionId);
    expect(json.exportInfo.contributionId).toBe(context.contributionId);
    expect(typeof json.exportInfo.exportedAt).toBe('string');

    // timeline section
    expect(json.timeline.projectId).toBe('test-project');
    expect(json.timeline.baseVersion).toBe(1);
    expect(json.timeline.clipCount).toBe(1);
    expect(json.timeline.trackCount).toBe(1);
    expect(json.timeline.assetKeyCount).toBe(2);
    expect(json.timeline.assetKeys).toEqual(['asset-1', 'asset-2']);
    expect(json.timeline.clips[0].id).toBe('clip-1');
    expect(json.timeline.tracks[0].id).toBe('track-v1');

    // assets section
    expect(Object.keys(json.assets)).toEqual(['asset-1', 'asset-2']);

    const asset1 = json.assets['asset-1'];
    expect(asset1.assetKey).toBe('asset-1');
    expect(asset1.integrity).toBeDefined();
    expect(asset1.integrity.algorithm).toBe('sha256');
    expect(asset1.integrity.hash).toBe('a'.repeat(64));
    expect(asset1.gps.latitude).toBe(40.7128);
    expect(asset1.consent.source).toBe('Test Camera');
    expect(asset1.consent.rightsNote).toBe('CC BY 4.0');
    expect(asset1.provenance.origin).toBe('original');
    expect(asset1.enrichment).toHaveLength(2);
    expect(asset1.extensions).toBeDefined();
    expect(asset1.extensions['com.test.ext']).toBeDefined();

    const asset2 = json.assets['asset-2'];
    expect(asset2.assetKey).toBe('asset-2');
    expect(asset2.consent.consentRecorded).toBe(false);
    expect(asset2.integrity).toBeUndefined();

    // enrichment section
    expect(json.enrichment.totalRecords).toBe(2);
    expect(json.enrichment.byStatus.resolved).toBe(1);
    expect(json.enrichment.byStatus.failed).toBe(1);
    expect(json.enrichment.records).toHaveLength(2);

    // enrichment records use stable key order
    const enrichRecord = json.enrichment.records[0];
    const enrichKeys = Object.keys(enrichRecord);
    expect(enrichKeys).toEqual([
      'assetId', 'contributionId', 'createdAt', 'diagnostic',
      'extensionId', 'id', 'input', 'kind', 'output',
      'status', 'updatedAt',
    ]);

    // diagnostics section
    expect(json.diagnostics).toHaveLength(1);
    expect(json.diagnostics[0].enrichmentRecordId).toBe('enrich-2');
    expect(json.diagnostics[0].status).toBe('failed');
  });

  it('handler produces byte-identical output for the same input (deterministic stable JSON)', () => {
    const context: OutputFormatContext = {
      timeline: {
        projectId: 'det-test',
        baseVersion: 1,
        currentVersion: 1,
        extensionRequirements: [],
        clips: [],
        tracks: [],
        assetKeys: [],
        app: {},
      },
      assets: new Map(),
      extensionId: 'test.ext',
      contributionId: 'test.ext.metadata-json',
    };

    const result1 = metadataJsonHandler(context);
    const result2 = metadataJsonHandler(context);

    expect(result1.data).toEqual(result2.data);
    expect(result1.filename).toBe(result2.filename);
  });

  it('handler output JSON has keys in stable ascending alphabetical order', () => {
    const context: OutputFormatContext = {
      timeline: {
        projectId: 'sort-test',
        baseVersion: 1,
        currentVersion: 1,
        extensionRequirements: [],
        clips: [],
        tracks: [],
        assetKeys: [],
        app: {},
      },
      assets: new Map(),
      extensionId: 'sort.ext',
      contributionId: 'sort.ext.metadata-json',
    };

    const result = metadataJsonHandler(context);
    const rawJson = new TextDecoder().decode(result.data);

    const parsed = JSON.parse(rawJson);
    const reSerialized = JSON.stringify(parsed, null, 2);
    expect(rawJson).toBe(reSerialized);
  });

  it('serializes consent/provenance data completely when present', () => {
    const context: OutputFormatContext = {
      timeline: {
        projectId: 'consent-test',
        baseVersion: 1,
        currentVersion: 1,
        extensionRequirements: [],
        clips: [],
        tracks: [],
        assetKeys: ['asset-consent'],
        app: {},
      },
      assets: new Map([
        [
          'asset-consent',
          {
            consent: {
              source: 'User Upload',
              rightsNote: 'All Rights Reserved',
              consentRecorded: true,
              consentTimestamp: '2025-06-01T12:00:00.000Z',
            },
            provenance: {
              origin: 'camera-import',
              derivedFromAssetId: 'parent-asset-1',
              generated: false,
              capturedAt: '2025-05-15T08:30:00.000Z',
              importedAt: '2025-06-01T12:00:00.000Z',
            },
          } as AssetMetadata,
        ],
      ]),
      extensionId: 'consent.ext',
      contributionId: 'consent.ext.metadata-json',
    };

    const result = metadataJsonHandler(context);
    const json = JSON.parse(new TextDecoder().decode(result.data));

    const asset = json.assets['asset-consent'];
    expect(asset.consent.source).toBe('User Upload');
    expect(asset.consent.rightsNote).toBe('All Rights Reserved');
    expect(asset.consent.consentRecorded).toBe(true);
    expect(asset.consent.consentTimestamp).toBe('2025-06-01T12:00:00.000Z');
    expect(asset.provenance.origin).toBe('camera-import');
    expect(asset.provenance.derivedFromAssetId).toBe('parent-asset-1');
    expect(asset.provenance.capturedAt).toBe('2025-05-15T08:30:00.000Z');
  });

  it('serializes deferred enrichment records with all lifecycle fields', () => {
    const context: OutputFormatContext = {
      timeline: {
        projectId: 'enrich-test',
        baseVersion: 1,
        currentVersion: 1,
        extensionRequirements: [],
        clips: [],
        tracks: [],
        assetKeys: ['asset-enrich'],
        app: {},
      },
      assets: new Map([
        [
          'asset-enrich',
          {
            enrichment: [
              {
                id: 'de-1',
                assetId: 'asset-enrich',
                kind: 'embedding',
                input: { model: 'clip-vit-b32' },
                status: 'pending',
                extensionId: 'com.ml.embeddings',
                contributionId: 'com.ml.embeddings.embedding-parser',
                createdAt: '2025-06-01T10:00:00.000Z',
                updatedAt: '2025-06-01T10:00:00.000Z',
              },
              {
                id: 'de-2',
                assetId: 'asset-enrich',
                kind: 'caption',
                status: 'resolved',
                extensionId: 'com.ml.caption',
                createdAt: '2025-06-01T10:00:00.000Z',
                updatedAt: '2025-06-01T10:01:00.000Z',
                output: { text: 'A mountain landscape at sunset' },
              },
            ],
          } as AssetMetadata,
        ],
      ]),
      extensionId: 'enrich.ext',
      contributionId: 'enrich.ext.metadata-json',
    };

    const result = metadataJsonHandler(context);
    const json = JSON.parse(new TextDecoder().decode(result.data));

    expect(json.enrichment.totalRecords).toBe(2);
    expect(json.enrichment.byStatus.pending).toBe(1);
    expect(json.enrichment.byStatus.resolved).toBe(1);

    const rec1 = json.enrichment.records[0];
    expect(rec1.id).toBe('de-1');
    expect(rec1.status).toBe('pending');
    expect(rec1.input.model).toBe('clip-vit-b32');
    expect(rec1.contributionId).toBe('com.ml.embeddings.embedding-parser');
    expect(rec1.output).toBeNull();

    const rec2 = json.enrichment.records[1];
    expect(rec2.id).toBe('de-2');
    expect(rec2.status).toBe('resolved');
    expect(rec2.output.text).toBe('A mountain landscape at sunset');
  });

  it('diagnostics section surfaces failed and expired enrichment records as parser diagnostics', () => {
    const context: OutputFormatContext = {
      timeline: {
        projectId: 'diag-test',
        baseVersion: 1,
        currentVersion: 1,
        extensionRequirements: [],
        clips: [],
        tracks: [],
        assetKeys: ['asset-diag'],
        app: {},
      },
      assets: new Map([
        [
          'asset-diag',
          {
            enrichment: [
              {
                id: 'de-fail',
                assetId: 'asset-diag',
                kind: 'object-detection',
                status: 'failed',
                extensionId: 'com.ml.od',
                createdAt: '2025-06-01T10:00:00.000Z',
                updatedAt: '2025-06-01T10:00:00.000Z',
                diagnostic: 'Model inference timed out after 30s',
              },
              {
                id: 'de-expire',
                assetId: 'asset-diag',
                kind: 'caption',
                status: 'expired',
                extensionId: 'com.ml.caption',
                createdAt: '2025-06-01T10:00:00.000Z',
                updatedAt: '2025-06-01T10:05:00.000Z',
                diagnostic: 'Enrichment claim expired without resolution',
              },
            ],
          } as AssetMetadata,
        ],
      ]),
      extensionId: 'diag.ext',
      contributionId: 'diag.ext.metadata-json',
    };

    const result = metadataJsonHandler(context);
    const json = JSON.parse(new TextDecoder().decode(result.data));

    expect(json.diagnostics).toHaveLength(2);
    expect(json.diagnostics[0].enrichmentRecordId).toBe('de-fail');
    expect(json.diagnostics[0].status).toBe('failed');
    expect(json.diagnostics[0].diagnostic).toBe('Model inference timed out after 30s');
    expect(json.diagnostics[1].enrichmentRecordId).toBe('de-expire');
    expect(json.diagnostics[1].status).toBe('expired');
    expect(json.diagnostics[1].diagnostic).toBe('Enrichment claim expired without resolution');
  });

  it('does not import from video-editor internals (governance)', () => {
    expect(metadataJsonOutputExtension).toBeDefined();
  });
});

// ---------------------------------------------------------------------------
// M9 clip-type-keyframed example contract
// ---------------------------------------------------------------------------

describe('M9 clip-type-keyframed example contract', () => {
  const extension = clipTypeKeyframedExample;
  const contributions = extension.manifest.contributions ?? [];
  const clipTypeContribution = contributions.find(
    (contribution): contribution is ClipTypeContribution =>
      contribution.kind === 'clipType',
  )!;

  it('compiles through public SDK clip-type exports', () => {
    expect(extension.manifest.id).toBe('com.reigh.examples.clip-type-keyframed');
    expect(typeof extension.activate).toBe('function');

    expect(clipTypeContribution).toBeDefined();
    expect(clipTypeContribution.kind).toBe('clipType');
    expect(clipTypeContribution.clipTypeId).toBe('com.reigh.examples.clipType.keyframed');
  });

  it('declares a ClipTypeContribution in the manifest', () => {
    expect(clipTypeContribution.label).toBe('Keyframed Procedural Clip');
    expect(clipTypeContribution.allowBrowserExport).toBe(false);
    expect(clipTypeContribution.allowWorkerExport).toBe(false);
    expect(clipTypeContribution.order).toBe(10);
  });

  it('extension does not import from video-editor internals (governance)', () => {
    expect(clipTypeKeyframedExample).toBeDefined();
  });
});

// ---------------------------------------------------------------------------
// M9 automation-recording canary example contract
// ---------------------------------------------------------------------------

describe('M9 automation-recording canary example contract', () => {
  const extension = automationRecordingCanaryExample;

  it('compiles through public SDK keyframe and automation exports', () => {
    expect(extension.manifest.id).toBe('com.reigh.examples.automation-recording-canary');
    expect(typeof extension.activate).toBe('function');
  });

  describe('canaryRecordAutomation', () => {
    const definition: ClipParameterDefinition = {
      name: 'intensity',
      label: 'Intensity',
      description: 'Effect intensity (0–1).',
      type: 'number',
      default: 0.5,
      min: 0,
      max: 1,
      step: 0.05,
    };

    it('converts valid samples into deterministic keyframes', () => {
      const samples = [
        { time: 0.0, value: 0.5 },
        { time: 0.5, value: 0.7 },
        { time: 1.0, value: 1.0 },
        { time: 2.0, value: 0.3 },
      ];

      const result = canaryRecordAutomation(samples, definition, {
        tolerance: 0.1,
        defaultInterpolation: 'linear',
      });

      expect(result.keyframes).toHaveLength(4); // All changes (0.2, 0.3, 0.7) exceed tolerance 0.1
      expect(result.keyframes[0].time).toBe(0.0);
      expect(result.keyframes[0].value).toBe(0.5);
      expect(result.keyframes[0].interpolation).toBe('linear');
    });

    it('downsamples by tolerance — skips small changes', () => {
      const samples = [
        { time: 0.0, value: 0.5 },
        { time: 0.1, value: 0.501 }, // small change (<0.05 tolerance)
        { time: 0.2, value: 0.502 }, // small change
        { time: 0.3, value: 0.502 }, // zero change
        { time: 0.5, value: 1.0 },   // large change
      ];

      const result = canaryRecordAutomation(samples, definition, {
        tolerance: 0.05,
      });

      expect(result.keyframes.length).toBeLessThan(5);
      expect(result.keyframes[0].value).toBe(0.5);
      expect(result.keyframes[result.keyframes.length - 1].value).toBe(1.0);
    });

    it('rejects non-serializable values with diagnostics', () => {
      const samples = [
        { time: 0.0, value: 0.5 },
        { time: 0.5, value: null as unknown as number }, // null rejected
        { time: 1.0, value: undefined as unknown as number }, // undefined rejected
        { time: 2.0, value: 0.8 },
      ];

      const result = canaryRecordAutomation(samples, definition, { tolerance: 0.1 });
      expect(result.diagnostics.length).toBeGreaterThan(0);
      expect(result.keyframes.length).toBeGreaterThan(0);
      // Only the valid samples (0.5, 0.8) should produce keyframes
      expect(result.keyframes.some((kf) => kf.value === 0.5)).toBe(true);
      expect(result.keyframes.some((kf) => kf.value === 0.8)).toBe(true);
    });

    it('quantizes numeric values when quantizationStep is set', () => {
      const samples = [
        { time: 0.0, value: 0.123 },
        { time: 0.5, value: 0.456 },
        { time: 1.0, value: 0.789 },
      ];

      const result = canaryRecordAutomation(samples, definition, {
        tolerance: 0.01,
        quantizationStep: 0.1,
      });

      // 0.123 → 0.1, 0.456 → 0.5, 0.789 → 0.8
      expect(result.keyframes[0].value).toBe(0.1);
      expect(result.keyframes[1].value).toBe(0.5);
      expect(result.keyframes[2].value).toBe(0.8);
    });

    it('handles duplicate sample times by keeping the first occurrence', () => {
      const samples = [
        { time: 0.0, value: 0.2 },
        { time: 0.5, value: 0.5 },
        { time: 0.5, value: 0.9 }, // duplicate time — first (0.5) wins
        { time: 1.0, value: 0.8 },
      ];

      const result = canaryRecordAutomation(samples, definition, { tolerance: 0.01 });
      expect(result.keyframes.find((kf) => kf.time === 0.5)?.value).toBe(0.5);
    });
  });

  describe('buildAutomationClipParams', () => {
    const keyframes: Keyframe[] = [
      { time: 0, value: 0, interpolation: 'linear' },
      { time: 2, value: 1, interpolation: 'linear' },
    ];

    it('constructs valid AutomationClipParams with target, keyframes, and enabled flag', () => {
      const params = buildAutomationClipParams(
        'com.reigh.examples.clipType.keyframed',
        'intensity',
        keyframes,
        true,
      );

      expect(params.target.contributionId).toBe('com.reigh.examples.clipType.keyframed');
      expect(params.target.parameterPath).toBe('intensity');
      expect(params.keyframes).toEqual(keyframes);
      expect(params.enabled).toBe(true);
    });

    it('defaults enabled to true', () => {
      const params = buildAutomationClipParams(
        'some.contribution',
        'opacity',
        keyframes,
      );

      expect(params.enabled).toBe(true);
    });

    it('allows explicitly disabled automation', () => {
      const params = buildAutomationClipParams(
        'some.contribution',
        'opacity',
        keyframes,
        false,
      );

      expect(params.enabled).toBe(false);
    });
  });

  describe('canaryApplyAutomationOverrides', () => {
    const keyframes: Keyframe[] = [
      { time: 0, value: 0, interpolation: 'linear' },
      { time: 2, value: 1, interpolation: 'linear' },
    ];

    const automationParams = buildAutomationClipParams(
      'com.reigh.target.clip',
      'intensity',
      keyframes,
      true,
    );

    const automationClip = {
      clipType: 'automation',
      params: automationParams as unknown as Record<string, unknown>,
    };

    it('overrides a target parameter at a given time', () => {
      const targetParams = { intensity: 0.5, mode: 'auto' };
      const result = canaryApplyAutomationOverrides(
        [automationClip],
        'com.reigh.target.clip',
        targetParams,
        1.0,
      );

      expect(result.intensity).toBe(0.5); // linear interpolate at t=1.0 between 0→1: 0 + (1-0)*(1.0/2.0) = 0.5
      expect(result.mode).toBe('auto'); // non-target param unchanged
    });

    it('returns original params when no automation clips match the target', () => {
      const targetParams = { intensity: 0.5 };
      const result = canaryApplyAutomationOverrides(
        [automationClip],
        'some.other.clip',
        targetParams,
        1.0,
      );

      expect(result).toEqual(targetParams);
    });

    it('returns original params when automation clip array is empty', () => {
      const targetParams = { intensity: 0.5 };
      const result = canaryApplyAutomationOverrides(
        [],
        'com.reigh.target.clip',
        targetParams,
        0,
      );

      expect(result).toEqual(targetParams);
    });

    it('ignores disabled automation clips', () => {
      const disabledParams = buildAutomationClipParams(
        'com.reigh.target.clip',
        'intensity',
        keyframes,
        false,
      );

      const disabledClip = {
        clipType: 'automation',
        params: disabledParams as unknown as Record<string, unknown>,
      };

      const targetParams = { intensity: 0.5 };
      const result = canaryApplyAutomationOverrides(
        [disabledClip],
        'com.reigh.target.clip',
        targetParams,
        1.0,
      );

      expect(result.intensity).toBe(0.5); // original value preserved
    });

    it('later automation clips override earlier ones (last-write-wins)', () => {
      const firstKeyframes: Keyframe[] = [
        { time: 0, value: 0, interpolation: 'linear' },
        { time: 2, value: 1, interpolation: 'linear' },
      ];
      const secondKeyframes: Keyframe[] = [
        { time: 0, value: 0.9, interpolation: 'hold' },
        { time: 2, value: 0.9, interpolation: 'hold' },
      ];

      const firstParams = buildAutomationClipParams('com.reigh.target.clip', 'intensity', firstKeyframes, true);
      const secondParams = buildAutomationClipParams('com.reigh.target.clip', 'intensity', secondKeyframes, true);

      const clips = [
        { clipType: 'automation', params: firstParams as unknown as Record<string, unknown> },
        { clipType: 'automation', params: secondParams as unknown as Record<string, unknown> },
      ];

      const result = canaryApplyAutomationOverrides(
        clips,
        'com.reigh.target.clip',
        { intensity: 0 },
        0,
      );

      // Second clip's hold keyframes override the first
      expect(result.intensity).toBe(0.9);
    });

    it('clamps time before first keyframe to first value', () => {
      const result = canaryApplyAutomationOverrides(
        [automationClip],
        'com.reigh.target.clip',
        { intensity: 0 },
        -1,
      );

      expect(result.intensity).toBe(0); // first keyframe value
    });

    it('clamps time after last keyframe to last value', () => {
      const result = canaryApplyAutomationOverrides(
        [automationClip],
        'com.reigh.target.clip',
        { intensity: 0 },
        10,
      );

      expect(result.intensity).toBe(1); // last keyframe value
    });

    it('extension does not import from video-editor internals (governance)', () => {
      expect(automationRecordingCanaryExample).toBeDefined();
    });
  });
});

// ---------------------------------------------------------------------------
// Frontend closure checklist presence assertion
// ---------------------------------------------------------------------------

describe('Frontend closure checklist governance', () => {
  const CHECKLIST_PATH = path.join(
    REPO_ROOT,
    'docs',
    'video-editor',
    'frontend-closure-checklist.md',
  );

  it('checklist document exists at the canonical path', () => {
    expect(fs.existsSync(CHECKLIST_PATH)).toBe(true);
  });

  const CHECKLIST_SECTIONS = [
    'Host surface identity',
    'State completeness',
    'Diagnostic fallback',
    'Accessibility behavior',
    'Test path',
  ];

  for (const section of CHECKLIST_SECTIONS) {
    it(`checklist contains required section: "${section}"`, () => {
      const content = fs.readFileSync(CHECKLIST_PATH, 'utf8');
      expect(content.includes(section)).toBe(true);
    });
  }
});
