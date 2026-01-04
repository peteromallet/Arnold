import 'dotenv/config';
import { Client as SSHClient } from 'ssh2';

const RUNPOD_API_URL = 'https://api.runpod.io/graphql';
const apiKey = process.env.RUNPOD_API_KEY;
const sshPrivateKey = process.env.RUNPOD_SSH_PRIVATE_KEY;
const sshPublicKey = process.env.RUNPOD_SSH_PUBLIC_KEY;

async function graphql(query) {
  const response = await fetch(RUNPOD_API_URL, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${apiKey}`,
    },
    body: JSON.stringify({ query }),
  });
  const result = await response.json();
  if (result.errors) throw new Error(result.errors[0].message);
  return result.data;
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function sshExec(ip, port, command) {
  return new Promise((resolve, reject) => {
    const conn = new SSHClient();
    let stdout = '';
    const timeout = setTimeout(() => { conn.end(); reject(new Error('SSH timeout')); }, 30000);
    
    conn.on('ready', () => {
      conn.exec(command, (err, stream) => {
        if (err) { clearTimeout(timeout); conn.end(); reject(err); return; }
        stream.on('data', d => stdout += d.toString());
        stream.on('close', () => { clearTimeout(timeout); conn.end(); resolve(stdout); });
      });
    });
    conn.on('error', e => { clearTimeout(timeout); reject(e); });
    conn.connect({ host: ip, port, username: 'root', privateKey: sshPrivateKey, readyTimeout: 10000 });
  });
}

async function main() {
  console.log('🚀 Creating RunPod instance...');
  
  // Get volume
  const volumeData = await graphql(`query { myself { networkVolumes { id name } } }`);
  const volume = volumeData.myself.networkVolumes.find(v => v.name === 'Peter');
  
  // Create pod
  const createResult = await graphql(`
    mutation {
      podFindAndDeployOnDemand(input: {
        name: "test-${Date.now()}"
        imageName: "runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04"
        gpuTypeId: "NVIDIA GeForce RTX 4090"
        gpuCount: 1
        cloudType: SECURE
        containerDiskInGb: 50
        networkVolumeId: "${volume.id}"
        volumeMountPath: "/workspace"
        minVcpuCount: 8
        minMemoryInGb: 32
        ports: "22/tcp,8888/http"
        startJupyter: true
        env: [{ key: "PUBLIC_KEY", value: "${sshPublicKey}" }]
      }) { id machineId }
    }
  `);
  
  const podId = createResult.podFindAndDeployOnDemand.id;
  console.log(`✅ Pod created: ${podId}`);
  
  // Wait for SSH
  console.log('⏳ Waiting for SSH...');
  let sshIp, sshPort;
  for (let i = 0; i < 60; i++) {
    const status = await graphql(`query { pod(input: {podId: "${podId}"}) { runtime { ports { ip privatePort publicPort } } } }`);
    const ports = status.pod?.runtime?.ports;
    const ssh = ports?.find(p => p.privatePort === 22);
    if (ssh?.ip) {
      sshIp = ssh.ip;
      sshPort = ssh.publicPort;
      console.log(`✅ SSH ready: ${sshIp}:${sshPort}`);
      break;
    }
    await sleep(3000);
  }
  
  if (!sshIp) {
    console.log('❌ SSH not ready');
    return;
  }
  
  // Wait for Jupyter to start
  console.log('⏳ Waiting for Jupyter...');
  await sleep(10000);
  
  // Get Jupyter token via SSH
  console.log('🔑 Getting Jupyter token...');
  const output = await sshExec(sshIp, sshPort, 'jupyter server list');
  console.log('   jupyter server list:', output.trim());
  
  const match = output.match(/token=([a-zA-Z0-9]+)/);
  if (!match) {
    console.log('❌ Could not find token');
    return;
  }
  
  const token = match[1];
  const jupyterUrl = `https://${podId}-8888.proxy.runpod.net/?token=${token}`;
  
  console.log('');
  console.log('✅ SUCCESS!');
  console.log(`🔗 Jupyter URL: ${jupyterUrl}`);
  console.log('');
  console.log('Test this URL - terminals should work!');
  console.log('');
  console.log('Pod will terminate in 3 minutes...');
  
  await sleep(180000);
  
  await graphql(`mutation { podTerminate(input: {podId: "${podId}"}) }`);
  console.log('🗑️ Pod terminated');
}

main().catch(e => console.error('Error:', e.message));
