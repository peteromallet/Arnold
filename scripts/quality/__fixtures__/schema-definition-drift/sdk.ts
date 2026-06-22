/**
 * Fixture SDK — schema-definition-drift scenario.
 * SDK has 'slot', 'dialog', 'panel' — but schema's Contribution oneOf
 * lists definitions for SlotContribution and DialogContribution only,
 * missing PanelContribution entirely.
 */
export type ContributionKind =
  | 'slot'
  | 'dialog'
  | 'panel';

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
] as const;

export const CONTRIBUTION_KIND_MILESTONE: Record<ContributionKind, string | undefined> = {
  slot: 'M1',
  dialog: 'M1',
  panel: 'M1',
};

export function contributionKindNotYetBridged(kind: ContributionKind): string | null {
  const milestone = CONTRIBUTION_KIND_MILESTONE[kind];
  if (!milestone) return 'unknown';
  if (milestone === 'M1' || milestone === 'M2') return null;
  return milestone;
}
