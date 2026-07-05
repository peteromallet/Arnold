#!/usr/bin/env node
/**
 * M15 Pre-Doc Example Readiness Gate
 *
 * Reads the canonical supported/deferred matrix
 * (`docs/video-editor/extension-platform-supported-deferred.md`) and
 * governance outputs (`config/governance/contract-surface-map.json`,
 * `config/governance/sdk-public-export-allowlist.json`) to determine which
 * example files are safe to reference in author-contract docs and quickstart
 * guides.
 *
 * ## What this gate enforces
 *
 * 1. Every EX: and EXT: evidence reference in a **supported** row must
 *    resolve to an existing file or directory on disk.
 * 2. Example files that demonstrate deferred, unsupported, or
 *    release-blocking behaviour are flagged as **unsupported docs
 *    candidates** and cause the check to fail (even in audit mode).
 * 3. Every example file under `src/examples/` must import exclusively
 *    from `@reigh/editor-sdk` (the public boundary).  Internal imports
 *    (`src/tools/video-editor/` etc.) are not allowed in public examples.
 * 4. Examples that exist on disk but have no corresponding **supported**
 *    matrix row are reported as unclassified.
 *
 * ## Modes
 *
 *   --audit     (default)  Report missing examples, internal imports, and
 *                          unclassified files as warnings.  Only fail when
 *                          a supported row's example is missing or an
 *                          unsupported-docs-candidate file exists.
 *
 *   --release             Same as audit, plus hard-fail on unclassified
 *                         examples and internal imports in example files.
 *
 * ## Machine-readable output
 *
 * The gate always writes a JSON record of docs-safe example IDs to stdout
 * as its final line, e.g.:
 *
 *   {"docsSafeExampleIds":["toolbar-example","command-extension",…]}
 *
 * This JSON is consumed by downstream doc-generation tooling.
 *
 * ## Dependencies
 *
 * Consumes the shared classification predicates from
 * `./lib/extension-contract-matrix.mjs` (SD1) but does NOT re-parse the
 * contract-recheck matrix — it only reads the supported/deferred matrix.
 */

import { readFileSync, existsSync, statSync, readdirSync } from 'node:fs';
import { resolve, dirname, relative, basename } from 'node:path';
import { fileURLToPath } from 'node:url';

// ---------------------------------------------------------------------------
// Path resolution
// ---------------------------------------------------------------------------

const moduleDir = dirname(fileURLToPath(import.meta.url));
const DEFAULT_REPO_ROOT = resolve(moduleDir, '..', '..');

let repoRoot = DEFAULT_REPO_ROOT;
let SUPPORTED_DEFERRED_PATH = '';
let CONTRACT_SURFACE_MAP_PATH = '';
let SDK_EXPORT_ALLOWLIST_PATH = '';
let EXAMPLES_DIR = '';
let EXTENSIONS_DIR = '';
let RELEASE_EXAMPLES_DOC_PATH = '';

const LABEL = '[example-readiness]';

function configurePaths(nextRepoRoot = DEFAULT_REPO_ROOT) {
  repoRoot = resolve(nextRepoRoot);
  SUPPORTED_DEFERRED_PATH = resolve(
    repoRoot,
    'docs/video-editor/extension-platform-supported-deferred.md',
  );
  CONTRACT_SURFACE_MAP_PATH = resolve(
    repoRoot,
    'config/governance/contract-surface-map.json',
  );
  SDK_EXPORT_ALLOWLIST_PATH = resolve(
    repoRoot,
    'config/governance/sdk-public-export-allowlist.json',
  );
  EXAMPLES_DIR = resolve(repoRoot, 'src/examples');
  EXTENSIONS_DIR = resolve(
    repoRoot,
    'src/tools/video-editor/examples/extensions',
  );
  RELEASE_EXAMPLES_DOC_PATH = resolve(
    repoRoot,
    'docs/extensions/composition-spine/m0-release-examples.md',
  );
}

configurePaths();

// ---------------------------------------------------------------------------
// CLI argument parsing
// ---------------------------------------------------------------------------

const cliArgs = process.argv.slice(2);
const args = new Set(cliArgs);

function readCliOption(name) {
  const exactPrefix = `${name}=`;
  const exact = cliArgs.find((arg) => arg.startsWith(exactPrefix));
  if (exact) {
    return exact.slice(exactPrefix.length);
  }
  const index = cliArgs.indexOf(name);
  if (index >= 0 && index < cliArgs.length - 1) {
    return cliArgs[index + 1];
  }
  return null;
}

/** @type {'audit' | 'release'} */
let mode = 'audit';
if (args.has('--release')) {
  mode = 'release';
} else if (args.has('--audit')) {
  mode = 'audit';
}

const isRelease = mode === 'release';
const repoRootOverride = readCliOption('--repo-root');
if (repoRootOverride) {
  configurePaths(resolve(repoRootOverride));
}

// ---------------------------------------------------------------------------
// Supported/deferred matrix parser
// ---------------------------------------------------------------------------

/**
 * @typedef {object} MatrixRow
 * @property {string} rowId        – e.g. "S-001", "D-001"
 * @property {string} behavior     – human-readable behaviour description
 * @property {string} classification – "supported" | "deferred" | "unsupported" | "release-blocking"
 * @property {string} evidence     – raw evidence string with EX:/EXT: refs
 */

/**
 * @typedef {object} ExampleRef
 * @property {string} refType       – "EX" or "EXT"
 * @property {string} refPath       – the path portion of the reference
 * @property {string} sourceRowId   – the matrix row ID that references it
 * @property {string} classification – the row's classification
 */

