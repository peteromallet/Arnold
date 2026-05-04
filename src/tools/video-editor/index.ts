/**
 * @publicContract
 * Edge-safe core SDK entrypoint for the video editor.
 *
 * Import browser-only host helpers from `./browser.ts`.
 * Import supported custom-sequence extension helpers from `./sequence.ts`.
 * Import test helpers from `./testing.ts`.
 */
export { BUILTIN_CLIP_TYPES } from './types/index.ts';

export type {
  TimelineEffect,
  ParameterType,
  AudioBindingValue,
  ParameterOption,
  ParameterDefinition,
  ParameterSchema,
  TrackKind,
  TrackFit,
  TrackBlendMode,
  BuiltinClipType,
  ClipType,
  TrackDefinition,
  ClipEntrance,
  ClipExit,
  ClipContinuous,
  ClipTransition,
  TextAlignment,
  TextClipData,
  TimelineClip,
  TimelineOutput,
  CustomEffectEntry,
  PinnedShotImageClipSnapshot,
  PinnedShotGroup,
  ThemeOverrides,
  GenerationDefaults,
  TimelineConfig,
  AssetRegistryEntry,
  AssetRegistry,
  ResolvedAssetRegistryEntry,
  ResolvedTimelineClip,
  ResolvedTimelineConfig,
} from './types/index.ts';

export type {
  CheckpointTriggerType,
  Checkpoint,
} from './types/history.ts';

export type {
  AgentSessionStatus,
  AgentTurnAttachment,
  AgentTurn,
  AgentSession,
} from './types/agent-session.ts';

export {
  TimelineVersionConflictError,
  isTimelineVersionConflictError,
  TimelineNotFoundError,
  isTimelineNotFoundError,
} from './data/DataProvider.ts';

export type {
  SilenceRegion,
  AssetProfile,
  UploadAssetOptions,
  LoadedTimeline,
  DataProvider,
} from './data/DataProvider.ts';

export {
  parseResolution,
  getClipSourceDuration,
  getClipTimelineDuration,
  secondsToFrames,
  getClipDurationInFrames,
  getTimelineDurationInFrames,
  getConfigSignature,
  getStableConfigSignature,
  resolveTimelineConfig,
} from './lib/config-utils.ts';

export type { UrlResolver } from './lib/config-utils.ts';

export {
  canonicalizeTimelinePair,
  getPairTimelineClipDuration,
  getPairTimelineDuration,
  serializeTimelineConfigSnapshot,
  serializeTimelinePair,
  TimelineDomainError,
} from './lib/timeline-domain.ts';

export {
  applyProvisionedMediaCommandToConfig,
  buildTimelineCommandData,
  createTimelineCommandRunner,
  MEDIA_COMMAND_DESCRIPTORS,
  provisionRegisteredTimelineMedia,
  provisionTimelineMedia,
} from './commands/index.ts';

export type {
  AddMediaCommand,
  JsonObject,
  SwapMediaCommand,
  TimelineCommand,
  TimelineCommandDescriptor,
  TimelineCommandExecutionResult,
  TimelineCommandInput,
  TimelineCommandRunMode,
  TimelineCommandTransaction,
  TimelineProvisionedAsset,
} from './commands/index.ts';

export { TRUSTED_SEQUENCE_CLIP_TYPES } from './sequences/metadata.ts';
