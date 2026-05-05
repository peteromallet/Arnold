// Edge-function proxy: imports directly from leaf files instead of the
// `sequence.ts` barrel. The barrel re-exports `lib/sequence-public.ts`
// which transitively pulls in React hooks (useTimelineCommit etc.) and
// would break Deno bundling.
export {
  TRUSTED_SEQUENCE_METADATA,
  TRUSTED_SEQUENCE_CLIP_TYPES,
} from "../../../src/tools/video-editor/sequences/metadata.ts";

export {
  validateSequenceDraft,
} from "../../../src/tools/video-editor/sequences/validation.ts";

export type {
  SequenceDraftParams,
  ValidatedSequenceDraft,
  SequenceDraftValidationError,
  SequenceDraftValidationResult,
} from "../../../src/tools/video-editor/sequences/validation.ts";
