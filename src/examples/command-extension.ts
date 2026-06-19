/**
 * command-extension — Extension example with commands, keybindings, and menus.
 *
 * Demonstrates M4 command contributions using only @reigh/editor-sdk:
 *   - A palette-visible command with category metadata
 *   - A keyboard shortcut contribution
 *   - A clip context-menu item contribution
 *   - An imperative command handler registered during activate()
 *   - Patch-backed behavior through ctx.creative.reader.snapshot() and
 *     ctx.creative.timeline.apply()
 *
 * This file must NOT import from editor internals (src/tools/video-editor/*).
 * It imports exclusively from @reigh/editor-sdk, the public SDK entrypoint.
 */

import { defineExtension } from '@reigh/editor-sdk';
import type {
  CommandHandler,
  CommandRunContext,
  CommandRegistrationOptions,
  ContextMenuItemContribution,
  DisposeHandle,
  EXTENSION_PROJECT_DATA_LIMITS,
  ExtensionContext,
  ExtensionCommandService,
  GeneratedObjectMeta,
  KeybindingContribution,
  ProjectDataLimitCode,
  ProjectDataLimitDetail,
  ProposalListener,
  ProposalPanelAction,
  ProposalPanelState,
  ProposalRuntime,
  ProposalState,
  ReighExtension,
  SourceMapEntry,
  SourceMapRuntime,
  TargetContext,
  TargetContextPayload,
  TimelineClipSummary,
  TimelineDiff,
  TimelineDiffEntry,
  TimelineDiffGranularity,
  TimelineDiffKind,
  TimelinePatch,
  TimelinePatchAnyOpFamily,
  TimelinePatchDiagnostic,
  TimelinePatchOpFamily,
  TimelinePatchOperation,
  TimelinePatchReservedOpFamily,
  TimelinePatchValidationResult,
  TimelinePreviewResult,
  TimelineProposal,
  TimelineProposalInput,
  TimelineReader,
  TimelineSnapshot,
  TimelineTrackSummary,
  TimelineOps,
  CommandContribution,
  createCreativeContext,
} from '@reigh/editor-sdk';

const EXTENSION_ID = 'com.reigh.examples.command-extension';
const COMMAND_ID = `${EXTENSION_ID}.markClipReview`;

function buildReviewMarkerPatch(
  ctx: ExtensionContext,
  run: CommandRunContext,
): TimelinePatch {
  const snapshot = ctx.creative.reader.snapshot();
  const targetClipId = run.target?.target === 'clip'
    ? run.target.clipId
    : snapshot.clips[0]?.id ?? null;

  return {
    version: snapshot.baseVersion,
    source: ctx.extension.id as string,
    meta: { kind: 'command-extension-review-marker' },
    operations: [
      {
        op: 'project-data.write',
        target: ctx.extension.id as string,
        payload: {
          key: 'lastReviewMarker',
          value: {
            commandId: run.commandId,
            targetClipId,
            clipCount: snapshot.clips.length,
            trackCount: snapshot.tracks.length,
            snapshotVersion: snapshot.currentVersion,
          },
          mode: 'replace',
        },
      },
    ],
  };
}

const contributions: readonly [
  CommandContribution,
  KeybindingContribution,
  ContextMenuItemContribution,
] = [
  {
    id: 'mark-clip-review-command' as any,
    kind: 'command',
    command: COMMAND_ID,
    label: 'Mark Clip for Review',
    category: 'Examples',
    order: 10,
  },
  {
    id: 'mark-clip-review-keybinding' as any,
    kind: 'keybinding',
    command: COMMAND_ID,
    key: 'CtrlOrCmd+Alt+R',
    order: 10,
  },
  {
    id: 'mark-clip-review-menu' as any,
    kind: 'contextMenuItem',
    command: COMMAND_ID,
    label: 'Mark Clip for Review',
    target: 'clip',
    when: 'target.clipId != null',
    order: 10,
  },
];

export const commandExtension: ReighExtension = defineExtension({
  manifest: {
    id: EXTENSION_ID as any,
    version: '1.0.0',
    label: 'Command Extension Example',
    description:
      'Adds a patch-backed command to the palette, keyboard shortcuts, and clip context menus.',
    apiVersion: 1,
    contributions,
  },

  activate(ctx: ExtensionContext): DisposeHandle {
    return ctx.commands.registerCommand(
      COMMAND_ID,
      (run: CommandRunContext): void => {
        const patch = buildReviewMarkerPatch(ctx, run);
        ctx.creative.timeline.apply(patch);
        ctx.chrome.toast('Clip review marker stored.', 'info');
      },
      {
        label: 'Mark Clip for Review',
        category: 'Examples',
      },
    );
  },
});
