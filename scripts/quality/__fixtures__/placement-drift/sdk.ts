/**
 * Fixture SDK — placement-drift scenario.
 * The matching schema has PanelContribution allowing 'left-panel' instead of 'asset-panel'.
 */
export type ContributionKind =
  | 'slot'
  | 'dialog'
  | 'panel'
  | 'inspectorSection';

export type VideoEditorSlotName =
  | 'header'
  | 'toolbar';

export interface ExtensionContribution {
  id: string;
  kind: ContributionKind;
  order?: number;
  slot?: VideoEditorSlotName;
  placement?: string;
  label?: string;
}

export const KNOWN_CONTRIBUTION_KINDS: readonly ContributionKind[] = [
  'slot',
  'dialog',
  'panel',
  'inspectorSection',
] as const;

export const CONTRIBUTION_KIND_MILESTONE: Record<ContributionKind, string | undefined> = {
  slot: 'M1',
  dialog: 'M1',
  panel: 'M1',
  inspectorSection: 'M1',
};

export function contributionKindNotYetBridged(kind: ContributionKind): string | null {
  const milestone = CONTRIBUTION_KIND_MILESTONE[kind];
  if (!milestone) return 'unknown';
  if (milestone === 'M1' || milestone === 'M2') return null;
  return milestone;
}
