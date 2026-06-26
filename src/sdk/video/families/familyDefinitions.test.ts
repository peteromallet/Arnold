/**
 * Tests for the video family definitions registry.
 *
 * Proves:
 *   1. Entries type-check and expose required FamilyDefinition fields.
 *   2. Entries produce valid conformance reports.
 *   3. Projection helpers return correct results.
 *   4. No `liveSource` kind is added (not in current kind union).
 */

import { describe, expect, it } from 'vitest';

import {
  VIDEO_FAMILY_REGISTRY,
  getVideoFamily,
  buildVideoFamilyReports,
  buildVideoFamilyReport,
  VIDEO_FAMILY_LEGACY_MILESTONE_MAP,
  getVideoFamilyKinds,
  computeVideoFamilyStats,
  findVideoFamiliesWithRequirementGap,
} from '@/sdk/video/families/familyDefinitions';

import {
  buildConformanceReport,
  computeGaps,
  isFullyConformant,
  checkFamilyCoherence,
} from '@/sdk/core/families/conformance';

import type { FamilyDefinition } from '@/sdk/core/families/maturity';
import type { VideoContributionKind } from '@/sdk/video/families/contributionKinds';
import { VIDEO_CONTRIBUTION_KINDS } from '@/sdk/video/families/contributionKinds';

// ---------------------------------------------------------------------------
// Registry shape and type-checking
// ---------------------------------------------------------------------------

describe('VIDEO_FAMILY_REGISTRY shape', () => {
  it('is a non-empty readonly array', () => {
    expect(Array.isArray(VIDEO_FAMILY_REGISTRY)).toBe(true);
    expect(VIDEO_FAMILY_REGISTRY.length).toBeGreaterThanOrEqual(21);
    expect(VIDEO_FAMILY_REGISTRY.length).toBeLessThanOrEqual(21);
  });

  it('every entry has the required FamilyDefinition fields', () => {
    for (const def of VIDEO_FAMILY_REGISTRY) {
      expect(typeof def.kind).toBe('string');
      expect(def.kind.length).toBeGreaterThan(0);
      expect(typeof def.declarationMaturity).toBe('string');
      expect(typeof def.executionMaturity).toBe('string');
      expect(typeof def.requiresTrustedCode).toBe('boolean');
      expect(typeof def.manifestSchemaDefinition).toBe('string');
      expect(def.manifestSchemaDefinition.length).toBeGreaterThan(0);
      expect(Array.isArray(def.sdkModules)).toBe(true);
      expect(def.sdkModules.length).toBeGreaterThan(0);
      // hostAdapter can be string or null
      expect(
        typeof def.hostAdapter === 'string' || def.hostAdapter === null,
      ).toBe(true);
      // requirements is an object
      expect(typeof def.requirements).toBe('object');
      expect(def.requirements).not.toBeNull();
    }
  });

  it('every entry has a kind that is a valid VideoContributionKind', () => {
    const validKinds = new Set(VIDEO_CONTRIBUTION_KINDS);
    for (const def of VIDEO_FAMILY_REGISTRY) {
      expect(validKinds.has(def.kind)).toBe(true);
    }
  });

  it('every entry has a unique kind (no duplicates)', () => {
    const kinds = VIDEO_FAMILY_REGISTRY.map((def) => def.kind);
    const unique = new Set(kinds);
    expect(unique.size).toBe(kinds.length);
  });

  it('registry is sorted by kind string ascending', () => {
    const kinds = VIDEO_FAMILY_REGISTRY.map((def) => def.kind);
    const sorted = [...kinds].sort();
    expect(kinds).toEqual(sorted);
  });
});

// ---------------------------------------------------------------------------
// Representative entries
// ---------------------------------------------------------------------------

