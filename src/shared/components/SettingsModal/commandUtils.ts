import type { CommandConfig } from './types';
import { writeClipboardTextSafe } from '@/shared/lib/browser/clipboard';

const WORKER_REPO_URL = 'https://github.com/banodoco/Reigh-Worker.git';
const REPO_DIR = 'Reigh-Worker';
const LINUX_UV_INSTALL = 'curl -LsSf https://astral.sh/uv/install.sh | sh';
const WINDOWS_UV_INSTALL = 'irm https://astral.sh/uv/install.ps1 | iex';
const WINDOWS_CMD_UV_EXE = '%USERPROFILE%/.local/bin/uv.exe';

export class UnsupportedPlatformError extends Error {
  constructor(platform: string) {
    super(`Local worker commands are not supported on ${platform}.`);
    this.name = 'UnsupportedPlatformError';
  }
}

/**
 * Safe clipboard copy with fallback for older browsers
 */
export const safeCopy = (text: string): Promise<boolean> => {
  return writeClipboardTextSafe(text, { allowExecCommandFallback: true });
};

const getCudaExtra = (gpuType: string): 'cuda124' | 'cuda128' => {
  return gpuType === 'nvidia-50' ? 'cuda128' : 'cuda124';
};

const buildBackupPreludeLinux = (): string => {
  return `if [ ! -f ".uv-migrated" ]; then
  UV_MIGRATION_TS="$(date +%Y%m%d%H%M%S)"
  if [ -d "venv" ]; then mv "venv" "venv.pre-uv-$UV_MIGRATION_TS"; fi
  if [ -d ".venv" ]; then mv ".venv" ".venv.pre-uv-$UV_MIGRATION_TS"; fi
fi`;
};

const buildBackupPreludePowerShell = (): string => {
  return `if (-not (Test-Path -LiteralPath '.uv-migrated')) {
  $uvMigrationTs = Get-Date -Format 'yyyyMMddHHmmss'
  foreach ($legacyDir in @('venv', '.venv')) {
    if (Test-Path -LiteralPath $legacyDir) {
      Move-Item -LiteralPath $legacyDir -Destination "$legacyDir.pre-uv-$uvMigrationTs"
    }
  }
}`;
};

const buildBackupPreludeCmd = (): string => {
  // Single-line: cmd.exe splits multiline pastes and loses && chains.
  // Uses powershell one-liner to do the backup only when sentinel is absent.
  return `if not exist ".uv-migrated" powershell -NoProfile -Command "$ts = Get-Date -Format 'yyyyMMddHHmmss'; if (Test-Path 'venv') { Move-Item 'venv' ('venv.pre-uv-' + $ts) }; if (Test-Path '.venv') { Move-Item '.venv' ('.venv.pre-uv-' + $ts) }"`;
};

/**
 * Build the `python run_worker.py ...` line that launches the worker.
 *
 * Sole producer of the worker launch flags — all OS branches consume this.
 */
export const buildWorkerLaunchLine = (config: CommandConfig): string => {
  const { memoryProfile, showDebugLogs, idleReleaseMinutes, token } = config;
  const flags = [
    `--reigh-access-token ${token}`,
    showDebugLogs ? '--debug' : null,
    `--wgp-profile ${memoryProfile}`,
    `--idle-release-minutes ${idleReleaseMinutes}`,
  ].filter((flag): flag is string => Boolean(flag));
  return `python run_worker.py ${flags.join(' ')}`;
};

const buildUvRunLine = (uvCommand: string, cudaExtra: string, config: CommandConfig): string => {
  return `${uvCommand} run --python 3.10 --extra ${cudaExtra} ${buildWorkerLaunchLine(config)}`;
};

