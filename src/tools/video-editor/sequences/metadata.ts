export const TRUSTED_SEQUENCE_THEME_ID = '2rp' as const;

export type SequenceParamKind = 'string' | 'asset-list';

export type SequenceParamMetadata = {
  key: string;
  label: string;
  kind: SequenceParamKind;
  description: string;
  required?: boolean;
  defaultValue?: string | readonly string[];
  options?: readonly string[];
  maxItems?: number;
  componentParam?: string;
};

export type SequenceHoldMetadata = {
  defaultSeconds: number;
  minSeconds: number;
  maxSeconds: number;
  stepSeconds: number;
};

export type TrustedSequenceMetadata = {
  clipType: string;
  themeId: typeof TRUSTED_SEQUENCE_THEME_ID;
  label: string;
  description: string;
  whenToUse: string;
  hold: SequenceHoldMetadata;
  params: readonly SequenceParamMetadata[];
};

const DEFAULT_HOLD: SequenceHoldMetadata = {
  defaultSeconds: 3,
  minSeconds: 1,
  maxSeconds: 12,
  stepSeconds: 0.5,
};

export const TRUSTED_SEQUENCE_METADATA = [
  {
    clipType: 'image-jump',
    themeId: TRUSTED_SEQUENCE_THEME_ID,
    label: 'Image Jump',
    description: 'Motion-only image sequence that snaps, pops, and jumps between selected assets.',
    whenToUse: 'Use when the prompt asks to move, jump, cycle, swap, flash, or animate selected images without needing titles or text.',
    hold: {
      defaultSeconds: 4,
      minSeconds: 1,
      maxSeconds: 20,
      stepSeconds: 0.5,
    },
    params: [
      {
        key: 'imageAssetKeys',
        label: 'Images',
        kind: 'asset-list',
        description: 'Selected or attached image asset keys to animate between.',
        required: true,
        defaultValue: [],
        maxItems: 8,
        componentParam: 'images',
      },
      {
        key: 'mode',
        label: 'Motion',
        kind: 'string',
        description: 'Motion style. Use jump for hard cuts, snap for quick scale hits, gallery for side-by-side browsing, pulse for rhythmic zooms, and shuffle for overlapping card movement.',
        defaultValue: 'jump',
        options: ['jump', 'snap', 'gallery', 'pulse', 'shuffle'],
      },
    ],
  },
  {
    clipType: 'section-hook',
    themeId: TRUSTED_SEQUENCE_THEME_ID,
    label: '2RP Section Hook',
    description: 'Large manifesto section title for 2RP videos.',
    whenToUse: 'Use for opening hooks, major section transitions, and statements of premise.',
    hold: DEFAULT_HOLD,
    params: [
      {
        key: 'kicker',
        label: 'Kicker',
        kind: 'string',
        description: 'Short label above the title.',
        defaultValue: '2RP',
      },
      {
        key: 'title',
        label: 'Title',
        kind: 'string',
        description: 'Primary section headline.',
        required: true,
        defaultValue: 'A new renaissance',
      },
      {
        key: 'subtitle',
        label: 'Subtitle',
        kind: 'string',
        description: 'Optional supporting sentence below the title.',
        defaultValue: 'Beauty, agency, and ambition at planetary scale.',
      },
    ],
  },
  {
    clipType: 'art-card',
    themeId: TRUSTED_SEQUENCE_THEME_ID,
    label: '2RP Art Card',
    description: 'Framed art beat with Renaissance-inspired captioning.',
    whenToUse: 'Use for individual art-piece reveal beats.',
    hold: DEFAULT_HOLD,
    params: [
      {
        key: 'title',
        label: 'Title',
        kind: 'string',
        description: 'Artwork or beat title.',
        required: true,
        defaultValue: 'Patronage returns',
      },
      {
        key: 'caption',
        label: 'Caption',
        kind: 'string',
        description: 'Short caption for the art reveal.',
        defaultValue: 'The studio becomes a cathedral for new tools.',
      },
      {
        key: 'credit',
        label: 'Credit',
        kind: 'string',
        description: 'Optional creator or attribution line.',
      },
    ],
  },
  {
    clipType: 'resource-card',
    themeId: TRUSTED_SEQUENCE_THEME_ID,
    label: '2RP Resource Card',
    description: 'Metric and resource beat for 2RP videos.',
    whenToUse: 'Use for individual resource reveal beats.',
    hold: DEFAULT_HOLD,
    params: [
      {
        key: 'label',
        label: 'Label',
        kind: 'string',
        description: 'Small uppercase category label.',
        defaultValue: 'RESOURCE',
      },
      {
        key: 'title',
        label: 'Title',
        kind: 'string',
        description: 'Resource title.',
        required: true,
        defaultValue: 'Leverage for creators',
      },
      {
        key: 'detail',
        label: 'Detail',
        kind: 'string',
        description: 'Brief description of the resource.',
        defaultValue: 'more surface area for craft, taste, and agency',
      },
      {
        key: 'metric',
        label: 'Metric',
        kind: 'string',
        description: 'Short metric or emphasis string.',
        defaultValue: '10x',
      },
      {
        key: 'previewAssetKeys',
        label: 'Preview Assets',
        kind: 'asset-list',
        description: 'Registry asset keys to materialize into preview image URLs.',
        defaultValue: [],
        maxItems: 3,
        componentParam: 'previews',
      },
    ],
  },
  {
    clipType: 'cta-card',
    themeId: TRUSTED_SEQUENCE_THEME_ID,
    label: '2RP CTA Card',
    description: 'Closing call-to-action card for 2RP videos.',
    whenToUse: 'Use for the final closing beat.',
    hold: DEFAULT_HOLD,
    params: [
      {
        key: 'title',
        label: 'Title',
        kind: 'string',
        description: 'Primary call-to-action headline.',
        required: true,
        defaultValue: 'Imagine, then create',
      },
      {
        key: 'action',
        label: 'Action',
        kind: 'string',
        description: 'Concrete action line.',
        defaultValue: 'Join the second renaissance.',
      },
      {
        key: 'note',
        label: 'Note',
        kind: 'string',
        description: 'Optional secondary note.',
      },
    ],
  },
] as const satisfies readonly TrustedSequenceMetadata[];

export type TrustedSequenceClipType = (typeof TRUSTED_SEQUENCE_METADATA)[number]['clipType'];

export const TRUSTED_SEQUENCE_CLIP_TYPES = TRUSTED_SEQUENCE_METADATA.map(
  (metadata) => metadata.clipType,
) as readonly TrustedSequenceClipType[];

export const isTrustedSequenceClipType = (value: unknown): value is TrustedSequenceClipType => {
  return typeof value === 'string' && (TRUSTED_SEQUENCE_CLIP_TYPES as readonly string[]).includes(value);
};

export const getTrustedSequenceMetadata = (
  clipType: string,
): TrustedSequenceMetadata | undefined => {
  return TRUSTED_SEQUENCE_METADATA.find((metadata) => metadata.clipType === clipType);
};
