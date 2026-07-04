import { describe, expect, it, vi } from 'vitest';
import { createCommandRegistry } from './commandRegistry';
import { registerProcessOperationCommands } from './processCommandRegistration';
import type { VideoEditorProcessDescriptor } from './extensionSurface';
import type { ProcessRoundtripResult } from '@reigh/editor-sdk';

function process(): VideoEditorProcessDescriptor {
  return {
    id: 'proc-contrib',
    extensionId: 'ext.process',
    processId: 'ffmpeg-local',
    label: 'FFmpeg',
    spec: {
      id: 'ffmpeg-local',
      label: 'FFmpeg',
      spawn: { command: 'ffmpeg' },
      protocol: 'stdio-jsonrpc',
      operations: [
        { id: 'render-mp4', label: 'Render MP4', inputSchema: { type: 'object', required: ['timeline'] } as any },
        { id: 'probe', label: 'Probe Media' },
      ],
    },
    protocol: 'stdio-jsonrpc',
    operations: [
      { id: 'render-mp4', label: 'Render MP4', inputSchema: { type: 'object', required: ['timeline'] } as any },
      { id: 'probe', label: 'Probe Media' },
    ],
    availableRoutes: ['sidecar-export'],
    requiredBy: [],
    blockers: [],
    nextActions: [],
  };
}

function completedResult(overrides: Partial<ProcessRoundtripResult> = {}): ProcessRoundtripResult {
  return {
    requestId: 'req-1',
    processId: 'ffmpeg-local',
    operationId: 'probe',
    status: 'completed',
    returnedMaterials: [],
    ...overrides,
  };
}

describe('registerProcessOperationCommands', () => {
  it('discovers process operations through the command registry with unavailable metadata', async () => {
    const registry = createCommandRegistry();
    registerProcessOperationCommands({
      commandRegistry: registry,
      processes: [process()],
      processStatuses: [{ processId: 'ffmpeg-local', state: 'not-installed', installHint: 'Install ffmpeg' }],
      services: { invokeProcess: vi.fn().mockResolvedValue(completedResult()) },
    });

    const snapshot = registry.getSnapshot();
    expect(snapshot.commands.map((cmd) => [cmd.commandId, cmd.category])).toEqual([
      ['host.process.ffmpeg-local.probe', 'Processes (Process is not-installed.)'],
      ['host.process.ffmpeg-local.render-mp4', 'Processes (Process is not-installed.)'],
    ]);
    await expect(registry.executeCommand('host.process.ffmpeg-local.probe')).resolves.toBe(false);
    expect(registry.getStatus('host.process.ffmpeg-local.probe').lastError).toBe('Process is not-installed.');
  });

  it('reports schema validation failures and dispatches successful operations through invokeProcess', async () => {
    const registry = createCommandRegistry();
    const invokeProcess = vi.fn().mockResolvedValue(completedResult());
    registerProcessOperationCommands({
      commandRegistry: registry,
      processes: [process()],
      processStatuses: [{ processId: 'ffmpeg-local', state: 'ready' }],
      services: { invokeProcess },
    });

    await expect(registry.executeCommand('host.process.ffmpeg-local.render-mp4')).resolves.toBe(false);
    expect(registry.getStatus('host.process.ffmpeg-local.render-mp4').lastError).toBe('Missing required process parameter "timeline".');

    await expect(registry.executeCommand('host.process.ffmpeg-local.probe')).resolves.toBe(true);
    expect(invokeProcess).toHaveBeenCalledWith({
      id: 'ffmpeg-local:probe',
      processId: 'ffmpeg-local',
      operationId: 'probe',
    });
  });
});
