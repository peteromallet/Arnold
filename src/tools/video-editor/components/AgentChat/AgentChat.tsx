import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from 'react';
import { ChevronDown, ChevronUp, Loader2, MessageSquareText, Mic, Send, Square, X } from 'lucide-react';
import { createPortal } from 'react-dom';
import { useLocation } from 'react-router-dom';
import type { GenerationRow } from '@/domains/generation/types';
import { MediaLightbox } from '@/domains/media-lightbox/MediaLightbox';
import { Button } from '@/shared/components/ui/button';
import { cn } from '@/shared/components/ui/contracts/cn';
import { useAgentChatBridge } from '@/shared/contexts/AgentChatContext';
import { usePanes } from '@/shared/contexts/PanesContext';
import { useGallerySelection } from '@/shared/state/selectionStore';
import { useAgentSession, useAgentSessions, useCancelSession, useCreateSession, useSendMessage } from '@/tools/video-editor/hooks/useAgentSession';
import {
  buildSummary,
  type SelectedMediaClip,
} from '@/tools/video-editor/hooks/useSelectedMediaClips';
import { useAgentVoice } from '@/tools/video-editor/hooks/useAgentVoice';
import { useRenderDiagnostic } from '@/tools/video-editor/hooks/usePerfDiagnostics';
import { loadGenerationForLightbox } from '@/tools/video-editor/lib/generation-utils';
import type { AgentTurn, AgentTurnAttachment } from '@/tools/video-editor/types/agent-session';
import { AgentChatAttachmentStrip, AgentChatMessage, AgentChatToolGroup, type AgentChatAttachmentPreviewItem } from './AgentChatMessage';

export type ToolCallPair = {
  call: AgentTurn;
  result: AgentTurn | null;
};

export type RenderedTurn =
  | { kind: 'message'; key: string; turn: AgentTurn }
  | { kind: 'tool_group'; key: string; pairs: ToolCallPair[] };

type QueuedMessage = {
  id: string;
  text: string;
  attachments: AgentTurnAttachment[];
};

type OptimisticMessage = QueuedMessage & {
  sentAtMs: number;
  priorTurnCount: number;
};

function mergeSelectedClips(
  timelineClips: SelectedMediaClip[],
  galleryClips: SelectedMediaClip[],
): SelectedMediaClip[] {
  const clipsByUrl = new Map<string, SelectedMediaClip>();

  for (const clip of [...timelineClips, ...galleryClips]) {
    const existing = clipsByUrl.get(clip.url);
    if (existing) {
      const preferIncoming = !existing.generationId && Boolean(clip.generationId);
      const preferred = preferIncoming ? clip : existing;
      const secondary = preferIncoming ? existing : clip;

      clipsByUrl.set(clip.url, {
        ...preferred,
        generationId: preferred.generationId ?? secondary.generationId,
        variantId: preferred.variantId ?? secondary.variantId,
        isTimelineBacked: preferred.isTimelineBacked || secondary.isTimelineBacked,
        shotId: preferred.shotId ?? secondary.shotId,
        shotName: preferred.shotName ?? secondary.shotName,
        shotSelectionClipCount: preferred.shotSelectionClipCount ?? secondary.shotSelectionClipCount,
        trackId: preferred.trackId ?? secondary.trackId,
        at: preferred.at ?? secondary.at,
        duration: preferred.duration ?? secondary.duration,
        assetKey: preferred.assetKey || secondary.assetKey,
      });
      continue;
    }

    // Prefer gallery entries when the same URL exists in both panes because they retain
    // generationId metadata that timeline clips for that asset may not carry.
    clipsByUrl.set(clip.url, clip);
  }

  return Array.from(clipsByUrl.values());
}

