import { useEffect, useRef } from 'react';

type MountTelemetry = {
  budget: number;
  count: number;
  name: string;
};

export type RenderBudgetTelemetryEntry = {
  budget: number;
  maxCount: number;
  mounts: number;
  name: string;
  status: 'over' | 'under';
};

type TelemetryListener = () => void;

const INTERACTION_WINDOW_MS = 1000;

const mountTelemetry = new Map<number, MountTelemetry>();
const listeners = new Set<TelemetryListener>();

let nextInstanceId = 1;

function emitTelemetryChange() {
  for (const listener of listeners) {
    listener();
  }
}

function upsertMountTelemetry(instanceId: number, telemetry: MountTelemetry) {
  mountTelemetry.set(instanceId, telemetry);
  emitTelemetryChange();
}

function removeMountTelemetry(instanceId: number) {
  if (mountTelemetry.delete(instanceId)) {
    emitTelemetryChange();
  }
}

export function getRenderBudgetTelemetrySnapshot(): RenderBudgetTelemetryEntry[] {
  const grouped = new Map<string, RenderBudgetTelemetryEntry>();

  for (const telemetry of mountTelemetry.values()) {
    const current = grouped.get(telemetry.name);
    if (current === undefined) {
      grouped.set(telemetry.name, {
        budget: telemetry.budget,
        maxCount: telemetry.count,
        mounts: 1,
        name: telemetry.name,
        status: telemetry.count > telemetry.budget ? 'over' : 'under',
      });
      continue;
    }

    const maxCount = Math.max(current.maxCount, telemetry.count);
    const budget = Math.max(current.budget, telemetry.budget);
    grouped.set(telemetry.name, {
      ...current,
      budget,
      maxCount,
      mounts: current.mounts + 1,
      status: maxCount > budget ? 'over' : 'under',
    });
  }

  return Array.from(grouped.values()).sort((a, b) => a.name.localeCompare(b.name));
}

export function subscribeRenderBudgetTelemetry(listener: TelemetryListener): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function useRenderBudget(name: string, budget: number): void {
  const instanceIdRef = useRef<number | null>(null);
  const countRef = useRef(0);
  const idleTimerRef = useRef<number | null>(null);
  const lastRenderAtRef = useRef<number>(0);
  const warnedInWindowRef = useRef(false);

  if (instanceIdRef.current === null) {
    instanceIdRef.current = nextInstanceId++;
  }

  const isDev = import.meta.env.DEV;

  if (isDev) {
    const now = Date.now();
    if (lastRenderAtRef.current > 0 && now - lastRenderAtRef.current > INTERACTION_WINDOW_MS) {
      countRef.current = 0;
      warnedInWindowRef.current = false;
    }

    countRef.current += 1;
    lastRenderAtRef.current = now;

    if (countRef.current > budget && !warnedInWindowRef.current) {
      console.warn(`[RenderBudget] ${name} rendered ${countRef.current} times (budget ${budget})`);
      warnedInWindowRef.current = true;
    }
  }

  useEffect(() => {
    if (!isDev) {
      return;
    }

    const instanceId = instanceIdRef.current!;

    upsertMountTelemetry(instanceId, {
      budget,
      count: countRef.current,
      name,
    });

    if (idleTimerRef.current !== null) {
      window.clearTimeout(idleTimerRef.current);
    }

    idleTimerRef.current = window.setTimeout(() => {
      countRef.current = 0;
      warnedInWindowRef.current = false;
      lastRenderAtRef.current = 0;

      upsertMountTelemetry(instanceId, {
        budget,
        count: 0,
        name,
      });
    }, INTERACTION_WINDOW_MS);
  });

  useEffect(() => {
    if (!isDev) {
      return;
    }

    const instanceId = instanceIdRef.current!;

    return () => {
      if (idleTimerRef.current !== null) {
        window.clearTimeout(idleTimerRef.current);
      }
      removeMountTelemetry(instanceId);
    };
  }, [isDev]);
}