/**
 * Parse the supported/deferred matrix markdown and return structured rows.
 *
 * @returns {{ supportedRows: MatrixRow[], deferredRows: MatrixRow[], unsupportedRows: MatrixRow[], releaseBlockingRows: MatrixRow[] }}
 */
function parseSupportedDeferredMatrix() {
  if (!existsSync(SUPPORTED_DEFERRED_PATH)) {
    throw new Error(
      `Supported/deferred matrix not found: ${SUPPORTED_DEFERRED_PATH}`,
    );
  }

  const markdown = readFileSync(SUPPORTED_DEFERRED_PATH, 'utf8');
  const lines = markdown.split('\n');

  /** @type {MatrixRow[]} */
  const supportedRows = [];
  /** @type {MatrixRow[]} */
  const deferredRows = [];
  /** @type {MatrixRow[]} */
  const unsupportedRows = [];
  /** @type {MatrixRow[]} */
  const releaseBlockingRows = [];

  // State machine: track which section we're in
  /** @type {'none' | 'supported' | 'deferred' | 'scope'} */
  let section = 'none';
  let inSupportedTable = false;
  let inDeferredTable = false;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();

    // ---- section detection ----
    if (line.startsWith('## 2. Supported V1 Behavior Matrix')) {
      section = 'supported';
      inSupportedTable = false;
      inDeferredTable = false;
      continue;
    }

    if (line.startsWith('## 3. Deferred / Unsupported V1 Behavior Matrix')) {
      section = 'deferred';
      inSupportedTable = false;
      inDeferredTable = false;
      continue;
    }

    if (line.startsWith('## 4. V1 Scope Boundaries')) {
      section = 'scope';
      inSupportedTable = false;
      inDeferredTable = false;
      continue;
    }

    if (line.startsWith('## 5.') || line.startsWith('## 6.') || line.startsWith('## 7.') || line.startsWith('## 8.')) {
      section = 'none';
      inSupportedTable = false;
      inDeferredTable = false;
      continue;
    }

    // ---- sub-section: enter a table ----
    if (section === 'supported' && line.startsWith('###') && line.includes('|')) {
      inSupportedTable = true;
      continue;
    }

    if (section === 'deferred' && line.startsWith('###')) {
      inDeferredTable = true;
      continue;
    }

    // ---- table row parsing ----
    if (line.startsWith('|') && line.endsWith('|')) {
      const cells = line
        .split('|')
        .slice(1, -1)
        .map((c) => c.trim());

      // Skip header and separator rows
      if (
        cells.every((c) => /^:?-{3,}:?$/.test(c)) ||
        cells.some((c) =>
          /^(Row ID|Behavior|Classification|Evidence|Concern|V1 Answer)$/i.test(c),
        )
      ) {
        continue;
      }

      if (section === 'supported' && cells.length >= 4) {
        const classification = (cells[2] || '')
          .replace(/[*_]{1,2}/g, '')
          .toLowerCase()
          .trim();

        const row = {
          rowId: cells[0] || '',
          behavior: cells[1] || '',
          classification: cells[2] || '',
          evidence: cells[3] || '',
        };

        if (classification === 'supported') {
          supportedRows.push(row);
        }
      }

      if (section === 'deferred' && cells.length >= 4) {
        const classification = (cells[2] || '')
          .replace(/[*_]{1,2}/g, '')
          .toLowerCase()
          .trim();

        const row = {
          rowId: cells[0] || '',
          behavior: cells[1] || '',
          classification: cells[2] || '',
          evidence: cells[3] || '',
        };

        if (classification === 'deferred') {
          deferredRows.push(row);
        } else if (classification === 'unsupported') {
          unsupportedRows.push(row);
        } else if (classification === 'release-blocking') {
          releaseBlockingRows.push(row);
        }
      }

      // Also handle out-of-scope table (§ 4.1)
      if (section === 'scope' && cells.length >= 2) {
        // These are unsupported by default
        unsupportedRows.push({
          rowId: '',
          behavior: cells[0] || '',
          classification: 'unsupported',
          evidence: cells[1] || '',
        });
      }
    }
  }

  return { supportedRows, deferredRows, unsupportedRows, releaseBlockingRows };
}

// ---------------------------------------------------------------------------
// Evidence reference extraction
// ---------------------------------------------------------------------------

/**
 * Extract EX: and EXT: references from an evidence string.
 *
 * @param {string} evidence
 * @returns {Array<{ type: 'EX'|'EXT', path: string }>}
 */
function extractExampleRefs(evidence) {
  /** @type {Array<{ type: 'EX'|'EXT', path: string }>} */
  const refs = [];

  // Split the evidence string on semicolons into segments, then process each.
  // Semicolons separate evidence-type groups; commas separate items within a group.
  const segments = evidence.split(/\s*;\s*/);

  for (const segment of segments) {
    const trimmed = segment.trim();

    // EX: prefix — may be followed by a comma-separated list of filenames
    if (trimmed.startsWith('EX:')) {
      const value = trimmed.slice(3).trim();
      const files = value.split(/,\s*/).filter((f) => f.length > 0);
      for (const file of files) {
        refs.push({ type: 'EX', path: file.trim() });
      }
      continue;
    }

    // EXT: prefix — may be followed by a comma-separated list of paths
    if (trimmed.startsWith('EXT:')) {
      const value = trimmed.slice(4).trim();
      const paths = value.split(/,\s*/).filter((p) => p.length > 0);
      for (const p of paths) {
        refs.push({ type: 'EXT', path: p.trim() });
      }
      continue;
    }
  }

  return refs;
}

