import type { CommandRegistry } from '@/tools/video-editor/runtime/commandRegistry.ts';
import type { VideoEditorProcessDescriptor } from '@/tools/video-editor/runtime/extensionSurface.ts';
import type { ProcessRoundtripRequest, ProcessRoundtripResult, ProcessStatus } from '@reigh/editor-sdk';

export interface ProcessCommandServices {
  invokeProcess: (request: ProcessRoundtripRequest) => Promise<ProcessRoundtripResult>;
}

export interface RegisterProcessCommandsOptions {
  commandRegistry: CommandRegistry;
  processes: readonly VideoEditorProcessDescriptor[];
  processStatuses?: readonly ProcessStatus[];
  services: ProcessCommandServices;
}

function processCommandId(processId: string, operationId: string): string {
  return `host.process.${processId}.${operationId}`;
}

function validateParams(schema: { required?: readonly string[] } | undefined, params: Record<string, unknown> | undefined): void {
  for (const key of schema?.required ?? []) {
    if (!params || !(key in params)) throw new Error(`Missing required process parameter "${key}".`);
  }
}

function statusBlocks(status: ProcessStatus | undefined): string | null {
  if (!status) return 'Process status is unavailable.';
  if (status.state === 'ready' || status.state === 'busy' || status.state === 'degraded') return null;
  return `Process is ${status.state}.`;
}

export function registerProcessOperationCommands({
  commandRegistry,
  processes,
  processStatuses = [],
  services,
}: RegisterProcessCommandsOptions) {
  const statuses = new Map(processStatuses.map((status) => [status.processId, status]));
  const handles = [];
  for (const process of processes) {
    for (const operation of process.operations) {
      const commandId = processCommandId(process.processId, operation.id);
      const status = statuses.get(process.processId);
      const unavailable = statusBlocks(status);
      commandRegistry.ingestCommandContribution('host.processes', {
        id: commandId as never,
        kind: 'command',
        command: commandId,
        label: operation.label,
        category: unavailable ? `Processes (${unavailable})` : 'Processes',
      });
      handles.push(commandRegistry.registerCommand('host.processes', commandId, async () => {
        const currentUnavailable = statusBlocks(statuses.get(process.processId));
        if (currentUnavailable) throw new Error(currentUnavailable);
        validateParams(operation.inputSchema as { required?: readonly string[] } | undefined, undefined);
        return services.invokeProcess({
          id: `${process.processId}:${operation.id}`,
          processId: process.processId,
          operationId: operation.id,
        });
      }, { label: operation.label, category: unavailable ? `Processes (${unavailable})` : 'Processes' }));
    }
  }
  return { dispose: () => handles.forEach((handle) => handle.dispose()) };
}
