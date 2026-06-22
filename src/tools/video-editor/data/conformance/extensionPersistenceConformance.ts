import { describe, expect, it } from 'vitest';
import {
  pushUnsupportedCapabilityDiagnostics,
  PROVIDER_CAPABILITY_EXTENSION_PROPOSALS_UNSUPPORTED,
  PROVIDER_CAPABILITY_EXTENSION_SETTINGS_UNSUPPORTED,
  PROVIDER_CAPABILITY_EXTENSION_STATE_UNSUPPORTED,
  type DataProvider,
  type ExtensionPersistenceScope,
  type ExtensionPersistenceService,
} from '@/tools/video-editor/data/DataProvider';
import type { ExtensionDiagnostic } from '@reigh/editor-sdk';

type ServiceFactory = (diagnostics: ExtensionDiagnostic[]) => ExtensionPersistenceService;

export interface ExtensionPersistenceConformanceOptions {
  readonly name: string;
  readonly scope?: ExtensionPersistenceScope;
  readonly createService: ServiceFactory;
  readonly reset?: () => void | Promise<void>;
  readonly seedCorruptSnapshot?: () => void | Promise<void>;
}

const DEFAULT_SCOPE: ExtensionPersistenceScope = {
  userId: 'conformance-user',
  timelineId: 'conformance-timeline',
};

async function withService<T>(
  createService: ServiceFactory,
  run: (service: ExtensionPersistenceService, diagnostics: ExtensionDiagnostic[]) => Promise<T>,
): Promise<T> {
  const diagnostics: ExtensionDiagnostic[] = [];
  const service = createService(diagnostics);
  await service.initialize();
  try {
    return await run(service, diagnostics);
  } finally {
    await service.dispose();
  }
}

function requireStateRepository(service: ExtensionPersistenceService) {
  expect(service.capabilities.state).toBe(true);
  expect(service.stateRepository).toBeTruthy();
  return service.stateRepository!;
}

