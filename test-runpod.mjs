import 'dotenv/config';

const RUNPOD_API_URL = 'https://api.runpod.io/graphql';
const apiKey = process.env.RUNPOD_API_KEY;

if (!apiKey) {
  console.error('❌ No RUNPOD_API_KEY in environment');
  process.exit(1);
}

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
  if (result.errors) {
    console.error('GraphQL errors:', JSON.stringify(result.errors, null, 2));
    throw new Error(result.errors[0].message);
  }
  return result.data;
}

async function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function main() {
  const podName = `test-jupyter-${Date.now()}`;
  console.log(`\n🚀 Creating pod: ${podName}`);
  console.log('   Using: startJupyter: true, JUPYTER_TOKEN env var');

  // Get network volume ID
  const volumeData = await graphql(`
    query {
      myself {
        networkVolumes {
          id
          name
        }
      }
    }
  `);
  const peterVolume = volumeData.myself.networkVolumes.find(v => v.name === 'Peter');
  if (!peterVolume) {
    console.error('❌ Network volume "Peter" not found');
    process.exit(1);
  }
  console.log(`   Volume ID: ${peterVolume.id}`);

  // Create pod with JUPYTER_TOKEN="" to disable auth
  const createMutation = `
    mutation {
      podFindAndDeployOnDemand(input: {
        name: "${podName}"
        imageName: "runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04"
        gpuTypeId: "NVIDIA GeForce RTX 4090"
        gpuCount: 1
        cloudType: SECURE
        containerDiskInGb: 50
        networkVolumeId: "${peterVolume.id}"
        volumeMountPath: "/workspace"
        minVcpuCount: 8
        minMemoryInGb: 32
        ports: "22/tcp,8888/http"
        startJupyter: true
        env: [
          { key: "JUPYTER_TOKEN", value: "" }
        ]
      }) {
        id
        name
        desiredStatus
        machineId
      }
    }
  `;

  let podId;
  try {
    const createData = await graphql(createMutation);
    const pod = createData.podFindAndDeployOnDemand;
    podId = pod.id;
    console.log(`\n✅ Pod created!`);
    console.log(`   ID: ${podId}`);
    console.log(`   Machine ID: ${pod.machineId || 'waiting...'}`);
  } catch (e) {
    console.error('❌ Failed to create pod:', e);
    process.exit(1);
  }

  // Wait for pod to be running with ports
  console.log('\n⏳ Waiting for pod to be ready...');
  const startTime = Date.now();
  let jupyterUrl = '';
  
  while (Date.now() - startTime < 120000) {
    const statusData = await graphql(`
      query {
        pod(input: {podId: "${podId}"}) {
          id
          desiredStatus
          runtime {
            uptimeInSeconds
            ports {
              ip
              privatePort
              publicPort
            }
          }
        }
      }
    `);
    
    const pod = statusData.pod;
    const elapsed = Math.round((Date.now() - startTime) / 1000);
    
    if (pod.desiredStatus === 'RUNNING' && pod.runtime?.ports?.length > 0) {
      const port8888 = pod.runtime.ports.find(p => p.privatePort === 8888);
      if (port8888) {
        jupyterUrl = `https://${podId}-8888.proxy.runpod.net`;
        console.log(`\n✅ Pod is RUNNING! (${elapsed}s)`);
        console.log(`   Jupyter URL: ${jupyterUrl}`);
        break;
      }
    }
    
    console.log(`   [${elapsed}s] Status: ${pod.desiredStatus}, Ports: ${pod.runtime?.ports?.length || 0}`);
    await sleep(5000);
  }

  console.log(`\n📋 TEST THIS URL IN BROWSER:`);
  console.log(`   ${jupyterUrl}`);
  console.log(`\n   1. Does it load without asking for token?`);
  console.log(`   2. Can you open a Terminal?`);
  console.log(`\n⚠️  Pod will terminate in 60 seconds...`);
  console.log(`   Pod ID: ${podId}`);
  
  await sleep(180000); // 3 minutes to test
  
  console.log('\n🗑️  Terminating pod...');
  await graphql(`mutation { podTerminate(input: {podId: "${podId}"}) }`);
  console.log('✅ Pod terminated');
}

main().catch(console.error);
