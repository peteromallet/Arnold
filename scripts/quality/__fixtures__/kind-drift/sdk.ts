/**
 * Fixture SDK — kind-drift scenario.
 * Intentionally has 'bogusKind' in ContributionKind type and KNOWN_CONTRIBUTION_KINDS
 * but the matching schema fixture omits it from the ContributionKind enum.
 */
export type ContributionKind =
  | 'slot'
  | 'dialog'
  | 'panel'
  | 'bogusKind';  // ← intentionally not in schema

export type VideoEditorSlotName =
  | 'header'
  | 'toolbar';

export interface ExtensionContribution {
  id: string;
  kind: ContributionKind;
  order?: number;
  slot?: VideoEditorSlotName;
  label?: string;
}

export const KNOWN_CONTRIBUTION_KINDS: readonly ContributionKind[] = [
  'slot',
  'dialog',
  'panel',
  'bogusKind',
] as const;

export const CONTRIBUTION_KIND_MILESTONE: Record<ContributionKind, string | undefined> = {
  slot: 'M1',
  dialog: 'M1',
  panel: 'M1',
  bogusKind: 'M1',
};

export function contributionKindNotYetBridged(kind: ContributionKind): string | null {
  const milestone = CONTRIBUTION_KIND_MILESTONE[kind];
  if (!milestone) return 'unknown';
  if (milestone === 'M1' || milestone === 'M2') return null;
  return milestone;
}
