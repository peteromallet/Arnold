import { useCallback, useMemo, useRef, useState } from 'react';
import { Loader2, Sparkles, X } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/shared/components/ui/dialog';
import { NumberInput } from '@/shared/components/ui/number-input';
import { Textarea } from '@/shared/components/ui/textarea';
import { toast } from '@/shared/components/ui/toast';
import { invokeSupabaseEdgeFunction } from '@/integrations/supabase/functions/invokeSupabaseEdgeFunction';
import { RemotionPreview } from '@/tools/video-editor/components/PreviewPanel/RemotionPreview';
import { SequenceParamEditor } from '@/tools/video-editor/components/PropertiesPanel/SequenceParamEditor';
import { useSelectedMediaClips, type SelectedMediaClip } from '@/tools/video-editor/hooks/useSelectedMediaClips';
import {
  useTimelineEditorData,
  useTimelineEditorOps,
  useTimelinePlaybackSelector,
} from '@/tools/video-editor/hooks/timelineStore';
import {
  buildInsertSequenceDraftEdit,
  buildReplaceSequenceDraftEdit,
  type SequenceDraftEditError,
} from '@/tools/video-editor/lib/sequence-drafts';
import { useCurrentAttachmentSet } from '@/shared/state/currentAttachmentSet';
import { materializeResolvedSequenceConfig } from '@/tools/video-editor/sequences/materialize';
import {
  AVAILABLE_SEQUENCE_CLIP_TYPES,
  AVAILABLE_SEQUENCE_METADATA,
  getAvailableSequenceMetadata,
} from '@/tools/video-editor/sequences/registry';
import {
  validateSequenceDraft,
  type ValidatedSequenceDraft,
} from '@/tools/video-editor/sequences/validation';
import type {
  ResolvedAssetRegistryEntry,
  ResolvedTimelineClip,
  ResolvedTimelineConfig,
} from '@/tools/video-editor/types';

type SequenceCreatorPanelProps = {
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
};

export type AllowedSequenceAsset = {
  key: string;
  url: string;
  mediaType: SelectedMediaClip['mediaType'];
  source: 'selected' | 'attached';
  label: string;
};

type EditableSequenceDraft = {
  clipType: string;
  hold: number;
  params: Record<string, unknown>;
};

type GenerateSequenceResponse = {
  drafts?: unknown[];
  invalid_drafts?: Array<{ index: number; errors: unknown[] }>;
  model?: string;
  error?: string;
  details?: string;
};

type SequenceGenerationClipPayload = {
  clipId: string;
  assetKey: string;
  url: string;
  mediaType: SelectedMediaClip['mediaType'];
  shotId?: string;
  shotName?: string;
};

const TEMP_SEQUENCE_PREVIEW_CLIP_ID = '__sequence_preview__';

const createEditableDraft = (draft: ValidatedSequenceDraft): EditableSequenceDraft => ({
  clipType: draft.clipType,
  hold: draft.hold,
  params: { ...draft.params },
});

const formatEditError = (error: SequenceDraftEditError): string => {
  switch (error) {
    case 'no_visual_track':
      return 'Add or select a visual track before inserting a sequence.';
    case 'replace_target_missing':
      return 'Select a visual clip to replace.';
    case 'replace_target_not_visual':
      return 'Sequences can only replace visual clips. Audio clips are not valid replace targets.';
    default:
      return 'This sequence cannot be inserted here.';
  }
};

export const buildAllowedSequenceAssets = (
  selectedClips: readonly SelectedMediaClip[],
  attachedClips: readonly SelectedMediaClip[],
  registry: ResolvedTimelineConfig['registry'],
): AllowedSequenceAsset[] => {
  const byKey = new Map<string, AllowedSequenceAsset>();

  const addClip = (clip: SelectedMediaClip, source: AllowedSequenceAsset['source']) => {
    if (!clip.assetKey || clip.isPlaceholder) return;
    const entry = registry[clip.assetKey];
    if (!entry?.src) return;
    if (byKey.has(clip.assetKey)) return;
    byKey.set(clip.assetKey, {
      key: clip.assetKey,
      url: entry.src,
      mediaType: clip.mediaType,
      source,
      label: clip.shotName ?? clip.assetKey,
    });
  };

  selectedClips.forEach((clip) => addClip(clip, 'selected'));
  attachedClips.forEach((clip) => addClip(clip, 'attached'));

  return [...byKey.values()];
};

