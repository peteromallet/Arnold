import { config } from '../config.js';
import { logger } from '../logger.js';
import type { RegisteredTool, ToolContext } from './types.js';
import type { ToolResult } from '../types.js';
import { Client as SSHClient } from 'ssh2';

const RUNPOD_API_URL = 'https://api.runpod.io/graphql';

// RAM tiers to try in order (highest first - 72GB has lowest failure rate)
const RAM_TIERS_GB = [72, 60];

// Retry configuration for when no instances are available
// Exponential backoff: 1 min, 2 min, 4 min, 8 min (total ~15 min worst case)
const MAX_RETRY_ATTEMPTS = 5;  // Initial attempt + 4 retries
const RETRY_DELAYS_MS = [60_000, 120_000, 240_000, 480_000]; // 1, 2, 4, 8 minutes

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
  const raw = volumeName.trim();

  // 1) Exact match
  let volume = volumes.find(v => v.name === raw);
  if (!volume) {
    // 2) Case-insensitive exact match (helps if casing differs)
    const rawLower = raw.toLowerCase();
    volume = volumes.find(v => v.name.toLowerCase() === rawLower);
  }

  if (!volume) {
    // 3) If the configured value includes accidental suffixes (e.g. extra whitespace),
    // try the first token before whitespace.
    const firstToken = raw.split(/\s+/)[0];
    if (firstToken && firstToken !== raw) {
      volume =
        volumes.find(v => v.name === firstToken) ??
        volumes.find(v => v.name.toLowerCase() === firstToken.toLowerCase());
    }
  }

  if (volume) {
    logger.debug('Found network volume', { name: volumeName, resolvedName: volume.name, id: volume.id, size: volume.size });
  } else {
    logger.debug('Network volume not found', { name: volumeName, available: volumes.map(v => v.name) });
  }

  return volume?.id || null;
}

interface PodTemplate {
  id: string;
  name: string;
  imageName: string;
}

/**
 * Get available pod templates
 */
async function getPodTemplates(): Promise<PodTemplate[]> {
  const query = `
    query {
      myself {
        podTemplates {
          id
          name
          imageName
        }
      }
    }
  `;

  const data = await runpodGraphQL(query) as { 
    myself: { podTemplates: PodTemplate[] } 
  };
  
  return data.myself?.podTemplates || [];
}

/**
 * Find a pod template ID by name or ID
 */
async function findTemplateId(templateNameOrId: string): Promise<string | null> {
  const templates = await getPodTemplates();
  
  // Try to match by name first, then by ID
  const template = templates.find(t => 
    t.name === templateNameOrId || 
    t.id === templateNameOrId ||
    t.name.toLowerCase() === templateNameOrId.toLowerCase()
  );
  
  if (template) {
    logger.info('Found template', { search: templateNameOrId, name: template.name, id: template.id, image: template.imageName });
  } else {
    logger.warn('Template not found', { search: templateNameOrId, available: templates.map(t => `${t.name} (${t.id})`) });
  }
  
  return template?.id || null;
}

// ============================================================================
// SSH Functions
// ============================================================================

interface SSHConnectionInfo {
  ip: string;
  port: number;
}

/**
 * Get SSH connection details for a pod
 */
async function getPodSSHDetails(podId: string): Promise<SSHConnectionInfo | null> {
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
    if (!pod || pod.desiredStatus !== 'RUNNING' || !pod.runtime?.ports) {
      return null;
    }

    // Find SSH port (private port 22)
    const sshPort = pod.runtime.ports.find(p => p.privatePort === 22);
    if (!sshPort || !sshPort.ip || !sshPort.publicPort) {
      return null;
    }

    return {
      ip: sshPort.ip,
      port: sshPort.publicPort,
    };
  } catch (error) {
    logger.warn('Error getting SSH details', { podId, error: error instanceof Error ? error.message : String(error) });
    return null;
  }
}

/**
 * Wait for SSH to be available on a pod
 */
