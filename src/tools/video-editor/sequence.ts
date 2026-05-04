/**
 * @publicContract
 * Edge-safe custom sequence SDK for the supported video-editor extension path.
 *
 * This contract freezes one supported clip-extension workflow:
 * validate a trusted sequence draft, materialize asset-backed params, and
 * apply the draft onto a plain `TimelineConfig` without importing internal
 * editor state or row-mutation helpers.
 */
export {
  TRUSTED_SEQUENCE_THEME_ID,
  TRUSTED_SEQUENCE_METADATA,
  TRUSTED_SEQUENCE_CLIP_TYPES,
  isTrustedSequenceClipType,
  getTrustedSequenceMetadata,
} from './sequences/metadata.ts';

export type {
  SequenceParamKind,
  SequenceParamMetadata,
  SequenceHoldMetadata,
  TrustedSequenceMetadata,
  TrustedSequenceClipType,
} from './sequences/metadata.ts';

export {
  validateSequenceDraft,
  validateSequenceDrafts,
} from './sequences/validation.ts';

export type {
  SequenceDraftParams,
  ValidatedSequenceDraft,
  SequenceDraftValidationError,
  SequenceDraftValidationResult,
  ValidateSequenceDraftOptions,
} from './sequences/validation.ts';

export {
  materializeSequenceParams,
  materializeSequenceClip,
  materializeSequenceConfig,
  materializeResolvedSequenceConfig,
} from './sequences/materialize.ts';

export type {
  SequenceAssetRegistry,
} from './sequences/materialize.ts';

export {
  applySequenceDraftToTimeline,
} from './lib/sequence-public.ts';

export type {
  InsertSequenceDraftIntoTimelineOptions,
  ReplaceSequenceDraftInTimelineOptions,
  ApplySequenceDraftToTimelineOptions,
  ApplySequenceDraftToTimelineResult,
} from './lib/sequence-public.ts';
