import { useState } from 'react';
import { ChevronDown, ChevronRight, Loader2, Terminal, X } from 'lucide-react';
import { cn } from '@/shared/components/ui/contracts/cn.ts';
import { buildAttachedSummary } from '@/tools/video-editor/hooks/useSelectedMediaClips.ts';
import type { AgentTurn } from '@/tools/video-editor/types/agent-session.ts';
import type { ToolCallPair } from './AgentChat.tsx';

const MAX_TOOL_NAME_LENGTH = 80;
const MAX_ATTACHMENT_SUMMARY_LENGTH = 120;
const MAX_ATTACHMENT_PREVIEW_COUNT = 4;

type AgentChatMessageProps = {
  turn: AgentTurn;
  onAttachmentClick?: (attachment: AgentChatAttachmentPreviewItem) => void;
};

type AgentChatToolGroupProps = {
  pairs: ToolCallPair[];
};

export type AgentChatAttachmentPreviewItem = {
  clipId: string;
  url: string;
  mediaType: 'image' | 'video';
  isPlaceholder?: boolean;
  generationId?: string;
  assetKey?: string;
  shotId?: string;
  shotName?: string;
  shotSelectionClipCount?: number;
};

function formatAttachmentSummary(attachments: AgentTurn['attachments']) {
  if (!attachments?.length) {
    return null;
  }

  return buildAttachedSummary(attachments);
}

