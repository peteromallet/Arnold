/**
 * process-example — M12 trusted local process declaration example.
 *
 * Demonstrates:
 *   1. A `ProcessContribution` declared in the extension manifest with a
 *      full `ProcessManifestEntry` describing a stdio-JSON-RPC process.
 *   2. Environment field declarations with platform defaults.
 *   3. Process operation specs declaring available operations and their
 *      input/output contracts.
 *
 * Process execution is deferred in V1 (invokeProcess returns a structured
 * not-available diagnostic). This example demonstrates the *declarative*
 * manifest shape that extensions use to describe trusted local processes.
 *
 * This file must NOT import from editor internals (src/tools/video-editor/*).
 * It imports only from the public @reigh/editor-sdk package surface.
 *
 * @publicContract
 */

import { defineExtension } from '@reigh/editor-sdk';
import type {
  ReighExtension,
  ExtensionContext,
  DisposeHandle,
  ProcessContribution,
  ProcessManifestEntry,
} from '@reigh/editor-sdk';

export type ProcessSpawnConfig = ProcessManifestEntry['spawn'];
export type ProcessEnvFieldSpec = NonNullable<ProcessManifestEntry['env']>[number];
export type ProcessOperationSpec = NonNullable<ProcessManifestEntry['operations']>[number];

// ---------------------------------------------------------------------------
// Process specification — declarative trusted-local process descriptor
// ---------------------------------------------------------------------------

const EXAMPLE_PROCESS_ENV: readonly ProcessEnvFieldSpec[] = [
  {
    key: 'MODEL_PATH',
    label: 'Model Path',
    description: 'Filesystem path to the ML model file.',
    required: true,
    secret: false,
    platformDefaults: {
      darwin: '/opt/models/example.mlmodel',
      linux: '/opt/models/example.mlmodel',
      win32: 'C:\\models\\example.mlmodel',
    },
  },
  {
    key: 'API_KEY',
    label: 'API Key',
    description: 'Optional API key for remote model fallback.',
    required: false,
    secret: true,
  },
];

const EXAMPLE_PROCESS_OPERATIONS: readonly ProcessOperationSpec[] = [
  {
    id: 'analyze',
    label: 'Analyze Frame',
    description: 'Analyze a single frame and return structured metadata.',
    inputSchema: {
      type: 'object',
      title: 'Analyze Input',
      properties: {
        frameIndex: { type: 'number', title: 'Frame Index' },
        region: {
          type: 'object',
          title: 'Region of Interest',
          properties: {
            x: { type: 'number', title: 'X' },
            y: { type: 'number', title: 'Y' },
            width: { type: 'number', title: 'Width' },
            height: { type: 'number', title: 'Height' },
          },
        },
      },
      required: ['frameIndex'],
    },
    outputKinds: ['diagnostic', 'tool-result'],
    requiredCapabilities: ['gpu'],
  },
  {
    id: 'health',
    label: 'Health Check',
    description: 'Returns process health status.',
    outputKinds: ['diagnostic'],
  },
];

const EXAMPLE_PROCESS_MANIFEST_ENTRY: ProcessManifestEntry = {
  id: 'example-analyzer',
  label: 'Example Analyzer Process',
  description:
    'A trusted local stdio-JSON-RPC process for frame analysis.',
  spawn: {
    command: 'example-analyzer',
    args: ['--mode', 'interactive'],
    env: {
      LOG_LEVEL: 'info',
    },
    cwd: '/tmp/example-analyzer',
  } as ProcessSpawnConfig,
  protocol: 'stdio-jsonrpc',
  healthCheck: 'health',
  restartPolicy: 'on-failure',
  version: { semver: '1.0.0' },
  env: EXAMPLE_PROCESS_ENV,
  operations: EXAMPLE_PROCESS_OPERATIONS,
};

// ---------------------------------------------------------------------------
// Extension
// ---------------------------------------------------------------------------

export const processExample: ReighExtension = defineExtension({
  manifest: {
    id: 'com.reigh.examples.process' as any,
    version: '1.0.0',
    label: 'Process Example',
    description:
      'Demonstrates trusted local process declaration via M12 SDK surface.',
    apiVersion: 1,
    contributions: [
      {
        id: 'example-process' as any,
        kind: 'process',
        label: 'Example Analyzer Process',
        order: 10,
        spec: EXAMPLE_PROCESS_MANIFEST_ENTRY,
      } as ProcessContribution,
    ],
    processes: [EXAMPLE_PROCESS_MANIFEST_ENTRY],
    messages: {
      activated: 'Process example activated (declaration-only in V1).',
      disposed: 'Process example disposed.',
    },
  },

  activate(ctx: ExtensionContext): DisposeHandle {
    ctx.chrome.toast(ctx.services.i18n.t('activated'), 'info');

    return {
      dispose(): void {
        ctx.chrome.toast(ctx.services.i18n.t('disposed'), 'info');
      },
    };
  },
});

/** Re-export types for SDK consumers. */
export type {
  ProcessContribution,
  ProcessManifestEntry,
};
