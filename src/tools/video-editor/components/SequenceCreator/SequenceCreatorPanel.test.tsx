import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { ComponentProps, RefObject } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  buildAllowedSequenceAssets,
  buildGenerationClipPayloads,
  SequenceCreatorPanel,
} from '@/tools/video-editor/components/SequenceCreator/SequenceCreatorPanel';
import { TIMELINE_CENTER_CLIP_EVENT } from '@/tools/video-editor/lib/timeline-viewport-events';
import type { SelectedMediaClip } from '@/tools/video-editor/hooks/useSelectedMediaClips';
import type { TimelineData } from '@/tools/video-editor/lib/timeline-data';
import type { ResolvedTimelineConfig } from '@/tools/video-editor/types';

const mocks = vi.hoisted(() => ({
  invokeSupabaseEdgeFunction: vi.fn(),
  useSelectedMediaClips: vi.fn(),
  useCurrentAttachmentSet: vi.fn(),
  useTimelineEditorData: vi.fn(),
  useTimelineEditorOps: vi.fn(),
  useTimelinePlaybackSelector: vi.fn(),
  applyEdit: vi.fn(),
  remotionPreview: vi.fn(),
  toast: vi.fn(),
  buildInsertSequenceDraftEdit: vi.fn(),
  buildReplaceSequenceDraftEdit: vi.fn(),
  composerRemoveAttachment: vi.fn(),
}));

vi.mock('@/integrations/supabase/functions/invokeSupabaseEdgeFunction', () => ({
  invokeSupabaseEdgeFunction: mocks.invokeSupabaseEdgeFunction,
}));

vi.mock('@/tools/video-editor/hooks/useSelectedMediaClips', () => ({
  useSelectedMediaClips: mocks.useSelectedMediaClips,
}));

vi.mock('@/shared/state/currentAttachmentSet', () => ({
  useCurrentAttachmentSet: mocks.useCurrentAttachmentSet,
}));

vi.mock('@/shared/state/selectionStore', () => ({
  composerRemoveAttachment: mocks.composerRemoveAttachment,
}));

vi.mock('@/tools/video-editor/hooks/timelineStore', () => ({
  useTimelineEditorData: mocks.useTimelineEditorData,
  useTimelineEditorOps: mocks.useTimelineEditorOps,
  useTimelinePlaybackSelector: mocks.useTimelinePlaybackSelector,
}));

vi.mock('@/tools/video-editor/components/PreviewPanel/RemotionPreview', () => ({
  RemotionPreview: (props: {
    compact?: boolean;
    config: ResolvedTimelineConfig;
    initialTime?: number;
    onTimeUpdate?: () => void;
    playerContainerRef?: RefObject<HTMLDivElement>;
  }) => {
    mocks.remotionPreview(props);
    const previewClip = props.config.clips.find((clip) => clip.id === '__sequence_preview__');
    return (
      <div data-testid="sequence-remotion-preview">
        {JSON.stringify(previewClip?.params ?? {})}
      </div>
    );
  },
}));

vi.mock('@/shared/components/ui/toast', () => ({
  toast: mocks.toast,
}));

vi.mock('@/tools/video-editor/lib/sequence-drafts', async (importActual) => {
  const actual = await importActual<typeof import('@/tools/video-editor/lib/sequence-drafts')>();
  return {
    ...actual,
    buildInsertSequenceDraftEdit: (...args: Parameters<typeof actual.buildInsertSequenceDraftEdit>) => {
      mocks.buildInsertSequenceDraftEdit(...args);
      return actual.buildInsertSequenceDraftEdit(...args);
    },
    buildReplaceSequenceDraftEdit: (...args: Parameters<typeof actual.buildReplaceSequenceDraftEdit>) => {
      mocks.buildReplaceSequenceDraftEdit(...args);
      return actual.buildReplaceSequenceDraftEdit(...args);
    },
  };
});

vi.mock('@/shared/components/ui/dialog', () => ({
  Dialog: ({ open, children }: { open?: boolean; children: React.ReactNode }) => (open ? <div>{children}</div> : null),
  DialogContent: ({ children, ...props }: ComponentProps<'div'>) => <div {...props}>{children}</div>,
  DialogDescription: ({ children }: { children: React.ReactNode }) => <p>{children}</p>,
  DialogHeader: ({ children, ...props }: ComponentProps<'div'>) => <div {...props}>{children}</div>,
  DialogTitle: ({ children }: { children: React.ReactNode }) => <h2>{children}</h2>,
}));

