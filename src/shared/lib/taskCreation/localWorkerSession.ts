import { probeLocalWorker } from '@/shared/lib/localWorker/healthcheck';

export type MaterializedInputKind = 'file' | 'remote';

export interface MaterializedInputRecord {
  generation_id: string;
  kind: MaterializedInputKind;
  target: string;
}

export interface CachedResolution {
  record: MaterializedInputRecord;
  url: string;
}

export interface LocalWorkerSession {
  probe(): Promise<boolean>;
  register(record: MaterializedInputRecord, url: string): void;
  records(): MaterializedInputRecord[];
  cached(generationId: string): CachedResolution | null;
}

export function beginLocalWorkerSession(): LocalWorkerSession {
  let probePromise: Promise<boolean> | null = null;
  const accumulated: MaterializedInputRecord[] = [];
  const byGenerationId = new Map<string, CachedResolution>();

  return {
    probe(): Promise<boolean> {
      if (!probePromise) {
        probePromise = probeLocalWorker();
      }
      return probePromise;
    },
    register(record: MaterializedInputRecord, url: string): void {
      if (byGenerationId.has(record.generation_id)) return;
      byGenerationId.set(record.generation_id, { record, url });
      accumulated.push(record);
    },
    records(): MaterializedInputRecord[] {
      return [...accumulated];
    },
    cached(generationId: string): CachedResolution | null {
      return byGenerationId.get(generationId) ?? null;
    },
  };
}