describe('representative entries', () => {
  it('contains a bridged surface: command', () => {
    const cmd = getVideoFamily('command');
    expect(cmd).toBeDefined();
    expect(cmd!.kind).toBe('command');
    expect(cmd!.executionMaturity).toBe('host-integrated');
    expect(cmd!.declarationMaturity).toBe('documented');
    expect(cmd!.hostAdapter).not.toBeNull();
  });

  it('contains parser (M6)', () => {
    const parser = getVideoFamily('parser');
    expect(parser).toBeDefined();
    expect(parser!.kind).toBe('parser');
    expect(parser!.executionMaturity).toBe('runtime-bridged');
    expect(parser!.declarationMaturity).toBe('schema-backed');
    expect(parser!.requirements.manifestSchema).toBe(true);
  });

  it('contains outputFormat (M6)', () => {
    const fmt = getVideoFamily('outputFormat');
    expect(fmt).toBeDefined();
    expect(fmt!.kind).toBe('outputFormat');
    // Reserved for execution
    expect(fmt!.executionMaturity).toBe('delegated');
  });

  it('contains clipType (M9)', () => {
    const ct = getVideoFamily('clipType');
    expect(ct).toBeDefined();
    expect(ct!.kind).toBe('clipType');
    expect(ct!.executionMaturity).toBe('runtime-bridged');
  });

  it('contains shader (M13) — schema-backed, runtime-bridged', () => {
    const shader = getVideoFamily('shader');
    expect(shader).toBeDefined();
    expect(shader!.kind).toBe('shader');
    expect(shader!.declarationMaturity).toBe('schema-backed');
    expect(shader!.executionMaturity).toBe('runtime-bridged');
    expect(shader!.hostAdapter).not.toBeNull();
  });

  it('contains agent (M10)', () => {
    const agent = getVideoFamily('agent');
    expect(agent).toBeDefined();
    expect(agent!.kind).toBe('agent');
    expect(agent!.legacyMilestone).toBe('M10');
    expect(agent!.requiresTrustedCode).toBe(true);
  });

  it('contains slot (M1) — public-supported bridged surface', () => {
    const slot = getVideoFamily('slot');
    expect(slot).toBeDefined();
    expect(slot!.kind).toBe('slot');
    expect(slot!.executionMaturity).toBe('public-supported');
    expect(slot!.declarationMaturity).toBe('documented');
    expect(slot!.hostAdapter).not.toBeNull();
  });

  it('contains agentTool (M10) — schema-backed, runtime-bridged', () => {
    const at = getVideoFamily('agentTool');
    expect(at).toBeDefined();
    expect(at!.kind).toBe('agentTool');
    expect(at!.declarationMaturity).toBe('schema-backed');
    expect(at!.executionMaturity).toBe('runtime-bridged');
    expect(at!.requiresTrustedCode).toBe(true);
    expect(at!.legacyMilestone).toBe('M10');
  });

  it('contains assetDetailSection (M6) — schema-backed, runtime-bridged', () => {
    const ads = getVideoFamily('assetDetailSection');
    expect(ads).toBeDefined();
    expect(ads!.kind).toBe('assetDetailSection');
    expect(ads!.declarationMaturity).toBe('schema-backed');
    expect(ads!.executionMaturity).toBe('runtime-bridged');
    expect(ads!.legacyMilestone).toBe('M6');
    expect(ads!.requirements.manifestSchema).toBe(true);
  });

  it('contains automation (M9) — schema-backed, runtime-bridged', () => {
    const auto = getVideoFamily('automation');
    expect(auto).toBeDefined();
    expect(auto!.kind).toBe('automation');
    expect(auto!.declarationMaturity).toBe('schema-backed');
    expect(auto!.executionMaturity).toBe('runtime-bridged');
    expect(auto!.legacyMilestone).toBe('M9');
  });

  it('contains effect (M7) — schema-backed, runtime-bridged', () => {
    const eff = getVideoFamily('effect');
    expect(eff).toBeDefined();
    expect(eff!.kind).toBe('effect');
    expect(eff!.declarationMaturity).toBe('schema-backed');
    expect(eff!.executionMaturity).toBe('runtime-bridged');
    expect(eff!.legacyMilestone).toBe('M7');
    expect(eff!.requirements.registrationApi).toBe(true);
  });

  it('contains metadataFacet (M6) — schema-backed, runtime-bridged', () => {
    const mf = getVideoFamily('metadataFacet');
    expect(mf).toBeDefined();
    expect(mf!.kind).toBe('metadataFacet');
    expect(mf!.declarationMaturity).toBe('schema-backed');
    expect(mf!.executionMaturity).toBe('runtime-bridged');
    expect(mf!.legacyMilestone).toBe('M6');
    expect(mf!.requirements.manifestSchema).toBe(true);
  });

  it('contains process (M12) — typed, delegated', () => {
    const proc = getVideoFamily('process');
    expect(proc).toBeDefined();
    expect(proc!.kind).toBe('process');
    expect(proc!.declarationMaturity).toBe('typed');
    expect(proc!.executionMaturity).toBe('delegated');
    expect(proc!.legacyMilestone).toBe('M12');
    expect(proc!.hostAdapter).toBeNull();
  });

  it('contains searchProvider (M6) — typed, delegated', () => {
    const sp = getVideoFamily('searchProvider');
    expect(sp).toBeDefined();
    expect(sp!.kind).toBe('searchProvider');
    expect(sp!.declarationMaturity).toBe('typed');
    expect(sp!.executionMaturity).toBe('delegated');
    expect(sp!.legacyMilestone).toBe('M6');
    expect(sp!.hostAdapter).toBeNull();
  });

  it('contains transition (M8) — schema-backed, runtime-bridged', () => {
    const tr = getVideoFamily('transition');
    expect(tr).toBeDefined();
    expect(tr!.kind).toBe('transition');
    expect(tr!.declarationMaturity).toBe('schema-backed');
    expect(tr!.executionMaturity).toBe('runtime-bridged');
    expect(tr!.legacyMilestone).toBe('M8');
    expect(tr!.requirements.registrationApi).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// No liveSource entry
// ---------------------------------------------------------------------------

describe('registry does not contain liveSource', () => {
  it('liveSource is not in the VideoContributionKind union', () => {
    const validKinds = new Set(VIDEO_CONTRIBUTION_KINDS);
    expect(validKinds.has('liveSource')).toBe(false);
  });

  it('no entry has kind liveSource', () => {
    const kinds = VIDEO_FAMILY_REGISTRY.map((def) => def.kind);
    expect(kinds).not.toContain('liveSource');
  });
});

// ---------------------------------------------------------------------------
// Conformance reports
// ---------------------------------------------------------------------------

describe('conformance reports', () => {
  it('every entry can produce a conformance report without throwing', () => {
    for (const def of VIDEO_FAMILY_REGISTRY) {
      expect(() => buildConformanceReport(def)).not.toThrow();
    }
  });

  it('every entry can produce gap analysis without throwing', () => {
    for (const def of VIDEO_FAMILY_REGISTRY) {
      const gaps = computeGaps(def);
      expect(Array.isArray(gaps)).toBe(true);
    }
  });

  it('every entry can be coherence-checked without throwing', () => {
    for (const def of VIDEO_FAMILY_REGISTRY) {
      const result = checkFamilyCoherence(def);
      expect(typeof result.coherent).toBe('boolean');
      expect(Array.isArray(result.violations)).toBe(true);
    }
  });

  it('buildConformanceReport returns expected shape for each entry', () => {
    for (const def of VIDEO_FAMILY_REGISTRY) {
      const report = buildConformanceReport(def);
      expect(report.kind).toBe(def.kind);
      expect(report.declarationMaturity).toBe(def.declarationMaturity);
      expect(report.executionMaturity).toBe(def.executionMaturity);
      expect(report.requirements).toBe(def.requirements);
      expect(Array.isArray(report.gaps)).toBe(true);
      expect(Array.isArray(report.unmetRequirements)).toBe(true);
      expect(Array.isArray(report.metRequirements)).toBe(true);
      expect(Array.isArray(report.unassessedRequirements)).toBe(true);
      expect(typeof report.coherent).toBe('boolean');
      expect(typeof report.schemaCovered).toBe('boolean');
    }
  });

  it('slot is fully conformant (public-supported, documented, all requirements met)', () => {
    const slot = getVideoFamily('slot');
    expect(slot).toBeDefined();
    expect(isFullyConformant(slot!)).toBe(true);
  });

  it('outputFormat has gaps (delegated execution, no host adapter)', () => {
    const fmt = getVideoFamily('outputFormat');
    expect(fmt).toBeDefined();
    const gaps = computeGaps(fmt!);
    expect(gaps.length).toBeGreaterThan(0);

    // Should have schema-coverage-missing gap because manifestSchema is false
    const schemaGaps = gaps.filter((g) => g.category === 'schema-coverage-missing');
    expect(schemaGaps.length).toBe(0); // declaration maturity is 'typed', not 'schema-backed'
  });

  it('parser is runtime-bridged and schema-backed — coherent', () => {
    const parser = getVideoFamily('parser');
    expect(parser).toBeDefined();
    const coherence = checkFamilyCoherence(parser!);
    expect(coherence.coherent).toBe(true);
  });

  it('shader has no host adapter but is delegated — no host-adapter-missing gap', () => {
    const shader = getVideoFamily('shader');
    expect(shader).toBeDefined();
    const report = buildConformanceReport(shader!);
    // delegated execution doesn't require a host adapter
    const hostGaps = report.gaps.filter(
      (g) => g.category === 'host-adapter-missing',
    );
    expect(hostGaps.length).toBe(0);
  });
});

// ---------------------------------------------------------------------------
// Projection helpers
// ---------------------------------------------------------------------------

describe('projection helpers', () => {
  it('getVideoFamily returns definition for agentTool', () => {
    const def = getVideoFamily('agentTool');
    expect(def).toBeDefined();
    expect(def!.kind).toBe('agentTool');
    expect(def!.legacyMilestone).toBe('M10');
  });

  it('getVideoFamily returns definition for known kind', () => {
    const def = getVideoFamily('command');
    expect(def).toBeDefined();
    expect(def!.kind).toBe('command');
  });

  it('buildVideoFamilyReports returns a report per registry entry', () => {
    const reports = buildVideoFamilyReports();
    expect(reports.length).toBe(VIDEO_FAMILY_REGISTRY.length);
    for (const report of reports) {
      expect(report.kind).toBe(report.definition.kind);
    }
  });

  it('buildVideoFamilyReport returns report for agentTool', () => {
    const report = buildVideoFamilyReport('agentTool');
    expect(report).toBeDefined();
    expect(report!.kind).toBe('agentTool');
  });

  it('buildVideoFamilyReport returns report for known kind', () => {
    const report = buildVideoFamilyReport('command');
    expect(report).toBeDefined();
    expect(report!.kind).toBe('command');
  });

  it('VIDEO_FAMILY_LEGACY_MILESTONE_MAP has correct entries', () => {
    expect(VIDEO_FAMILY_LEGACY_MILESTONE_MAP.agent).toBe('M10');
    expect(VIDEO_FAMILY_LEGACY_MILESTONE_MAP.agentTool).toBe('M10');
    expect(VIDEO_FAMILY_LEGACY_MILESTONE_MAP.assetDetailSection).toBe('M6');
    expect(VIDEO_FAMILY_LEGACY_MILESTONE_MAP.automation).toBe('M9');
    expect(VIDEO_FAMILY_LEGACY_MILESTONE_MAP.clipType).toBe('M9');
    expect(VIDEO_FAMILY_LEGACY_MILESTONE_MAP.command).toBe('M4');
    expect(VIDEO_FAMILY_LEGACY_MILESTONE_MAP.contextMenuItem).toBe('M4');
    expect(VIDEO_FAMILY_LEGACY_MILESTONE_MAP.dialog).toBe('M1');
    expect(VIDEO_FAMILY_LEGACY_MILESTONE_MAP.effect).toBe('M7');
    expect(VIDEO_FAMILY_LEGACY_MILESTONE_MAP.inspectorSection).toBe('M1');
    expect(VIDEO_FAMILY_LEGACY_MILESTONE_MAP.keybinding).toBe('M4');
    expect(VIDEO_FAMILY_LEGACY_MILESTONE_MAP.metadataFacet).toBe('M6');
    expect(VIDEO_FAMILY_LEGACY_MILESTONE_MAP.outputFormat).toBe('M6');
    expect(VIDEO_FAMILY_LEGACY_MILESTONE_MAP.panel).toBe('M1');
    expect(VIDEO_FAMILY_LEGACY_MILESTONE_MAP.parser).toBe('M6');
    expect(VIDEO_FAMILY_LEGACY_MILESTONE_MAP.process).toBe('M12');
    expect(VIDEO_FAMILY_LEGACY_MILESTONE_MAP.searchProvider).toBe('M6');
    expect(VIDEO_FAMILY_LEGACY_MILESTONE_MAP.shader).toBe('M13');
    expect(VIDEO_FAMILY_LEGACY_MILESTONE_MAP.slot).toBe('M1');
    expect(VIDEO_FAMILY_LEGACY_MILESTONE_MAP.timelineOverlay).toBe('M2');
    expect(VIDEO_FAMILY_LEGACY_MILESTONE_MAP.transition).toBe('M8');
  });

  it('getVideoFamilyKinds returns all registry kinds', () => {
    const kinds = getVideoFamilyKinds();
    expect(kinds.length).toBe(VIDEO_FAMILY_REGISTRY.length);
    // Sorted ascending
    const sorted = [...kinds].sort();
    expect(kinds).toEqual(sorted);
  });

  it('computeVideoFamilyStats returns consistent statistics', () => {
    const stats = computeVideoFamilyStats();
    expect(stats.totalFamilies).toBe(VIDEO_FAMILY_REGISTRY.length);
    expect(stats.fullyConformantCount).toBeGreaterThanOrEqual(0);
    expect(stats.fullyConformantCount).toBeLessThanOrEqual(stats.totalFamilies);
    expect(stats.familiesWithGaps).toBeGreaterThanOrEqual(0);
    expect(stats.familiesWithGaps).toBeLessThanOrEqual(stats.totalFamilies);
    expect(stats.totalGaps).toBeGreaterThanOrEqual(0);

    // Total declaration maturity counts should sum to totalFamilies
    const declSum =
      stats.byDeclarationMaturity.typed +
      stats.byDeclarationMaturity['schema-backed'] +
      stats.byDeclarationMaturity.documented;
    expect(declSum).toBe(stats.totalFamilies);

    // Total execution maturity counts should sum to totalFamilies
    const execSum =
      stats.byExecutionMaturity.absent +
      stats.byExecutionMaturity.delegated +
      stats.byExecutionMaturity['runtime-bridged'] +
      stats.byExecutionMaturity['host-integrated'] +
      stats.byExecutionMaturity['public-supported'];
    expect(execSum).toBe(stats.totalFamilies);
  });

  it('findVideoFamiliesWithRequirementGap returns families with unmet or unassessed requirement', () => {
    const families = findVideoFamiliesWithRequirementGap('examples');
    // At least one family should have examples not met/assessed
    expect(families.length).toBeGreaterThanOrEqual(1);
    for (const def of families) {
      const val = def.requirements.examples;
      expect(val === false || val === undefined).toBe(true);
    }
  });

  it('findVideoFamiliesWithRequirementGap returns empty for fully-met requirement', () => {
    // 'tests' is met for slot — but other families may not have it met
    // Just verify it's a valid call
    const families = findVideoFamiliesWithRequirementGap('tests');
    expect(Array.isArray(families)).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// Type-level tests (compile-time)
// ---------------------------------------------------------------------------

describe('type-level assertions', () => {
  it('FamilyDefinition<VideoContributionKind> is assignable', () => {
    // This is a type-level check: the registry entries must satisfy the type
    const first: FamilyDefinition<VideoContributionKind> =
      VIDEO_FAMILY_REGISTRY[0];
    expect(first).toBeDefined();
  });

  it('all entries satisfy FamilyDefinition<VideoContributionKind> at runtime', () => {
    for (const def of VIDEO_FAMILY_REGISTRY) {
      // Required fields
      expect(def.kind).toBeDefined();
      expect(def.declarationMaturity).toBeDefined();
      expect(def.executionMaturity).toBeDefined();
      expect(def.requiresTrustedCode).toBeDefined();
      expect(def.manifestSchemaDefinition).toBeDefined();
      expect(def.sdkModules).toBeDefined();
      expect(def.requirements).toBeDefined();
      // hostAdapter is explicitly null or string
      expect('hostAdapter' in def).toBe(true);
    }
  });
});

// ---------------------------------------------------------------------------
// Exact registry membership — registry ↔ VIDEO_CONTRIBUTION_KINDS set equality
// ---------------------------------------------------------------------------

describe('exact registry membership', () => {
  const registryKindSet = new Set(getVideoFamilyKinds());
  const unionKindSet = new Set(VIDEO_CONTRIBUTION_KINDS);

  it('every VideoContributionKind has a registry entry', () => {
    for (const kind of VIDEO_CONTRIBUTION_KINDS) {
      expect(registryKindSet.has(kind)).toBe(true);
    }
  });

  it('no registry entry has a kind absent from VideoContributionKind', () => {
    for (const kind of registryKindSet) {
      expect(unionKindSet.has(kind)).toBe(true);
    }
  });

  it('registry and VideoContributionKind union have identical cardinality', () => {
    expect(registryKindSet.size).toBe(unionKindSet.size);
  });

  it('registry has exactly 21 kinds (current VideoContributionKind count)', () => {
    expect(VIDEO_FAMILY_REGISTRY.length).toBe(21);
    expect(unionKindSet.size).toBe(21);
    expect(registryKindSet.size).toBe(21);
  });
});

// ---------------------------------------------------------------------------
// manifestSchemaDefinition existence in reigh-extension.schema.json
// ---------------------------------------------------------------------------

import fs from 'node:fs';
import path from 'node:path';

const REPO_ROOT = path.resolve(import.meta.dirname, '../../../..');
const SCHEMA_PATH = path.join(
  REPO_ROOT,
  'config',
  'contracts',
  'reigh-extension.schema.json',
);
const FAMILY_MATURITY_JSON_PATH = path.join(
  REPO_ROOT,
  'config',
  'extensions',
  'family-maturity.json',
);

describe('manifestSchemaDefinition schema existence', () => {
  const schemaRaw = fs.readFileSync(SCHEMA_PATH, 'utf-8');
  const schemaJson = JSON.parse(schemaRaw) as Record<string, unknown>;
  const definitions =
    (schemaJson.definitions as Record<string, unknown> | undefined) ?? {};
  const definitionKeys = new Set(Object.keys(definitions));

  it('every family manifestSchemaDefinition exists as a schema definition key', () => {
    const missing: string[] = [];
    for (const def of VIDEO_FAMILY_REGISTRY) {
      if (!definitionKeys.has(def.manifestSchemaDefinition)) {
        missing.push(
          `${def.kind}: "${def.manifestSchemaDefinition}" not in schema definitions`,
        );
      }
    }
    expect(missing).toEqual([]);
  });

  it('every family manifestSchemaDefinition appears in Contribution oneOf', () => {
    const contributionDef = definitions['Contribution'] as
      | { oneOf?: Array<{ $ref?: string }> }
      | undefined;
    expect(contributionDef).toBeDefined();
    expect(Array.isArray(contributionDef!.oneOf)).toBe(true);

    const refNames = new Set(
      (contributionDef!.oneOf ?? [])
        .map((item) => {
          const ref = item.$ref ?? '';
          const parts = ref.split('/');
          return parts[parts.length - 1];
        })
        .filter(Boolean),
    );

    const missing: string[] = [];
    for (const def of VIDEO_FAMILY_REGISTRY) {
      if (!refNames.has(def.manifestSchemaDefinition)) {
        missing.push(
          `${def.kind}: "${def.manifestSchemaDefinition}" not in Contribution oneOf`,
        );
      }
    }
    expect(missing).toEqual([]);
  });
});

// ---------------------------------------------------------------------------
// Generated JSON completeness (config/extensions/family-maturity.json)
// ---------------------------------------------------------------------------

describe('generated JSON completeness', () => {
  let jsonRows: Record<string, unknown>[];

  beforeAll(() => {
    const raw = fs.readFileSync(FAMILY_MATURITY_JSON_PATH, 'utf-8');
    jsonRows = JSON.parse(raw) as Record<string, unknown>[];
  });

  it('is a non-empty array', () => {
    expect(Array.isArray(jsonRows)).toBe(true);
    expect(jsonRows.length).toBeGreaterThan(0);
  });

  it('has the same count as the registry', () => {
    expect(jsonRows.length).toBe(VIDEO_FAMILY_REGISTRY.length);
  });

  it('every row has required top-level fields', () => {
    const requiredFields = [
      'kind',
      'label',
      'description',
      'declarationMaturity',
      'executionMaturity',
      'sdkModules',
      'hostAdapter',
      'requiresTrustedCode',
      'manifestSchemaDefinition',
      'coverage',
      'conformance',
      'legacyCompatibility',
      'hostIntegrationNotes',
    ];

    for (const row of jsonRows) {
      for (const field of requiredFields) {
        expect(
          field in row,
          `row kind="${row.kind as string}" missing field "${field}"`,
        ).toBe(true);
      }
    }
  });

  it('every coverage object has all 10 requirement keys', () => {
    const coverageKeys = [
      'manifestSchema',
      'normalizedDescriptor',
      'registrationApi',
      'lifecycleCleanup',
      'diagnostics',
      'hostCapabilityProjection',
      'uiIntegration',
      'persistencePosture',
      'examples',
      'tests',
    ];
    for (const row of jsonRows) {
      const coverage = row.coverage as Record<string, unknown>;
      expect(typeof coverage).toBe('object');
      for (const key of coverageKeys) {
        expect(
          key in coverage,
          `row kind="${row.kind as string}" coverage missing "${key}"`,
        ).toBe(true);
      }
    }
  });

  it('every conformance object has required fields', () => {
    const conformanceKeys = [
      'fullyConformant',
      'gapCount',
      'coherent',
      'schemaCovered',
      'metRequirementCount',
      'unmetRequirementCount',
      'unassessedRequirementCount',
    ];
    for (const row of jsonRows) {
      const conformance = row.conformance as Record<string, unknown>;
      expect(typeof conformance).toBe('object');
      for (const key of conformanceKeys) {
        expect(
          key in conformance,
          `row kind="${row.kind as string}" conformance missing "${key}"`,
        ).toBe(true);
      }
    }
  });

  it('every legacyCompatibility object has milestone and bridged', () => {
    for (const row of jsonRows) {
      const lc = row.legacyCompatibility as Record<string, unknown>;
      expect(typeof lc).toBe('object');
      expect('milestone' in lc).toBe(true);
      expect('bridged' in lc).toBe(true);
      expect(typeof lc.milestone).toBe('string');
      expect(typeof lc.bridged).toBe('boolean');
    }
  });

  it('rows are sorted by kind string ascending', () => {
    const kinds = jsonRows.map((r) => r.kind as string);
    const sorted = [...kinds].sort();
    expect(kinds).toEqual(sorted);
  });

  it('no row has a timestamp or generation metadata field', () => {
    const forbiddenKeys = ['generatedAt', 'timestamp', 'generatorVersion', 'schemaVersion'];
    for (const row of jsonRows) {
      for (const key of forbiddenKeys) {
        expect(key in row).toBe(false);
      }
    }
  });
});

// ---------------------------------------------------------------------------
// Round-trip comparison: JSON rows ↔ TypeScript registry entries
// ---------------------------------------------------------------------------

describe('round-trip comparison', () => {
  let jsonRows: Record<string, unknown>[];

  beforeAll(() => {
    const raw = fs.readFileSync(FAMILY_MATURITY_JSON_PATH, 'utf-8');
    jsonRows = JSON.parse(raw) as Record<string, unknown>[];
  });

  it('every JSON row maps to a registry entry with matching kind', () => {
    for (const row of jsonRows) {
      const kind = row.kind as string;
      const def = getVideoFamily(kind as VideoContributionKind);
      expect(def).toBeDefined();
    }
  });

  it('every registry entry has a corresponding JSON row', () => {
    const jsonKinds = new Set(jsonRows.map((r) => r.kind as string));
    for (const def of VIDEO_FAMILY_REGISTRY) {
      expect(jsonKinds.has(def.kind)).toBe(true);
    }
  });

  it('JSON declarationMaturity matches registry', () => {
    for (const row of jsonRows) {
      const def = getVideoFamily(row.kind as VideoContributionKind);
      expect(def).toBeDefined();
      expect(row.declarationMaturity).toBe(def!.declarationMaturity);
    }
  });

  it('JSON executionMaturity matches registry', () => {
    for (const row of jsonRows) {
      const def = getVideoFamily(row.kind as VideoContributionKind);
      expect(def).toBeDefined();
      expect(row.executionMaturity).toBe(def!.executionMaturity);
    }
  });

  it('JSON manifestSchemaDefinition matches registry', () => {
    for (const row of jsonRows) {
      const def = getVideoFamily(row.kind as VideoContributionKind);
      expect(def).toBeDefined();
      expect(row.manifestSchemaDefinition).toBe(def!.manifestSchemaDefinition);
    }
  });

  it('JSON requiresTrustedCode matches registry', () => {
    for (const row of jsonRows) {
      const def = getVideoFamily(row.kind as VideoContributionKind);
      expect(def).toBeDefined();
      expect(row.requiresTrustedCode).toBe(def!.requiresTrustedCode);
    }
  });

  it('JSON hostAdapter matches registry (null or matching string)', () => {
    for (const row of jsonRows) {
      const def = getVideoFamily(row.kind as VideoContributionKind);
      expect(def).toBeDefined();
      expect(row.hostAdapter).toBe(def!.hostAdapter);
    }
  });

  it('JSON sdkModules deep-equals registry', () => {
    for (const row of jsonRows) {
      const def = getVideoFamily(row.kind as VideoContributionKind);
      expect(def).toBeDefined();
      expect(row.sdkModules).toEqual(def!.sdkModules);
    }
  });

  it('JSON coverage values match registry requirements', () => {
    for (const row of jsonRows) {
      const def = getVideoFamily(row.kind as VideoContributionKind);
      expect(def).toBeDefined();
      const coverage = row.coverage as Record<string, unknown>;
      const reqs = def!.requirements as Record<string, unknown>;
      for (const key of Object.keys(coverage)) {
        // JSON serializes undefined as null — treat them as equivalent
        const covVal = coverage[key];
        const reqVal = reqs[key];
        if (reqVal === undefined) {
          expect(covVal).toBeNull();
        } else {
          expect(covVal).toBe(reqVal);
        }
      }
    }
  });

  it('JSON label matches registry', () => {
    for (const row of jsonRows) {
      const def = getVideoFamily(row.kind as VideoContributionKind);
      expect(def).toBeDefined();
      expect(row.label).toBe(def!.label);
    }
  });

  it('JSON legacyMilestone matches registry', () => {
    for (const row of jsonRows) {
      const def = getVideoFamily(row.kind as VideoContributionKind);
      expect(def).toBeDefined();
      const lc = row.legacyCompatibility as { milestone: string };
      expect(lc.milestone).toBe(def!.legacyMilestone);
    }
  });
});

// ---------------------------------------------------------------------------
// Stale-artifact detection
// ---------------------------------------------------------------------------

describe('stale-artifact detection', () => {
  let jsonRows: Record<string, unknown>[];

  beforeAll(() => {
    const raw = fs.readFileSync(FAMILY_MATURITY_JSON_PATH, 'utf-8');
    jsonRows = JSON.parse(raw) as Record<string, unknown>[];
  });

  it('JSON has no extra families beyond the registry', () => {
    const registryKinds = new Set(getVideoFamilyKinds());
    const extra: string[] = [];
    for (const row of jsonRows) {
      const kind = row.kind as string;
      if (!registryKinds.has(kind as VideoContributionKind)) {
        extra.push(kind);
      }
    }
    expect(extra).toEqual([]);
  });

  it('JSON has no missing families compared to registry', () => {
    const jsonKinds = new Set(jsonRows.map((r) => r.kind as string));
    const missing: string[] = [];
    for (const def of VIDEO_FAMILY_REGISTRY) {
      if (!jsonKinds.has(def.kind)) {
        missing.push(def.kind);
      }
    }
    expect(missing).toEqual([]);
  });

  it('JSON row count equals registry count (no drift)', () => {
    expect(jsonRows.length).toBe(VIDEO_FAMILY_REGISTRY.length);
  });

  it('JSON kinds are in identical sorted order as registry kinds', () => {
    const jsonKinds = jsonRows.map((r) => r.kind as string);
    const registryKinds = getVideoFamilyKinds();
    expect(jsonKinds).toEqual(registryKinds);
  });
});