vi.mock('@/shared/components/ui/input', () => ({
  Input: ({ onChange, value, ...props }: ComponentProps<'input'>) => (
    <input value={value} onChange={onChange} {...props} />
  ),
}));

vi.mock('@/shared/components/ui/textarea', () => ({
  Textarea: ({ onChange, value, ...props }: ComponentProps<'textarea'>) => (
    <textarea value={value} onChange={onChange} {...props} />
  ),
}));

vi.mock('@/shared/components/ui/number-input', () => ({
  NumberInput: ({ onChange, value, min, max, step }: {
    onChange: (value: number | null) => void;
    value: number | null;
    min?: number;
    max?: number;
    step?: number;
  }) => (
    <input
      role="spinbutton"
      value={value ?? ''}
      min={min}
      max={max}
      step={step}
      onChange={(event) => onChange(event.currentTarget.value === '' ? null : Number(event.currentTarget.value))}
    />
  ),
}));

const registry: ResolvedTimelineConfig['registry'] = {
  'asset-a': {
    file: 'asset-a.png',
    src: 'https://cdn.example.test/asset-a.png',
    type: 'image/png',
  },
  'asset-b': {
    file: 'asset-b.png',
    src: 'https://cdn.example.test/asset-b.png',
    type: 'image/png',
  },
  'asset-c': {
    file: 'asset-c.png',
    src: 'https://cdn.example.test/asset-c.png',
    type: 'image/png',
  },
};

const resolvedConfig: ResolvedTimelineConfig = {
  output: {
    resolution: '1920x1080',
    fps: 30,
    file: 'timeline.mp4',
  },
  tracks: [
    { id: 'visual-1', kind: 'visual', label: 'Visual 1' },
    { id: 'audio-1', kind: 'audio', label: 'Audio 1' },
  ],
  clips: [
    {
      id: 'clip-1',
      asset: 'asset-a',
      clipType: 'image',
      track: 'visual-1',
      at: 0,
      hold: 3,
      assetEntry: registry['asset-a'],
    },
    {
      id: 'audio-clip',
      asset: 'asset-c',
      clipType: 'audio',
      track: 'audio-1',
      at: 0,
      hold: 3,
      assetEntry: registry['asset-c'],
    },
  ],
  registry,
  theme: '2rp',
};

const timelineData: TimelineData = {
  config: resolvedConfig,
  resolvedConfig,
  rows: [
    {
      id: 'visual-1',
      kind: 'visual',
      label: 'Visual 1',
      actions: [{ id: 'clip-1', start: 0, end: 3, effectId: 'effect-clip-1' }],
    },
    {
      id: 'audio-1',
      kind: 'audio',
      label: 'Audio 1',
      actions: [{ id: 'audio-clip', start: 0, end: 3, effectId: 'effect-audio-clip' }],
    },
  ],
  tracks: resolvedConfig.tracks,
  meta: {
    'clip-1': {
      track: 'visual-1',
      clipType: 'image',
      asset: 'asset-a',
      hold: 3,
    },
    'audio-clip': {
      track: 'audio-1',
      clipType: 'audio',
      asset: 'asset-c',
      hold: 3,
    },
  },
  clipOrder: {
    'visual-1': ['clip-1'],
    'audio-1': ['audio-clip'],
  },
  trackScale: {},
  stableSignature: 'test-signature',
} as TimelineData;

const selectedClip = (patch: Partial<SelectedMediaClip>): SelectedMediaClip => ({
  clipId: 'clip-1',
  assetKey: 'asset-a',
  url: 'https://cdn.example.test/asset-a.png',
  mediaType: 'image',
  isTimelineBacked: true,
  ...patch,
});