const buildLinuxCommand = (config: CommandConfig, mode: 'install' | 'run'): string => {
  const cudaExtra = getCudaExtra(config.gpuType);
  const uvCommand = '"$HOME/.local/bin/uv"';
  const lines: string[] = [];

  if (mode === 'install') {
    lines.push(`if [ ! -d ${REPO_DIR} ]; then git clone --depth 1 ${WORKER_REPO_URL}; fi &&`);
    lines.push(`cd ${REPO_DIR} &&`);
    lines.push(`apt-cache show python3.10-venv >/dev/null 2>&1 || { echo "python3.10-venv is unavailable. Install deadsnakes first; see README."; exit 1; } &&`);
    lines.push('sudo apt-get update && sudo apt-get install -y python3.10-venv python3.10-dev ffmpeg git curl &&');
    lines.push(`if [ ! -x "$HOME/.local/bin/uv" ]; then ${LINUX_UV_INSTALL}; fi &&`);
  } else {
    lines.push(`cd ${REPO_DIR} &&`);
  }

  lines.push('export PATH="$HOME/.local/bin:$PATH" &&');
  lines.push(`${buildBackupPreludeLinux()} &&`);
  lines.push('git pull --ff-only &&');
  lines.push('git submodule update --init --recursive &&');
  lines.push(`${uvCommand} sync --locked --python 3.10 --extra ${cudaExtra} &&`);
  lines.push('touch .uv-migrated &&');
  lines.push(buildUvRunLine(uvCommand, cudaExtra, config));

  return lines.join('\n');
};

const buildWindowsPowerShellCommand = (config: CommandConfig, mode: 'install' | 'run'): string => {
  const cudaExtra = getCudaExtra(config.gpuType);
  const uvCommand = '& $uvExe';
  const lines: string[] = [];

  if (mode === 'install') {
    lines.push(`if (-not (Test-Path -LiteralPath '${REPO_DIR}')) { git clone --depth 1 ${WORKER_REPO_URL} }`);
    lines.push(`Set-Location -LiteralPath '${REPO_DIR}'`);
  } else {
    lines.push(`Set-Location -LiteralPath '${REPO_DIR}'`);
  }

  lines.push(`$uvExe = Join-Path $env:USERPROFILE '.local\\bin\\uv.exe'`);
  if (mode === 'install') {
    lines.push(`if (-not (Test-Path -LiteralPath $uvExe)) { ${WINDOWS_UV_INSTALL} }`);
  }
  lines.push(buildBackupPreludePowerShell());
  lines.push('git pull --ff-only');
  lines.push('git submodule update --init --recursive');
  lines.push(`${uvCommand} sync --locked --python 3.10 --extra ${cudaExtra}`);
  lines.push(`New-Item -ItemType File -Force -Path '.uv-migrated' | Out-Null`);
  lines.push(buildUvRunLine(uvCommand, cudaExtra, config));

  return lines.join('\n');
};

const buildWindowsCmdCommand = (config: CommandConfig, mode: 'install' | 'run'): string => {
  const cudaExtra = getCudaExtra(config.gpuType);
  const uvCommand = `"${WINDOWS_CMD_UV_EXE}"`;
  const parts: string[] = [];

  if (mode === 'install') {
    parts.push(`if not exist "${REPO_DIR}" git clone --depth 1 ${WORKER_REPO_URL}`);
    parts.push(`cd /d ${REPO_DIR}`);
    parts.push(`if not exist "${WINDOWS_CMD_UV_EXE}" powershell -NoProfile -ExecutionPolicy Bypass -Command "${WINDOWS_UV_INSTALL}"`);
  } else {
    parts.push(`cd /d ${REPO_DIR}`);
  }

  parts.push(buildBackupPreludeCmd());
  parts.push('git pull --ff-only');
  parts.push('git submodule update --init --recursive');
  parts.push(`${uvCommand} sync --locked --python 3.10 --extra ${cudaExtra}`);
  parts.push('type nul > .uv-migrated');
  parts.push(buildUvRunLine(uvCommand, cudaExtra, config));

  // Single line — cmd.exe splits multiline pastes and loses && chains
  return parts.join(' && ');
};

/**
 * Generate the installation command based on system configuration
 */
export const getInstallationCommand = (config: CommandConfig): string => {
  const { computerType, windowsShell } = config;

  if (computerType === 'linux') {
    return buildLinuxCommand(config, 'install');
  }

  if (computerType === 'windows') {
    return windowsShell === 'powershell'
      ? buildWindowsPowerShellCommand(config, 'install')
      : buildWindowsCmdCommand(config, 'install');
  }

  throw new UnsupportedPlatformError(computerType);
};