const buildAllowedAssetRegistry = (
  assets: readonly AllowedSequenceAsset[],
  registry: ResolvedTimelineConfig['registry'],
): ResolvedTimelineConfig['registry'] => {
  return assets.reduce<Record<string, ResolvedAssetRegistryEntry>>((next, asset) => {
    const entry = registry[asset.key];
    if (entry) next[asset.key] = entry;
    return next;
  }, {});
};

export const buildGenerationClipPayloads = (
  clips: readonly SelectedMediaClip[],
  allowedAssets: readonly AllowedSequenceAsset[],
): SequenceGenerationClipPayload[] => {
  const allowedByKey = new Map(allowedAssets.map((asset) => [asset.key, asset]));
  return clips.flatMap((clip) => {
    if (!clip.assetKey || clip.isPlaceholder) return [];
    const asset = allowedByKey.get(clip.assetKey);
    if (!asset) return [];
    return [{
      clipId: clip.clipId,
      assetKey: asset.key,
      url: asset.url,
      mediaType: clip.mediaType,
      shotId: clip.shotId,
      shotName: clip.shotName,
    }];
  });
};

const validateEditableSequenceDraft = (
  draft: EditableSequenceDraft,
  allowedAssetKeys: readonly string[],
) => validateSequenceDraft(draft, {
  metadata: AVAILABLE_SEQUENCE_METADATA,
  allowedClipTypes: AVAILABLE_SEQUENCE_CLIP_TYPES,
  allowedAssetKeys,
});

export const buildSequencePreviewConfig = (
  resolvedConfig: ResolvedTimelineConfig,
  draft: ValidatedSequenceDraft,
): ResolvedTimelineConfig | null => {
  const sourceTrack = resolvedConfig.tracks.find((track) => track.kind === 'visual');
  const trackId = sourceTrack?.id ?? 'sequence-preview-visual';

  const clip: ResolvedTimelineClip = {
    id: TEMP_SEQUENCE_PREVIEW_CLIP_ID,
    clipType: draft.clipType,
    track: trackId,
    at: 0,
    hold: draft.hold,
    params: { ...draft.params },
  };

  return materializeResolvedSequenceConfig({
    ...resolvedConfig,
    tracks: [
      sourceTrack
        ? { ...sourceTrack, id: trackId }
        : { id: trackId, kind: 'visual', label: 'Sequence preview' },
    ],
    clips: [clip],
  });
};

const summarizeValidationErrors = (errors: readonly { message: string }[]): string => (
  errors.map((error) => error.message).join(' ')
);