export function defineExtensionPersistenceConformanceSuite(
  options: ExtensionPersistenceConformanceOptions,
): void {
  const scope = options.scope ?? DEFAULT_SCOPE;

  describe(`${options.name} extension persistence conformance`, () => {
    it('exposes full extension persistence capabilities for its scope', async () => {
      await options.reset?.();
      await withService(options.createService, async (service) => {
        expect(service.scope).toEqual(scope);
        expect(service.capabilities).toEqual({
          state: true,
          settings: true,
          proposals: true,
        });
        expect(service.stateRepository).toBeTruthy();
        expect(service.putSettings).toBeTypeOf('function');
        expect(service.createProposal).toBeTypeOf('function');
      });
    });

    it('supports extension state CRUD', async () => {
      await options.reset?.();
      await withService(options.createService, async (service) => {
        const repository = requireStateRepository(service);
        await repository.putEnablementState({
          extensionId: 'ext.state',
          enabled: true,
          lastToggledAt: '2026-06-22T00:00:00.000Z',
        });
        await expect(repository.getEnablementState('ext.state')).resolves.toEqual(
          expect.objectContaining({ extensionId: 'ext.state', enabled: true }),
        );

        await repository.deleteEnablementState('ext.state');
        await expect(repository.getEnablementState('ext.state')).resolves.toBeNull();
      });
    });

    it('supports settings CRUD with schema version preservation', async () => {
      await options.reset?.();
      await withService(options.createService, async (service) => {
        await service.putSettings?.({
          extensionId: 'ext.settings',
          schemaVersion: 7,
          values: { theme: 'dark' },
          lastWrittenAt: '2026-06-22T00:00:00.000Z',
        });

        await expect(service.getSettings?.('ext.settings')).resolves.toEqual(
          expect.objectContaining({
            extensionId: 'ext.settings',
            schemaVersion: 7,
            values: { theme: 'dark' },
          }),
        );

        await service.deleteSettings?.('ext.settings');
        await expect(service.getSettings?.('ext.settings')).resolves.toBeNull();
      });
    });

    it('supports proposal create, read, status update, and query', async () => {
      await options.reset?.();
      await withService(options.createService, async (service) => {
        const created = await service.createProposal?.({
          extensionId: 'ext.proposal',
          status: 'draft',
          payload: { operation: 'trim' },
          title: 'Trim clip',
        });
        const proposalId = typeof created === 'string' ? created : created?.id;
        expect(proposalId).toEqual(expect.any(String));

        await expect(service.getProposal?.(proposalId!)).resolves.toEqual(
          expect.objectContaining({ id: proposalId, status: 'draft' }),
        );

        await service.updateProposalStatus?.(
          proposalId!,
          'accepted',
          { acceptedBy: 'test' },
        );
        await expect(service.getProposal?.(proposalId!)).resolves.toEqual(expect.objectContaining({
          id: proposalId,
          status: 'accepted',
          detail: { acceptedBy: 'test' },
        }));

        await expect(service.queryProposals?.({
          extensionId: 'ext.proposal',
          statuses: ['accepted'],
        })).resolves.toEqual([
          expect.objectContaining({ id: proposalId, status: 'accepted' }),
        ]);
      });
    });

    it('hydrates persisted state for a later service instance', async () => {
      await options.reset?.();
      await withService(options.createService, async (service) => {
        await service.putSettings?.({
          extensionId: 'ext.hydrate',
          schemaVersion: 2,
          values: { volume: 0.5 },
          lastWrittenAt: '2026-06-22T00:00:00.000Z',
        });
      });

      await withService(options.createService, async (service) => {
        await expect(service.getSettings?.('ext.hydrate')).resolves.toEqual(
          expect.objectContaining({
            extensionId: 'ext.hydrate',
            schemaVersion: 2,
            values: { volume: 0.5 },
          }),
        );
      });
    });

    it('makes writes visible before the async flush completes', async () => {
      await options.reset?.();
      await withService(options.createService, async (service) => {
        const repository = requireStateRepository(service);
        await repository.putEnablementState({
          extensionId: 'ext.flush',
          enabled: true,
          lastToggledAt: '2026-06-22T00:00:00.000Z',
        });
        await expect(repository.getEnablementState('ext.flush')).resolves.toEqual(
          expect.objectContaining({ enabled: true }),
        );
      });
    });

    it('fails closed on corrupt persisted snapshots when a corrupt hook is provided', async () => {
      if (!options.seedCorruptSnapshot) {
        return;
      }

      await options.reset?.();
      await options.seedCorruptSnapshot();

      const diagnostics: ExtensionDiagnostic[] = [];
      const service = options.createService(diagnostics);
      await service.initialize();
      const repository = requireStateRepository(service);

      await expect(repository.getEnablementState('anything')).rejects.toThrow(/hydrat|parse/i);
      expect(diagnostics.some((diagnostic) =>
        diagnostic.code.includes('hydration') ||
        diagnostic.code.includes('future_schema') ||
        diagnostic.code.includes('parse'),
      )).toBe(true);

      await service.dispose();
    });
  });
}

export function expectUnsupportedExtensionPersistenceDiagnostics(
  provider: Pick<DataProvider, 'createExtensionPersistenceService'>,
  diagnostics: ExtensionDiagnostic[],
  providerName = 'test provider',
): void {
  expect(provider.createExtensionPersistenceService).toBeUndefined();

  pushUnsupportedCapabilityDiagnostics(diagnostics, undefined, providerName);

  expect(diagnostics.map((diagnostic) => diagnostic.code)).toEqual([
    PROVIDER_CAPABILITY_EXTENSION_STATE_UNSUPPORTED,
    PROVIDER_CAPABILITY_EXTENSION_SETTINGS_UNSUPPORTED,
    PROVIDER_CAPABILITY_EXTENSION_PROPOSALS_UNSUPPORTED,
  ]);
}