const renderPanel = (overrides: {
  selectedClipId?: string | null;
  selectedClipIds?: string[];
  selectedTrackId?: string | null;
  selectedClips?: SelectedMediaClip[];
  attachedClips?: SelectedMediaClip[];
  data?: TimelineData;
} = {}) => {
  mocks.useSelectedMediaClips.mockReturnValue({
    clips: overrides.selectedClips ?? [selectedClip({})],
    summary: '1 selected',
  });
  mocks.useCurrentAttachmentSet.mockReturnValue({
    clips: overrides.attachedClips ?? [selectedClip({
      clipId: 'attached-1',
      assetKey: 'asset-b',
      url: 'https://cdn.example.test/asset-b.png',
      isTimelineBacked: false,
    })],
    summary: '1 attached',
  });
  mocks.useTimelineEditorData.mockReturnValue({
    data: overrides.data ?? timelineData,
    resolvedConfig,
    selectedClipId: overrides.selectedClipId ?? 'clip-1',
    selectedClipIds: new Set(overrides.selectedClipIds ?? [overrides.selectedClipId ?? 'clip-1']),
    selectedTrackId: overrides.selectedTrackId ?? 'visual-1',
  });
  mocks.useTimelineEditorOps.mockReturnValue({
    applyEdit: mocks.applyEdit,
  });
  mocks.useTimelinePlaybackSelector.mockImplementation((selector: (value: { currentTime: number }) => unknown) => selector({ currentTime: 2 }));

  return render(<SequenceCreatorPanel open onOpenChange={vi.fn()} />);
};

const generateValidResourceDraft = async () => {
  fireEvent.change(screen.getByPlaceholderText('Make these selected images jump between each other...'), {
    target: { value: 'Make a resource card' },
  });
  fireEvent.click(screen.getByRole('button', { name: /generate new animation/i }));
  await screen.findByDisplayValue('Generated title');
};

const createDeferred = <T,>() => {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((promiseResolve) => {
    resolve = promiseResolve;
  });
  return { promise, resolve };
};

