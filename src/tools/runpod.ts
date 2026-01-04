import { config } from '../config.js';
import { logger } from '../logger.js';
import type { RegisteredTool, ToolContext } from './types.js';
import type { ToolResult } from '../types.js';

const RUNPOD_API_URL = 'https://api.runpod.io/graphql';

/**
 * Make a GraphQL request to RunPod API
 */
async function runpodGraphQL(query: string, variables?: Record<string, unknown>): Promise<unknown> {
  const apiKey = config.runpod.apiKey;
  if (!apiKey) {
    throw new Error('RUNPOD_API_KEY not configured');
  }

  const response = await fetch(RUNPOD_API_URL, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${apiKey}`,
    },
    body: JSON.stringify({ query, variables }),
  });

  if (!response.ok) {
    throw new Error(`RunPod API error: ${response.status} ${response.statusText}`);
  }

  const result = await response.json();
  
  if (result.errors && result.errors.length > 0) {
    throw new Error(`RunPod GraphQL error: ${result.errors[0].message}`);
  }

  return result.data;
}

/**
 * Get all Arnold-managed pods (those with our prefix)
 */
async function getArnoldPods(): Promise<Array<{ id: string; name: string }>> {
  const query = `
    query {
      myself {
        pods {
          id
          name
        }
      }
    }
  `;

  const data = await runpodGraphQL(query) as { myself: { pods: Array<{ id: string; name: string }> } };
  const allPods = data.myself?.pods || [];
  const prefix = config.runpod.podPrefix;
  return allPods.filter(pod => pod.name.startsWith(prefix));
}

/**
 * Generate a unique pod name with Arnold prefix
 */
function generatePodName(): string {
  const prefix = config.runpod.podPrefix;
  const timestamp = new Date().toISOString().replace(/[-:T.Z]/g, '').substring(0, 14);
  const random = Math.random().toString(36).substring(2, 6);
  return `${prefix}${timestamp}_${random}`;
}

/**
 * Find GPU type ID from display name
 */
async function findGpuTypeId(gpuName: string): Promise<string | null> {
  const query = `
    query {
      gpuTypes {
        id
        displayName
      }
    }
  `;

  const data = await runpodGraphQL(query) as { 
    gpuTypes: Array<{ id: string; displayName: string }> 
  };
  
  const gpuTypes = data.gpuTypes || [];
  
  // Try exact match first, then partial match
  const gpu = gpuTypes.find(g => 
    g.displayName === gpuName || 
    g.id === gpuName ||
    g.displayName.toLowerCase().includes(gpuName.toLowerCase())
  );
  
  return gpu?.id || null;
}

// ============================================================================
// Tools
// ============================================================================

/**
 * Wait for a pod to be running and get its Jupyter URL
 */
async function waitForPodReady(podId: string, maxWaitMs = 300000): Promise<string | null> {
  const startTime = Date.now();
  const pollIntervalMs = 5000;

  while (Date.now() - startTime < maxWaitMs) {
    // Use the simpler query format that matches RunPod's API
    const query = `
      query {
        pod(input: {podId: "${podId}"}) {
          id
          desiredStatus
          runtime {
            ports {
              ip
              isIpPublic
              privatePort
              publicPort
              type
            }
          }
        }
      }
    `;

    const data = await runpodGraphQL(query) as {
      pod: {
        id: string;
        desiredStatus: string;
        runtime?: {
          ports?: Array<{
            ip: string;
            isIpPublic: boolean;
            privatePort: number;
            publicPort: number;
            type: string;
          }>;
        };
      } | null;
    };

    const pod = data.pod;
    
    if (!pod) {
      logger.debug('Pod not found yet', { podId });
      await new Promise(resolve => setTimeout(resolve, pollIntervalMs));
      continue;
    }
    
    logger.debug('Pod status', { podId, status: pod.desiredStatus, hasRuntime: !!pod.runtime });
    
    if (pod.desiredStatus === 'RUNNING' && pod.runtime?.ports) {
      // Find the Jupyter port (8888)
      const jupyterPort = pod.runtime.ports.find(p => p.privatePort === 8888);
      if (jupyterPort) {
        // RunPod proxies HTTP ports via their domain
        return `https://${podId}-8888.proxy.runpod.net`;
      }
    }

    await new Promise(resolve => setTimeout(resolve, pollIntervalMs));
  }

  return null;
}

/**
 * Create a new RunPod GPU instance
 */