function buildRenderedTurns(turns: AgentTurn[]): RenderedTurn[] {
  const items: RenderedTurn[] = [];
  let pendingToolPairs: ToolCallPair[] = [];
  let toolGroupStartIndex = 0;

  const flushToolGroup = () => {
    if (pendingToolPairs.length === 0) return;
    items.push({
      kind: 'tool_group',
      key: `tool-group:${toolGroupStartIndex}`,
      pairs: pendingToolPairs,
    });
    pendingToolPairs = [];
  };

  for (let index = 0; index < turns.length; index += 1) {
    const turn = turns[index];

    if (turn.role === 'tool_result') {
      continue;
    }

    if (turn.role === 'tool_call') {
      const nextTurn = turns[index + 1];
      const pairedResult = nextTurn?.role === 'tool_result' ? nextTurn : null;

      if (pendingToolPairs.length === 0) {
        toolGroupStartIndex = index;
      }
      pendingToolPairs.push({ call: turn, result: pairedResult });
      if (pairedResult) index += 1;
      continue;
    }

    flushToolGroup();

    // Skip assistant messages that duplicate a preceding message_user result
    if (turn.role === 'assistant' && items.length > 0) {
      const prev = items[items.length - 1];
      if (prev.kind === 'message' && prev.turn.content === turn.content) {
        continue;
      }
    }

    items.push({
      kind: 'message',
      key: `${turn.timestamp}:${turn.role}:${index}`,
      turn,
    });
  }

  flushToolGroup();
  return items;
}