/**
 * Generate the run command for an already installed worker
 */
export const getRunCommand = (config: CommandConfig): string => {
  const { computerType, windowsShell } = config;

  if (computerType === 'linux') {
    return buildLinuxCommand(config, 'run');
  }

  if (computerType === 'windows') {
    return windowsShell === 'powershell'
      ? buildWindowsPowerShellCommand(config, 'run')
      : buildWindowsCmdCommand(config, 'run');
  }

  throw new UnsupportedPlatformError(computerType);
};

/**
 * Generate AI troubleshooting instructions
 */
export const generateAIInstructions = (
  config: CommandConfig,
  activeInstallTab: string
): string => {
  const { computerType } = config;
  const isWindows = computerType === 'windows';
  const isInstalling = activeInstallTab === 'need-install';

  const prerequisites = isWindows ? `

PREREQUISITES (Windows only - install these first):
1. NVIDIA GPU with CUDA 6.0+ and 8GB+ VRAM
   - Check with: nvidia-smi
   - AMD/Intel GPUs will NOT work for local processing

2. Latest NVIDIA drivers from nvidia.com/drivers
   - Download and install latest drivers
   - Restart computer after installation
   - Verify with: nvidia-smi

3. Python 3.10+ from python.org (NOT Microsoft Store)
   - During install, check "Add Python to PATH"
   - Verify with: python --version

4. Git from git-scm.com/download/win
   - Use default settings during installation
   - Verify with: git --version

5. FFmpeg from ffmpeg.org/download.html
   - Download "Windows builds by BtbN" (recommended)
   - Extract to C:\\ffmpeg
   - Add C:\\ffmpeg\\bin to system PATH
   - Verify with: ffmpeg -version
   - Need PATH help? Search "Windows add to PATH" on YouTube
` : '';

  let installCommand: string;
  try {
    installCommand = isInstalling ? getInstallationCommand(config) : getRunCommand(config);
  } catch (error) {
    if (error instanceof UnsupportedPlatformError) {
      installCommand = error.message;
    } else {
      throw error;
    }
  }
  const commandType = isInstalling ? 'INSTALLATION' : 'RUN';

  return `I'm trying to set up a local AI worker for Reigh and need help troubleshooting.

FIRST - Please ask me these questions to understand my setup:
1. What's my operating system and version?
2. What graphics card do I have and how much VRAM? (need at least 8GB for local AI processing)
3. What's my total system RAM?
4. How much free disk space do I have? (AI models can be 10+ GB)
5. Am I using a laptop or desktop computer?
6. Am I getting any specific error messages? If so, what exactly?
7. Have I completed the prerequisites for my system?
8. Do I have experience setting up AI/ML tools before?

SYSTEM REQUIREMENTS:
- NVIDIA GPU with CUDA Compute Capability 6.0+ (AMD/Intel GPUs will NOT work)
- Minimum 8GB VRAM (graphics card memory) for local AI processing
- Latest NVIDIA drivers and CUDA Toolkit
- Windows 10/11, Linux, or Mac (though Mac isn't currently supported for local processing)
- Git, Python 3.10+, FFmpeg installed
- PyTorch with CUDA support (critical - CPU-only PyTorch will NOT work)${prerequisites}

MY CURRENT SITUATION:
- Operating System: ${computerType === 'windows' ? 'Windows' : computerType === 'linux' ? 'Linux' : 'Mac'}
- Task: ${isInstalling ? 'Initial installation' : 'Running existing installation'}
- Status: Encountering errors

${commandType} COMMAND I'M USING:
\`\`\`
${installCommand}
\`\`\`

WHAT I NEED:
After understanding my system specs, please guide me step-by-step through this process. If I encounter any errors:
1. Help me understand what went wrong
2. Provide the exact commands to fix it
3. Explain how to verify each step worked
4. Tell me what to do next

Please be very specific with file paths, command syntax, and verification steps since I'm on ${computerType === 'windows' ? 'Windows' : computerType}.`;
};
