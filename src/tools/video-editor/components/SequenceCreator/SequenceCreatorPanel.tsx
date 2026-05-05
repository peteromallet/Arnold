import { useCallback, useMemo, useRef, useState } from 'react';
import { Loader2, Sparkles } from 'lucide-react';
import { Button } from '@/shared/components/ui/button.tsx';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/shared/components/ui/dialog.tsx';
import { NumberInput } from '@/shared/components/ui/number-input.tsx';
import { Textarea } from '@/shared/components/ui/textarea.tsx';
import { toast } from '@/shared/components/ui/toast.tsx';
import { RemotionPreview } from '@/tools/video-editor/components/PreviewPanel/RemotionPreview.tsx';
import { SequenceParamEditor } from '@/tools/video-editor/components/PropertiesPanel/SequenceParamEditor.tsx';
import { useSelectedMediaClips } from '@/tools/video-editor/hooks/useSelectedMediaClips.ts';
import {
  useTimelineEditorData,
  useTimelineEditorOps,
  useTimelinePlaybackSelector,
} from '@/tools/video-editor/hooks/timelineStore.ts';
import {
  buildInsertSequenceDraftEdit,
  buildReplaceSequenceDraftEdit,
  type SequenceDraftEditError,
} from '@/tools/video-editor/lib/sequence-drafts.ts';
import { requestCenterTimelineClip } from '@/tools/video-editor/lib/timeline-viewport-events.ts';
import { useCurrentAttachmentSet } from '@/shared/state/currentAttachmentSet.ts';
import { composerRemoveAttachment } from '@/shared/state/selectionStore.ts';
import { AgentChatAttachmentStrip } from '@/tools/video-editor/components/AgentChat/AgentChatMessage.tsx';
import {
  attachSequenceGenerationMetadata,
  buildAllowedAssetRegistry,
  buildAllowedSequenceAssets,
  buildSequenceGenerationMetadata,
  createDraftGroupId,
  nameDraftGroupFromPrompt,
  type EditableSequenceDraft,
  type SequenceCreatorMode,
  type SequenceDraftGroup,
} from '@/tools/video-editor/sequences/generation.ts';
import { materializeResolvedSequenceConfig } from '@/tools/video-editor/sequences/materialize.ts';
import {
  AVAILABLE_SEQUENCE_CLIP_TYPES,
  AVAILABLE_SEQUENCE_METADATA,
  getAvailableClipTypeDescriptor,
  getAvailableSequenceMetadata,
} from '@/tools/video-editor/sequences/registry.ts';
import {
  validateSequenceDraft,
  type ValidatedSequenceDraft,
} from '@/tools/video-editor/sequences/validation.ts';
import type {
  ResolvedTimelineClip,
  ResolvedTimelineConfig,
} from '@/tools/video-editor/types/index.ts';
import {
  runSequenceComponentGenerationRequest,
  runSequenceGenerationRequest,
} from './sequenceGenerationService.ts';
import { getBundledComponentSource } from '@/tools/video-editor/sequences/getBundledComponentSource.ts';
import { getClipCapabilityDescriptor } from '@/tools/video-editor/sequences/registry.ts';
import { smokeRenderSequenceComponent } from '@/tools/video-editor/sequences/headlessRender.ts';
import { useCreateSequenceComponentResource } from '@/tools/video-editor/hooks/useSequenceResources.ts';
import { CodePathPreview } from './CodePathPreview.tsx';

type SequenceCreatorPanelProps = {
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
};