export const createRunpodInstance: RegisteredTool = {
  name: 'create_runpod_instance',
  schema: {
    name: 'create_runpod_instance',
    description: 'Create a new RunPod GPU instance with the arnold_ prefix. Waits for it to launch and returns the Jupyter URL.',
    input_schema: {
      type: 'object' as const,
      properties: {},
    },
  },
  handler: async (_input: Record<string, never>, _context: ToolContext): Promise<ToolResult> => {
    if (!config.runpod.apiKey) {
      return {
        success: false,
        action: 'create_runpod_instance',
        error: 'RunPod API key not configured. Set RUNPOD_API_KEY environment variable.',
      };
    }

    try {
      const podName = generatePodName();

      // Look up GPU type ID from display name
      const gpuTypeId = await findGpuTypeId(config.runpod.gpuType);
      if (!gpuTypeId) {
        return {
          success: false,
          action: 'create_runpod_instance',
          error: `GPU type "${config.runpod.gpuType}" not found. Check RUNPOD_GPU_TYPE config.`,
        };
      }

      logger.info('Creating RunPod instance', { podName, gpuTypeId });

      const mutation = `
        mutation createPod($input: PodFindAndDeployOnDemandInput!) {
          podFindAndDeployOnDemand(input: $input) {
            id
            name
          }
        }
      `;

      // Startup script to launch Jupyter immediately
      const dockerStartCmd = `
cd /workspace && \
nohup jupyter lab --ip=0.0.0.0 --port=8888 --no-browser --allow-root \
  --ServerApp.token='' --ServerApp.password='' --ServerApp.root_dir=/workspace \
  > /var/log/jupyter.log 2>&1 &
      `.trim();

      const variables = {
        input: {
          name: podName,
          imageName: config.runpod.image,
          gpuTypeId: gpuTypeId,
          gpuCount: 1,
          cloudType: 'SECURE',
          volumeInGb: config.runpod.diskSizeGb,
          containerDiskInGb: config.runpod.containerDiskGb,
          ports: '22/tcp,8888/http',
          dockerArgs: dockerStartCmd,
        },
      };

      const data = await runpodGraphQL(mutation, variables) as { 
        podFindAndDeployOnDemand: { id: string; name: string } 
      };
      const pod = data.podFindAndDeployOnDemand;

      logger.info('RunPod instance created, waiting for it to start', { podId: pod.id, podName: pod.name });

      // Wait for the pod to be running
      const jupyterUrl = await waitForPodReady(pod.id);

      if (jupyterUrl) {
        logger.info('RunPod instance ready', { podId: pod.id, jupyterUrl });
        return {
          success: true,
          action: 'create_runpod_instance',
          pod_id: pod.id,
          pod_name: pod.name,
          message: `RunPod instance "${pod.name}" is ready!\n\n🔗 Jupyter: ${jupyterUrl}`,
        };
      } else {
        logger.warn('Pod created but Jupyter URL not available yet', { podId: pod.id });
        return {
          success: true,
          action: 'create_runpod_instance',
          pod_id: pod.id,
          pod_name: pod.name,
          message: `Created RunPod instance "${pod.name}" (ID: ${pod.id}). Pod is starting but Jupyter URL not available yet.`,
        };
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      logger.error('Failed to create RunPod instance', error instanceof Error ? error : undefined);
      return {
        success: false,
        action: 'create_runpod_instance',
        error: message,
      };
    }
  },
};

/**
 * Terminate all Arnold-managed RunPod instances
 */
export const terminateRunpodInstances: RegisteredTool = {
  name: 'terminate_runpod_instances',
  schema: {
    name: 'terminate_runpod_instances',
    description: 'Terminate all RunPod GPU instances created by Arnold (those with the arnold_ prefix).',
    input_schema: {
      type: 'object' as const,
      properties: {},
    },
  },
  handler: async (_input: Record<string, never>, _context: ToolContext): Promise<ToolResult> => {
    if (!config.runpod.apiKey) {
      return {
        success: false,
        action: 'terminate_runpod_instances',
        error: 'RunPod API key not configured. Set RUNPOD_API_KEY environment variable.',
      };
    }

    try {
      const arnoldPods = await getArnoldPods();

      if (arnoldPods.length === 0) {
        return {
          success: true,
          action: 'terminate_runpod_instances',
          terminated: [],
          count: 0,
          message: 'No Arnold-managed RunPod instances found.',
        };
      }

      logger.info('Terminating RunPod instances', { count: arnoldPods.length });

      const terminated: string[] = [];

      for (const pod of arnoldPods) {
        try {
          const mutation = `
            mutation terminatePod($input: PodTerminateInput!) {
              podTerminate(input: $input)
            }
          `;
          await runpodGraphQL(mutation, { input: { podId: pod.id } });
          terminated.push(pod.id);
          logger.info('Terminated pod', { podId: pod.id, podName: pod.name });
        } catch (error) {
          logger.error('Failed to terminate pod', error instanceof Error ? error : undefined, { podId: pod.id });
        }
      }

      return {
        success: true,
        action: 'terminate_runpod_instances',
        terminated,
        count: terminated.length,
        message: `Terminated ${terminated.length} RunPod instance(s).`,
      };
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      logger.error('Failed to terminate RunPod instances', error instanceof Error ? error : undefined);
      return {
        success: false,
        action: 'terminate_runpod_instances',
        error: message,
      };
    }
  },
};

/**
 * All RunPod-related tools
 */
export const runpodTools: RegisteredTool[] = [
  createRunpodInstance,
  terminateRunpodInstances,
];
