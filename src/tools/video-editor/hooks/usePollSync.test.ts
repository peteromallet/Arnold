// @vitest-environment jsdom
import { renderHook } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { shouldAcceptPolledData } from '@/tools/video-editor/lib/timeline-save-utils';
import { createInteractionState } from '@/tools/video-editor/lib/interaction-state';
import { getTimelinePollRejectionReason, isTimelinePollIdle, usePollSync } from '@/tools/video-editor/hooks/usePollSync';
import type { DataProvider } from '@/tools/video-editor/data/DataProvider';
import type { TimelineData } from '@/tools/video-editor/lib/timeline-data';

function getLegacyPollRejectionReason(input: {
  editSeq: number;
  savedSeq: number;
  pendingOps: number;
  polledConfigVersion: number;
  currentConfigVersion: number;
  polledStableSignature: string;
  lastSavedStableSignature: string;
}): string | null {
  if (input.savedSeq < input.editSeq) {
    return 'unsaved edits';
  }

  if (input.pendingOps > 0) {
    return 'pending ops';
  }

  if (input.polledConfigVersion < input.currentConfigVersion) {
    return 'stale version';
  }

  if (
    !shouldAcceptPolledData(
      input.editSeq,
      input.savedSeq,
      input.pendingOps,
      input.polledStableSignature,
      input.lastSavedStableSignature,
    )
  ) {
    return input.polledConfigVersion === input.currentConfigVersion ? 'own echo' : 'signature match';
  }

  return null;
}

describe('usePollSync helpers', () => {
  it('preserves legacy poll decisions except for the intentional save-in-flight rejection', () => {
    const editSeqValues = [2, 4];
    const savedSeqValues = [1, 2, 4, 6];
    const pendingOpsValues = [0, 1];
    const isSavingValues = [false, true];
    const configVersions = [
      { polledConfigVersion: 7, currentConfigVersion: 7 },
      { polledConfigVersion: 8, currentConfigVersion: 7 },
      { polledConfigVersion: 6, currentConfigVersion: 7 },
    ];
    const signatures = [
      { polledStableSignature: 'saved-sig', lastSavedStableSignature: 'saved-sig' },
      { polledStableSignature: 'remote-sig', lastSavedStableSignature: 'saved-sig' },
    ];

    for (const editSeq of editSeqValues) {
      for (const savedSeq of savedSeqValues) {
        for (const pendingOps of pendingOpsValues) {
          for (const isSaving of isSavingValues) {
            for (const versionState of configVersions) {
              for (const signatureState of signatures) {
                const nextReason = getTimelinePollRejectionReason({
                  editSeq,
                  savedSeq,
                  pendingOps,
                  isSaving,
                  ...versionState,
                  ...signatureState,
                });
                const legacyReason = getLegacyPollRejectionReason({
                  editSeq,
                  savedSeq,
                  pendingOps,
                  ...versionState,
                  ...signatureState,
                });
                const expectedReason = isSaving && savedSeq >= editSeq && pendingOps === 0
                  ? 'saving'
                  : legacyReason;

                expect(nextReason).toBe(expectedReason);
              }
            }
          }
        }
      }
    }
  });

  it('default-rejects polls while a save is in flight even if other idle conditions are true', () => {
    expect(isTimelinePollIdle({
      editSeq: 4,
      savedSeq: 4,
      pendingOps: 0,
      isSaving: true,
    })).toBe(false);

    expect(getTimelinePollRejectionReason({
      editSeq: 4,
      savedSeq: 4,
      pendingOps: 0,
      isSaving: true,
      polledConfigVersion: 8,
      currentConfigVersion: 7,
      polledStableSignature: 'remote-sig',
      lastSavedStableSignature: 'saved-sig',
    })).toBe('saving');
  });

  it('rejects polls while an interaction (drag/resize) is active', () => {
    // Even when the timeline would otherwise be idle and the poll signature is fresh,
    // an active interaction must defer the conflict reload.
    expect(isTimelinePollIdle({
      editSeq: 4,
      savedSeq: 4,
      pendingOps: 0,
      isSaving: false,
      interactionActive: true,
    })).toBe(false);

    expect(getTimelinePollRejectionReason({
      editSeq: 4,
      savedSeq: 4,
      pendingOps: 0,
      isSaving: false,
      interactionActive: true,
      polledConfigVersion: 8,
      currentConfigVersion: 7,
      polledStableSignature: 'remote-sig',
      lastSavedStableSignature: 'saved-sig',
    })).toBe('interaction active');
  });

  it('accepts polls when interaction is no longer active', () => {
    expect(isTimelinePollIdle({
      editSeq: 4,
      savedSeq: 4,
      pendingOps: 0,
      isSaving: false,
      interactionActive: false,
    })).toBe(true);

    expect(getTimelinePollRejectionReason({
      editSeq: 4,
      savedSeq: 4,
      pendingOps: 0,
      isSaving: false,
      interactionActive: false,
      polledConfigVersion: 8,
      currentConfigVersion: 7,
      polledStableSignature: 'remote-sig',
      lastSavedStableSignature: 'saved-sig',
    })).toBeNull();
  });

  it('keeps configVersionRef pinned to the accepted local base version while a remote payload is still deferred', async () => {
    const provider: DataProvider = {
      loadTimeline: vi.fn(),
      saveTimeline: vi.fn(),
      loadAssetRegistry: vi.fn(),
      resolveAssetUrl: vi.fn(async (file: string) => file),
    };
    const interactionState = createInteractionState();
    interactionState.drag = true;
    const interactionStateRef = { current: interactionState };
    const configVersionRef = { current: 3 };
    const commitData = vi.fn();
    const polledData = {
      configVersion: 7,
      stableSignature: 'remote-sig',
      signature: 'remote-sig',
    } as unknown as TimelineData;

    renderHook(() => usePollSync({
      queries: {
        timelineQuery: {
          data: polledData,
          isLoading: false,
        },
        assetRegistryQuery: {
          data: undefined,
        },
      },
      provider,
      commitData,
      dataRef: { current: null },
      selectedClipIdRef: { current: null },
      selectedTrackIdRef: { current: null },
      editSeqRef: { current: 4 },
      pendingOpsRef: { current: 0 },
      savedSeqRef: { current: 4 },
      configVersionRef,
      lastSavedSignatureRef: { current: 'saved-sig' },
      isSavingRef: { current: false },
      interactionStateRef,
    }));

    await Promise.resolve();

    expect(configVersionRef.current).toBe(3);
    expect(commitData).not.toHaveBeenCalled();
  });
});
