import path from 'node:path';
import { fileURLToPath } from 'node:url';
import type { ProcessLifecycleState, ProcessSpec } from '@reigh/editor-sdk';

export const PROCESS_FIXTURE_PROCESS_ID = 'video-editor.process-fixture';
export const PROCESS_FIXTURE_OPERATION_ID = 'fixture.execute';
export const PROCESS_FIXTURE_MISSING_BINARY = '__reigh_process_fixture_missing_binary__';

export interface ProcessFixtureHealthStateConfig {
  readonly state: ProcessLifecycleState;
  readonly message?: string;
  readonly versionSemver?: string;
  readonly uptimeMs?: number;
  readonly errorCode?: string;
  readonly recoverable?: boolean;
  readonly operationId?: string;
  readonly reason?: string;
}

export interface ProcessFixtureDescriptorOptions {
  readonly processId?: string;
  readonly label?: string;
  readonly operationId?: string;
  readonly versionSemver?: string;
  readonly healthSequence?: readonly (ProcessLifecycleState | ProcessFixtureHealthStateConfig)[];
  readonly restartPolicy?: ProcessSpec['restartPolicy'];
  readonly spawnEnv?: Record<string, string>;
}

const currentFile = fileURLToPath(import.meta.url);
const fixtureDir = path.dirname(currentFile);
const repoRoot = path.resolve(fixtureDir, '..', '..', '..');
const fixtureScriptPath = path.resolve(fixtureDir, 'process-fixture.ts');
const tsxLoaderPath = path.resolve(repoRoot, 'node_modules', 'tsx', 'dist', 'loader.mjs');

export function createProcessFixtureDescriptor(
  options: ProcessFixtureDescriptorOptions = {},
): ProcessSpec {
  const processId = options.processId ?? PROCESS_FIXTURE_PROCESS_ID;
  const operationId = options.operationId ?? PROCESS_FIXTURE_OPERATION_ID;
  const versionSemver = options.versionSemver ?? '1.0.0';
  const healthSequence = options.healthSequence ?? ['starting', 'ready'];

  return {
    id: processId,
    label: options.label ?? 'Video Editor Process Fixture',
    description: 'Repo-controlled stdio JSON-RPC fixture for trusted local process runtime tests.',
    protocol: 'stdio-jsonrpc',
    spawn: {
      command: process.execPath,
      args: ['--import', tsxLoaderPath, fixtureScriptPath],
      cwd: repoRoot,
      env: {
        REIGH_PROCESS_FIXTURE_PROCESS_ID: processId,
        REIGH_PROCESS_FIXTURE_OPERATION_IDS: JSON.stringify([operationId]),
        REIGH_PROCESS_FIXTURE_VERSION_SEMVER: versionSemver,
        REIGH_PROCESS_FIXTURE_HEALTH_SEQUENCE: JSON.stringify(healthSequence),
        ...options.spawnEnv,
      },
    },
    healthCheck: 'health',
    shutdown: 'shutdown',
    restartPolicy: options.restartPolicy ?? 'never',
    version: { semver: versionSemver },
    operations: [
      {
        id: operationId,
        label: 'Fixture Execute',
        outputKinds: ['material', 'artifact', 'sidecar', 'diagnostic', 'tool-result'],
      },
    ],
  };
}

export function createNotInstalledProcessFixtureDescriptor(
  options: Omit<ProcessFixtureDescriptorOptions, 'spawnEnv'> = {},
): ProcessSpec {
  const descriptor = createProcessFixtureDescriptor(options);
  return {
    ...descriptor,
    spawn: {
      ...descriptor.spawn,
      command: PROCESS_FIXTURE_MISSING_BINARY,
      args: [],
      env: {},
    },
  };
}

export const processFixtureDescriptor = createProcessFixtureDescriptor();