function createMessageId() {
  return globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random()}`;
}

function getTurnTimestampMs(turn: AgentTurn) {
  const timestampMs = Date.parse(turn.timestamp);
  return Number.isNaN(timestampMs) ? 0 : timestampMs;
}

export function AgentChat() {
  useRenderDiagnostic('AgentChat');
  const location = useLocation();
  const isToolPage = location.pathname.startsWith('/tools') || location.pathname === '/shots' || location.pathname === '/art';

  const {
    timelineId,
    timelineClips,
    replaceSelectedTimelineClips,
  } = useAgentChatBridge();
  const sessions = useAgentSessions(timelineId);
  const createSession = useCreateSession(timelineId);
  const { isTasksPaneLocked, tasksPaneWidth, isGenerationsPaneLocked, isGenerationsPaneOpen, effectiveGenerationsPaneHeight } = usePanes();
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [isOpen, setIsOpen] = useState(false);
  const [draft, setDraft] = useState('');
  const [queue, setQueue] = useState<QueuedMessage[]>([]);
  const [pausedQueueHeadId, setPausedQueueHeadId] = useState<string | null>(null);
  const [optimisticMessage, setOptimisticMessage] = useState<OptimisticMessage | null>(null);
  const [attachmentLightboxMedia, setAttachmentLightboxMedia] = useState<GenerationRow | null>(null);
  const [lastSeenAssistantTurnCount, setLastSeenAssistantTurnCount] = useState(0);
  const hasAutoCreatedSessionRef = useRef(false);
  const lightboxRequestIdRef = useRef(0);
  const bottomAnchorRef = useRef<HTMLDivElement | null>(null);
  const scrollContainerRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const hasTimeline = timelineId !== null;
  const positionStyle = useMemo<CSSProperties>(() => ({
    right: isTasksPaneLocked ? tasksPaneWidth + 20 : 20,
    bottom: (isGenerationsPaneLocked || isGenerationsPaneOpen) ? effectiveGenerationsPaneHeight + 20 : 20,
    transition: 'right 300ms cubic-bezier(0.25, 0.1, 0.25, 1), bottom 300ms cubic-bezier(0.25, 0.1, 0.25, 1)',
  }), [isTasksPaneLocked, tasksPaneWidth, isGenerationsPaneLocked, isGenerationsPaneOpen, effectiveGenerationsPaneHeight]);

  const activeSession = useAgentSession(activeSessionId);
  const sendMessage = useSendMessage(activeSessionId, timelineId);
  const cancelSession = useCancelSession(activeSessionId);
  const sessionOptions = useMemo(() => sessions.data ?? [], [sessions.data]);
  const {
    gallerySelectionMap,
    selectedGalleryClips,
    deselectGalleryItems,
    clearGallerySelection,
  } = useGallerySelection();
  const clips = useMemo(
    () => mergeSelectedClips(timelineClips, selectedGalleryClips),
    [selectedGalleryClips, timelineClips],
  );
  const summary = useMemo(() => {
    return buildSummary(clips);
  }, [clips]);

  const voice = useAgentVoice({
    onTranscription: (text) => {
      void handleSend(text);
    },
  });

  const renderedTurns = useMemo(
    () => buildRenderedTurns(activeSession.data?.turns ?? []),
    [activeSession.data?.turns],
  );
  const activeStatus = activeSession.data?.status;
  const isCancelled = activeStatus === 'cancelled';
  const isProcessing = activeStatus === 'processing' || activeStatus === 'continue';
  const showKillSwitch = activeStatus === 'processing' || activeStatus === 'continue';
  const showNoTimelineState = !hasTimeline && sessionOptions.length === 0;
  const hasQueuedMessages = queue.length > 0;
  const inputPlaceholder = showNoTimelineState
    ? 'Create a timeline to start chatting...'
    : voice.isRecording
      ? 'Recording...'
      : (isProcessing || sendMessage.isPending || hasQueuedMessages)
        ? 'Type to queue next message...'
        : 'Type or press Cmd+Shift+R to talk...';

  const handleAttachmentPreviewClick = useCallback(async (attachment: AgentChatAttachmentPreviewItem) => {
    if (!attachment.generationId) {
      return;
    }

    const requestId = lightboxRequestIdRef.current + 1;
    lightboxRequestIdRef.current = requestId;
    setAttachmentLightboxMedia(null);

    try {
      const media = await loadGenerationForLightbox(attachment.generationId);
      if (lightboxRequestIdRef.current !== requestId) {
        return;
      }

      setAttachmentLightboxMedia(media);
    } catch (error) {
      if (lightboxRequestIdRef.current === requestId) {
        setAttachmentLightboxMedia(null);
      }
      console.warn('[AgentChat] Failed to open attachment lightbox', error);
    }
  }, []);

  const handleCloseAttachmentLightbox = useCallback(() => {
    lightboxRequestIdRef.current += 1;
    setAttachmentLightboxMedia(null);
  }, []);

  const deselectGalleryMatches = useCallback((matcher: (clip: SelectedMediaClip) => boolean) => {
    const idsToRemove = Array.from(gallerySelectionMap.entries())
      .filter(([, item]) => {
        const matchingGalleryClip = selectedGalleryClips.find((clip) => (
          clip.url === item.url
          && clip.mediaType === item.mediaType
          && clip.generationId === item.generationId
        ));

        return matchingGalleryClip ? matcher(matchingGalleryClip) : false;
      })
      .map(([id]) => id);

    if (idsToRemove.length > 0) {
      deselectGalleryItems(idsToRemove);
    }
  }, [deselectGalleryItems, gallerySelectionMap, selectedGalleryClips]);

  const handleRemoveAttachment = useCallback((attachment: AgentChatAttachmentPreviewItem) => {
    replaceSelectedTimelineClips(
      timelineClips.filter((clip) => !(
        clip.url === attachment.url
        && clip.mediaType === attachment.mediaType
        && (
          (attachment.generationId && clip.generationId === attachment.generationId)
          || (!attachment.generationId && clip.clipId === attachment.clipId)
          || (!attachment.generationId && clip.url === attachment.url)
        )
      )),
    );

    deselectGalleryMatches((clip) => (
      clip.url === attachment.url
      && clip.mediaType === attachment.mediaType
      && (
        (attachment.generationId && clip.generationId === attachment.generationId)
        || (!attachment.generationId && clip.url === attachment.url)
      )
    ));
  }, [deselectGalleryMatches, replaceSelectedTimelineClips, timelineClips]);

  const handleRemoveShot = useCallback((shotId: string) => {
    const removedShotClips = timelineClips.filter((clip) => clip.shotId === shotId);
    const removedUrls = new Set(removedShotClips.map((clip) => clip.url));
    const removedGenerationIds = new Set(
      removedShotClips
        .map((clip) => clip.generationId)
        .filter((generationId): generationId is string => Boolean(generationId)),
    );

    replaceSelectedTimelineClips(timelineClips.filter((clip) => clip.shotId !== shotId));
    deselectGalleryMatches((clip) => (
      removedUrls.has(clip.url)
      || (clip.generationId ? removedGenerationIds.has(clip.generationId) : false)
    ));
  }, [deselectGalleryMatches, replaceSelectedTimelineClips, timelineClips]);

  const moveQueuedMessageUp = useCallback((index: number) => {
    if (index <= 0) {
      return;
    }

    setQueue((prev) => {
      if (index >= prev.length) {
        return prev;
      }

      const next = [...prev];
      [next[index - 1], next[index]] = [next[index], next[index - 1]];
      return next;
    });
  }, []);

  const moveQueuedMessageDown = useCallback((index: number) => {
    setQueue((prev) => {
      if (index < 0 || index >= prev.length - 1) {
        return prev;
      }

      const next = [...prev];
      [next[index], next[index + 1]] = [next[index + 1], next[index]];
      return next;
    });
  }, []);

  const removeQueuedMessage = useCallback((id: string) => {
    if (pausedQueueHeadId === id) {
      setPausedQueueHeadId(null);
    }
    setQueue((prev) => prev.filter((item) => item.id !== id));
  }, [pausedQueueHeadId]);

  // Auto-select or create session
  useEffect(() => {
    if (!sessionOptions.length) {
      setActiveSessionId(null);
      return;
    }

    setActiveSessionId((current) => {
      const currentSession = current
        ? sessionOptions.find((session) => session.id === current) ?? null
        : null;
      if (currentSession && currentSession.status !== 'cancelled') {
        return current;
      }

      const preferredSession = sessionOptions.find((session) => session.status !== 'cancelled');
      if (preferredSession) {
        return preferredSession.id;
      }

      if (currentSession) {
        return currentSession.id;
      }

      return sessionOptions[0]?.id ?? null;
    });
  }, [sessionOptions]);

  // Auto-create session when needed (only when chat is open or voice is active)
  useEffect(() => {
    if (
      hasAutoCreatedSessionRef.current
      || sessions.isLoading
      || createSession.isPending
      || sessionOptions.length > 0
      || !hasTimeline
      || (!isOpen && !voice.isRecording && !voice.isProcessing)
    ) {
      return;
    }

    hasAutoCreatedSessionRef.current = true;
    createSession.mutate(undefined, {
      onError: () => { hasAutoCreatedSessionRef.current = false; },
      onSuccess: (session) => { setActiveSessionId(session.id); },
    });
  }, [createSession, hasTimeline, sessionOptions.length, sessions.isLoading, isOpen, voice.isRecording, voice.isProcessing]);

  // Scroll to bottom helper
  const scrollToBottom = useCallback((smooth = true) => {
    const container = scrollContainerRef.current;
    if (!container) return;
    // Use requestAnimationFrame to ensure DOM has updated
    requestAnimationFrame(() => {
      container.scrollTo({
        top: container.scrollHeight,
        behavior: smooth ? 'smooth' : 'instant',
      });
    });
  }, []);

  // Auto-scroll on new turns or processing state change
  useEffect(() => {
    scrollToBottom();
  }, [renderedTurns, isProcessing, optimisticMessage, scrollToBottom]);

  // Scroll to bottom when opening the chat
  useEffect(() => {
    if (isOpen) {
      scrollToBottom(false);
    }
  }, [isOpen, scrollToBottom]);

  // Cmd+Shift+R global shortcut — toggle recording without opening chat
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.shiftKey && event.key.toLowerCase() === 'r') {
        event.preventDefault();
        if (!hasTimeline) {
          setIsOpen(true);
          return;
        }
        if (voice.isRecording) {
          voice.stopRecording();
        } else if (!voice.isProcessing) {
          voice.startRecording();
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [hasTimeline, voice]);

  // Focus input when opened
  useEffect(() => {
    if (isOpen && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isOpen]);

  useEffect(() => {
    setQueue([]);
    setPausedQueueHeadId(null);
    setOptimisticMessage(null);
  }, [activeSessionId]);

  useEffect(() => {
    if (pausedQueueHeadId && !queue.some((item) => item.id === pausedQueueHeadId)) {
      setPausedQueueHeadId(null);
    }
  }, [pausedQueueHeadId, queue]);

  // Clear optimistic message only when the matching turn appears in real data
  useEffect(() => {
    if (!optimisticMessage || !activeSession.data?.turns) return;
    if (activeSession.data.turns.length <= optimisticMessage.priorTurnCount) return;

    const hasRealTurn = activeSession.data.turns.some((turn, index) => (
      index >= optimisticMessage.priorTurnCount
      && turn.role === 'user'
      && turn.content === optimisticMessage.text
      && getTurnTimestampMs(turn) >= optimisticMessage.sentAtMs - 1000
    ));

    if (hasRealTurn) {
      setOptimisticMessage(null);
    }
  }, [activeSession.data?.turns, optimisticMessage]);

  const sendingRef = useRef(false);
  const sendNow = useCallback(async (item: QueuedMessage) => {
    if (!activeSessionId || !timelineId) {
      return;
    }

    const priorTurnCount = activeSession.data?.turns.length ?? 0;
    const sentAtMs = Date.now();

    sendingRef.current = true;
    setOptimisticMessage({
      id: item.id,
      text: item.text,
      attachments: item.attachments,
      sentAtMs,
      priorTurnCount,
    });

    try {
      await sendMessage.mutateAsync({
        message: item.text,
        attachments: item.attachments,
      });
      clearGallerySelection();
    } catch (error) {
      setPausedQueueHeadId(item.id);
      setOptimisticMessage((prev) => (prev && prev.id === item.id ? null : prev));
      throw error;
    } finally {
      sendingRef.current = false;
    }
  }, [activeSession.data?.turns.length, activeSessionId, clearGallerySelection, sendMessage, timelineId]);

  const handleSend = useCallback(async (rawText?: string) => {
    const text = (rawText ?? draft).trim();
    if (!text || !activeSessionId || !timelineId) return;

    const attachments: AgentTurnAttachment[] = clips.map((clip) => ({
      clipId: clip.clipId,
      url: clip.url,
      mediaType: clip.mediaType,
      isTimelineBacked: clip.isTimelineBacked,
      generationId: clip.generationId,
      variantId: clip.variantId,
      shotId: clip.shotId,
      shotName: clip.shotName,
      shotSelectionClipCount: clip.shotSelectionClipCount,
      trackId: clip.trackId,
      at: clip.at,
      duration: clip.duration,
    }));

    if (rawText === undefined) setDraft('');
    const item: QueuedMessage = {
      id: createMessageId(),
      text,
      attachments,
    };

    if (
      sendingRef.current
      || isProcessing
      || sendMessage.isPending
      || optimisticMessage
      || queue.length > 0
    ) {
      setQueue((prev) => [...prev, item]);
      return;
    }

    await sendNow(item);
  }, [activeSessionId, clips, draft, isProcessing, optimisticMessage, queue.length, sendMessage.isPending, sendNow, timelineId]);

  useEffect(() => {
    if (
      sendingRef.current
      || isProcessing
      || sendMessage.isPending
      || optimisticMessage
      || queue.length === 0
      || !activeSessionId
      || !timelineId
    ) {
      return;
    }

    const next = queue[0];
    if (!next || next.id === pausedQueueHeadId) {
      return;
    }

    void (async () => {
      try {
        await sendNow(next);
        setQueue((prev) => (prev[0]?.id === next.id ? prev.slice(1) : prev));
      } catch {
        // Leave the failed head in place; pausedQueueHeadId will prevent further drains.
      }
    })();
  }, [queue, pausedQueueHeadId, isProcessing, sendMessage.isPending, optimisticMessage, activeSessionId, timelineId, sendNow]);

  const handleNewSession = useCallback(async () => {
    if (!hasTimeline) {
      return;
    }
    setQueue([]);
    setPausedQueueHeadId(null);
    setOptimisticMessage(null);
    const session = await createSession.mutateAsync();
    setActiveSessionId(session.id);
    setDraft('');
  }, [createSession, hasTimeline]);

  const assistantTurnCount = useMemo(
    () => (activeSession.data?.turns ?? []).filter((t) => t.role === 'assistant' && t.content.trim().length > 0).length,
    [activeSession.data?.turns],
  );
  useEffect(() => {
    if (isOpen) setLastSeenAssistantTurnCount(assistantTurnCount);
  }, [isOpen, assistantTurnCount]);
  useEffect(() => {
    setLastSeenAssistantTurnCount(0);
  }, [activeSessionId]);

  const isPending = isProcessing || sendMessage.isPending || optimisticMessage !== null || queue.length > 0;
  const hasUnseenMessages = !isOpen && assistantTurnCount > lastSeenAssistantTurnCount;
  const showPendingIndicator = !isOpen && isPending;
  const showUnseenIndicator = hasUnseenMessages && !showPendingIndicator;
  if (!isToolPage) {
    return null;
  }

  let content: JSX.Element;

  if (!isOpen && (voice.isRecording || voice.isProcessing)) {
    content = (
      <div className="fixed z-50 flex items-center gap-3" style={positionStyle}>
        <div className="flex items-center gap-2 rounded-full border border-border/80 bg-background/95 px-4 py-2.5 shadow-lg backdrop-blur">
          {voice.isRecording ? (
            <>
              <span className="inline-flex h-2.5 w-2.5 animate-pulse rounded-full bg-red-500" />
              <div className="flex min-w-0 flex-col">
                <span className="text-sm text-foreground">Recording... {voice.remainingSeconds}s</span>
                {clips.length > 0 && (
                  <span className="text-xs text-muted-foreground">{summary}</span>
                )}
              </div>
              <Button
                type="button"
                size="sm"
                variant="ghost"
                className="h-7 px-2 text-xs"
                onClick={() => voice.stopRecording()}
              >
                Done
              </Button>
            </>
          ) : (
            <>
              <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
              <span className="text-sm text-muted-foreground">Transcribing...</span>
            </>
          )}
        </div>
      </div>
    );
  } else if (!isOpen) {
    content = (
      <div className="fixed z-50 flex items-center gap-2" style={positionStyle}>
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            voice.startRecording();
          }}
          disabled={!hasTimeline || voice.isProcessing}
          className={cn(
            'flex h-10 w-10 items-center justify-center rounded-full shadow-md transition-all hover:scale-105 active:scale-95',
            'bg-muted text-muted-foreground hover:bg-muted/80',
            'disabled:pointer-events-none disabled:opacity-50',
          )}
          title="Voice input (Cmd+Shift+R)"
        >
          <Mic className="h-4 w-4" />
        </button>
        <button
          type="button"
          onClick={() => setIsOpen(true)}
          className={cn(
            'group relative flex h-14 w-14 items-center justify-center rounded-full shadow-lg transition-all hover:scale-105 active:scale-95',
            'bg-primary text-primary-foreground',
          )}
          title="Timeline Agent"
        >
          <MessageSquareText className="h-6 w-6" />
          {showPendingIndicator && (
            <span className="absolute -right-0.5 -top-0.5 flex h-3.5 w-3.5 items-center justify-center rounded-full bg-sky-500 shadow">
              <Loader2 className="h-2.5 w-2.5 animate-spin text-white" />
            </span>
          )}
          {showUnseenIndicator && (
            <span className="absolute -right-0.5 -top-0.5 flex h-3 w-3">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-sky-400 opacity-75" />
              <span className="relative inline-flex h-3 w-3 rounded-full bg-sky-500" />
            </span>
          )}
        </button>
      </div>
    );
  } else {
    content = (
      <div className="fixed z-50 flex h-[min(520px,calc(100vh-3rem))] w-[380px] max-w-[calc(100vw-2.5rem)] flex-col overflow-hidden rounded-2xl border border-border/80 bg-background/95 shadow-2xl backdrop-blur" style={positionStyle}>
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border/70 px-4 py-3">
          <div className="flex items-center gap-2">
            <MessageSquareText className="h-4 w-4 text-muted-foreground" />
            <span className="text-sm font-medium">Timeline Agent</span>
            {isProcessing && <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground" />}
          </div>
          <div className="flex items-center gap-1">
            {showKillSwitch && (
              <Button
                type="button"
                size="icon"
                variant="destructive"
                className="h-7 w-7"
                onClick={() => {
                  setQueue([]);
                  setPausedQueueHeadId(null);
                  setOptimisticMessage(null);
                  cancelSession.mutate();
                }}
                disabled={cancelSession.isPending}
                title="Stop agent"
              >
                <Square className="h-3.5 w-3.5" />
              </Button>
            )}
            <Button
              type="button"
              size="sm"
              variant="ghost"
              className="h-7 px-2 text-xs text-muted-foreground"
              onClick={() => void handleNewSession()}
              disabled={createSession.isPending || !hasTimeline}
            >
              New
            </Button>
            <Button
              type="button"
              size="icon"
              variant="ghost"
              className="h-7 w-7"
              onClick={() => setIsOpen(false)}
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
        </div>
        {/* Messages */}
        <div ref={scrollContainerRef} className="flex-1 overflow-y-auto overscroll-contain px-4 py-3">
          {activeSession.isLoading && (
            <div className="flex items-center gap-2 py-6 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading...
            </div>
          )}

          {!activeSession.isLoading && renderedTurns.length === 0 && (
            <div className="py-8 text-center text-sm text-muted-foreground">
              {showNoTimelineState ? (
                <>
                  <p>Create a timeline to start chatting.</p>
                  <p className="mt-1 text-xs">Open the video editor to create one.</p>
                </>
              ) : (
                <>
                  <p>Ask me to edit your timeline.</p>
                  <p className="mt-1 text-xs">Press <kbd className="rounded border border-border px-1 py-0.5 text-[10px]">Cmd+Shift+R</kbd> to talk</p>
                </>
              )}
            </div>
          )}

          <div className="flex flex-col gap-2.5">
            {renderedTurns.map((item) =>
              item.kind === 'message' ? (
                <AgentChatMessage
                  key={item.key}
                  turn={item.turn}
                  onAttachmentClick={handleAttachmentPreviewClick}
                />
              ) : (
                <AgentChatToolGroup key={item.key} pairs={item.pairs} />
              ),
            )}

            {optimisticMessage && (
              <div className="flex w-full justify-end">
                <div className="max-w-[85%] rounded-2xl bg-primary px-4 py-2.5 text-sm leading-relaxed text-primary-foreground shadow-sm">
                  <div>{optimisticMessage.text}</div>
                  {optimisticMessage.attachments.length > 0 && (
                    <AgentChatAttachmentStrip
                      attachments={optimisticMessage.attachments}
                      isUser
                    />
                  )}
                </div>
              </div>
            )}

            {(isProcessing || sendMessage.isPending || optimisticMessage || hasQueuedMessages) && (
              <div className="flex items-center gap-2 py-1 text-xs text-muted-foreground">
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                Thinking...
              </div>
            )}
          </div>

          <div ref={bottomAnchorRef} />
        </div>

        {/* Input bar */}
        <div className="border-t border-border/70 px-3 py-3">
          {queue.length > 0 && (
            <div className="mb-2 flex flex-col gap-2">
              {queue.map((item, index) => (
                <div
                  key={item.id}
                  className="flex items-center gap-2 rounded-lg bg-muted/50 px-3 py-2 text-xs"
                >
                  <div className="flex-1 text-foreground">
                    <div className="line-clamp-2 break-words leading-relaxed">{item.text}</div>
                  </div>
                  {item.attachments.length > 0 && (
                    <span className="shrink-0 rounded-full bg-background/80 px-2 py-0.5 text-[11px] text-muted-foreground">
                      {`📎 ${item.attachments.length}`}
                    </span>
                  )}
                  <Button
                    type="button"
                    size="icon"
                    variant="ghost"
                    className="h-6 w-6 shrink-0"
                    disabled={index === 0}
                    onClick={() => moveQueuedMessageUp(index)}
                    title="Move queued message up"
                  >
                    <ChevronUp className="h-3.5 w-3.5" />
                  </Button>
                  <Button
                    type="button"
                    size="icon"
                    variant="ghost"
                    className="h-6 w-6 shrink-0"
                    disabled={index === queue.length - 1}
                    onClick={() => moveQueuedMessageDown(index)}
                    title="Move queued message down"
                  >
                    <ChevronDown className="h-3.5 w-3.5" />
                  </Button>
                  <Button
                    type="button"
                    size="icon"
                    variant="ghost"
                    className="h-6 w-6 shrink-0"
                    onClick={() => removeQueuedMessage(item.id)}
                    title="Remove queued message"
                  >
                    <X className="h-3.5 w-3.5" />
                  </Button>
                </div>
              ))}
            </div>
          )}

          {clips.length > 0 && (
            <div className="mb-2 rounded-lg bg-muted/50 px-3 py-2 text-xs text-muted-foreground">
              <AgentChatAttachmentStrip
                attachments={clips}
                isUser={false}
                className="mt-0"
                onAttachmentClick={handleAttachmentPreviewClick}
                onRemoveAttachment={handleRemoveAttachment}
                onRemoveShot={handleRemoveShot}
                maxPreviewCount={null}
              />
              <div className="mt-2">{summary}</div>
            </div>
          )}

          {voice.isRecording && (
            <div className="mb-2 flex items-center justify-between rounded-lg bg-red-500/10 px-3 py-2 text-sm">
              <div className="flex items-center gap-2 text-red-400">
                <span className="inline-flex h-2 w-2 animate-pulse rounded-full bg-red-500" />
                Recording... {voice.remainingSeconds}s
              </div>
              <Button
                type="button"
                size="sm"
                variant="ghost"
                className="h-7 px-2 text-xs text-red-400 hover:text-red-300"
                onClick={() => voice.stopRecording()}
              >
                Done
              </Button>
            </div>
          )}

          {voice.isProcessing && (
            <div className="mb-2 flex items-center gap-2 rounded-lg bg-muted/50 px-3 py-2 text-xs text-muted-foreground">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              Transcribing...
            </div>
          )}

          {!isProcessing && !sendMessage.isPending && isCancelled && (
            <div className="mb-2 rounded-lg border border-border/70 bg-muted/40 px-3 py-2 text-xs text-muted-foreground">
              Session stopped. Start a new conversation to continue.
            </div>
          )}

          {!isProcessing && !sendMessage.isPending && !isCancelled && (sendMessage.localError || activeStatus === 'error') && (
            <div className="mb-2 rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-xs text-destructive">
              {sendMessage.localError ?? 'Agent error. Try again or start a new conversation.'}
            </div>
          )}

          <div className="flex items-center gap-2">
            <input
              ref={inputRef}
              type="text"
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              placeholder={inputPlaceholder}
              className="h-10 flex-1 rounded-xl border border-border/70 bg-card px-3 text-sm outline-none transition-colors placeholder:text-muted-foreground/70 focus:border-primary/50"
              disabled={!hasTimeline || !activeSessionId || isCancelled || voice.isRecording || voice.isProcessing}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && !event.shiftKey) {
                  event.preventDefault();
                  void handleSend();
                }
              }}
            />

            <div className="relative shrink-0">
              <Button
                type="button"
                size="icon"
                variant={voice.isRecording ? 'destructive' : 'outline'}
                className="h-10 w-10 rounded-xl"
                onClick={() => voice.isRecording ? voice.stopRecording() : voice.startRecording()}
                disabled={!hasTimeline || !activeSessionId || isCancelled || voice.isProcessing || sendMessage.isPending}
                title={voice.isRecording ? 'Stop recording' : 'Voice input (Cmd+Shift+R)'}
              >
                {voice.isRecording ? <Square className="h-4 w-4" /> : <Mic className="h-4 w-4" />}
              </Button>
              {voice.isRecording && (
                <Button
                  type="button"
                  size="icon"
                  variant="ghost"
                  className="absolute -top-2 -right-2 h-5 w-5 rounded-full bg-muted hover:bg-destructive hover:text-destructive-foreground"
                  onClick={() => voice.cancelRecording()}
                  title="Cancel recording"
                >
                  <X className="h-3 w-3" />
                </Button>
              )}
            </div>

            <Button
              type="button"
              size="icon"
              className="h-10 w-10 shrink-0 rounded-xl"
              onClick={() => void handleSend()}
              disabled={!hasTimeline || !draft.trim() || !activeSessionId || isCancelled}
              title="Send"
            >
              <Send className="h-4 w-4" />
            </Button>
          </div>
        </div>

        {attachmentLightboxMedia && (
          <MediaLightbox
            media={attachmentLightboxMedia}
            initialVariantId={attachmentLightboxMedia.primary_variant_id ?? undefined}
            onClose={handleCloseAttachmentLightbox}
            features={{ showDownload: true, showTaskDetails: true }}
          />
        )}
      </div>
    );
  }

  if (typeof document === 'undefined') {
    return null;
  }

  return createPortal(content, document.body);
}