async function waitForSSH(podId: string, maxWaitMs = 120000): Promise<SSHConnectionInfo | null> {
  const startTime = Date.now();
  const pollIntervalMs = 5000;

  while (Date.now() - startTime < maxWaitMs) {
    const sshDetails = await getPodSSHDetails(podId);
    if (sshDetails) {
      logger.info('SSH available', { podId, ip: sshDetails.ip, port: sshDetails.port });
      return sshDetails;
    }
    
    logger.debug('Waiting for SSH...', { podId, elapsed: Date.now() - startTime });
    await new Promise(resolve => setTimeout(resolve, pollIntervalMs));
  }

  return null;
}

/**
 * Execute a command on a pod via SSH
 */
async function executeSSHCommand(
  sshDetails: SSHConnectionInfo,
  command: string,
  timeoutMs = 30000
): Promise<{ stdout: string; stderr: string; code: number }> {
  const privateKey = config.runpod.sshPrivateKey;
  if (!privateKey) {
    throw new Error('RUNPOD_SSH_PRIVATE_KEY not configured');
  }

  return new Promise((resolve, reject) => {
    const conn = new SSHClient();
    let stdout = '';
    let stderr = '';
    
    const timeout = setTimeout(() => {
      conn.end();
      reject(new Error(`SSH command timed out after ${timeoutMs}ms`));
    }, timeoutMs);

    conn.on('ready', () => {
      logger.debug('SSH connection established');
      
      conn.exec(command, (err, stream) => {
        if (err) {
          clearTimeout(timeout);
          conn.end();
          reject(err);
          return;
        }

        stream.on('close', (code: number) => {
          clearTimeout(timeout);
          conn.end();
          resolve({ stdout, stderr, code: code || 0 });
        });

        stream.on('data', (data: Buffer) => {
          stdout += data.toString();
        });

        stream.stderr.on('data', (data: Buffer) => {
          stderr += data.toString();
        });
      });
    });

    conn.on('error', (err) => {
      clearTimeout(timeout);
      reject(err);
    });

    conn.connect({
      host: sshDetails.ip,
      port: sshDetails.port,
      username: 'root',
      privateKey: privateKey,
      readyTimeout: 10000,
    });
  });
}

/**
 * Get Jupyter token via SSH by running `jupyter server list`
 */
async function getJupyterTokenViaSSH(sshDetails: SSHConnectionInfo, podId: string): Promise<string | null> {
  try {
    const result = await executeSSHCommand(sshDetails, 'jupyter server list', 15000);
    const match = result.stdout.match(/token=([a-zA-Z0-9]+)/);
    if (match) {
      logger.info('Got Jupyter token via SSH', { podId, token: match[1].substring(0, 8) + '...' });
      return match[1];
    }
    logger.warn('Could not find Jupyter token in output', { podId, output: result.stdout });
    return null;
  } catch (error) {
    logger.error('Failed to get Jupyter token via SSH', error instanceof Error ? error : undefined, { podId });
    return null;
  }
}

/**
 * Run setup script on a pod via SSH (installs Node.js, Claude Code, etc.)
 */
async function runSetupScriptViaSSH(sshDetails: SSHConnectionInfo, podId: string): Promise<boolean> {
  // Setup script that installs dependencies
  const setupScript = `
#!/bin/bash
set -e
echo "🚀 Starting pod setup..."

# Update and install basic dependencies
echo "📦 Installing system dependencies..."
apt-get update
apt-get install -y curl gnupg python3-venv ffmpeg

# Install Jupyter Lab if not already installed
if ! command -v jupyter &> /dev/null; then
  echo "📦 Installing Jupyter Lab..."
  pip3 install --break-system-packages jupyterlab || pip install jupyterlab
else
  echo "✓ Jupyter already installed"
fi

# Remove old Node.js if present and install Node.js 20
echo "📦 Installing Node.js 20..."
apt-get remove -y nodejs npm libnode-dev libnode72 nodejs-doc 2>/dev/null || true
apt-get autoremove -y
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt-get install -y nodejs

# Install Claude Code CLI
echo "📦 Installing Claude Code CLI..."
npm install -g @anthropic-ai/claude-code

# Set up Anthropic API key in bashrc for interactive sessions
echo "export ANTHROPIC_API_KEY='${config.runpod.podAnthropicApiKey || ''}'" >> /root/.bashrc

# Update Headless-Wan2GP if it exists
if [ -d "/workspace/Headless-Wan2GP" ]; then
  echo "📦 Updating Headless-Wan2GP..."
  cd /workspace/Headless-Wan2GP
  git pull || echo "⚠️ git pull failed, continuing anyway"
else
  echo "⚠️ /workspace/Headless-Wan2GP not found, skipping git pull"
fi

echo "✅ Pod setup complete!"
`;

  try {
    logger.info('Running setup script via SSH (this may take a few minutes)...', { podId });
    
    // Run setup script with longer timeout (5 minutes)
    const result = await executeSSHCommand(sshDetails, setupScript, 300000);
    
    if (result.code === 0) {
      logger.info('Setup script completed successfully', { podId });
      return true;
    } else {
      logger.error('Setup script failed', { podId, code: result.code, stderr: result.stderr });
      return false;
    }
  } catch (error) {
    logger.error('Failed to run setup script', error instanceof Error ? error : undefined, { podId });
    return false;
  }
}

