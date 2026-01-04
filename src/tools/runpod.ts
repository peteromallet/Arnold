import { config } from '../config.js';
import { logger } from '../logger.js';
import type { RegisteredTool, ToolContext } from './types.js';
import type { ToolResult } from '../types.js';

const RUNPOD_API_URL = 'https://api.runpod.io/graphql';

// RAM tiers to try in order (highest first - 72GB has lowest failure rate)
const RAM_TIERS_GB = [72, 60, 48, 32];

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

interface NetworkVolume {
  id: string;
  name: string;
  size: number;
  dataCenterId: string;
}

/**
 * Get all network volumes for the account
 */
async function getNetworkVolumes(): Promise<NetworkVolume[]> {
  const query = `
    query {
      myself {
        networkVolumes {
          id
          name
          size
          dataCenterId
        }
      }
    }
  `;

  const data = await runpodGraphQL(query) as { 
    myself: { networkVolumes: NetworkVolume[] } 
  };
  
  return data.myself?.networkVolumes || [];
}

/**
 * Find a network volume ID by name
 */
async function findNetworkVolumeId(volumeName: string): Promise<string | null> {
  const volumes = await getNetworkVolumes();
  const volume = volumes.find(v => v.name === volumeName);
  
  if (volume) {
    logger.debug('Found network volume', { name: volumeName, id: volume.id, size: volume.size });
  } else {
    logger.debug('Network volume not found', { name: volumeName, available: volumes.map(v => v.name) });
  }
  
  return volume?.id || null;
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

    try {
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
      
      logger.debug('Pod status', { podId, status: pod.desiredStatus, hasRuntime: !!pod.runtime, hasPorts: !!pod.runtime?.ports });
      
      if (pod.desiredStatus === 'RUNNING' && pod.runtime?.ports && pod.runtime.ports.length > 0) {
        // Pod is running with ports - return the Jupyter URL
        return `https://${podId}-8888.proxy.runpod.net`;
      }
    } catch (error) {
      logger.warn('Error polling pod status', { podId, error: error instanceof Error ? error.message : String(error) });
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

      logger.info('Creating RunPod instance', { podName, gpuTypeId, storageVolumes: config.runpod.storageVolumes });

      // Build list of network volume IDs to try (in order)
      const storageVolumesToTry: Array<{ name: string; id: string }> = [];
      for (const volumeName of config.runpod.storageVolumes) {
        const volumeId = await findNetworkVolumeId(volumeName);
        if (volumeId) {
          storageVolumesToTry.push({ name: volumeName, id: volumeId });
        } else {
          logger.warn(`Network volume "${volumeName}" not found, skipping`);
        }
      }

      if (storageVolumesToTry.length === 0) {
        logger.warn('No network volumes found, will use pod volume instead');
      }

      // Try RAM tiers from highest to lowest (72GB has lowest failure rate)
      // Within each RAM tier, try all storage volumes before falling back to lower RAM
      let pod: { id: string; name: string; desiredStatus: string; machineId?: string } | null = null;
      let lastError: string | null = null;
      let usedRamTier: number | undefined = undefined;
      let usedStorageVolume: string | undefined = undefined;
      const failedPodIds: string[] = []; // Track pods created without machines (to terminate later)

      // Strategy: Try each RAM tier across ALL storage volumes before falling back to next tier
      // This prioritizes 72GB machines (lowest failure rate) over 60GB (higher failure rate)
      ramLoop: for (const ramTier of RAM_TIERS_GB) {
        logger.info(`Trying ${ramTier}GB RAM across all storage volumes...`);
        
        // If we have network volumes, try each one
        const volumesToTry = storageVolumesToTry.length > 0 
          ? storageVolumesToTry 
          : [{ name: 'pod-volume', id: '' }]; // Fallback to pod volume if no network volumes

        for (const volume of volumesToTry) {
          try {
            const useNetworkVolume = volume.id !== '';
            logger.info(`Trying: ${volume.name}, ${ramTier}GB RAM`, { podName, gpuTypeId, useNetworkVolume });

            // Build mutation based on whether we're using network volume or pod volume
            const volumeParams = useNetworkVolume
              ? `networkVolumeId: "${volume.id}"\n                  volumeMountPath: "${config.runpod.volumeMountPath}"`
              : `volumeInGb: ${config.runpod.diskSizeGb}\n                  volumeMountPath: "${config.runpod.volumeMountPath}"`;

            const mutation = `
              mutation {
                podFindAndDeployOnDemand(input: {
                  name: "${podName}"
                  imageName: "${config.runpod.image}"
                  gpuTypeId: "${gpuTypeId}"
                  gpuCount: 1
                  cloudType: SECURE
                  containerDiskInGb: ${config.runpod.containerDiskGb}
                  ${volumeParams}
                  minVcpuCount: 8
                  minMemoryInGb: ${ramTier}
                  ports: "22/tcp,8888/http"
                }) {
                  id
                  name
                  desiredStatus
                  imageName
                  machineId
                }
              }
            `;

            const data = await runpodGraphQL(mutation) as { 
              podFindAndDeployOnDemand: { id: string; name: string; desiredStatus: string; machineId?: string } | null
            };
            
            const result = data.podFindAndDeployOnDemand;
            
            if (result?.id) {
              // Check if a machine was actually assigned
              if (result.machineId) {
                // Success! Machine was assigned
                pod = result;
                usedRamTier = ramTier;
                usedStorageVolume = volume.name;
                logger.info(`Success: ${volume.name}, ${ramTier}GB RAM, machine ${result.machineId}`, { podId: pod.id });
                break ramLoop;
              } else {
                // Pod created but no machine available - terminate it and try next config
                logger.warn(`No machine available for ${volume.name}/${ramTier}GB, terminating orphan pod ${result.id}`);
                failedPodIds.push(result.id);
                
                // Terminate the orphan pod
                try {
                  const terminateMutation = `mutation { podTerminate(input: {podId: "${result.id}"}) }`;
                  await runpodGraphQL(terminateMutation);
                  logger.info(`Terminated orphan pod ${result.id}`);
                } catch (termError) {
                  logger.warn(`Failed to terminate orphan pod ${result.id}`, { error: termError });
                }
                
                lastError = `No machine available for ${volume.name}/${ramTier}GB`;
              }
            } else {
              lastError = 'No pod ID returned';
              logger.warn(`${volume.name}/${ramTier}GB: no pod returned, trying next config`);
            }
          } catch (error) {
            const message = error instanceof Error ? error.message : String(error);
            lastError = message;
            logger.warn(`${volume.name}/${ramTier}GB failed: ${message}, trying next config`);
          }
        }
        
        if (!pod && ramTier !== RAM_TIERS_GB[RAM_TIERS_GB.length - 1]) {
          logger.warn(`${ramTier}GB RAM not available in any storage, trying ${RAM_TIERS_GB[RAM_TIERS_GB.indexOf(ramTier) + 1]}GB...`);
        }
      }
      
      if (!pod || !pod.id) {
        logger.error('Pod creation failed - all configurations exhausted', { lastError, failedPodIds });
        return {
          success: false,
          action: 'create_runpod_instance',
          error: `Pod creation failed after trying all configurations (storages × 72/60/48/32 GB). No 4090s available. Last error: ${lastError}`,
        };
      }

      logger.info('RunPod instance created, waiting for it to start', { 
        podId: pod.id, 
        podName: pod.name, 
        status: pod.desiredStatus, 
        ramTier: usedRamTier,
        storageVolume: usedStorageVolume,
        machineId: pod.machineId 
      });

      // Wait for the pod to be running
      const jupyterUrl = await waitForPodReady(pod.id);

      if (jupyterUrl) {
        logger.info('RunPod instance ready', { podId: pod.id, jupyterUrl, ramTier: usedRamTier, storage: usedStorageVolume });
        return {
          success: true,
          action: 'create_runpod_instance',
          pod_id: pod.id,
          pod_name: pod.name,
          ram_gb: usedRamTier,
          message: `RunPod instance "${pod.name}" is ready! (${usedStorageVolume}, ${usedRamTier}GB RAM)\n\n🔗 Jupyter: ${jupyterUrl}`,
        };
      } else {
        // Still return success since pod was created with a machine
        logger.warn('Pod created but Jupyter URL not available yet', { podId: pod.id, ramTier: usedRamTier, storage: usedStorageVolume });
        return {
          success: true,
          action: 'create_runpod_instance',
          pod_id: pod.id,
          pod_name: pod.name,
          ram_gb: usedRamTier,
          message: `Created RunPod instance "${pod.name}" (${usedStorageVolume}, ${usedRamTier}GB RAM).\n\nPod is starting - check RunPod dashboard for status.\n🔗 Jupyter (when ready): https://${pod.id}-8888.proxy.runpod.net`,
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
            mutation {
              podTerminate(input: {podId: "${pod.id}"})
            }
          `;
          await runpodGraphQL(mutation);
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
 * List all RunPod instances with detailed status
 */
export const listRunpodInstances: RegisteredTool = {
  name: 'list_runpod_instances',
  schema: {
    name: 'list_runpod_instances',
    description: 'List all RunPod GPU instances with detailed status information.',
    input_schema: {
      type: 'object' as const,
      properties: {},
    },
  },
  handler: async (_input: Record<string, never>, _context: ToolContext): Promise<ToolResult> => {
    if (!config.runpod.apiKey) {
      return {
        success: false,
        action: 'list_runpod_instances',
        error: 'RunPod API key not configured. Set RUNPOD_API_KEY environment variable.',
      };
    }

    try {
      const query = `
        query {
          myself {
            pods {
              id
              name
              desiredStatus
              lastStatusChange
              imageName
              machineId
              costPerHr
              machine {
                gpuDisplayName
              }
              runtime {
                uptimeInSeconds
                ports {
                  ip
                  isIpPublic
                  privatePort
                  publicPort
                  type
                }
                gpus {
                  id
                  gpuUtilPercent
                  memoryUtilPercent
                }
              }
            }
          }
        }
      `;

      const data = await runpodGraphQL(query) as {
        myself: {
          pods: Array<{
            id: string;
            name: string;
            desiredStatus: string;
            lastStatusChange: string;
            imageName: string;
            machineId: string;
            costPerHr: number;
            machine?: { gpuDisplayName: string };
            runtime?: {
              uptimeInSeconds: number;
              ports?: Array<{
                ip: string;
                isIpPublic: boolean;
                privatePort: number;
                publicPort: number;
                type: string;
              }>;
              gpus?: Array<{
                id: string;
                gpuUtilPercent: number;
                memoryUtilPercent: number;
              }>;
            };
          }>;
        };
      };

      const allPods = data.myself?.pods || [];
      const prefix = config.runpod.podPrefix;
      
      const instances = allPods.map(pod => ({
        id: pod.id,
        name: pod.name,
        status: pod.desiredStatus,
        gpu: pod.machine?.gpuDisplayName || 'Unknown',
        cost_per_hour: pod.costPerHr || 0,
        uptime_minutes: Math.round((pod.runtime?.uptimeInSeconds || 0) / 60),
        has_ports: !!(pod.runtime?.ports && pod.runtime.ports.length > 0),
        port_8888: pod.runtime?.ports?.find(p => p.privatePort === 8888)?.publicPort || null,
        is_arnold_managed: pod.name.startsWith(prefix),
        last_status_change: pod.lastStatusChange,
      }));

      const arnoldInstances = instances.filter(i => i.is_arnold_managed);
      const totalCost = arnoldInstances.reduce((sum, i) => sum + i.cost_per_hour, 0);

      // Build a detailed message
      let message = `Found ${arnoldInstances.length} Arnold-managed instance(s)`;
      if (arnoldInstances.length > 0) {
        message += `:\n\n`;
        for (const inst of arnoldInstances) {
          message += `• **${inst.name}** (${inst.id})\n`;
          message += `  Status: ${inst.status}\n`;
          message += `  GPU: ${inst.gpu}\n`;
          message += `  Uptime: ${inst.uptime_minutes} min\n`;
          message += `  Ports ready: ${inst.has_ports ? 'Yes' : 'No'}\n`;
          if (inst.has_ports) {
            message += `  Jupyter: https://${inst.id}-8888.proxy.runpod.net\n`;
          }
          message += `\n`;
        }
        message += `Total cost: $${totalCost.toFixed(3)}/hr`;
      }

      return {
        success: true,
        action: 'list_runpod_instances',
        instances,
        count: arnoldInstances.length,
        total_cost_per_hour: totalCost,
        message,
      };
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      logger.error('Failed to list RunPod instances', error instanceof Error ? error : undefined);
      return {
        success: false,
        action: 'list_runpod_instances',
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
  listRunpodInstances,
];