// ---------------------------------------------------------------------------
// File resolution helpers
// ---------------------------------------------------------------------------

/**
 * Resolve an EX: reference path to an absolute file path.
 * EX: references without a leading directory are assumed to be in
 * `src/examples/`.  References with a directory prefix are resolved
 * relative to the repo root.
 *
 * @param {string} exPath
 * @returns {string}
 */
function resolveExPath(exPath) {
  // Strip leading/trailing whitespace and punctuation
  const cleaned = exPath.replace(/[;,]+$/, '').trim();

  if (cleaned.includes('/')) {
    // Has a directory prefix — resolve from repo root
    // But strip any leading src/ if present to avoid double-prefixing
    const normalized = cleaned.startsWith('src/') ? cleaned : cleaned;
    return resolve(repoRoot, normalized);
  }

  // Bare filename — look in src/examples/
  return resolve(EXAMPLES_DIR, cleaned);
}

/**
 * Resolve an EXT: reference path.
 *
 * EXT: references can be:
 *   - Directory paths: `flagship-local/` → resolves to the extension directory
 *   - File paths within an extension: `flagship-local/FlagshipEffectComponent.tsx` → resolves to that file
 *   - Test paths: `__tests__/flagship-local-transition.test.ts` → resolves to the test file
 *
 * Returns { absPath, isFile } where isFile=true means the reference points to
 * a specific file rather than a directory.
 *
 * @param {string} extPath
 * @returns {{ absPath: string, isFile: boolean }}
 */
function resolveExtPath(extPath) {
  const cleaned = extPath.replace(/[;,]+$/, '').trim().replace(/\/$/, '');

  // Determine if it looks like a file (has a file extension)
  const isFile = /\.(ts|tsx|js|jsx|json)$/i.test(cleaned);

  // If the path starts with __tests__/, it's a test file in the extensions
  // __tests__ directory. Resolve relative to the extensions dir.
  if (cleaned.startsWith('__tests__/')) {
    return {
      absPath: resolve(EXTENSIONS_DIR, cleaned),
      isFile: true,
    };
  }

  // If the path already includes src/, resolve from repo root
  if (cleaned.startsWith('src/')) {
    return {
      absPath: resolve(repoRoot, cleaned),
      isFile,
    };
  }

  // Otherwise resolve relative to the extensions directory
  return {
    absPath: resolve(EXTENSIONS_DIR, cleaned),
    isFile,
  };
}

/**
 * Check that an EX: example file exists and hasn't been deleted.
 *
 * @param {string} absPath
 * @returns {{ exists: boolean, reason?: string }}
 */
function checkExFile(absPath) {
  if (!existsSync(absPath)) {
    return { exists: false, reason: `File not found: ${absPath}` };
  }

  try {
    const stat = statSync(absPath);
    if (!stat.isFile()) {
      return { exists: false, reason: `Not a regular file: ${absPath}` };
    }
  } catch {
    return { exists: false, reason: `Cannot stat file: ${absPath}` };
  }

  return { exists: true };
}

/**
 * Check that an EXT: example directory exists and has the required files
 * (index.ts and reigh-extension.json).
 *
 * @param {string} absDir
 * @returns {{ exists: boolean, reason?: string }}
 */
function checkExtDir(absDir) {
  if (!existsSync(absDir)) {
    return { exists: false, reason: `Directory not found: ${absDir}` };
  }

  try {
    const stat = statSync(absDir);
    if (!stat.isDirectory()) {
      return { exists: false, reason: `Not a directory: ${absDir}` };
    }
  } catch {
    return { exists: false, reason: `Cannot stat directory: ${absDir}` };
  }

  const indexFile = resolve(absDir, 'index.ts');
  const manifestFile = resolve(absDir, 'reigh-extension.json');

  if (!existsSync(indexFile)) {
    return {
      exists: false,
      reason: `Extension directory missing index.ts: ${absDir}`,
    };
  }

  if (!existsSync(manifestFile)) {
    return {
      exists: false,
      reason: `Extension directory missing reigh-extension.json: ${absDir}`,
    };
  }

  return { exists: true };
}

// ---------------------------------------------------------------------------
// Import boundary check
// ---------------------------------------------------------------------------

/**
 * Check that a TypeScript source file only imports from @reigh/editor-sdk
 * (the public SDK entrypoint).  Returns a list of internal-import violations.
 *
 * @param {string} absPath
 * @returns {{ clean: boolean, violations: string[] }}
 */