const TEMP_SEQUENCE_PREVIEW_CLIP_ID = '__sequence_preview__';

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
  const { data, resolvedConfig, selectedClipId, selectedClipIds, selectedTrackId } = useTimelineEditorData();
  const { applyEdit } = useTimelineEditorOps();
  const currentTime = useTimelinePlaybackSelector((playback) => playback.currentTime);
  const previewContainerRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  const [mode, setMode] = useState<SequenceCreatorMode>('generate');
  const [prompt, setPrompt] = useState('');
  const [editPrompt, setEditPrompt] = useState('');
  const [draftGroups, setDraftGroups] = useState<SequenceDraftGroup[]>([]);
  const [selectedGroupId, setSelectedGroupId] = useState<string | null>(null);
  const [selectedDraftIndex, setSelectedDraftIndex] = useState(0);
  const [isGenerating, setIsGenerating] = useState(false);
  const [generationNote, setGenerationNote] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  // Unified-UX classifier state: tracks what path the most recent
  // generation took (json|code) so the path/capability badge can render
  // unconditionally (always visible per CLAUDE.md UI conventions).
  const [classifierVerdict, setClassifierVerdict] = useState<{ path: 'json' | 'code'; reason: string } | null>(null);

  // Fork-to-DB pending state: when the classifier returns path:'code' AND
  // the selected clip is theme-bundled (`installed-sequence` source), we
  // gate the code-path follow-up behind a deliberate "Customize this
  // sequence for yourself" confirmation. Stores the prompt + classifier
  // reason so the confirm action can dispatch the follow-up call.
  const [forkPending, setForkPending] = useState<{
    prompt: string;
    reason: string;
    selectedClipType: string;
    bundledSource: ReturnType<typeof getBundledComponentSource>;
  } | null>(null);

  // Latest generated component metadata (when the code path produces a
  // result). Surfaces in the path badge so the user can see whether
  // they're editing JSON params or DB-stored component code.
  const [generatedComponent, setGeneratedComponent] = useState<{
    code: string;
    name: string;
    description: string;
    schemaJson: object;
    defaultsJson: object;
  } | null>(null);

  const allowedAssets = useMemo(() => (
    resolvedConfig
      ? buildAllowedSequenceAssets(selectedMedia.clips, attachmentSet.clips, resolvedConfig.registry)
      : []
  ), [attachmentSet.clips, resolvedConfig, selectedMedia.clips]);

  const allowedAssetKeys = useMemo(() => allowedAssets.map((asset) => asset.key), [allowedAssets]);

  const allowedRegistry = useMemo(() => (
    resolvedConfig ? buildAllowedAssetRegistry(allowedAssets, resolvedConfig.registry) : {}
  ), [allowedAssets, resolvedConfig]);

  const selectedGroup = useMemo(() => (
    selectedGroupId
      ? draftGroups.find((group) => group.id === selectedGroupId) ?? null
      : null
  ), [draftGroups, selectedGroupId]);
  const drafts = selectedGroup?.drafts ?? [];
  const selectedDraft = drafts[selectedDraftIndex] ?? null;
  const selectedValidation = useMemo(() => (
    selectedDraft ? validateEditableSequenceDraft(selectedDraft, allowedAssetKeys) : null
  ), [allowedAssetKeys, selectedDraft]);
  const validatedDraft = selectedValidation?.ok ? selectedValidation.draft : null;
  const selectedDescriptor = selectedDraft
    ? getAvailableClipTypeDescriptor(selectedDraft.clipType)
    : undefined;
  const selectedMetadata = selectedDraft ? getAvailableSequenceMetadata(selectedDraft.clipType) : undefined;

  const previewConfig = useMemo(() => {
    if (!resolvedConfig || !validatedDraft) return null;
    return buildSequencePreviewConfig(resolvedConfig, validatedDraft);
  }, [resolvedConfig, validatedDraft]);

  const replaceProbe = useMemo(() => {
    if (!data || !validatedDraft) return null;
    return buildReplaceSequenceDraftEdit(data, validatedDraft, { selectedClipId, selectedClipIds });
  }, [data, selectedClipId, selectedClipIds, validatedDraft]);

  const replaceDisabledReason = useMemo(() => {
    if (!validatedDraft) {
      return selectedValidation && !selectedValidation.ok
        ? summarizeValidationErrors(selectedValidation.errors)
        : 'Generate or select a valid sequence draft first.';
    }
    if (!replaceProbe) return 'Select a visual clip to replace.';
    return replaceProbe.ok ? null : formatEditError(replaceProbe.error);
  }, [replaceProbe, selectedValidation, validatedDraft]);

  const runSequenceGeneration = useCallback(async (rawPrompt: string, options: {
    mode?: SequenceCreatorMode;
    replaceGroupId?: string | null;
    editContext?: unknown;
    nameOverride?: string;
  } = {}) => {
    const generationPrompt = rawPrompt.trim();
    if (!generationPrompt) {
      toast({
        title: 'Prompt required',
        description: options.mode === 'edit' ? 'Describe how to change this animation.' : 'Describe the sequence you want to create.',
        variant: 'destructive',
      });
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
    if ((options.mode ?? 'generate') === 'generate') {
      setSelectedGroupId(null);
    }

    try {
      const result = await runSequenceGenerationRequest({
        prompt: generationPrompt,
        mode: options.mode,
        editContext: options.editContext,
        resolvedConfig,
        selectedClips: selectedMedia.clips,
        attachedClips: attachmentSet.clips,
        allowedAssets,
        allowedAssetKeys,
        signal: controller.signal,
      });
      if (result.status === 'aborted') return;

      if (result.status === 'classifier_code') {
        // Unified-UX (T13): classifier routed this prompt to the code path.
        // For theme-bundled clips we require deliberate fork-to-DB confirmation
        // ("Customize this sequence for yourself"); otherwise we dispatch
        // the follow-up call directly.
        setClassifierVerdict(result.classifier);
        // Resolve the clipType of the currently-selected timeline clip via
        // resolvedConfig — `SelectedMediaClip` doesn't carry clipType.
        const primaryClipId = selectedClipId ?? selectedClipIds?.values().next().value ?? null;
        const primaryClip = primaryClipId
          ? resolvedConfig.clips.find((c) => c.id === primaryClipId) ?? null
          : null;
        const selectedClipType = primaryClip?.clipType ?? '';
        const descriptor = getClipCapabilityDescriptor(selectedClipType);
        const isThemeBundled = descriptor?.source === 'installed-sequence';
        if (isThemeBundled && selectedClipType) {
          const bundled = getBundledComponentSource(selectedClipType);
          setForkPending({
            prompt: result.generationPrompt,
            reason: result.classifier.reason,
            selectedClipType,
            bundledSource: bundled,
          });
          setGenerationNote(
            bundled.status === 'cannot-fork'
              ? bundled.reason
              : 'This change requires custom component code. Confirm fork-to-DB to proceed.',
          );
          return;
        }
        // Non-bundled selection (DB-stored sequence or no selection): dispatch
        // the code-path call directly.
        const codeResult = await runSequenceComponentGenerationRequest({
          prompt: result.generationPrompt,
          resolvedConfig,
          selectedClips: selectedMedia.clips,
          attachedClips: attachmentSet.clips,
          allowedAssets,
          allowedAssetKeys,
          signal: controller.signal,
        });
        if (codeResult.status === 'aborted') return;
        if (codeResult.status === 'error') {
          setActionError(codeResult.error);
          setGenerationNote(`Code-path generation failed: ${codeResult.error}`);
          return;
        }
        setGeneratedComponent({
          code: codeResult.code,
          name: codeResult.name,
          description: codeResult.description,
          schemaJson: codeResult.schemaJson,
          defaultsJson: codeResult.defaultsJson,
        });
        setGenerationNote(codeResult.message ?? 'Generated component code (browser-only render).');
        return;
      }

      if (result.status === 'no_valid_drafts') {
        setClassifierVerdict(result.classifier ?? null);
        setGenerationNote(result.generationNote);
        return;
      }

      const nextGroupId = options.replaceGroupId ?? createDraftGroupId();
      setDraftGroups((current) => {
        const nextGroup: SequenceDraftGroup = {
          id: nextGroupId,
          name: options.nameOverride ?? nameDraftGroupFromPrompt(generationPrompt, current.length),
          prompt: result.generationPrompt,
          intent: result.animationIntentPayload,
          drafts: result.validDrafts,
        };
        if (options.replaceGroupId) {
          return current.map((group) => (group.id === options.replaceGroupId ? nextGroup : group));
        }
        return [nextGroup];
      });
      setSelectedGroupId(nextGroupId);
      setSelectedDraftIndex(0);
      setMode('edit');
      setGenerationNote(result.generationNote);
      setClassifierVerdict(result.classifier ?? null);
      // Successful JSON-path result: clear any stale generated component.
      setGeneratedComponent(null);
      setForkPending(null);
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
    resolvedConfig,
    selectedClipId,
    selectedClipIds,
    selectedMedia.clips,
  ]);

  const handleGenerate = useCallback(() => {
    void runSequenceGeneration(prompt);
  }, [prompt, runSequenceGeneration]);

  // Fork-to-DB confirmation handler (T13): when the classifier asked for
  // the code path on a theme-bundled clip, this dispatches the actual
  // ai-generate-sequence-component call with `existingComponent` derived
  // from the bundled TSX source. The badge stays visible after either
  // success or error so the user always knows which path ran.
  const handleConfirmFork = useCallback(async () => {
    if (!forkPending || forkPending.bundledSource.status !== 'available' || !resolvedConfig) {
      return;
    }
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setIsGenerating(true);
    setActionError(null);
    try {
      const codeResult = await runSequenceComponentGenerationRequest({
        prompt: forkPending.prompt,
        existingComponent: {
          code: forkPending.bundledSource.code,
          schema: forkPending.bundledSource.schema,
          defaults: forkPending.bundledSource.defaults,
        },
        resolvedConfig,
        selectedClips: selectedMedia.clips,
        attachedClips: attachmentSet.clips,
        allowedAssets,
        allowedAssetKeys,
        signal: controller.signal,
      });
      if (codeResult.status === 'aborted') return;
      if (codeResult.status === 'error') {
        setActionError(codeResult.error);
        setGenerationNote(`Fork failed: ${codeResult.error}`);
        return;
      }
      setGeneratedComponent({
        code: codeResult.code,
        name: codeResult.name,
        description: codeResult.description,
        schemaJson: codeResult.schemaJson,
        defaultsJson: codeResult.defaultsJson,
      });
      setGenerationNote(
        codeResult.message ?? `Forked "${forkPending.selectedClipType}" into a custom DB-stored sequence.`,
      );
      setForkPending(null);
    } catch (err) {
      if ((err as Error).name === 'AbortError') return;
      const message = err instanceof Error ? err.message : 'Fork failed.';
      setActionError(message);
      setGenerationNote(message);
    } finally {
      setIsGenerating(false);
    }
  }, [allowedAssetKeys, allowedAssets, attachmentSet.clips, forkPending, resolvedConfig, selectedMedia.clips]);

  const handleCancelFork = useCallback(() => {
    setForkPending(null);
    setGenerationNote(null);
  }, []);

  // T14 — headless smoke-render gate before persisting a generated
  // sequence component. Save flow:
  //   1. Run smokeRenderSequenceComponent({code, schema, defaults}). If it
  //      returns { ok: false }, surface the error inline (NOT a toast — per
  //      CLAUDE.md UI conventions: errors-only toasts; panel-inline is
  //      correct for this gate) and DO NOT persist.
  //   2. On success, call useCreateSequenceComponentResource.mutateAsync
  //      with the SequenceComponentMetadata derived from the generated
  //      component.
  // The gate catches compile errors + obvious runtime errors via
  // react-dom/server.renderToString — see headlessRender.ts for the
  // FLAG-005 caveat that ThemeProvider/SequenceContext are NOT exercised.
  const createSequenceComponent = useCreateSequenceComponentResource();
  const [isSaving, setIsSaving] = useState(false);
  const handleSaveGeneratedComponent = useCallback(async () => {
    if (!generatedComponent) return;
    setIsSaving(true);
    setActionError(null);
    try {
      const smoke = await smokeRenderSequenceComponent({
        code: generatedComponent.code,
        schemaJson: generatedComponent.schemaJson,
        defaultsJson: generatedComponent.defaultsJson,
        fps: resolvedConfig?.output.fps ?? 30,
      });
      if (!smoke.ok) {
        setActionError(`Smoke render failed: ${smoke.error}. Component NOT saved.`);
        return;
      }
      const metadata = {
        name: generatedComponent.name || 'Untitled component',
        slug: (generatedComponent.name || 'component').toLowerCase().replace(/[^a-z0-9]+/g, '-'),
        code: generatedComponent.code,
        schemaJson: generatedComponent.schemaJson,
        defaultsJson: generatedComponent.defaultsJson,
        clipType: forkPending?.selectedClipType ?? 'custom-component',
        themeId: resolvedConfig?.theme ?? '2rp',
        description: generatedComponent.description,
        created_by: { is_you: true },
        is_public: false,
      };
      await createSequenceComponent.mutateAsync({ metadata });
      setGenerationNote('Sequence component saved.');
      setGeneratedComponent(null);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Save failed.';
      setActionError(`Save failed: ${message}. Component NOT saved.`);
    } finally {
      setIsSaving(false);
    }
  }, [createSequenceComponent, forkPending, generatedComponent, resolvedConfig?.output.fps, resolvedConfig?.theme]);

  const handleEditSelected = useCallback(() => {
    if (!selectedGroup || !selectedDraft) return;
    void runSequenceGeneration(editPrompt, {
      mode: 'edit',
      replaceGroupId: selectedGroup.id,
      nameOverride: selectedGroup.name,
      editContext: {
        original_prompt: selectedGroup.prompt,
        selected_draft_index: selectedDraftIndex,
        source_draft: selectedDraft,
        valid_source_draft: validatedDraft,
      },
    });
  }, [editPrompt, runSequenceGeneration, selectedDraft, selectedDraftIndex, selectedGroup, validatedDraft]);

  const updateSelectedDraft = useCallback((patch: Partial<EditableSequenceDraft>) => {
    if (!selectedGroup) return;
    setDraftGroups((current) => current.map((group) => (
      group.id === selectedGroup.id
        ? {
            ...group,
            drafts: group.drafts.map((draft, index) => (
              index === selectedDraftIndex
                ? { ...draft, ...patch }
                : draft
            )),
          }
        : group
    )));
    setActionError(null);
  }, [selectedDraftIndex, selectedGroup]);

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
    applyEdit(attachSequenceGenerationMetadata(
      result.mutation,
      result.clipId,
      buildSequenceGenerationMetadata(selectedGroup, selectedDraftIndex),
    ), {
      selectedClipId: result.selectedClipId,
      selectedTrackId: result.selectedTrackId,
    });
    requestCenterTimelineClip(result.selectedClipId);
    onOpenChange?.(false);
  }, [applyEdit, currentTime, data, onOpenChange, selectedDraftIndex, selectedGroup, selectedTrackId, validatedDraft]);

  const handleReplace = useCallback(() => {
    if (!data || !validatedDraft) return;
    const result = buildReplaceSequenceDraftEdit(data, validatedDraft, { selectedClipId, selectedClipIds });
    if (!result.ok) {
      setActionError(formatEditError(result.error));
      return;
    }
    applyEdit(attachSequenceGenerationMetadata(
      result.mutation,
      result.clipId,
      buildSequenceGenerationMetadata(selectedGroup, selectedDraftIndex),
    ), {
      selectedClipId: result.selectedClipId,
      selectedTrackId: result.selectedTrackId,
    });
    requestCenterTimelineClip(result.selectedClipId);
    onOpenChange?.(false);
  }, [applyEdit, data, onOpenChange, selectedClipId, selectedClipIds, selectedDraftIndex, selectedGroup, validatedDraft]);

  const handleRemoveAllowedAsset = useCallback((asset: {
    clipId: string;
    url: string;
    mediaType: 'image' | 'video';
    generationId?: string;
  }) => {
    composerRemoveAttachment({
      clipId: asset.clipId,
      url: asset.url,
      mediaType: asset.mediaType,
      generationId: asset.generationId,
    });
  }, []);

  const handleRemoveAllowedShot = useCallback((shotId: string) => {
    allowedAssets
      .filter((asset) => asset.shotId === shotId)
      .forEach((asset) => composerRemoveAttachment({
        clipId: asset.clipId,
        url: asset.url,
        mediaType: asset.mediaType,
        generationId: asset.generationId,
      }));
  }, [allowedAssets]);

  const insertDisabledReason = !validatedDraft
    ? (selectedValidation && !selectedValidation.ok
      ? summarizeValidationErrors(selectedValidation.errors)
      : 'Generate or select a valid sequence draft first.')
    : (!data ? 'Timeline unavailable.' : null);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="h-[min(92vh,820px)] max-h-[92vh] max-w-6xl overflow-hidden p-0">
        <div className="flex h-full min-h-0 flex-col">
          <DialogHeader className="border-b border-border px-5 py-4">
            <div className="pr-8">
              <DialogTitle>Sequence Creator</DialogTitle>
              <DialogDescription>
                Generate trusted timeline sequence drafts from a prompt and the currently selected or attached assets.
              </DialogDescription>
            </div>
          </DialogHeader>

          <div className="grid min-h-0 flex-1 grid-cols-[minmax(320px,420px)_1fr] overflow-hidden">
            <div className="min-h-0 overflow-y-auto border-r border-border p-4">
              <div className="space-y-4">
                <div className="grid grid-cols-2 rounded-lg border border-border bg-muted/30 p-1">
                  <button
                    type="button"
                    className={[
                      'rounded-md px-3 py-1.5 text-sm transition-colors',
                      mode === 'generate'
                        ? 'bg-background text-foreground shadow-sm'
                        : 'text-muted-foreground hover:text-foreground',
                    ].join(' ')}
                    onClick={() => setMode('generate')}
                  >
                    Generate
                  </button>
                  <button
                    type="button"
                    className={[
                      'rounded-md px-3 py-1.5 text-sm transition-colors',
                      mode === 'edit'
                        ? 'bg-background text-foreground shadow-sm'
                        : 'text-muted-foreground hover:text-foreground',
                    ].join(' ')}
                    onClick={() => setMode('edit')}
                    disabled={draftGroups.length === 0}
                  >
                    Edit
                  </button>
                </div>

                {mode === 'generate' ? (
                  <div className="space-y-2">
                    <div className="text-sm font-medium text-foreground">Prompt</div>
                    <Textarea
                      value={prompt}
                      rows={5}
                      placeholder="Make these selected images jump between each other..."
                      onChange={(event) => setPrompt(event.target.value)}
                      voiceInput
                      onVoiceResult={(result) => setPrompt(result.transcription)}
                      voiceContext="The user is describing an animated sequence to generate inside a video editor. They may refer to selected or attached images, videos, text, motion, timing, or style. Transcribe their animation request accurately."
                      voiceTask="transcribe_only"
                    />
                    <Button
                      type="button"
                      className="w-full gap-2"
                      onClick={handleGenerate}
                      disabled={isGenerating || !prompt.trim()}
                    >
                      {isGenerating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
                      Generate new animation
                    </Button>
                  </div>
                ) : (
                  <div className="space-y-3 rounded-lg border border-border bg-card/60 p-3">
                    <div className="text-sm font-medium text-foreground">Selected Animation</div>
                    {selectedGroup ? (
                      <>
                        <div className="text-sm text-foreground">{selectedGroup.name}</div>
                        <div className="line-clamp-2 text-xs text-muted-foreground">{selectedGroup.prompt}</div>
                        <Textarea
                          value={editPrompt}
                          rows={4}
                          placeholder="Make the motion faster, use all three selected images, remove the title..."
                          onChange={(event) => setEditPrompt(event.target.value)}
                          voiceInput
                          onVoiceResult={(result) => setEditPrompt(result.transcription)}
                          voiceContext="The user is describing edits to an existing generated animated sequence in a video editor. They may ask to change motion, timing, selected assets, titles, labels, or layout. Transcribe their edit instruction accurately."
                          voiceTask="transcribe_only"
                        />
                        <Button
                          type="button"
                          variant="secondary"
                          className="w-full gap-2"
                          onClick={handleEditSelected}
                          disabled={isGenerating || !editPrompt.trim() || !selectedDraft}
                        >
                          {isGenerating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
                          Apply edit to animation
                        </Button>
                      </>
                    ) : (
                      <div className="text-xs text-muted-foreground">Generate an animation before editing.</div>
                    )}
                  </div>
                )}

                <div className="space-y-2 rounded-lg border border-border bg-card/60 p-3">
                  <div className="flex items-center justify-between gap-3">
                    <div className="text-sm font-medium text-foreground">Allowed Assets</div>
                    <div className="text-xs text-muted-foreground">{allowedAssets.length}</div>
                  </div>
                  {allowedAssets.length > 0 ? (
                    <AgentChatAttachmentStrip
                      attachments={allowedAssets.map((asset) => ({
                        clipId: asset.clipId,
                        url: asset.url,
                        mediaType: asset.mediaType,
                        isPlaceholder: asset.isPlaceholder,
                        generationId: asset.generationId,
                        assetKey: asset.key,
                        shotId: asset.shotId,
                        shotName: asset.shotName,
                        shotSelectionClipCount: asset.shotSelectionClipCount,
                      }))}
                      isUser={false}
                      className="mt-0"
                      onRemoveAttachment={handleRemoveAllowedAsset}
                      onRemoveShot={handleRemoveAllowedShot}
                      maxPreviewCount={null}
                    />
                  ) : (
                    <div className="text-xs text-muted-foreground">
                      Select timeline media or attach asset chips before asking for asset-backed drafts.
                    </div>
                  )}
                </div>

                {/*
                  Path/capability badge (T13): always visible. Surfaces
                  whether the classifier ran the JSON path or the code
                  path so the user knows whether their clip can be
                  worker-rendered server-side. Uses Tailwind tokens
                  (bg-background/text-foreground) per CLAUDE.md.
                */}
                <div
                  data-testid="sequence-creator-path-badge"
                  className="flex items-center gap-2 rounded-md border border-border bg-background px-3 py-2 text-xs text-foreground"
                >
                  <span className="font-medium">Mode:</span>
                  {generatedComponent || classifierVerdict?.path === 'code' ? (
                    <span>Generated component code · browser-only render (DB-stored)</span>
                  ) : classifierVerdict?.path === 'json' ? (
                    <span>Edited params · worker render available</span>
                  ) : (
                    <span className="text-muted-foreground">Awaiting generation…</span>
                  )}
                </div>

                {generatedComponent && (
                  <div
                    data-testid="sequence-creator-generated-component"
                    className="space-y-2 rounded-lg border border-border bg-background p-3 text-xs text-foreground"
                  >
                    <div className="font-medium">{generatedComponent.name || 'Generated component'}</div>
                    {generatedComponent.description && (
                      <p className="text-muted-foreground">{generatedComponent.description}</p>
                    )}
                    <div className="flex gap-2">
                      <Button
                        type="button"
                        size="sm"
                        onClick={() => void handleSaveGeneratedComponent()}
                        disabled={isSaving}
                      >
                        {isSaving ? 'Saving…' : 'Save component'}
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        onClick={() => setGeneratedComponent(null)}
                        disabled={isSaving}
                      >
                        Discard
                      </Button>
                    </div>
                    {actionError && (
                      <div
                        data-testid="sequence-creator-save-error"
                        className="text-destructive"
                      >
                        {actionError}
                      </div>
                    )}
                  </div>
                )}

                {forkPending && (
                  <div
                    data-testid="sequence-creator-fork-prompt"
                    className="space-y-2 rounded-lg border border-border bg-muted/30 p-3 text-xs text-foreground"
                  >
                    <div className="font-medium">Customize this sequence for yourself</div>
                    <p className="text-muted-foreground">
                      This change requires a custom component. Forking copies "{forkPending.selectedClipType}"
                      into a per-user DB resource you can edit. The result renders in browser only —
                      worker-side render isn't supported for custom components yet.
                    </p>
                    <p className="text-muted-foreground italic">{forkPending.reason}</p>
                    <div className="flex gap-2">
                      <Button
                        type="button"
                        size="sm"
                        onClick={() => void handleConfirmFork()}
                        disabled={
                          isGenerating || forkPending.bundledSource.status !== 'available'
                        }
                      >
                        Customize
                      </Button>
                      <Button type="button" size="sm" variant="ghost" onClick={handleCancelFork}>
                        Cancel
                      </Button>
                    </div>
                    {forkPending.bundledSource.status === 'cannot-fork' && (
                      <div className="text-destructive">{forkPending.bundledSource.reason}</div>
                    )}
                  </div>
                )}

                {generationNote && (
                  <div className="rounded-lg border border-border bg-muted/50 p-3 text-xs text-muted-foreground">
                    {generationNote}
                  </div>
                )}

                {drafts.length > 1 && (
                  <div className="space-y-2">
                    <div className="text-sm font-medium text-foreground">Draft Variants</div>
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

            <div className="grid min-h-0 grid-rows-[minmax(180px,1fr)_minmax(0,360px)]">
              <div className="min-h-0 overflow-hidden bg-black">
                {previewConfig ? (
                  <RemotionPreview
                    config={previewConfig}
                    onTimeUpdate={() => undefined}
                    playerContainerRef={previewContainerRef}
                    compact
                    initialTime={0}
                  />
                ) : generatedComponent ? (
                  <CodePathPreview
                    code={generatedComponent.code}
                    defaultsJson={generatedComponent.defaultsJson}
                    fps={resolvedConfig?.output.fps ?? 30}
                  />
                ) : (
                  <div className="flex h-full items-center justify-center p-6 text-center text-sm text-muted-foreground">
                    Generate a sequence to preview it here.
                  </div>
                )}
              </div>

              <div className="flex max-h-[360px] min-h-0 flex-col border-t border-border">
                {selectedDraft && selectedMetadata ? (
                  <>
                    <div className="min-h-0 flex-1 overflow-y-auto p-4">
                      <div className="space-y-4">
                        <div className="grid grid-cols-[1fr_140px] items-end gap-3">
                          <div>
                            <div className="text-sm font-medium text-foreground">
                              {selectedDescriptor?.label ?? selectedMetadata.label}
                            </div>
                            <div className="text-xs text-muted-foreground">
                              {selectedDescriptor?.description ?? selectedMetadata.description}
                            </div>
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
                          clipType={selectedDraft.clipType}
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
                      </div>
                    </div>

                    <div className="flex shrink-0 justify-end gap-2 border-t border-border bg-background/95 p-4">
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
                  </>
                ) : (
                  <div className="p-4">
                    <div className="rounded-lg border border-border bg-card/60 p-4 text-sm text-muted-foreground">
                      Generated sequence drafts will appear here for timing and parameter edits.
                    </div>
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