describe('SequenceCreatorPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.invokeSupabaseEdgeFunction.mockResolvedValue({
      drafts: [
        {
          clipType: 'resource-card',
          hold: 4,
          params: {
            title: 'Generated title',
            detail: 'Generated detail',
            previewAssetKeys: ['asset-a', 'asset-b'],
          },
        },
      ],
      invalid_drafts: [],
    });
  });

  it('builds allowed sequence assets from selected clips plus current attachment chips only', async () => {
    const assets = buildAllowedSequenceAssets(
      [selectedClip({ assetKey: 'asset-a' })],
      [
        selectedClip({ clipId: 'attached-1', assetKey: 'asset-b', isTimelineBacked: false }),
        selectedClip({ clipId: 'attached-missing', assetKey: 'asset-missing', isTimelineBacked: false }),
      ],
      registry,
    );

    expect(assets.map((asset) => asset.key)).toEqual(['asset-a', 'asset-b']);
    expect(buildGenerationClipPayloads(
      [
        selectedClip({ assetKey: 'asset-a', url: 'https://stale.example.test/asset-a.png' }),
        selectedClip({ clipId: 'selected-missing', assetKey: 'asset-missing', url: 'https://untrusted.example.test/missing.png' }),
        selectedClip({ clipId: 'placeholder', assetKey: 'asset-c', isPlaceholder: true }),
      ],
      assets,
    )).toEqual([expect.objectContaining({
      assetKey: 'asset-a',
      url: 'https://cdn.example.test/asset-a.png',
    })]);

    mocks.invokeSupabaseEdgeFunction.mockResolvedValueOnce({
      drafts: [
        {
          clipType: 'resource-card',
          hold: 4,
          params: {
            title: 'Generated title',
            detail: 'Generated detail',
            previewAssetKeys: ['asset-a', 'asset-b'],
          },
        },
        {
          clipType: 'resource-card',
          hold: 4,
          params: {
            title: 'Invalid asset draft',
            detail: 'Should be rejected',
            previewAssetKeys: ['asset-c'],
          },
        },
      ],
      invalid_drafts: [],
    });

    renderPanel({
      selectedClips: [
        selectedClip({
          assetKey: 'asset-a',
          url: 'https://stale.example.test/asset-a.png',
        }),
        selectedClip({
          clipId: 'selected-missing',
          assetKey: 'asset-missing',
          url: 'https://untrusted.example.test/missing.png',
        }),
        selectedClip({
          clipId: 'selected-placeholder',
          assetKey: 'asset-c',
          url: 'https://cdn.example.test/asset-c.png',
          isPlaceholder: true,
        }),
      ],
      attachedClips: [
        selectedClip({
          clipId: 'attached-1',
          assetKey: 'asset-b',
          url: 'https://stale.example.test/asset-b.png',
          isTimelineBacked: false,
        }),
        selectedClip({
          clipId: 'attached-missing',
          assetKey: 'asset-missing',
          url: 'https://untrusted.example.test/attached-missing.png',
          isTimelineBacked: false,
        }),
      ],
    });
    await generateValidResourceDraft();

    const requestBody = mocks.invokeSupabaseEdgeFunction.mock.calls[0][1].body;
    expect(requestBody.selected_clips.map((clip: { assetKey?: string }) => clip.assetKey)).toEqual(['asset-a']);
    expect(requestBody.attached_clips.map((clip: { assetKey?: string }) => clip.assetKey)).toEqual(['asset-b']);
    expect(requestBody.selected_clips.map((clip: { url?: string }) => clip.url)).toEqual(['https://cdn.example.test/asset-a.png']);
    expect(requestBody.attached_clips.map((clip: { url?: string }) => clip.url)).toEqual(['https://cdn.example.test/asset-b.png']);
    expect(requestBody.allowed_assets.map((asset: { key: string }) => asset.key)).toEqual(['asset-a', 'asset-b']);
    expect(requestBody.allowed_assets.map((asset: { source: string }) => asset.source)).toEqual(['selected', 'attached']);
    expect(requestBody.allowed_assets.map((asset: { key: string }) => asset.key)).not.toContain('asset-c');
    expect(screen.getByText('1 invalid draft was rejected.')).toBeInTheDocument();
    expect(screen.queryByText('Invalid asset draft')).not.toBeInTheDocument();
  });

  it('client-validates generated drafts and previews the selected draft through Remotion with materialized assets', async () => {
    renderPanel();
    await generateValidResourceDraft();

    await waitFor(() => expect(mocks.remotionPreview).toHaveBeenCalled());
    const previewProps = mocks.remotionPreview.mock.calls.at(-1)?.[0];
    expect(previewProps).toMatchObject({
      compact: true,
      initialTime: 0,
    });
    expect(previewProps.onTimeUpdate).toEqual(expect.any(Function));
    expect(previewProps.playerContainerRef).toBeDefined();
    const previewConfig = previewProps.config as ResolvedTimelineConfig;
    const previewClip = previewConfig.clips.find((clip) => clip.id === '__sequence_preview__');
    expect(previewClip).toMatchObject({
      clipType: 'resource-card',
      track: 'visual-1',
      at: 0,
      hold: 4,
    });
    expect(previewConfig.clips).toHaveLength(1);
    expect(previewClip?.params).toMatchObject({
      previewAssetKeys: ['asset-a', 'asset-b'],
      previews: [
        'https://cdn.example.test/asset-a.png',
        'https://cdn.example.test/asset-b.png',
      ],
    });
    expect(screen.getByTestId('sequence-remotion-preview')).toHaveTextContent('https://cdn.example.test/asset-a.png');
  });

  it('shows selected assets as removable attachment previews', () => {
    renderPanel();

    expect(screen.getByLabelText('Attached image 1')).toBeInTheDocument();
    expect(screen.getByLabelText('Attached image 2')).toBeInTheDocument();

    fireEvent.click(screen.getByLabelText('Deselect attached image 1'));

    expect(mocks.composerRemoveAttachment).toHaveBeenCalledWith({
      clipId: 'clip-1',
      url: 'https://cdn.example.test/asset-a.png',
      mediaType: 'image',
      generationId: undefined,
    });
  });

  it('removes full-shot allowed asset groups through the backing attachment source', () => {
    renderPanel({
      selectedClips: [
        selectedClip({
          clipId: 'shot-clip-1',
          assetKey: 'asset-a',
          shotId: 'shot-1',
          shotName: 'Opening shot',
          shotSelectionClipCount: 2,
        }),
        selectedClip({
          clipId: 'shot-clip-2',
          assetKey: 'asset-b',
          url: 'https://cdn.example.test/asset-b.png',
          shotId: 'shot-1',
          shotName: 'Opening shot',
          shotSelectionClipCount: 2,
        }),
      ],
      attachedClips: [],
    });

    fireEvent.click(screen.getByLabelText('Deselect Opening shot'));

    expect(mocks.composerRemoveAttachment).toHaveBeenCalledTimes(2);
    expect(mocks.composerRemoveAttachment).toHaveBeenCalledWith(expect.objectContaining({
      clipId: 'shot-clip-1',
      url: 'https://cdn.example.test/asset-a.png',
    }));
    expect(mocks.composerRemoveAttachment).toHaveBeenCalledWith(expect.objectContaining({
      clipId: 'shot-clip-2',
      url: 'https://cdn.example.test/asset-b.png',
    }));
  });

  it('clears stale drafts when starting a new generation and accepts image-jump drafts without titles', async () => {
    renderPanel({
      selectedClips: [
        selectedClip({ assetKey: 'asset-a' }),
        selectedClip({ clipId: 'clip-2', assetKey: 'asset-b' }),
      ],
      attachedClips: [selectedClip({ clipId: 'clip-3', assetKey: 'asset-c', isTimelineBacked: false })],
    });
    await generateValidResourceDraft();
    expect(screen.getByDisplayValue('Generated title')).toBeInTheDocument();

    mocks.invokeSupabaseEdgeFunction.mockResolvedValueOnce({
      drafts: [
        {
          clipType: 'image-jump',
          hold: 4,
          params: {
            imageAssetKeys: ['asset-a', 'asset-b', 'asset-c'],
            mode: 'jump',
          },
        },
      ],
      invalid_drafts: [],
    });
    fireEvent.click(screen.getByRole('button', { name: 'Generate' }));
    fireEvent.change(screen.getByPlaceholderText('Make these selected images jump between each other...'), {
      target: { value: 'Make it jump between these three images' },
    });
    fireEvent.click(screen.getByRole('button', { name: /generate new animation/i }));

    await waitFor(() => expect(screen.getAllByText('Image Jump').length).toBeGreaterThan(0));
    expect(screen.queryByDisplayValue('Generated title')).not.toBeInTheDocument();
    expect(screen.getAllByText('Motion-only image sequence that snaps, pops, and jumps between selected assets.').length).toBeGreaterThan(0);
    const requestBody = mocks.invokeSupabaseEdgeFunction.mock.calls.at(-1)?.[1].body;
    expect(requestBody.allowed_clip_types).toContain('image-jump');
  });

  it('clears the stale selected draft UI while a fresh generate request is pending', async () => {
    renderPanel();
    await generateValidResourceDraft();
    expect(screen.getByDisplayValue('Generated title')).toBeInTheDocument();

    const deferred = createDeferred<{
      drafts: Array<{ clipType: string; hold: number; params: Record<string, unknown> }>;
      invalid_drafts: never[];
    }>();
    mocks.invokeSupabaseEdgeFunction.mockReturnValueOnce(deferred.promise);

    fireEvent.click(screen.getByRole('button', { name: 'Generate' }));
    fireEvent.change(screen.getByPlaceholderText('Make these selected images jump between each other...'), {
      target: { value: 'Make a new animation' },
    });
    fireEvent.click(screen.getByRole('button', { name: /generate new animation/i }));

    await waitFor(() => {
      expect(screen.queryByDisplayValue('Generated title')).not.toBeInTheDocument();
    });

    deferred.resolve({
      drafts: [
        {
          clipType: 'resource-card',
          hold: 4,
          params: {
            title: 'Fresh title',
            detail: 'Fresh detail',
            previewAssetKeys: ['asset-a'],
          },
        },
      ],
      invalid_drafts: [],
    });

    await screen.findByDisplayValue('Fresh title');
  });

  it('names generated animations from their prompt and can edit the selected one by instruction', async () => {
    renderPanel();
    await generateValidResourceDraft();

    expect(screen.getAllByText('Make a resource card').length).toBeGreaterThan(0);
    expect(screen.getByText('Selected Animation')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /regenerate from scratch/i })).not.toBeInTheDocument();

    mocks.invokeSupabaseEdgeFunction.mockResolvedValueOnce({
      drafts: [
        {
          clipType: 'resource-card',
          hold: 6,
          params: {
            title: 'Regenerated title',
            detail: 'Fresh detail',
            previewAssetKeys: ['asset-a'],
          },
        },
      ],
      invalid_drafts: [],
    });
    fireEvent.change(screen.getByPlaceholderText('Make the motion faster, use all three selected images, remove the title...'), {
      target: { value: 'Make the animation slower and remove the headline' },
    });
    fireEvent.click(screen.getByRole('button', { name: /apply edit to animation/i }));

    await screen.findByDisplayValue('Regenerated title');
    expect(screen.queryByDisplayValue('Generated title')).not.toBeInTheDocument();
    expect(mocks.invokeSupabaseEdgeFunction).toHaveBeenCalledTimes(2);
    expect(mocks.invokeSupabaseEdgeFunction.mock.calls[1][1].body).toMatchObject({
      prompt: 'Make the animation slower and remove the headline',
      mode: 'edit',
      edit_context: expect.objectContaining({
        original_prompt: 'Make a resource card',
        selected_draft_index: 0,
        source_draft: expect.objectContaining({
          clipType: 'resource-card',
          params: expect.objectContaining({ title: 'Generated title' }),
        }),
        valid_source_draft: expect.objectContaining({
          clipType: 'resource-card',
          params: expect.objectContaining({ title: 'Generated title' }),
        }),
      }),
    });

    fireEvent.click(screen.getByRole('button', { name: 'Generate' }));
    expect(screen.getByPlaceholderText('Make these selected images jump between each other...')).toBeInTheDocument();
  });

  it('preserves the prior valid draft group when edit regeneration returns no valid replacement', async () => {
    renderPanel();
    await generateValidResourceDraft();

    mocks.invokeSupabaseEdgeFunction.mockResolvedValueOnce({
      drafts: [],
      invalid_drafts: [{ index: 0, errors: [{ code: 'invalid_param_option' }] }],
    });
    fireEvent.change(screen.getByPlaceholderText('Make the motion faster, use all three selected images, remove the title...'), {
      target: { value: 'Try an invalid edit' },
    });
    fireEvent.click(screen.getByRole('button', { name: /apply edit to animation/i }));

    expect(await screen.findByText('The model returned drafts, but none matched the trusted sequence schema for the current selected or attached assets.')).toBeInTheDocument();
    expect(screen.getByDisplayValue('Generated title')).toBeInTheDocument();
    expect(screen.getByText('Selected Animation')).toBeInTheDocument();
  });

  it('distinguishes empty generation responses from schema rejection', async () => {
    renderPanel();

    mocks.invokeSupabaseEdgeFunction.mockResolvedValueOnce({
      drafts: [],
      invalid_drafts: [],
    });
    fireEvent.change(screen.getByPlaceholderText('Make these selected images jump between each other...'), {
      target: { value: 'Return nothing useful' },
    });
    fireEvent.click(screen.getByRole('button', { name: /generate new animation/i }));

    expect(await screen.findByText('No sequence drafts were returned.')).toBeInTheDocument();
  });

  it('revalidates edited drafts and disables insert and replace when timing becomes invalid', async () => {
    renderPanel();
    await generateValidResourceDraft();

    fireEvent.change(screen.getByRole('spinbutton'), {
      target: { value: '20' },
    });

    expect(screen.getAllByText('hold is outside the allowed timing range.').length).toBeGreaterThan(0);
    expect(screen.getByRole('button', { name: /insert at playhead/i })).toBeDisabled();
    expect(screen.getByRole('button', { name: /replace selected/i })).toBeDisabled();

    fireEvent.click(screen.getByRole('button', { name: /insert at playhead/i }));
    expect(mocks.applyEdit).not.toHaveBeenCalled();
  });

  it('edits draft params and timing before inserting through the sequence helper mutation path', async () => {
    renderPanel();
    await generateValidResourceDraft();
    const dispatchEventSpy = vi.spyOn(window, 'dispatchEvent');

    fireEvent.change(screen.getByDisplayValue('Generated title'), {
      target: { value: 'Edited title' },
    });
    fireEvent.change(screen.getByRole('spinbutton'), {
      target: { value: '5' },
    });
    fireEvent.click(screen.getByRole('button', { name: /insert at playhead/i }));

    expect(mocks.buildInsertSequenceDraftEdit).toHaveBeenCalledTimes(1);
    expect(mocks.buildInsertSequenceDraftEdit).toHaveBeenCalledWith(
      timelineData,
      expect.objectContaining({
        clipType: 'resource-card',
        hold: 5,
        params: expect.objectContaining({ title: 'Edited title' }),
      }),
      { at: 2, selectedTrackId: 'visual-1' },
    );
    expect(mocks.applyEdit).toHaveBeenCalledTimes(1);
    const [mutation, options] = mocks.applyEdit.mock.calls[0];
    expect(mutation.type).toBe('rows');
    expect(options.selectedClipId).toEqual(expect.any(String));
    expect(options.selectedTrackId).toBe('visual-1');
    expect(dispatchEventSpy).toHaveBeenCalledWith(expect.objectContaining({
      type: TIMELINE_CENTER_CLIP_EVENT,
    }));
    const createdMeta = Object.values(mutation.metaUpdates).find((meta) => meta.clipType === 'resource-card');
    expect(createdMeta).toMatchObject({
      track: 'visual-1',
      clipType: 'resource-card',
      hold: 5,
      params: {
        title: 'Edited title',
        detail: 'Generated detail',
        previewAssetKeys: ['asset-a', 'asset-b'],
      },
    });
  });

  it('replaces selected visual clips through the sequence helper mutation path', async () => {
    renderPanel();
    await generateValidResourceDraft();
    const dispatchEventSpy = vi.spyOn(window, 'dispatchEvent');

    fireEvent.click(screen.getByRole('button', { name: /replace selected/i }));

    expect(mocks.buildReplaceSequenceDraftEdit).toHaveBeenCalledWith(
      timelineData,
      expect.objectContaining({ clipType: 'resource-card' }),
      { selectedClipId: 'clip-1', selectedClipIds: new Set(['clip-1']) },
    );
    expect(mocks.applyEdit).toHaveBeenCalledTimes(1);
    const [mutation, options] = mocks.applyEdit.mock.calls[0];
    expect(mutation.type).toBe('rows');
    expect(mutation.metaDeletes).toEqual(['clip-1']);
    expect(options.selectedClipId).toEqual(expect.any(String));
    expect(options.selectedTrackId).toBe('visual-1');
    expect(dispatchEventSpy).toHaveBeenCalledWith(expect.objectContaining({
      type: TIMELINE_CENTER_CLIP_EVENT,
    }));
    expect(Object.values(mutation.metaUpdates).some((meta) => meta.clipType === 'resource-card')).toBe(true);
  });

  it('passes the full selected clip set when probing and replacing a multi-selection', async () => {
    const multiSelectedTimelineData = {
      ...timelineData,
      rows: timelineData.rows.map((row) => (
        row.id === 'visual-1'
          ? {
              ...row,
              actions: [
                ...row.actions,
                { id: 'clip-2', start: 4, end: 7, effectId: 'effect-clip-2' },
              ],
            }
          : row
      )),
      meta: {
        ...timelineData.meta,
        'clip-2': {
          track: 'visual-1',
          clipType: 'image',
          asset: 'asset-b',
          hold: 3,
        },
      },
      clipOrder: {
        ...timelineData.clipOrder,
        'visual-1': ['clip-1', 'clip-2'],
      },
    } as TimelineData;

    renderPanel({
      data: multiSelectedTimelineData,
      selectedClipId: 'clip-1',
      selectedClipIds: ['clip-1', 'clip-2'],
    });
    await generateValidResourceDraft();

    expect(mocks.buildReplaceSequenceDraftEdit).toHaveBeenCalledWith(
      multiSelectedTimelineData,
      expect.objectContaining({ clipType: 'resource-card' }),
      { selectedClipId: 'clip-1', selectedClipIds: new Set(['clip-1', 'clip-2']) },
    );

    fireEvent.click(screen.getByRole('button', { name: /replace selected/i }));

    expect(mocks.buildReplaceSequenceDraftEdit).toHaveBeenLastCalledWith(
      multiSelectedTimelineData,
      expect.objectContaining({ clipType: 'resource-card' }),
      { selectedClipId: 'clip-1', selectedClipIds: new Set(['clip-1', 'clip-2']) },
    );
  });

  it('disables replace with a clear state for audio-track selections', async () => {
    renderPanel({
      selectedClipId: 'audio-clip',
      selectedTrackId: 'audio-1',
    });
    await generateValidResourceDraft();

    const replaceButton = screen.getByRole('button', { name: /replace selected/i });
    expect(replaceButton).toBeDisabled();
    expect(replaceButton).toHaveAttribute('title', 'Sequences can only replace visual clips. Audio clips are not valid replace targets.');
    expect(screen.getByText('Sequences can only replace visual clips. Audio clips are not valid replace targets.')).toBeInTheDocument();
  });
});