function formatTimestamp(timestamp: string) {
  if (!timestamp) return '';
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

type AgentChatAttachmentStripProps = {
  attachments: readonly AgentChatAttachmentPreviewItem[];
  isUser: boolean;
  className?: string;
  onAttachmentClick?: (attachment: AgentChatAttachmentPreviewItem) => void;
  onRemoveAttachment?: (attachment: AgentChatAttachmentPreviewItem) => void;
  onRemoveShot?: (shotId: string) => void;
  maxPreviewCount?: number | null;
};

type AttachmentGroup =
  | {
    kind: 'shot';
    shotId: string;
    shotName?: string;
    attachments: AgentChatAttachmentPreviewItem[];
    expectedClipCount: number;
  }
  | {
    kind: 'attachment';
    attachment: AgentChatAttachmentPreviewItem;
  };

function buildAttachmentGroups(
  attachments: readonly AgentChatAttachmentPreviewItem[],
): AttachmentGroup[] {
  const shotGroups = new Map<string, {
    attachments: AgentChatAttachmentPreviewItem[];
    expectedClipCount: number;
    shotName?: string;
  }>();

  attachments.forEach((attachment) => {
    if (
      !attachment.shotId
      || typeof attachment.shotSelectionClipCount !== 'number'
      || attachment.shotSelectionClipCount < 1
    ) {
      return;
    }

    const existing = shotGroups.get(attachment.shotId);
    if (existing) {
      existing.attachments.push(attachment);
      return;
    }

    shotGroups.set(attachment.shotId, {
      attachments: [attachment],
      expectedClipCount: attachment.shotSelectionClipCount,
      shotName: attachment.shotName,
    });
  });

  const fullShotIds = new Set(
    Array.from(shotGroups.entries())
      .filter(([, group]) => group.attachments.length === group.expectedClipCount)
      .map(([shotId]) => shotId),
  );

  const groups: AttachmentGroup[] = [];
  const emittedShotIds = new Set<string>();

  attachments.forEach((attachment) => {
    if (attachment.shotId && fullShotIds.has(attachment.shotId)) {
      if (emittedShotIds.has(attachment.shotId)) {
        return;
      }

      const shotGroup = shotGroups.get(attachment.shotId);
      if (!shotGroup) {
        return;
      }

      groups.push({
        kind: 'shot',
        shotId: attachment.shotId,
        shotName: shotGroup.shotName,
        attachments: shotGroup.attachments,
        expectedClipCount: shotGroup.expectedClipCount,
      });
      emittedShotIds.add(attachment.shotId);
      return;
    }

    groups.push({
      kind: 'attachment',
      attachment,
    });
  });

  return groups;
}

export function AgentChatAttachmentStrip({
  attachments,
  isUser,
  className,
  onAttachmentClick,
  onRemoveAttachment,
  onRemoveShot,
  maxPreviewCount = MAX_ATTACHMENT_PREVIEW_COUNT,
}: AgentChatAttachmentStripProps) {
  const previewAttachments = maxPreviewCount === null
    ? attachments
    : attachments.slice(0, maxPreviewCount);
  const remainingCount = attachments.length - previewAttachments.length;
  const groups = buildAttachmentGroups(previewAttachments);

  const previewSurfaceClassName = cn(
    'h-10 w-10 overflow-hidden rounded-md border',
    isUser
      ? 'border-primary-foreground/20 bg-primary-foreground/10'
      : 'border-border/70 bg-muted/40',
  );

  const removeButtonClassName = cn(
    'absolute -right-1 -top-1 z-10 flex h-5 w-5 items-center justify-center rounded-full border shadow-sm',
    isUser
      ? 'border-primary-foreground/30 bg-background/95 text-foreground hover:bg-background'
      : 'border-border/80 bg-background/95 text-foreground hover:bg-background',
  );

  const renderPreview = (
    attachment: AgentChatAttachmentPreviewItem,
    index: number,
    removeLabel: string,
  ) => {
    const isPlaceholder = attachment.isPlaceholder === true;
    const isInteractive = Boolean(onAttachmentClick && attachment.generationId && !isPlaceholder);
    const content = isPlaceholder ? (
      <div
        className="flex h-full w-full flex-col items-center justify-center gap-0.5 bg-muted/50 text-[8px] leading-none text-muted-foreground"
        aria-label={`Loading attached ${attachment.mediaType} ${index + 1}`}
      >
        <Loader2 className="h-3 w-3 animate-spin" aria-hidden="true" />
        <span>Loading…</span>
      </div>
    ) : attachment.mediaType === 'video' ? (
      <video
        src={attachment.url}
        className="h-full w-full object-cover"
        muted
        playsInline
        preload="metadata"
        aria-hidden="true"
      />
    ) : (
      <img
        src={attachment.url}
        alt=""
        className="h-full w-full object-cover"
        loading="lazy"
      />
    );

    return (
      <div
        key={`${attachment.clipId}:${index}`}
        className={cn(
          'relative',
          isInteractive && 'transition-transform hover:scale-[1.03]',
        )}
      >
        <div className={previewSurfaceClassName}>
          {isInteractive ? (
            <button
              type="button"
              className="h-full w-full cursor-pointer"
              onClick={() => onAttachmentClick?.(attachment)}
              aria-label={`Open attached ${attachment.mediaType} ${index + 1}`}
            >
              {content}
            </button>
          ) : (
            <div
              className="h-full w-full"
              aria-label={`Attached ${attachment.mediaType} ${index + 1}`}
            >
              {content}
            </div>
          )}
        </div>
        {onRemoveAttachment && !isPlaceholder && (
          <button
            type="button"
            className={removeButtonClassName}
            aria-label={removeLabel}
            onClick={(event) => {
              event.stopPropagation();
              onRemoveAttachment(attachment);
            }}
          >
            <X className="h-3 w-3" />
          </button>
        )}
      </div>
    );
  };

  return (
    <div className={cn('mt-2 flex flex-wrap gap-1.5', className)}>
      {groups.map((group, index) => {
        if (group.kind === 'shot') {
          return (
            <div
              key={`${group.shotId}:${index}`}
              className={cn(
                'relative inline-flex w-fit max-w-full flex-col self-start rounded-lg border p-1.5',
                isUser
                  ? 'border-primary-foreground/30 bg-primary-foreground/5'
                  : 'border-primary/30 bg-primary/5',
              )}
              aria-label={`${group.shotName ?? 'Shot'} group`}
            >
              {onRemoveShot && (
                <button
                  type="button"
                  className={removeButtonClassName}
                  aria-label={`Deselect ${group.shotName ?? 'shot'}`}
                  onClick={(event) => {
                    event.stopPropagation();
                    onRemoveShot(group.shotId);
                  }}
                >
                  <X className="h-3 w-3" />
                </button>
              )}
              <div
                className="mb-1 max-w-20 truncate px-0.5 text-[10px] font-medium uppercase tracking-[0.12em] text-muted-foreground"
                title={group.shotName ?? 'Shot'}
              >
                {group.shotName ?? 'Shot'} ({group.expectedClipCount})
              </div>
              <div className="flex flex-wrap gap-1.5">
                {group.attachments.map((attachment, groupIndex) => (
                  renderPreview(
                    attachment,
                    groupIndex,
                    `Deselect ${attachment.mediaType} ${groupIndex + 1} from ${group.shotName ?? 'shot'}`,
                  )
                ))}
              </div>
            </div>
          );
        }

        return renderPreview(
          group.attachment,
          index,
          `Deselect attached ${group.attachment.mediaType} ${index + 1}`,
        );
      })}
      {remainingCount > 0 && (
        <div
          className={cn(
            'flex h-10 w-10 items-center justify-center rounded-md border text-[10px] font-medium',
            isUser
              ? 'border-primary-foreground/20 bg-primary-foreground/10 text-primary-foreground/80'
              : 'border-border/70 bg-muted/40 text-muted-foreground',
          )}
          aria-label={`${remainingCount} more attachments`}
        >
          +{remainingCount}
        </div>
      )}
    </div>
  );
}

export function AgentChatToolGroup({ pairs }: AgentChatToolGroupProps) {
  const [isOpen, setIsOpen] = useState(false);
  const count = pairs.length;

  // For run commands, show the command string directly
  const commandSummaries = pairs.map((p) => {
    const command = p.call.tool_args?.command;
    return typeof command === 'string' ? command : (p.call.content ?? p.call.tool_name ?? 'tool');
  });

  const label = count === 1
    ? commandSummaries[0]
    : `${count} commands`;

  return (
    <div className="w-full">
      <button
        type="button"
        className="flex w-full min-w-0 items-center gap-2 rounded-lg bg-muted/30 px-2.5 py-1.5 text-left text-xs transition-colors hover:bg-muted/50"
        onClick={() => setIsOpen(!isOpen)}
      >
        <Terminal className="h-3 w-3 shrink-0 text-muted-foreground" />
        <code className="min-w-0 flex-1 truncate font-mono text-foreground/80">{label}</code>
        {count > 1 && (isOpen ? <ChevronDown className="h-3 w-3 shrink-0 text-muted-foreground" /> : <ChevronRight className="h-3 w-3 shrink-0 text-muted-foreground" />)}
      </button>

      {isOpen && count > 1 && (
        <div className="mt-1 space-y-0.5 pl-2">
          {pairs.map((pair, index) => (
            <div key={`${pair.call.timestamp}:${index}`} className="flex min-w-0 items-start gap-2 rounded px-2 py-1 text-xs">
              <code className="min-w-0 break-all font-mono text-foreground/70">{commandSummaries[index]}</code>
              {pair.result && (
                <span className="min-w-0 break-words text-muted-foreground">→ {pair.result.content?.slice(0, MAX_TOOL_NAME_LENGTH)}</span>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Show result inline for single commands */}
      {count === 1 && pairs[0].result?.content && (
        <div className="mt-0.5 break-words px-2.5 text-xs text-muted-foreground">
          {pairs[0].result.content.slice(0, MAX_ATTACHMENT_SUMMARY_LENGTH)}
        </div>
      )}
    </div>
  );
}

export function AgentChatMessage({ turn, onAttachmentClick }: AgentChatMessageProps) {
  const timestamp = formatTimestamp(turn.timestamp);
  const isUser = turn.role === 'user';
  const attachmentSummary = formatAttachmentSummary(turn.attachments);
  const hasAttachmentPreviews = Boolean(turn.attachments?.length);

  return (
    <div className={cn('flex w-full', isUser ? 'justify-end' : 'justify-start')}>
      <div
        className={cn(
          'min-w-0 max-w-[85%] rounded-2xl px-4 py-2.5 shadow-sm',
          isUser
            ? 'bg-primary text-primary-foreground'
            : 'border border-border/70 bg-card text-card-foreground',
        )}
      >
        <div className="whitespace-pre-wrap break-words text-sm leading-relaxed [overflow-wrap:anywhere]">
          {turn.content}
        </div>
        {hasAttachmentPreviews && turn.attachments && (
          <AgentChatAttachmentStrip
            attachments={turn.attachments}
            isUser={isUser}
            onAttachmentClick={onAttachmentClick}
          />
        )}
        {attachmentSummary && (
          <span
            className={cn(
              'mt-1.5 block text-xs',
              isUser ? 'text-primary-foreground/75' : 'text-muted-foreground',
            )}
          >
            {attachmentSummary}
          </span>
        )}
        {timestamp && (
          <div
            className={cn(
              'mt-1.5 text-[10px] uppercase tracking-[0.14em]',
              isUser ? 'text-primary-foreground/70' : 'text-muted-foreground',
            )}
          >
            {timestamp}
          </div>
        )}
      </div>
    </div>
  );
}