function checkImportBoundary(absPath) {
  if (!existsSync(absPath)) {
    return { clean: false, violations: [`File not found: ${absPath}`] };
  }

  const content = readFileSync(absPath, 'utf8');
  const violations = [];

  // Find all import/require statements
  const importRe = /from\s+['"]([^'"]+)['"]/g;
  let match;

  while ((match = importRe.exec(content)) !== null) {
    const specifier = match[1];

    // Allow @reigh/editor-sdk imports
    if (specifier === '@reigh/editor-sdk') continue;

    // Allow relative imports within the examples/extensions directories
    if (specifier.startsWith('./') || specifier.startsWith('../')) continue;

    // Allow standard library and npm packages
    if (
      !specifier.startsWith('@/') &&
      !specifier.startsWith('src/') &&
      !specifier.includes('video-editor')
    ) {
      // Looks like an npm package — allow it
      continue;
    }

    // Internal imports are violations
    violations.push(
      `Internal import "${specifier}" in ${relative(repoRoot, absPath)}`,
    );
  }

  // Also check for dynamic imports / require()
  const dynamicImportRe = /import\s*\(\s*['"]([^'"]+)['"]\s*\)/g;
  while ((match = dynamicImportRe.exec(content)) !== null) {
    const specifier = match[1];
    if (specifier === '@reigh/editor-sdk') continue;
    if (specifier.startsWith('./') || specifier.startsWith('../')) continue;
    if (
      !specifier.startsWith('@/') &&
      !specifier.startsWith('src/') &&
      !specifier.includes('video-editor')
    ) {
      continue;
    }
    violations.push(
      `Internal dynamic import "${specifier}" in ${relative(repoRoot, absPath)}`,
    );
  }

  return { clean: violations.length === 0, violations };
}

// ---------------------------------------------------------------------------
// Governance cross-reference
// ---------------------------------------------------------------------------

/**
 * Load the contract-surface-map and sdk-public-export-allowlist.
 *
 * @returns {{ contractSurfaceMap: object, exportAllowlist: object }}
 */
function loadGovernanceData() {
  let contractSurfaceMap = {};
  let exportAllowlist = { allowlist: [] };

  if (existsSync(CONTRACT_SURFACE_MAP_PATH)) {
    try {
      contractSurfaceMap = JSON.parse(
        readFileSync(CONTRACT_SURFACE_MAP_PATH, 'utf8'),
      );
    } catch (err) {
      console.warn(
        `${LABEL} Could not parse contract-surface-map: ${err.message}`,
      );
    }
  }

  if (existsSync(SDK_EXPORT_ALLOWLIST_PATH)) {
    try {
      exportAllowlist = JSON.parse(
        readFileSync(SDK_EXPORT_ALLOWLIST_PATH, 'utf8'),
      );
    } catch (err) {
      console.warn(
        `${LABEL} Could not parse sdk-public-export-allowlist: ${err.message}`,
      );
    }
  }

  return { contractSurfaceMap, exportAllowlist };
}

