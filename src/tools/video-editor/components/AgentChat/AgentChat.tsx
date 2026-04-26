import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ChevronDown, ChevronUp, Loader2, MessageSquareText, Mic, Send, Square, X } from 'lucide-react';
import type { GenerationRow } from '@/domains/generation/types';
import { MediaLightbox } from '@/domains/media-lightbox/MediaLightbox';
import { Button } from '@/shared/components/ui/button';
import { useAgentChatBridge, useAgentChatActionsRegistry, type AgentChatActionsHandlers } from '@/shared/contexts/AgentChatContext';
import { composerClearAttachments, composerRemoveAttachment } from '@/shared/state/selectionStore';
import { useCurrentAttachmentSet } from '@/shared/state/currentAttachmentSet';
import { usePanesStore } from '@/shared/state/panesStore';
import { useAgentSession, useAgentSessions, useCancelSession, useCreateSession, useSendMessage } from '@/tools/video-editor/hooks/useAgentSession';
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

export function AgentChatPanel() {
  useRenderDiagnostic('AgentChatPanel');

  const { timelineId } = useAgentChatBridge();
  const sessions = useAgentSessions(timelineId);
  const createSession = useCreateSession(timelineId);
  // Engagement signal: when the pane is locked the user has clearly committed to
  // having chat visible, so auto-create can fire without an explicit click.
  const isTasksPaneLocked = usePanesStore((state) => state.isTasksPaneLocked);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [draft, setDraft] = useState('');
  const [queue, setQueue] = useState<QueuedMessage[]>([]);
  const [pausedQueueHeadId, setPausedQueueHeadId] = useState<string | null>(null);
  const [optimisticMessage, setOptimisticMessage] = useState<OptimisticMessage | null>(null);
  const [attachmentLightboxMedia, setAttachmentLightboxMedia] = useState<GenerationRow | null>(null);
  // Engagement flag local to AgentChatPanel: flipped by markEngaged() (split-button click)
  // and decoupled from pane open state so the close-path bug from the rev-4
  // setIsTasksPaneOpenProgrammatic approach can't recur.
  const [userEngaged, setUserEngaged] = useState(false);
  const hasAutoCreatedSessionRef = useRef(false);
  const lightboxRequestIdRef = useRef(0);
  const bottomAnchorRef = useRef<HTMLDivElement | null>(null);
  const scrollContainerRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const hasTimeline = timelineId !== null;

  const activeSession = useAgentSession(activeSessionId);
  const sendMessage = useSendMessage(activeSessionId, timelineId);
  const cancelSession = useCancelSession(activeSessionId);
  const sessionOptions = useMemo(() => sessions.data ?? [], [sessions.data]);
  const { clips, summary } = useCurrentAttachmentSet();

  const voice = useAgentVoice({
    onTranscription: (text) => {
      void handleSend(text);
    },
  });
  // Stable ref so registered handlers always invoke the current voice closure
  // without re-registering when useVoiceRecording returns new function identities.
  const voiceRef = useRef(voice);
  voiceRef.current = voice;

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

  const handleRemoveAttachment = useCallback((attachment: AgentChatAttachmentPreviewItem) => {
    composerRemoveAttachment({
      url: attachment.url,
      mediaType: attachment.mediaType,
      generationId: attachment.generationId,
      clipId: attachment.clipId,
    });
  }, []);

  const handleRemoveShot = useCallback((shotId: string) => {
    clips
      .filter((clip) => clip.shotId === shotId)
      .forEach((clip) => composerRemoveAttachment({
        url: clip.url,
        mediaType: clip.mediaType,
        generationId: clip.generationId,
        clipId: clip.clipId,
      }));
  }, [clips]);

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

  // Auto-select session — always picks the latest non-cancelled session if available.
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

  // Auto-create session — gated on user engagement, never on mount alone.
  // Engagement signals: pane locked, voice activity, or markEngaged() called via
  // the split message button. Decoupled from pane open state per plan_v5 Option C.
  const isEngaged = userEngaged || isTasksPaneLocked || voice.isRecording || voice.isProcessing;
  useEffect(() => {
    if (
      hasAutoCreatedSessionRef.current
      || sessions.isLoading
      || createSession.isPending
      || sessionOptions.length > 0
      || !hasTimeline
      || !isEngaged
    ) {
      return;
    }

    hasAutoCreatedSessionRef.current = true;
    createSession.mutate(undefined, {
      onError: () => { hasAutoCreatedSessionRef.current = false; },
      onSuccess: (session) => { setActiveSessionId(session.id); },
    });
  }, [createSession, hasTimeline, sessionOptions.length, sessions.isLoading, isEngaged]);

  const scrollToBottom = useCallback((smooth = true) => {
    const container = scrollContainerRef.current;
    if (!container) return;
    requestAnimationFrame(() => {
      container.scrollTo({
        top: container.scrollHeight,
        behavior: smooth ? 'smooth' : 'instant',
      });
    });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [renderedTurns, isProcessing, optimisticMessage, scrollToBottom]);

  // Cmd+Shift+R global shortcut — kept verbatim per plan_v5 Step 4.7.
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.shiftKey && event.key.toLowerCase() === 'r') {
        event.preventDefault();
        if (!hasTimeline) {
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
      composerClearAttachments();
    } catch (error) {
      setPausedQueueHeadId(item.id);
      setOptimisticMessage((prev) => (prev && prev.id === item.id ? null : prev));
      throw error;
    } finally {
      sendingRef.current = false;
    }
  }, [activeSession.data?.turns.length, activeSessionId, sendMessage, timelineId]);

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

  // ==========================================================================
  // Actions registry — exposes stable handlers the parent (TasksPane split
  // button) can invoke. Stable identity means the registration effect runs
  // exactly once per mount, even though `voice` re-renders. Reactive state is
  // published separately so the split button mic icon flips with recording.
  // ==========================================================================
  const actionsRegistry = useAgentChatActionsRegistry();
  const stableHandlers = useMemo<AgentChatActionsHandlers>(() => ({
    toggleRecording: () => {
      const v = voiceRef.current;
      if (v.isRecording) {
        v.stopRecording();
      } else if (!v.isProcessing) {
        v.startRecording();
      }
    },
    focusComposer: () => {
      inputRef.current?.focus();
    },
    markEngaged: () => {
      setUserEngaged(true);
    },
  }), []);

  useEffect(() => {
    actionsRegistry.registerHandlers(stableHandlers);
    actionsRegistry.publishState({
      isRecording: voice.isRecording,
      isProcessing: voice.isProcessing,
    });
    return () => actionsRegistry.unregister();
    // stableHandlers and actionsRegistry are both referentially stable, so this
    // effect runs exactly once per mount despite voice churn.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [actionsRegistry, stableHandlers]);

  useEffect(() => {
    actionsRegistry.publishState({
      isRecording: voice.isRecording,
      isProcessing: voice.isProcessing,
    });
  }, [actionsRegistry, voice.isRecording, voice.isProcessing]);

  return (
    // No background of its own — sits on the parent pane's bg so the only
    // visible color change between halves is the divider line itself.
    <div className="flex h-full w-full flex-col overflow-hidden">
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
            <div className="mt-2 flex items-center justify-between gap-2">
              <span>{summary}</span>
              {clips.length > 1 && (
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  className="h-6 px-2 text-xs text-muted-foreground hover:text-foreground"
                  onClick={() => {
                    // Clear both surfaces. Gallery is always available; the
                    // timeline-side replace is bridge-nullable when no
                    // VideoEditorProvider is mounted (e.g. /shots, /art routes).
                    composerClearAttachments();
                  }}
                >
                  Clear
                </Button>
              )}
            </div>
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
