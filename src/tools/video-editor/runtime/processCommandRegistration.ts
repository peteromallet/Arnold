import type { CommandRegistry } from '@/tools/video-editor/runtime/commandRegistry.ts';
import type { VideoEditorProcessDescriptor } from '@/tools/video-editor/runtime/extensionSurface.ts';
import type { ProcessRoundtripRequest, ProcessRoundtripResult } from '@/sdk/capabilities';
import type { ProcessStatus } from '@/sdk/video/families/processes';
import type { ProcessManager } from '@/tools/video-editor/runtime/processes/ProcessManager.ts';
import type { ProcessResultAttachRecord } from '@/tools/video-editor/runtime/composition/processResultAttach.ts';
import { createProcessResultAttachRecord } from '@/tools/video-editor/runtime/composition/processResultAttach.ts';

export interface ProcessCommandServices {
  invokeProcess: (request: ProcessRoundtripRequest) => Promise<ProcessRoundtripResult>;
}

export interface RegisterProcessCommandsOptions {
  commandRegistry: CommandRegistry;
  processes: readonly VideoEditorProcessDescriptor[];
  processStatuses?: readonly ProcessStatus[];
  /** Legacy execution bridge; used only when processManager is not supplied. */
  services?: ProcessCommandServices;
  /** Provider-owned process manager for trusted local execution with attach recording. */
  processManager?: ProcessManager;
  /** Records a process result attach record before returned refs can be consumed. */
  recordProcessResultAttach?: (record: ProcessResultAttachRecord) => void;
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
  processManager,
  recordProcessResultAttach,
}: RegisterProcessCommandsOptions) {
  const statuses = new Map(processStatuses.map((status) => [status.processId, status]));
  const descriptorByProcessId = new Map(processes.map((d) => [d.processId, d]));
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

        const request: ProcessRoundtripRequest = {
          id: `${process.processId}:${operation.id}`,
          processId: process.processId,
          operationId: operation.id,
        };

        // When a process manager is available, execute through it and record
        // attach evidence before any returned refs can be consumed.
        if (processManager && recordProcessResultAttach) {
          const result = await processManager.execute(request);
          const descriptor = descriptorByProcessId.get(process.processId);
          if (descriptor) {
            const attachRecord = createProcessResultAttachRecord({
              processDescriptor: descriptor,
              result,
            });
            recordProcessResultAttach(attachRecord);
          }
          return result;
        }

        // Fallback: legacy execution bridge for callers that haven't wired
        // the process manager yet.
        if (services) {
          return services.invokeProcess(request);
        }

        throw new Error(
          `No execution bridge available for process "${process.processId}". ` +
          'Provide a processManager or services.invokeProcess.',
        );
      }, { label: operation.label, category: unavailable ? `Processes (${unavailable})` : 'Processes' }));
    }
  }
  return { dispose: () => handles.forEach((handle) => handle.dispose()) };
}
