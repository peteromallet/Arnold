import { describe, expect, it } from 'vitest';
import { InMemoryDataProvider } from '@/tools/video-editor/testing/InMemoryDataProvider';
import {
  expectUnsupportedExtensionPersistenceDiagnostics,
  defineExtensionPersistenceConformanceSuite,
} from '@/tools/video-editor/data/conformance/extensionPersistenceConformance';
import type { ExtensionPersistenceScope } from '@/tools/video-editor/data/DataProvider';
import type { ExtensionDiagnostic } from '@reigh/editor-sdk';

const scope: ExtensionPersistenceScope = {
  userId: 'memory-user',
  timelineId: 'memory-timeline',
};

const provider = new InMemoryDataProvider();

defineExtensionPersistenceConformanceSuite({
  name: 'InMemoryDataProvider',
  scope,
  reset: () => provider.clearExtensionPersistence(),
  seedCorruptSnapshot: () => provider.seedExtensionPersistenceSnapshot(scope, '{not-json'),
  createService: (diagnostics) =>
    provider.createExtensionPersistenceService(scope, diagnostics),
});

describe('unsupported extension persistence conformance helper', () => {
  it('emits normalized unsupported diagnostics for providers without a factory', () => {
    const diagnostics: ExtensionDiagnostic[] = [];
    expectUnsupportedExtensionPersistenceDiagnostics({}, diagnostics, 'unsupported provider');
    expect(diagnostics).toHaveLength(3);
  });
});