const RELEASE_EXAMPLE_CONTRACTS = Object.freeze([
  {
    exampleId: 'EX-01',
    requiredDocRefPaths: Object.freeze([
      'src/tools/video-editor/examples/extensions/__tests__/clip-local-shader-canary.integration.test.tsx',
    ]),
    supportedDocRefPaths: Object.freeze([
      'src/tools/video-editor/examples/extensions/clip-local-shader-canary/index.ts',
      'src/tools/video-editor/examples/extensions/__tests__/clip-local-shader-canary.integration.test.tsx',
    ]),
    markerChecks: Object.freeze([
      {
        relPath:
          'src/tools/video-editor/examples/extensions/__tests__/clip-local-shader-canary.integration.test.tsx',
        label: 'shader-uniform target-path evidence',
        patterns: Object.freeze([
          {
            regex: /targetKind:\s*'shader-uniform'/,
            message: 'missing shader-uniform target kind evidence.',
          },
          {
            regex: /targetPath:\s*'uniforms\.intensity'/,
            message: 'missing supported shader-uniform target path evidence.',
          },
          {
            regex: /reason:\s*'missing-material'/,
            message: 'missing route-scoped missing-material blocker evidence.',
          },
        ]),
      },
    ]),
  },
  {
    exampleId: 'EX-02',
    requiredDocRefPaths: Object.freeze([
      'src/tools/video-editor/examples/extensions/__tests__/flagship-local-m5-effect-live-canary.integration.test.tsx',
      'src/tools/video-editor/examples/extensions/__tests__/m5-composed-examples.browser.test.tsx',
    ]),
    supportedDocRefPaths: Object.freeze([
      'src/tools/video-editor/examples/extensions/flagship-local/index.ts',
      'src/tools/video-editor/examples/extensions/live-webcam-canary/index.ts',
      'src/tools/video-editor/examples/extensions/live-generated-frame-canary/index.ts',
      'src/tools/video-editor/examples/extensions/__tests__/live-data-bridge.integration.test.tsx',
      'src/tools/video-editor/examples/extensions/__tests__/flagship-local-m5-effect-live-canary.integration.test.tsx',
      'src/tools/video-editor/examples/extensions/__tests__/m5-composed-examples.browser.test.tsx',
    ]),
    markerChecks: Object.freeze([
      {
        relPath:
          'src/tools/video-editor/examples/extensions/__tests__/flagship-local-m5-effect-live-canary.integration.test.tsx',
        label: 'effect live-binding target-path evidence',
        patterns: Object.freeze([
          {
            regex: /targetKind:\s*'effect-param'/,
            message: 'missing effect-param target kind evidence.',
          },
          {
            regex: /targetPath:\s*'intensity'/,
            message: 'missing supported effect-param target path evidence.',
          },
          {
            regex: /code:\s*'export\/live-binding-unresolved'/,
            message: 'missing export/live-binding-unresolved blocker evidence.',
          },
          {
            regex: /reason:\s*'live-unbaked'/,
            message: 'missing live-unbaked planner blocker evidence.',
          },
        ]),
      },
    ]),
  },
  {
    exampleId: 'EX-03',
    requiredDocRefPaths: Object.freeze([
      'src/tools/video-editor/examples/extensions/__tests__/flagship-local-m5-transition-mask-canary.integration.test.tsx',
      'src/tools/video-editor/examples/extensions/__tests__/m5-composed-examples.browser.test.tsx',
    ]),
    supportedDocRefPaths: Object.freeze([
      'src/tools/video-editor/examples/extensions/flagship-local/index.ts',
      'src/tools/video-editor/examples/extensions/__tests__/flagship-local-transition.test.ts',
      'src/tools/video-editor/examples/extensions/agent-tools-canary/index.ts',
      'src/tools/video-editor/examples/extensions/live-generated-frame-canary/index.ts',
      'src/tools/video-editor/examples/extensions/__tests__/flagship-local-m5-transition-mask-canary.integration.test.tsx',
      'src/tools/video-editor/examples/extensions/__tests__/m5-composed-examples.browser.test.tsx',
    ]),
    markerChecks: Object.freeze([
      {
        relPath:
          'src/tools/video-editor/examples/extensions/__tests__/m5-composed-examples.browser.test.tsx',
        label: 'material status coverage',
        patterns: Object.freeze([
          {
            regex:
              /state:\s*'missing'\s*\|\s*'pending'\s*\|\s*'resolved'\s*\|\s*'stale'\s*\|\s*'failed'/,
            message: 'missing the full material status coverage required for EX-03.',
          },
          {
            regex: /kind:\s*'materialize'/,
            message: 'missing the materialize repair action surface for EX-03.',
          },
        ]),
      },
      {
        relPath:
          'src/tools/video-editor/runtime/composition/materialRuntime.test.ts',
        label: 'stale planner action evidence',
        patterns: Object.freeze([
          {
            regex: /materialStatus:\s*'stale'/,
            message: 'missing stale material-status evidence for EX-03.',
          },
          {
            regex: /repairAction:\s*\{/,
            message: 'missing stale repair-action evidence for EX-03.',
          },
          {
            regex: /kind:\s*'materialize'/,
            message: 'missing stale planner materialize action evidence for EX-03.',
          },
          {
            regex: /materialSlot:\s*'transition-mask'/,
            message: 'missing transition-mask slot evidence for EX-03.',
          },
        ]),
      },
    ]),
  },
  {
    exampleId: 'EX-04',
    classifiedExamplePaths: Object.freeze([
      'src/examples/output-format-sidecar-composed-example.ts',
    ]),
    requiredDocRefPaths: Object.freeze([
      'src/examples/output-format-sidecar-composed-example.ts',
      'src/tools/video-editor/components/RouteCompletionDashboard/RouteCompletionDashboard.tsx',
      'src/tools/video-editor/examples/extensions/__tests__/m5-composed-examples.browser.test.tsx',
    ]),
    supportedDocRefPaths: Object.freeze([
      'src/examples/output-format-sidecar-composed-example.ts',
      'src/examples/metadata-json-output-example.ts',
      'src/examples/process-example.ts',
      'src/tools/video-editor/components/RouteCompletionDashboard/RouteCompletionDashboard.tsx',
      'src/tools/video-editor/examples/extensions/__tests__/m5-composed-examples.browser.test.tsx',
      'src/tools/video-editor/runtime/extensionSurface.test.ts',
      'src/tools/video-editor/runtime/renderPlanner.test.ts',
      'src/tools/video-editor/runtime/outputFormatRegistry.test.ts',
    ]),
    markerChecks: Object.freeze([
      {
        relPath: 'src/examples/output-format-sidecar-composed-example.ts',
        label: 'sidecar blocker and artifact-route evidence',
        patterns: Object.freeze([
          {
            regex: /graphPathMarker:\s*EX04_GRAPH_PATH_MARKER/,
            message: 'missing EX-04 graph-path marker evidence.',
          },
          {
            regex: /reason:\s*'process-dependent'/,
            message: 'missing the route-scoped sidecar blocker for EX-04.',
          },
          {
            regex: /routeConstraints:\s*EX04_ROUTE_CONSTRAINTS/,
            message: 'missing the sidecar artifact route-constraint evidence for EX-04.',
          },
          {
            regex:
              /artifact evidence route constraints must match the sidecar-export route\./,
            message: 'missing the conjunctive artifact-route guard for EX-04.',
          },
          {
            regex: /requiredProfiles:\s*\['sidecar'\]/,
            message: 'missing the route-completion required profile evidence for EX-04.',
          },
        ]),
      },
      {
        relPath:
          'src/tools/video-editor/examples/extensions/__tests__/m5-composed-examples.browser.test.tsx',
        label: 'graph-path and dashboard acceptance evidence',
        patterns: Object.freeze([
          {
            regex:
              /edge\.detail\?\.graphPathMarker === contract\.graphPathMarker/,
            message: 'missing graph-path marker assertions in EX-04 browser acceptance.',
          },
          {
            regex: /route-completion-profile-sidecar/,
            message: 'missing route-completion sidecar profile assertions for EX-04.',
          },
          {
            regex: /requires the Example Analyzer process/i,
            message: 'missing the route-scoped process blocker assertion for EX-04.',
          },
        ]),
      },
    ]),
  },
]);

function parseReleaseExampleSections(markdown) {
  const sections = new Map();
  const matches = [...markdown.matchAll(/^## (EX-\d+) - .+$/gm)];

  for (let i = 0; i < matches.length; i++) {
    const match = matches[i];
    const exampleId = match[1];
    const start = match.index ?? 0;
    const end = matches[i + 1]?.index ?? markdown.length;
    sections.set(exampleId, markdown.slice(start, end));
  }

  return sections;
}

function parseDocPathRef(pathRef) {
  const withLines = pathRef.match(/^(.*?):(\d+)(?:-(\d+))?$/);
  if (!withLines) {
    const barePath = pathRef.match(/^(src\/.*\.(?:ts|tsx|js|jsx|mjs|json|md))$/);
    if (!barePath) return null;
    return {
      relPath: barePath[1],
      startLine: null,
      endLine: null,
    };
  }
  const [, relPath, startLineRaw, endLineRaw] = withLines;
  return {
    relPath,
    startLine: Number(startLineRaw),
    endLine: Number(endLineRaw ?? startLineRaw),
  };
}

function extractDocPathRefs(sectionText) {
  return [...sectionText.matchAll(/`(src\/[^`]+\.(?:ts|tsx|js|jsx|mjs|json|md)(?::\d+(?:-\d+)?)?)`/g)]
    .map((match) => match[1]);
}

function validateDocPathRef(pathRef) {
  const parsed = parseDocPathRef(pathRef);
  if (!parsed) {
    return {
      ok: false,
      reason: `invalid path reference format "${pathRef}"`,
    };
  }

  const absPath = resolve(repoRoot, parsed.relPath);
  if (!existsSync(absPath)) {
    return {
      ok: false,
      reason: `broken ref "${pathRef}" resolves to a missing file`,
    };
  }

  const stat = statSync(absPath);
  if (!stat.isFile()) {
    return {
      ok: false,
      reason: `broken ref "${pathRef}" resolves to a non-file target`,
    };
  }

  const lineCount = readFileSync(absPath, 'utf8').split('\n').length;
  if (
    parsed.startLine != null
    && parsed.endLine != null
    && (
      parsed.startLine < 1
      || parsed.endLine < parsed.startLine
      || parsed.endLine > lineCount
    )
  ) {
    return {
      ok: false,
      reason:
        `broken ref "${pathRef}" points outside the file ` +
        `(line count ${lineCount})`,
    };
  }

  return { ok: true };
}

function validateReleaseExampleContracts(failures) {
  if (!existsSync(RELEASE_EXAMPLES_DOC_PATH)) {
    failures.push(
      `[release-example-contract] Release example doc is missing: ${relative(repoRoot, RELEASE_EXAMPLES_DOC_PATH)}`,
    );
    return;
  }

  const markdown = readFileSync(RELEASE_EXAMPLES_DOC_PATH, 'utf8');
  const sections = parseReleaseExampleSections(markdown);

  for (const contract of RELEASE_EXAMPLE_CONTRACTS) {
    const section = sections.get(contract.exampleId);
    if (!section) {
      failures.push(
        `[release-example-contract] ${contract.exampleId} is missing from ${relative(repoRoot, RELEASE_EXAMPLES_DOC_PATH)}.`,
      );
      continue;
    }

    const docPathRefs = extractDocPathRefs(section);
    const seenPaths = new Set(
      docPathRefs
        .map((pathRef) => parseDocPathRef(pathRef)?.relPath)
        .filter(Boolean),
    );
    const supportedDocRefPaths = contract.supportedDocRefPaths
      ?? contract.requiredDocRefPaths;

    for (const pathRef of docPathRefs) {
      const validated = validateDocPathRef(pathRef);
      if (!validated.ok) {
        failures.push(
          `[release-example-contract] ${contract.exampleId} ${validated.reason}.`,
        );
      }
    }

    for (const relPath of contract.requiredDocRefPaths) {
      if (!seenPaths.has(relPath)) {
        failures.push(
          `[release-example-contract] ${contract.exampleId} is missing the expected doc target path "${relPath}".`,
        );
      }
    }

    for (const relPath of seenPaths) {
      if (!supportedDocRefPaths.includes(relPath)) {
        failures.push(
          `[release-example-contract] ${contract.exampleId} references unsupported target path "${relPath}".`,
        );
      }
    }

    for (const markerCheck of contract.markerChecks) {
      const absPath = resolve(repoRoot, markerCheck.relPath);
      if (!existsSync(absPath)) {
        failures.push(
          `[release-example-contract] ${contract.exampleId} evidence target is missing: ${markerCheck.relPath}.`,
        );
        continue;
      }

      const content = readFileSync(absPath, 'utf8');
      for (const pattern of markerCheck.patterns) {
        if (!pattern.regex.test(content)) {
          failures.push(
            `[release-example-contract] ${contract.exampleId} ${markerCheck.label} failed: ${pattern.message}`,
          );
        }
      }
    }
  }
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

function run() {
  console.log(`${LABEL} Running in ${mode} mode…\n`);

  // ---- Step 1: Parse the supported/deferred matrix ----
  console.log(`${LABEL} Parsing supported/deferred matrix…`);

  let supportedRows = [];
  let deferredRows = [];
  let unsupportedRows = [];
  let releaseBlockingRows = [];

  try {
    const sdm = parseSupportedDeferredMatrix();
    supportedRows = sdm.supportedRows;
    deferredRows = sdm.deferredRows;
    unsupportedRows = sdm.unsupportedRows;
    releaseBlockingRows = sdm.releaseBlockingRows;

    console.log(
      `${LABEL} Parsed matrix: ${supportedRows.length} supported, ` +
        `${deferredRows.length} deferred, ${unsupportedRows.length} unsupported, ` +
        `${releaseBlockingRows.length} release-blocking row(s).`,
    );
  } catch (err) {
    console.error(`${LABEL} Failed to parse supported/deferred matrix: ${err.message}`);
    process.exit(1);
  }

  // ---- Step 2: Load governance data ----
  console.log(`${LABEL} Loading governance data…`);
  const { contractSurfaceMap, exportAllowlist } = loadGovernanceData();
  void contractSurfaceMap;
  void exportAllowlist;

  // ---- Step 3: Extract example references from supported rows ----
  console.log(`${LABEL} Extracting example references from supported rows…`);

  /** @type {ExampleRef[]} */
  const supportedExampleRefs = [];

  for (const row of supportedRows) {
    const refs = extractExampleRefs(row.evidence);
    for (const ref of refs) {
      supportedExampleRefs.push({
        refType: ref.type,
        refPath: ref.path,
        sourceRowId: row.rowId,
        classification: 'supported',
      });
    }
  }

  console.log(
    `${LABEL} Found ${supportedExampleRefs.length} example reference(s) in supported rows.`,
  );

  // ---- Step 4: Extract example references from deferred/unsupported rows ----
  /** @type {ExampleRef[]} */
  const unsupportedExampleRefs = [];

  for (const row of [...deferredRows, ...unsupportedRows, ...releaseBlockingRows]) {
    const refs = extractExampleRefs(row.evidence);
    for (const ref of refs) {
      unsupportedExampleRefs.push({
        refType: ref.type,
        refPath: ref.path,
        sourceRowId: row.rowId,
        classification: row.classification.replace(/[*_]{1,2}/g, '').toLowerCase().trim(),
      });
    }
  }

  if (unsupportedExampleRefs.length > 0) {
    console.log(
      `${LABEL} Found ${unsupportedExampleRefs.length} example reference(s) in deferred/unsupported rows — ` +
        `these will be flagged as unsupported docs candidates.`,
    );
  }

  // ---- Step 5: Verify supported example references ----
  console.log(`\n${LABEL} Verifying supported example references…`);

  /** @type {string[]} */
  const failures = [];
  /** @type {string[]} */
  const warnings = [];
  /** @type {Set<string>} */
  const docsSafeExampleIds = new Set();
  /** @type {Map<string, string>} */
  const failedExampleIds = new Map();

  for (const ref of supportedExampleRefs) {
    const refLabel = `${ref.refType}:${ref.refPath} (from row ${ref.sourceRowId})`;

    if (ref.refType === 'EX') {
      const absPath = resolveExPath(ref.refPath);
      const check = checkExFile(absPath);

      if (!check.exists) {
        const msg = `Supported example ${refLabel} does not exist: ${check.reason}`;
        failures.push(msg);
        failedExampleIds.set(ref.refPath, check.reason || 'missing');
        continue;
      }

      if (absPath.endsWith('.ts') || absPath.endsWith('.tsx')) {
        const boundaryCheck = checkImportBoundary(absPath);
        if (!boundaryCheck.clean) {
          for (const violation of boundaryCheck.violations) {
            const msg = `Supported example ${refLabel} has internal import: ${violation}`;
            if (isRelease) {
              failures.push(msg);
            } else {
              warnings.push(msg);
            }
          }
          if (isRelease) {
            failedExampleIds.set(ref.refPath, 'internal-imports');
            continue;
          }
        }
      }

      const exampleId = basename(absPath, '.ts').replace(/\.tsx$/, '');
      docsSafeExampleIds.add(exampleId);
      console.log(`${LABEL}   ✓ ${refLabel} → ${exampleId}`);
    }

    if (ref.refType === 'EXT') {
      const { absPath, isFile } = resolveExtPath(ref.refPath);

      if (isFile) {
        const check = checkExFile(absPath);

        if (!check.exists) {
          const msg = `Supported extension file ${refLabel} does not exist: ${check.reason}`;
          failures.push(msg);
          failedExampleIds.set(ref.refPath, check.reason || 'missing');
          continue;
        }

        const relToExt = relative(EXTENSIONS_DIR, absPath);
        const parts = relToExt.split('/');

        let exampleId;
        if (parts[0] === '__tests__') {
          const testFile = basename(absPath);
          exampleId = testFile
            .replace(/\.(test|integration)\.(ts|tsx)$/, '')
            .replace(/\.(ts|tsx)$/, '');
        } else {
          exampleId = parts[0];
        }

        if (exampleId && exampleId !== '..') {
          docsSafeExampleIds.add(exampleId);
        }
        console.log(`${LABEL}   ✓ ${refLabel} → ${exampleId} (file)`);
      } else {
        const check = checkExtDir(absPath);

        if (!check.exists) {
          const msg = `Supported extension directory ${refLabel} does not exist: ${check.reason}`;
          failures.push(msg);
          failedExampleIds.set(ref.refPath, check.reason || 'missing');
          continue;
        }

        const indexFile = resolve(absPath, 'index.ts');
        if (existsSync(indexFile)) {
          const boundaryCheck = checkImportBoundary(indexFile);
          if (!boundaryCheck.clean) {
            for (const violation of boundaryCheck.violations) {
              const msg = `Supported extension example ${refLabel} has internal import: ${violation}`;
              if (isRelease) {
                failures.push(msg);
              } else {
                warnings.push(msg);
              }
            }
            if (isRelease) {
              failedExampleIds.set(ref.refPath, 'internal-imports');
              continue;
            }
          }
        }

        const exampleId = basename(absPath);
        docsSafeExampleIds.add(exampleId);
        console.log(`${LABEL}   ✓ ${refLabel} → ${exampleId}`);
      }
    }
  }

  // ---- Step 6: Check for on-disk example files with no supported matrix row ----
  console.log(`\n${LABEL} Checking for unclassified on-disk examples…`);

  function listExampleFiles() {
    if (!existsSync(EXAMPLES_DIR)) return [];

    try {
      return readdirSync(EXAMPLES_DIR)
        .filter((f) => f.endsWith('.ts') || f.endsWith('.tsx'))
        .map((f) => resolve(EXAMPLES_DIR, f));
    } catch {
      return [];
    }
  }

  const onDiskExamples = listExampleFiles();
  const resolvedSupportedExPaths = new Set();
  const resolvedUnsupportedExPaths = new Set();
  const classifiedReleaseExamplePaths = new Set(
    RELEASE_EXAMPLE_CONTRACTS.flatMap((contract) =>
      contract.classifiedExamplePaths ?? []),
  );

  for (const ref of supportedExampleRefs) {
    if (ref.refType === 'EX') {
      resolvedSupportedExPaths.add(resolveExPath(ref.refPath));
    }
  }

  for (const ref of unsupportedExampleRefs) {
    if (ref.refType === 'EX') {
      resolvedUnsupportedExPaths.add(resolveExPath(ref.refPath));
    }
  }

  for (const absPath of onDiskExamples) {
    const relPath = relative(repoRoot, absPath);

    if (resolvedSupportedExPaths.has(absPath)) {
      continue;
    }

    if (classifiedReleaseExamplePaths.has(relPath)) {
      continue;
    }

    if (resolvedUnsupportedExPaths.has(absPath)) {
      const msg =
        `Example "${relPath}" exists on disk but corresponds to deferred/unsupported behaviour. ` +
        `This is an unsupported docs candidate. Either reclassify the matrix row or remove the example.`;
      failures.push(`[unsupported-docs-candidate] ${msg}`);
      continue;
    }

    const msg =
      `Example "${relPath}" exists on disk but has no corresponding row in the ` +
      `supported/deferred matrix. Add a supported row with EX: evidence, or ` +
      `document the file as deferred/unsupported.`;
    if (isRelease) {
      failures.push(`[unclassified-example] ${msg}`);
    } else {
      warnings.push(`[unclassified-example] ${msg}`);
    }
  }

  // ---- Step 7: Check for unsupported example refs that resolve to existing files ----
  console.log(`\n${LABEL} Checking unsupported-docs-candidate references…`);

  for (const ref of unsupportedExampleRefs) {
    const refLabel = `${ref.refType}:${ref.refPath} (${ref.classification} row ${ref.sourceRowId})`;

    let exists = false;

    if (ref.refType === 'EX') {
      const absPath = resolveExPath(ref.refPath);
      exists = existsSync(absPath) && statSync(absPath).isFile();
    } else if (ref.refType === 'EXT') {
      const { absPath, isFile } = resolveExtPath(ref.refPath);
      if (isFile) {
        exists = existsSync(absPath) && statSync(absPath).isFile();
      } else {
        exists = existsSync(absPath) && statSync(absPath).isDirectory();
      }
    }

    if (exists) {
      const msg =
        `Example ${refLabel} exists on disk but is classified as "${ref.classification}" ` +
        `in the supported/deferred matrix. This is an unsupported docs candidate — ` +
        `docs must not reference deferred/unsupported behaviour.`;
      failures.push(`[unsupported-docs-candidate] ${msg}`);
    }
  }

  // ---- Step 8: Validate EX-01 through EX-04 release-example contracts ----
  console.log(`\n${LABEL} Validating EX-01 through EX-04 release-example contracts…`);
  validateReleaseExampleContracts(failures);

  // ---- Step 9: Report ----
  console.log(`\n${LABEL} === Results ===\n`);

  if (failures.length > 0) {
    console.error(`${LABEL} FAILURES (${failures.length}):`);
    for (const f of failures) {
      console.error(`  ✗ ${f}`);
    }
  }

  if (warnings.length > 0) {
    console.warn(`${LABEL} WARNINGS (${warnings.length}):`);
    for (const w of warnings) {
      console.warn(`  ⚠ ${w}`);
    }
  }

  const sortedIds = [...docsSafeExampleIds].sort();
  const machineOutput = {
    docsSafeExampleIds: sortedIds,
    failedExampleIds: [...failedExampleIds.keys()].sort(),
    summary: {
      totalSupportedRefs: supportedExampleRefs.length,
      totalFailed: failedExampleIds.size,
      totalSafe: sortedIds.length,
      unsupportedCandidates: unsupportedExampleRefs.length,
      unclassifiedWarnings: warnings.filter((w) =>
        w.startsWith('[unclassified-example]'),
      ).length,
      releaseExampleFailures: failures.filter((failure) =>
        failure.startsWith('[release-example-contract]'),
      ).length,
    },
  };

  console.log(`\n${LABEL} Machine-readable output:`);
  console.log(JSON.stringify(machineOutput));

  if (failures.length > 0) {
    const failureText = failures.length === 1 ? 'failure' : 'failures';
    console.error(
      `\n${LABEL} ${mode.toUpperCase()} FAILED with ${failures.length} ${failureText}.`,
    );
    process.exitCode = 1;
  } else {
    console.log(
      `\n${LABEL} ${mode.toUpperCase()} PASSED. ` +
        `${sortedIds.length} docs-safe example(s), ${warnings.length} warning(s).`,
    );
  }
}

run();
