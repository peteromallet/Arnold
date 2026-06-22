/**
 * Fixture SDK — manifest-placement-mismatch scenario.
 * SDK allows 'panel' with placement. Manifest uses invalid placement 'wrong-spot'
 * for a panel contribution.
 */
export type ContributionKind =
  | 'slot'
  | 'dialog'
  | 'panel'
  | 'inspectorSection'
  | 'assetDetailSection';

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
  'assetDetailSection',
] as const;

export const CONTRIBUTION_KIND_MILESTONE: Record<ContributionKind, string | undefined> = {
  slot: 'M1',
  dialog: 'M1',
  panel: 'M1',
  inspectorSection: 'M1',
  assetDetailSection: 'M6',
};

export function contributionKindNotYetBridged(kind: ContributionKind): string | null {
  const milestone = CONTRIBUTION_KIND_MILESTONE[kind];
  if (!milestone) return 'unknown';
  if (milestone === 'M1' || milestone === 'M2') return null;
  if (milestone === 'M6' && kind === 'assetDetailSection') return null;
  return milestone;
}