export function SequenceCreatorPanel({
  open = true,
  onOpenChange,
}: SequenceCreatorPanelProps) {
  const selectedMedia = useSelectedMediaClips();
  const attachmentSet = useCurrentAttachmentSet();
  const { data, resolvedConfig, selectedClipId, selectedTrackId } = useTimelineEditorData();
  const { applyEdit } = useTimelineEditorOps();
  const currentTime = useTimelinePlaybackSelector((playback) => playback.currentTime);
  const previewContainerRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  const [prompt, setPrompt] = useState('');
  const [drafts, setDrafts] = useState<EditableSequenceDraft[]>([]);
  const [selectedDraftIndex, setSelectedDraftIndex] = useState(0);
  const [isGenerating, setIsGenerating] = useState(false);
  const [generationNote, setGenerationNote] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const allowedAssets = useMemo(() => (
    resolvedConfig
      ? buildAllowedSequenceAssets(selectedMedia.clips, attachmentSet.clips, resolvedConfig.registry)
      : []
  ), [attachmentSet.clips, resolvedConfig, selectedMedia.clips]);

  const allowedAssetKeys = useMemo(() => allowedAssets.map((asset) => asset.key), [allowedAssets]);

  const allowedRegistry = useMemo(() => (
    resolvedConfig ? buildAllowedAssetRegistry(allowedAssets, resolvedConfig.registry) : {}
  ), [allowedAssets, resolvedConfig]);

  const selectedDraft = drafts[selectedDraftIndex] ?? null;
  const selectedValidation = useMemo(() => (
    selectedDraft ? validateEditableSequenceDraft(selectedDraft, allowedAssetKeys) : null
  ), [allowedAssetKeys, selectedDraft]);
  const validatedDraft = selectedValidation?.ok ? selectedValidation.draft : null;
  const selectedMetadata = selectedDraft ? getAvailableSequenceMetadata(selectedDraft.clipType) : undefined;

  const previewConfig = useMemo(() => {
    if (!resolvedConfig || !validatedDraft) return null;
    return buildSequencePreviewConfig(resolvedConfig, validatedDraft);
  }, [resolvedConfig, validatedDraft]);

  const replaceProbe = useMemo(() => {
    if (!data || !validatedDraft) return null;
    return buildReplaceSequenceDraftEdit(data, validatedDraft, { selectedClipId });
  }, [data, selectedClipId, validatedDraft]);

  const replaceDisabledReason = useMemo(() => {
    if (!validatedDraft) {
      return selectedValidation && !selectedValidation.ok
        ? summarizeValidationErrors(selectedValidation.errors)
        : 'Generate or select a valid sequence draft first.';
    }
    if (!replaceProbe) return 'Select a visual clip to replace.';
    return replaceProbe.ok ? null : formatEditError(replaceProbe.error);
  }, [replaceProbe, selectedValidation, validatedDraft]);

  const handleGenerate = useCallback(async () => {
    if (!prompt.trim()) {
      toast({ title: 'Prompt required', description: 'Describe the sequence you want to create.', variant: 'destructive' });
      return;
    }
    if (!resolvedConfig) {
      toast({ title: 'Timeline unavailable', description: 'Load a timeline before generating a sequence.', variant: 'destructive' });
      return;
    }

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setIsGenerating(true);
    setGenerationNote(null);
    setActionError(null);
    setDrafts([]);
    setSelectedDraftIndex(0);

    try {
      const response = await invokeSupabaseEdgeFunction<GenerateSequenceResponse>(
        'ai-generate-sequence',
        {
          body: {
            prompt: prompt.trim(),
            timeline: {
              output: resolvedConfig.output,
              tracks: resolvedConfig.tracks,
              clips: resolvedConfig.clips.map((clip) => ({
                id: clip.id,
                clipType: clip.clipType,
                asset: clip.asset,
                track: clip.track,
                at: clip.at,
                hold: clip.hold,
                params: clip.params,
              })),
            },
            selected_clips: buildGenerationClipPayloads(selectedMedia.clips, allowedAssets),
            attached_clips: buildGenerationClipPayloads(attachmentSet.clips, allowedAssets),
            allowed_clip_types: AVAILABLE_SEQUENCE_CLIP_TYPES,
            allowed_assets: allowedAssets.map((asset) => ({
              key: asset.key,
              assetKey: asset.key,
              url: asset.url,
              mediaType: asset.mediaType,
              source: asset.source,
            })),
            theme: resolvedConfig.theme,
            theme_overrides: resolvedConfig.theme_overrides,
          },
          timeoutMs: 150_000,
          signal: controller.signal,
        },
      );
      if (controller.signal.aborted) return;
      if (response.error) {
        throw new Error(response.details || response.error);
      }

      const validDrafts: EditableSequenceDraft[] = [];
      const invalidCountFromClient = (response.drafts ?? []).reduce((count, rawDraft) => {
        const validation = validateSequenceDraft(rawDraft, {
          metadata: AVAILABLE_SEQUENCE_METADATA,
          allowedClipTypes: AVAILABLE_SEQUENCE_CLIP_TYPES,
          allowedAssetKeys,
        });
        if (validation.ok) {
          validDrafts.push(createEditableDraft(validation.draft));
          return count;
        }
        return count + 1;
      }, 0);
      const invalidCount = invalidCountFromClient + (response.invalid_drafts?.length ?? 0);

      if (validDrafts.length === 0) {
        setDrafts([]);
        setGenerationNote(invalidCount > 0
          ? 'The model returned drafts, but none matched the trusted sequence schema for the current selected or attached assets.'
          : 'No sequence drafts were returned.');
        return;
      }

      setDrafts(validDrafts);
      setSelectedDraftIndex(0);
      setGenerationNote(invalidCount > 0
        ? `${invalidCount} invalid draft${invalidCount === 1 ? '' : 's'} ${invalidCount === 1 ? 'was' : 'were'} rejected.`
        : null);
    } catch (err) {
      if ((err as Error).name === 'AbortError') return;
      const message = err instanceof Error ? err.message : 'Sequence generation failed.';
      toast({ title: 'Sequence generation failed', description: message, variant: 'destructive' });
      setGenerationNote(message);
    } finally {
      setIsGenerating(false);
    }
  }, [
    allowedAssetKeys,
    allowedAssets,
    attachmentSet.clips,
    prompt,
    resolvedConfig,
    selectedMedia.clips,
  ]);

  const updateSelectedDraft = useCallback((patch: Partial<EditableSequenceDraft>) => {
    setDrafts((current) => current.map((draft, index) => (
      index === selectedDraftIndex
        ? { ...draft, ...patch }
        : draft
    )));
    setActionError(null);
  }, [selectedDraftIndex]);

  const handleInsert = useCallback(() => {
    if (!data || !validatedDraft) return;
    const result = buildInsertSequenceDraftEdit(data, validatedDraft, {
      at: currentTime,
      selectedTrackId,
    });
    if (!result.ok) {
      setActionError(formatEditError(result.error));
      return;
    }
    applyEdit(result.mutation, {
      selectedClipId: result.selectedClipId,
      selectedTrackId: result.selectedTrackId,
    });
    onOpenChange?.(false);
  }, [applyEdit, currentTime, data, onOpenChange, selectedTrackId, validatedDraft]);

  const handleReplace = useCallback(() => {
    if (!data || !validatedDraft) return;
    const result = buildReplaceSequenceDraftEdit(data, validatedDraft, { selectedClipId });
    if (!result.ok) {
      setActionError(formatEditError(result.error));
      return;
    }
    applyEdit(result.mutation, {
      selectedClipId: result.selectedClipId,
      selectedTrackId: result.selectedTrackId,
    });
    onOpenChange?.(false);
  }, [applyEdit, data, onOpenChange, selectedClipId, validatedDraft]);

  const insertDisabledReason = !validatedDraft
    ? (selectedValidation && !selectedValidation.ok
      ? summarizeValidationErrors(selectedValidation.errors)
      : 'Generate or select a valid sequence draft first.')
    : (!data ? 'Timeline unavailable.' : null);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[92vh] max-w-6xl overflow-hidden p-0">
        <div className="flex max-h-[92vh] min-h-[720px] flex-col">
          <DialogHeader className="border-b border-border px-5 py-4">
            <div className="flex items-start justify-between gap-4">
              <div>
                <DialogTitle>Sequence Creator</DialogTitle>
                <DialogDescription>
                  Generate trusted timeline sequence drafts from a prompt and the currently selected or attached assets.
                </DialogDescription>
              </div>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                aria-label="Close sequence creator"
                onClick={() => onOpenChange?.(false)}
              >
                <X className="h-4 w-4" />
              </Button>
            </div>
          </DialogHeader>

          <div className="grid min-h-0 flex-1 grid-cols-[minmax(320px,420px)_1fr] overflow-hidden">
            <div className="min-h-0 overflow-y-auto border-r border-border p-4">
              <div className="space-y-4">
                <div className="space-y-2">
                  <div className="text-sm font-medium text-foreground">Prompt</div>
                  <Textarea
                    value={prompt}
                    rows={5}
                    placeholder="Make these selected images jump between each other..."
                    onChange={(event) => setPrompt(event.target.value)}
                  />
                  <Button
                    type="button"
                    className="w-full gap-2"
                    onClick={handleGenerate}
                    disabled={isGenerating || !prompt.trim()}
                  >
                    {isGenerating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
                    Generate Sequence
                  </Button>
                </div>

                <div className="space-y-2 rounded-lg border border-border bg-card/60 p-3">
                  <div className="flex items-center justify-between gap-3">
                    <div className="text-sm font-medium text-foreground">Allowed Assets</div>
                    <div className="text-xs text-muted-foreground">{allowedAssets.length}</div>
                  </div>
                  {allowedAssets.length > 0 ? (
                    <div className="flex flex-wrap gap-1.5">
                      {allowedAssets.map((asset) => (
                        <span
                          key={asset.key}
                          className="max-w-full truncate rounded-md border border-border/70 bg-background px-2 py-1 text-[11px] text-muted-foreground"
                          title={asset.url}
                        >
                          {asset.source}: {asset.key}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <div className="text-xs text-muted-foreground">
                      Select timeline media or attach asset chips before asking for asset-backed drafts.
                    </div>
                  )}
                </div>

                {generationNote && (
                  <div className="rounded-lg border border-border bg-muted/50 p-3 text-xs text-muted-foreground">
                    {generationNote}
                  </div>
                )}

                {drafts.length > 0 && (
                  <div className="space-y-2">
                    <div className="text-sm font-medium text-foreground">Drafts</div>
                    <div className="space-y-2">
                      {drafts.map((draft, index) => {
                        const metadata = getAvailableSequenceMetadata(draft.clipType);
                        return (
                          <button
                            key={`${draft.clipType}-${index}`}
                            type="button"
                            className={[
                              'w-full rounded-lg border p-3 text-left transition-colors',
                              index === selectedDraftIndex
                                ? 'border-primary bg-primary/10'
                                : 'border-border bg-card/60 hover:bg-muted/60',
                            ].join(' ')}
                            onClick={() => {
                              setSelectedDraftIndex(index);
                              setActionError(null);
                            }}
                          >
                            <div className="text-sm font-medium text-foreground">
                              {metadata?.label ?? draft.clipType}
                            </div>
                            <div className="text-xs text-muted-foreground">{draft.hold}s</div>
                          </button>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>
            </div>

            <div className="grid min-h-0 grid-rows-[minmax(280px,1fr)_auto]">
              <div className="min-h-0 overflow-hidden bg-black">
                {previewConfig ? (
                  <RemotionPreview
                    config={previewConfig}
                    onTimeUpdate={() => undefined}
                    playerContainerRef={previewContainerRef}
                    compact
                    initialTime={0}
                  />
                ) : (
                  <div className="flex h-full items-center justify-center p-6 text-center text-sm text-muted-foreground">
                    Generate a valid draft to preview it in the Remotion player.
                  </div>
                )}
              </div>

              <div className="max-h-[360px] min-h-0 overflow-y-auto border-t border-border p-4">
                {selectedDraft && selectedMetadata ? (
                  <div className="space-y-4">
                    <div className="grid grid-cols-[1fr_140px] items-end gap-3">
                      <div>
                        <div className="text-sm font-medium text-foreground">{selectedMetadata.label}</div>
                        <div className="text-xs text-muted-foreground">{selectedMetadata.description}</div>
                      </div>
                      <div className="space-y-1.5">
                        <div className="text-xs font-medium text-muted-foreground">Duration</div>
                        <NumberInput
                          value={selectedDraft.hold}
                          min={selectedMetadata.hold.minSeconds}
                          max={selectedMetadata.hold.maxSeconds}
                          step={selectedMetadata.hold.stepSeconds}
                          onChange={(value) => updateSelectedDraft({ hold: value ?? selectedMetadata.hold.defaultSeconds })}
                        />
                      </div>
                    </div>

                    <SequenceParamEditor
                      metadata={selectedMetadata}
                      params={selectedDraft.params}
                      registry={allowedRegistry}
                      onChange={(params) => updateSelectedDraft({ params })}
                    />

                    {selectedValidation && !selectedValidation.ok && (
                      <div className="rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-xs text-destructive">
                        {summarizeValidationErrors(selectedValidation.errors)}
                      </div>
                    )}

                    {(actionError || replaceDisabledReason || insertDisabledReason) && (
                      <div className="rounded-lg border border-border bg-muted/50 p-3 text-xs text-muted-foreground">
                        {actionError ?? replaceDisabledReason ?? insertDisabledReason}
                      </div>
                    )}

                    <div className="flex justify-end gap-2">
                      <Button
                        type="button"
                        variant="secondary"
                        disabled={Boolean(replaceDisabledReason)}
                        onClick={handleReplace}
                        title={replaceDisabledReason ?? undefined}
                      >
                        Replace selected
                      </Button>
                      <Button
                        type="button"
                        disabled={Boolean(insertDisabledReason)}
                        onClick={handleInsert}
                        title={insertDisabledReason ?? undefined}
                      >
                        Insert at playhead
                      </Button>
                    </div>
                  </div>
                ) : (
                  <div className="rounded-lg border border-border bg-card/60 p-4 text-sm text-muted-foreground">
                    Generated sequence drafts will appear here for timing and parameter edits.
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
