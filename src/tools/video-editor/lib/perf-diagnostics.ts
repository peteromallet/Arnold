type CounterState = { count: number; start: number; fired: boolean };
type RafState = CounterState & { last: number };

const now = () => (typeof performance === 'undefined' ? Date.now() : performance.now());
const PERF_DIAGNOSTICS_STORAGE_KEY = 'reigh:perf-diagnostics';
const PERF_DIAGNOSTICS_GLOBAL_FLAG = '__REIGH_PERF_DIAGNOSTICS__';

function arePerfDiagnosticsEnabled() {
  const globalScope = globalThis as typeof globalThis & {
    [PERF_DIAGNOSTICS_GLOBAL_FLAG]?: unknown;
  };

  if (globalScope[PERF_DIAGNOSTICS_GLOBAL_FLAG] === true) {
    return true;
  }

  if (typeof localStorage !== 'undefined') {
    try {
      return localStorage.getItem(PERF_DIAGNOSTICS_STORAGE_KEY) === '1';
    } catch {
      return false;
    }
  }

  return false;
}

const logPerf = (message: string, ...args: unknown[]) => {
  if (!arePerfDiagnosticsEnabled()) {
    return;
  }

  console.error(`[PERF] ${message}`, ...args);
};

// One-time confirmation that diagnostics loaded
let _booted = false;
export function bootDiagnostics() {
  if (_booted || !arePerfDiagnosticsEnabled()) return;
  _booted = true;
  logPerf('diagnostics active');

  // Report long tasks via PerformanceObserver (catches any JS blocking >50ms)
  if (typeof PerformanceObserver !== 'undefined') {
    try {
      const observer = new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          if (entry.duration > 50) {
            logPerf(`long-task: ${Math.round(entry.duration)}ms`, entry.toJSON());
          }
        }
      });
      observer.observe({ type: 'longtask', buffered: false });
    } catch {
      // longtask not supported in this browser
    }
  }

  // Monitor slow resource loads (video/image assets)
  if (typeof PerformanceObserver !== 'undefined') {
    try {
      const resourceObserver = new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          const res = entry as PerformanceResourceTiming;
          if (res.duration > 2000 && (res.name.includes('supabase') || res.name.includes('storage'))) {
            logPerf(`slow-resource: ${Math.round(res.duration)}ms | ${res.initiatorType} | ${res.name.slice(0, 120)}`);
          }
        }
      });
      resourceObserver.observe({ type: 'resource', buffered: false });
    } catch {
      // resource timing not supported
    }
  }

}

const createWindowDetector = (
  label: string,
  threshold: number,
  windowMs: number,
) => {
  let states: Map<string, CounterState> | undefined;

  return {
    track(id: string) {
      if (!arePerfDiagnosticsEnabled()) {
        return;
      }

      const time = now();
      const map = states ?? (states = new Map());
      const state = map.get(id);
      if (!state) {
        map.set(id, { count: 1, start: time, fired: false });
        return;
      }
      if (time - state.start > windowMs) {
        state.count = 1;
        state.start = time;
        state.fired = false;
        return;
      }
      state.count += 1;
      if (!state.fired && state.count > threshold) {
        state.fired = true;
        logPerf(`${label}: ${id} exceeded ${threshold}/${windowMs}ms`);
      }
    },
  };
};

let rafStates: Map<string, RafState> | undefined;

export const RafLoopDetector = {
  track(id: string) {
    if (!arePerfDiagnosticsEnabled()) {
      return;
    }

    const time = now();
    const map = rafStates ?? (rafStates = new Map());
    const state = map.get(id);
    if (!state) {
      map.set(id, { count: 1, start: time, last: time, fired: false });
      return;
    }
    if (time - state.last > 1000 || time - state.start > 5000) {
      state.count = 1;
      state.start = time;
      state.last = time;
      state.fired = false;
      return;
    }
    state.count += 1;
    state.last = time;
    if (!state.fired && state.count > 300) {
      state.fired = true;
      logPerf(`raf-loop: ${id} exceeded 1000 callbacks in 5s`);
    }
  },
};

export const RenderStormDetector = createWindowDetector('render-storm', 20, 1000);
export const EffectLoopDetector = createWindowDetector('effect-loop', 15, 1000);

type PerfWithMemory = Performance & { memory?: { usedJSHeapSize?: number } };

let memoryInterval: ReturnType<typeof setInterval> | undefined;
let lastHeap = 0;
let growthSamples = 0;
let memoryFired = false;

const sampleHeap = () => {
  if (!arePerfDiagnosticsEnabled()) {
    return;
  }

  if (typeof performance === 'undefined' || !('memory' in performance)) {
    return;
  }
  const usedHeap = (performance as PerfWithMemory).memory?.usedJSHeapSize;
  if (typeof usedHeap !== 'number') {
    return;
  }
  if (lastHeap === 0) {
    lastHeap = usedHeap;
    return;
  }
  if (usedHeap > lastHeap) {
    growthSamples += 1;
    if (!memoryFired && growthSamples >= 5) {
      memoryFired = true;
      logPerf(`memory-pressure: heap grew across ${growthSamples} samples`);
    }
  } else {
    growthSamples = 0;
    memoryFired = false;
  }
  lastHeap = usedHeap;
};

const startMemoryPressure = () => {
  if (!arePerfDiagnosticsEnabled()) {
    return;
  }

  if (memoryInterval !== undefined || typeof performance === 'undefined' || !('memory' in performance)) {
    return;
  }
  sampleHeap();
  memoryInterval = setInterval(sampleHeap, 30000);
};

const stopMemoryPressure = () => {
  if (memoryInterval !== undefined) {
    clearInterval(memoryInterval);
    memoryInterval = undefined;
  }
  lastHeap = 0;
  growthSamples = 0;
  memoryFired = false;
};

export const MemoryPressureDetector = {
  track(_id = 'video-editor') {
    startMemoryPressure();
  },
  start() {
    startMemoryPressure();
  },
  stop() {
    stopMemoryPressure();
  },
};
