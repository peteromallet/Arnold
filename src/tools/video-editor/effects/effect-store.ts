import type { CustomEffectEntry } from '@/tools/video-editor/types/index.ts';

const STORAGE_KEY = 'video-editor:draft-effects';

export function loadDraftEffects(): Record<string, string> {
  if (typeof window === 'undefined' || typeof localStorage === 'undefined') {
    return {};
  }

  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return {};
    return JSON.parse(raw) as Record<string, string>;
  } catch {
    return {};
  }
}

export function saveDraftEffect(name: string, code: string): void {
  if (typeof localStorage === 'undefined') return;

  const drafts = loadDraftEffects();
  drafts[name] = code;
  localStorage.setItem(STORAGE_KEY, JSON.stringify(drafts));
}

export function deleteDraftEffect(name: string): void {
  if (typeof localStorage === 'undefined') return;

  const drafts = loadDraftEffects();
  delete drafts[name];
  localStorage.setItem(STORAGE_KEY, JSON.stringify(drafts));
}

export async function promoteDraftToTimeline(
  name: string,
  saveEffect: (entry: { name: string; code: string; category?: CustomEffectEntry['category'] }) => Promise<void>,
  category?: CustomEffectEntry['category'],
): Promise<void> {
  const drafts = loadDraftEffects();
  const code = drafts[name];
  if (!code) {
    throw new Error(`No draft effect found with name "${name}"`);
  }

  await saveEffect({ name, code, category });
  deleteDraftEffect(name);
}