/**
 * Start Jupyter Lab on a pod via SSH
 */
async function startJupyterViaSSH(
  podId: string,
  options: { runSetup?: boolean; startJupyter?: boolean } = { runSetup: true, startJupyter: true },
): Promise<boolean> {
  if (!config.runpod.sshPrivateKey) {
    logger.warn('SSH private key not configured, cannot auto-start Jupyter');
    return false;
  }

  // Wait for SSH to be available
  const sshDetails = await waitForSSH(podId);
  if (!sshDetails) {
    logger.error('SSH not available after waiting', { podId });
    return false;
  }

  // Give the container a moment to fully initialize
  await new Promise(resolve => setTimeout(resolve, 3000));

  // Run setup script first if requested
  if (options.runSetup) {
    const setupSuccess = await runSetupScriptViaSSH(sshDetails, podId);
    if (!setupSuccess) {
      logger.warn('Setup script failed, continuing with Jupyter start anyway', { podId });
    }
  }

  if (options.startJupyter === false) {
    return true;
  }

  const jupyterCmd = `nohup jupyter lab --ip=0.0.0.0 --port=8888 --no-browser --allow-root --ServerApp.token='' --ServerApp.password='' --ServerApp.terminals_enabled=True --ServerApp.root_dir=/workspace > /var/log/jupyter.log 2>&1 &`;

  try {
    logger.info('Starting Jupyter via SSH', { podId });
    
    const result = await executeSSHCommand(sshDetails, jupyterCmd);
    
    if (result.code === 0) {
      logger.info('Jupyter start command executed', { podId, stdout: result.stdout, stderr: result.stderr });
      
      // Wait a moment for Jupyter to start
      await new Promise(resolve => setTimeout(resolve, 3000));
      
      // Verify Jupyter is running
      const checkResult = await executeSSHCommand(sshDetails, 'pgrep -f "jupyter-lab" || pgrep -f "jupyter lab"');
      if (checkResult.stdout.trim()) {
        logger.info('Jupyter confirmed running', { podId, pid: checkResult.stdout.trim() });
        return true;
      } else {
        logger.warn('Jupyter process not found after starting', { podId });
        return false;
      }
    } else {
      logger.error('Jupyter start command failed', { podId, code: result.code, stderr: result.stderr });
      return false;
    }
  } catch (error) {
    logger.error('Failed to start Jupyter via SSH', error instanceof Error ? error : undefined, { podId });
    return false;
  }
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

      // Look up template ID (templates have Jupyter properly configured)
      let templateId: string | null = null;
      if (config.runpod.templateId) {
        templateId = await findTemplateId(config.runpod.templateId);
        if (templateId) {
          logger.info('Using template', { configured: config.runpod.templateId, resolved: templateId });
        } else {
          logger.warn(`Template "${config.runpod.templateId}" not found, will use raw image`);
        }
      }

      logger.info('Creating RunPod instance', { podName, gpuTypeId, templateId, storageVolumes: config.runpod.storageVolumes });

      // Build list of network volume IDs to try (in order)
      const storageVolumesToTry: Array<{ name: string; id: string }> = [];
      logger.info('Looking up storage volumes...', { configured: config.runpod.storageVolumes });
      
      for (const volumeName of config.runpod.storageVolumes) {
        const volumeId = await findNetworkVolumeId(volumeName);
        if (volumeId) {
          storageVolumesToTry.push({ name: volumeName, id: volumeId });
          logger.info(`✓ Found volume: ${volumeName} → ${volumeId}`);
        } else {
          logger.warn(`✗ Network volume "${volumeName}" not found, skipping`);
        }
      }
      
      logger.info('Storage volumes resolved', { 
        found: storageVolumesToTry.map(v => `${v.name}(${v.id})`),
        count: storageVolumesToTry.length,
        configured: config.runpod.storageVolumes.length 
      });

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

      // Retry loop - if all combinations fail, wait and try again with exponential backoff
      for (let attempt = 1; attempt <= MAX_RETRY_ATTEMPTS; attempt++) {
        if (attempt > 1) {
          const delayMs = RETRY_DELAYS_MS[attempt - 2] || RETRY_DELAYS_MS[RETRY_DELAYS_MS.length - 1];
          const delayMinutes = delayMs / 60_000;
          logger.info(`⏳ Retry attempt ${attempt}/${MAX_RETRY_ATTEMPTS} - waiting ${delayMinutes} minute(s) before retrying...`);
          await new Promise(resolve => setTimeout(resolve, delayMs));
          logger.info(`🔄 Retrying all storage/RAM combinations (attempt ${attempt}/${MAX_RETRY_ATTEMPTS})...`);
        }

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
            logger.info(`Trying: ${volume.name}, ${ramTier}GB RAM`, { 
              podName, 
              gpuTypeId, 
              useNetworkVolume,
              networkVolumeId: volume.id || '(none - using pod volume)',
              templateId: templateId || '(none - using image)',
            });

            // Build mutation based on whether we're using network volume or pod volume
            const volumeParams = useNetworkVolume
              ? `networkVolumeId: "${volume.id}"\n                  volumeMountPath: "${config.runpod.volumeMountPath}"`
              : `volumeInGb: ${config.runpod.diskSizeGb}\n                  volumeMountPath: "${config.runpod.volumeMountPath}"`;

            // Build environment variables for the pod
            const envVars: Array<{ key: string; value: string }> = [];
            
            // SSH public key for authentication (RunPod images use PUBLIC_KEY env var)
            if (config.runpod.sshPublicKey) {
              envVars.push({ key: 'PUBLIC_KEY', value: config.runpod.sshPublicKey });
            }
            
            // Anthropic API key for Claude Code
            if (config.runpod.podAnthropicApiKey) {
              envVars.push({ key: 'ANTHROPIC_API_KEY', value: config.runpod.podAnthropicApiKey });
            }
            
            const envParams = envVars.length > 0
              ? `env: [${envVars.map(e => `{ key: "${e.key}", value: "${e.value.replace(/"/g, '\\"')}" }`).join(', ')}]`
              : '';

            // Use templateId if available (templates have Jupyter pre-configured), otherwise use raw image
            const imageOrTemplate = templateId
              ? `templateId: "${templateId}"`
              : `imageName: "${config.runpod.image}"`;

            // CUDA version filter - prevents scheduling on incompatible hosts (e.g., CUDA 13.0 with 12.x containers)
            const cudaVersionsParam = config.runpod.allowedCudaVersions.length > 0
              ? `allowedCudaVersions: [${config.runpod.allowedCudaVersions.map(v => `"${v}"`).join(', ')}]`
              : '';

            const mutation = `
              mutation {
                podFindAndDeployOnDemand(input: {
                  name: "${podName}"
                  ${imageOrTemplate}
                  gpuTypeId: "${gpuTypeId}"
                  gpuCount: 1
                  cloudType: ALL
                  containerDiskInGb: ${config.runpod.containerDiskGb}
                  ${volumeParams}
                  minMemoryInGb: ${ramTier}
                  ports: "22/tcp,8888/http"
                  startJupyter: true
                  ${envParams}
                  ${cudaVersionsParam}
                }) {
                  id
                  name
                  desiredStatus
                  imageName
                  machineId
                }
              }
            `;

            // Log the exact request parameters for debugging
            logger.info(`API Request: ${volume.name}/${ramTier}GB`, {
              gpuTypeId,
              networkVolumeId: useNetworkVolume ? volume.id : null,
              minMemoryInGb: ramTier,
              cloudType: 'ALL',
              templateId: templateId || null,
              allowedCudaVersions: config.runpod.allowedCudaVersions,
            });

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
        }  // end ramLoop

        // If we got a pod, break out of retry loop
        if (pod?.id) {
          break;
        }

        // Log status after this attempt
        if (attempt < MAX_RETRY_ATTEMPTS) {
          const nextDelayMs = RETRY_DELAYS_MS[attempt - 1] || RETRY_DELAYS_MS[RETRY_DELAYS_MS.length - 1];
          const nextDelayMinutes = nextDelayMs / 60_000;
          logger.warn(`Attempt ${attempt}/${MAX_RETRY_ATTEMPTS} failed - no instances available. Will retry in ${nextDelayMinutes} minute(s)...`);
        }
      }  // end retry loop
      
      if (!pod || !pod.id) {
        const storagesFound = storageVolumesToTry.map(v => v.name);
        const storagesNotFound = config.runpod.storageVolumes.filter(name => !storagesFound.includes(name));
        logger.error('Pod creation failed - all retry attempts exhausted', { 
          lastError, 
          failedPodIds,
          storagesFound,
          storagesNotFound,
          configuredStorages: config.runpod.storageVolumes,
          totalAttempts: MAX_RETRY_ATTEMPTS,
        });
        
        const storageInfo = storagesNotFound.length > 0 
          ? ` (Note: storages not found: ${storagesNotFound.join(', ')})`
          : '';
        
        return {
          success: false,
          action: 'create_runpod_instance',
          error: `Pod creation failed after ${MAX_RETRY_ATTEMPTS} attempts (${storagesFound.length} storages × 72/60/48/32 GB RAM each). No 4090s available.${storageInfo} Last error: ${lastError}`,
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

      // Wait for the pod to be running with ports
      await waitForPodReady(pod.id);
      
      // Run setup script and start Jupyter via SSH
      // For raw images (no template), we need to install Jupyter first
      let setupComplete = false;
      if (config.runpod.sshPrivateKey && config.runpod.sshPublicKey) {
        if (templateId) {
          logger.info('Running setup script via SSH (template manages Jupyter)...', { podId: pod.id });
          setupComplete = await startJupyterViaSSH(pod.id, { runSetup: true, startJupyter: false });
        } else {
          logger.info('Installing dependencies and starting Jupyter via SSH (no template)...', { podId: pod.id });
          setupComplete = await startJupyterViaSSH(pod.id, { runSetup: true, startJupyter: true });
        }

        if (setupComplete) {
          logger.info('SSH setup completed', { podId: pod.id });
        } else {
          logger.warn('SSH setup had issues', { podId: pod.id });
        }
      } else {
        logger.info('SSH keys not configured, skipping setup', { podId: pod.id });
      }
      
      // Get Jupyter token via SSH (after setup has installed and started Jupyter)
      let jupyterToken: string | null = null;
      if (config.runpod.sshPrivateKey && config.runpod.sshPublicKey) {
        logger.info('Getting Jupyter token via SSH...', { podId: pod.id });
        const sshDetails = await waitForSSH(pod.id, 60000);
        if (sshDetails) {
          // Wait a bit for Jupyter to be ready
          await new Promise(resolve => setTimeout(resolve, 5000));
          jupyterToken = await getJupyterTokenViaSSH(sshDetails, pod.id);
        }
      }
      
      const jupyterProxyUrl = jupyterToken 
        ? `https://${pod.id}-8888.proxy.runpod.net/?token=${jupyterToken}`
        : `https://${pod.id}-8888.proxy.runpod.net/`;
      
      if (jupyterToken || templateId) {
        logger.info('RunPod instance ready', { podId: pod.id, jupyterUrl: jupyterProxyUrl, ramTier: usedRamTier, storage: usedStorageVolume, setupComplete, hasToken: !!jupyterToken });
        
        const setupNote = setupComplete 
          ? '\n\n✅ Node.js 20 & Claude Code CLI installed!' 
          : '';
        
        const tokenNote = jupyterToken ? '' : '\n\n⚠️ Could not get Jupyter token - get URL from RunPod dashboard';
        
        const message = `🚀 GPU is UP!\n\n📍 Storage: ${usedStorageVolume}\n💾 RAM: ${usedRamTier}GB\n\n🔗 Jupyter: ${jupyterProxyUrl}${setupNote}${tokenNote}`;
        
        return {
          success: true,
          action: 'create_runpod_instance',
          pod_id: pod.id,
          pod_name: pod.name,
          ram_gb: usedRamTier,
          message,
        };
      } else {
        // Still return success since pod was created with a machine
        logger.warn('Pod created but ports not available yet', { podId: pod.id, ramTier: usedRamTier, storage: usedStorageVolume });
        return {
          success: true,
          action: 'create_runpod_instance',
          pod_id: pod.id,
          pod_name: pod.name,
          ram_gb: usedRamTier,
          message: `🚀 GPU is UP! (still initializing)\n\n📍 Storage: ${usedStorageVolume}\n💾 RAM: ${usedRamTier}GB\n\nPod is starting - check RunPod dashboard for status.\n\n🔗 Jupyter URL (when ready): ${jupyterProxyUrl}`,
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

// ============================================================================
// Scheduled Termination
// ============================================================================

// Track scheduled termination (in-memory, lost on restart)
let scheduledTerminationTimeout: ReturnType<typeof setTimeout> | null = null;
let scheduledTerminationTime: Date | null = null;

/**
 * Schedule termination of all Arnold-managed RunPod instances
 */
export const scheduleTerminateRunpodInstances: RegisteredTool = {
  name: 'schedule_terminate_runpod_instances',
  schema: {
    name: 'schedule_terminate_runpod_instances',
    description: 'Schedule termination of all Arnold-managed RunPod GPU instances after a delay. Use this for "kill machines in X minutes" requests.',
    input_schema: {
      type: 'object' as const,
      properties: {
        minutes: {
          type: 'number',
          description: 'Number of minutes until termination (e.g., 30 for "in 30 minutes")',
        },
      },
      required: ['minutes'],
    },
  },
  handler: async (input: { minutes: number }, _context: ToolContext): Promise<ToolResult> => {
    if (!config.runpod.apiKey) {
      return {
        success: false,
        action: 'schedule_terminate_runpod_instances',
        error: 'RunPod API key not configured. Set RUNPOD_API_KEY environment variable.',
      };
    }

    // Tool inputs can be imperfect (e.g., minutes passed as a string). Coerce + validate.
    const rawMinutes = (input as unknown as { minutes?: unknown })?.minutes;
    const minutes = typeof rawMinutes === 'string' ? Number(rawMinutes) : (rawMinutes as number);

    if (!Number.isFinite(minutes)) {
      return {
        success: false,
        action: 'schedule_terminate_runpod_instances',
        error: 'Minutes must be a valid number',
      };
    }

    if (minutes <= 0) {
      return {
        success: false,
        action: 'schedule_terminate_runpod_instances',
        error: 'Minutes must be greater than 0',
      };
    }

    // Check if there are any Arnold pods to terminate
    const arnoldPods = await getArnoldPods();
    if (arnoldPods.length === 0) {
      return {
        success: true,
        action: 'schedule_terminate_runpod_instances',
        message: 'No Arnold-managed RunPod instances found to schedule for termination.',
      };
    }

    // Cancel any existing scheduled termination
    if (scheduledTerminationTimeout) {
      clearTimeout(scheduledTerminationTimeout);
      logger.info('Cancelled previous scheduled termination');
    }

    const delayMs = Math.round(minutes * 60 * 1000);
    // Node timers clamp around 2^31-1 ms (~24.8 days)
    if (delayMs > 2_147_483_647) {
      return {
        success: false,
        action: 'schedule_terminate_runpod_instances',
        error: 'Delay is too large (must be <= ~24 days).',
      };
    }
    scheduledTerminationTime = new Date(Date.now() + delayMs);

    logger.info('Scheduling termination of all Arnold pods', { 
      minutes, 
      podCount: arnoldPods.length,
      scheduledFor: scheduledTerminationTime.toISOString(),
    });

    scheduledTerminationTimeout = setTimeout(async () => {
      logger.info('⏰ Executing scheduled termination...');
      scheduledTerminationTimeout = null;
      scheduledTerminationTime = null;
      
      try {
        const pods = await getArnoldPods();
        let terminated = 0;
        
        for (const pod of pods) {
          try {
            const mutation = `mutation { podTerminate(input: {podId: "${pod.id}"}) }`;
            await runpodGraphQL(mutation);
            terminated++;
            logger.info('Terminated pod (scheduled)', { podId: pod.id, podName: pod.name });
          } catch (error) {
            logger.error('Failed to terminate pod (scheduled)', error instanceof Error ? error : undefined, { podId: pod.id });
          }
        }
        
        logger.info('Scheduled termination complete', { terminated, total: pods.length });
      } catch (error) {
        logger.error('Scheduled termination failed', error instanceof Error ? error : undefined);
      }
    }, delayMs);
    // Don’t keep the process alive solely because of this timer (safe no-op in older runtimes)
    scheduledTerminationTimeout.unref?.();

    const podNames = arnoldPods.map(p => p.name).join(', ');
    const timeStr = scheduledTerminationTime.toLocaleTimeString();

    return {
      success: true,
      action: 'schedule_terminate_runpod_instances',
      scheduled_for: scheduledTerminationTime.toISOString(),
      pod_count: arnoldPods.length,
      message: `⏰ Scheduled termination of ${arnoldPods.length} instance(s) in ${minutes} minute(s) (at ${timeStr}).\n\nPods: ${podNames}\n\n⚠️ Note: Schedule is in-memory only - will be lost if bot restarts.`,
    };
  },
};

/**
 * Cancel scheduled termination of RunPod instances
 */
export const cancelScheduledTermination: RegisteredTool = {
  name: 'cancel_scheduled_termination',
  schema: {
    name: 'cancel_scheduled_termination',
    description: 'Cancel a previously scheduled termination of RunPod GPU instances.',
    input_schema: {
      type: 'object' as const,
      properties: {},
    },
  },
  handler: async (_input: Record<string, never>, _context: ToolContext): Promise<ToolResult> => {
    if (!scheduledTerminationTimeout || !scheduledTerminationTime) {
      return {
        success: true,
        action: 'cancel_scheduled_termination',
        message: 'No termination is currently scheduled.',
      };
    }

    clearTimeout(scheduledTerminationTimeout);
    const wasScheduledFor = scheduledTerminationTime.toISOString();
    scheduledTerminationTimeout = null;
    scheduledTerminationTime = null;

    logger.info('Cancelled scheduled termination', { wasScheduledFor });

    return {
      success: true,
      action: 'cancel_scheduled_termination',
      cancelled_time: wasScheduledFor,
      message: `✅ Cancelled scheduled termination (was scheduled for ${wasScheduledFor}).`,
    };
  },
};

/**
 * Get status of scheduled termination
 */
export const getScheduledTerminationStatus: RegisteredTool = {
  name: 'get_scheduled_termination_status',
  schema: {
    name: 'get_scheduled_termination_status',
    description: 'Check if there is a scheduled termination of RunPod instances pending.',
    input_schema: {
      type: 'object' as const,
      properties: {},
    },
  },
  handler: async (_input: Record<string, never>, _context: ToolContext): Promise<ToolResult> => {
    if (!scheduledTerminationTimeout || !scheduledTerminationTime) {
      return {
        success: true,
        action: 'get_scheduled_termination_status',
        has_scheduled: false,
        message: 'No termination is currently scheduled.',
      };
    }

    const now = new Date();
    const remainingMs = scheduledTerminationTime.getTime() - now.getTime();
    const remainingMinutes = Math.max(0, Math.round(remainingMs / 60000));

    return {
      success: true,
      action: 'get_scheduled_termination_status',
      has_scheduled: true,
      scheduled_for: scheduledTerminationTime.toISOString(),
      remaining_minutes: remainingMinutes,
      message: `⏰ Termination scheduled for ${scheduledTerminationTime.toLocaleTimeString()} (in ~${remainingMinutes} minute(s)).`,
    };
  },
};

/**
 * All RunPod-related tools
 */
export const runpodTools: RegisteredTool[] = [
  createRunpodInstance,
  terminateRunpodInstances,
  listRunpodInstances,
  scheduleTerminateRunpodInstances,
  cancelScheduledTermination,
  getScheduledTerminationStatus,
];
