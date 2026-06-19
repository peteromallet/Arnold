// @vitest-environment jsdom
import { render, screen, fireEvent, within } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { ProposalPanel } from '@/tools/video-editor/components/ProposalPanel/ProposalPanel';
import type {
  ProposalRuntime,
  TimelineProposal,
  TimelinePatch,
  TimelineDiff,
  TimelinePreviewResult,
  ProposalListener,
  DisposeHandle,
  ProposalState,
} from '@reigh/editor-sdk';

// ---------------------------------------------------------------------------
// Mock factories
// ---------------------------------------------------------------------------

function mockPatch(overrides?: Partial<TimelinePatch>): TimelinePatch {
  return {
    version: 1,
    operations: [
      {
        op: 'clip.add',
        payload: { track: 'track-1', at: 0, clipType: 'video' },
      },
    ],
    source: 'test-extension',
    ...overrides,
  };
}

function mockDiff(overrides?: Partial<TimelineDiff>): TimelineDiff {
  return {
    version: 1,
    entries: [
      {
        granularity: 'clip',
        kind: 'added',
        target: 'clip-1',
        op: 'clip.add',
        after: { track: 'track-1', at: 0, clipType: 'video' },
      },
    ],
    affectedObjectIds: ['clip-1', 'track-1'],
    ...overrides,
  };
}

function mockPreviewResult(overrides?: Partial<TimelinePreviewResult>): TimelinePreviewResult {
  return {
    diff: mockDiff(),
    fullyPreviewable: true,
    diagnostics: [],
    ...overrides,
  };
}

function mockProposal(overrides?: Partial<TimelineProposal>): TimelineProposal {
  const now = Date.now();
  return {
    id: 'proposal-1',
    source: 'test-extension',
    rationale: 'Add a clip for testing',
    state: 'pending',
    patch: mockPatch(),
    baseVersion: 5,
    previewable: true,
    previewDiff: mockDiff(),
    createdAt: now - 60000,
    updatedAt: now,
    diagnostics: [],
    ...overrides,
  };
}

interface MockProposalRuntimeOptions {
  proposals?: TimelineProposal[];
  previewResult?: TimelinePreviewResult;
  acceptResult?: TimelineDiff;
  previewError?: Error;
  acceptError?: Error;
  rejectError?: Error;
}

function createMockProposalRuntime(
  options: MockProposalRuntimeOptions = {},
): ProposalRuntime {
  const {
    proposals: initialProposals = [],
    previewResult = mockPreviewResult(),
    acceptResult = mockDiff(),
    previewError,
    acceptError,
    rejectError,
  } = options;

  let proposals = new Map<string, TimelineProposal>();
  for (const p of initialProposals) {
    proposals.set(p.id, p);
  }
  const listeners = new Set<ProposalListener>();

  function notify(proposal: TimelineProposal) {
    for (const l of listeners) {
      try { l(proposal); } catch { /* silent */ }
    }
  }

  return {
    subscribe(listener: ProposalListener): DisposeHandle {
      listeners.add(listener);
      let disposed = false;
      return {
        dispose() {
          if (!disposed) {
            disposed = true;
            listeners.delete(listener);
          }
        },
      };
    },
    create(input) {
      const p: TimelineProposal = {
        id: `proposal-${proposals.size + 1}`,
        source: input.source,
        rationale: input.rationale,
        state: 'pending',
        patch: input.patch,
        baseVersion: input.baseVersion,
        previewable: true,
        previewDiff: mockDiff(),
        createdAt: Date.now(),
        updatedAt: Date.now(),
      };
      proposals.set(p.id, p);
      notify(p);
      return p;
    },
    preview(id) {
      const p = proposals.get(id);
      if (!p) throw new Error(`Proposal ${id} not found`);
      if (previewError) throw previewError;
      const updated: TimelineProposal = {
        ...p,
        previewDiff: previewResult.diff,
        previewable: previewResult.fullyPreviewable,
        diagnostics: previewResult.diagnostics.length > 0 ? previewResult.diagnostics : undefined,
        updatedAt: Date.now(),
      };
      proposals.set(id, updated);
      notify(updated);
      return previewResult;
    },
    accept(id) {
      const p = proposals.get(id);
      if (!p) throw new Error(`Proposal ${id} not found`);
      if (acceptError) throw acceptError;
      const updated: TimelineProposal = {
        ...p,
        state: 'accepted',
        updatedAt: Date.now(),
      };
      proposals.set(id, updated);
      notify(updated);
      return acceptResult;
    },
    reject(id, _reason?) {
      const p = proposals.get(id);
      if (!p) throw new Error(`Proposal ${id} not found`);
      if (rejectError) throw rejectError;
      const updated: TimelineProposal = {
        ...p,
        state: 'rejected',
        updatedAt: Date.now(),
      };
      proposals.set(id, updated);
      notify(updated);
    },
    get(id) {
      return proposals.get(id);
    },
    list(state?) {
      const all = Array.from(proposals.values());
      if (state === undefined) return all;
      return all.filter((p) => p.state === state);
    },
    get currentVersion() {
      return 10;
    },
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('ProposalPanel', () => {
  describe('subscription and listing', () => {
    it('renders proposal count and status badges', () => {
      const runtime = createMockProposalRuntime({
        proposals: [
          mockProposal({ id: 'p1', source: 'ext.a', state: 'pending' }),
          mockProposal({ id: 'p2', source: 'ext.b', state: 'accepted' }),
        ],
      });

      render(<ProposalPanel proposalRuntime={runtime} />);

      // Check proposal count
      expect(screen.getByText('2')).toBeDefined();

      // Check pending count badge
      expect(screen.getByText('1 pending')).toBeDefined();

      // Check state badges (use getAllByText since filter toggles also show these labels)
      expect(screen.getAllByText('Pending').length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText('Accepted').length).toBeGreaterThanOrEqual(1);
    });

    it('shows source names for each proposal', () => {
      const runtime = createMockProposalRuntime({
        proposals: [
          mockProposal({ id: 'p1', source: 'com.example.foo' }),
          mockProposal({ id: 'p2', source: 'com.example.bar' }),
        ],
      });

      render(<ProposalPanel proposalRuntime={runtime} />);

      expect(screen.getByText('com.example.foo')).toBeDefined();
      expect(screen.getByText('com.example.bar')).toBeDefined();
    });

    it('displays rationale when present', () => {
      const runtime = createMockProposalRuntime({
        proposals: [
          mockProposal({
            id: 'p1',
            source: 'ext',
            rationale: 'Reorder clips for pacing',
          }),
        ],
      });

      render(<ProposalPanel proposalRuntime={runtime} />);

      expect(screen.getByText('Reorder clips for pacing')).toBeDefined();
    });

    it('shows empty state when no proposals exist', () => {
      const runtime = createMockProposalRuntime({ proposals: [] });

      render(<ProposalPanel proposalRuntime={runtime} />);

      expect(screen.getByText('No proposals.')).toBeDefined();
    });

    it('shows stale count badge when stale proposals exist', () => {
      const runtime = createMockProposalRuntime({
        proposals: [
          mockProposal({ id: 'p1', source: 'ext', state: 'stale' }),
        ],
      });

      render(<ProposalPanel proposalRuntime={runtime} />);

      expect(screen.getByText('1 stale')).toBeDefined();
      expect(screen.getByText('Stale')).toBeDefined();
    });
  });

  describe('previewability indicators', () => {
    it('shows previewable icon when previewable is true', () => {
      const runtime = createMockProposalRuntime({
        proposals: [
          mockProposal({ id: 'p1', source: 'ext', previewable: true }),
        ],
      });

      render(<ProposalPanel proposalRuntime={runtime} />);

      const panel = screen.getByRole('region', { name: 'Proposal panel' });
      const previewableIcon = panel.querySelector('[data-video-editor-proposal-previewable="true"]');
      expect(previewableIcon).toBeTruthy();
    });

    it('shows not-previewable icon when previewable is false and pending', () => {
      const runtime = createMockProposalRuntime({
        proposals: [
          mockProposal({ id: 'p1', source: 'ext', previewable: false, state: 'pending' }),
        ],
      });

      render(<ProposalPanel proposalRuntime={runtime} />);

      const panel = screen.getByRole('region', { name: 'Proposal panel' });
      const notPreviewableIcon = panel.querySelector('[data-video-editor-proposal-not-previewable="true"]');
      expect(notPreviewableIcon).toBeTruthy();
    });

    it('shows stale icon when proposal is stale', () => {
      const runtime = createMockProposalRuntime({
        proposals: [
          mockProposal({ id: 'p1', source: 'ext', state: 'stale' }),
        ],
      });

      render(<ProposalPanel proposalRuntime={runtime} />);

      const panel = screen.getByRole('region', { name: 'Proposal panel' });
      const staleIcon = panel.querySelector('[data-video-editor-proposal-stale="true"]');
      expect(staleIcon).toBeTruthy();
    });
  });

  describe('diagnostics display', () => {
    it('shows diagnostics section when expanded', () => {
      const runtime = createMockProposalRuntime({
        proposals: [
          mockProposal({
            id: 'p1',
            source: 'ext',
            diagnostics: [
              {
                severity: 'warning',
                code: 'timeline-patch/unknown-op' as const,
                message: 'Unknown operation "clip.split"',
                operationIndex: 0,
              },
            ],
          }),
        ],
      });

      render(<ProposalPanel proposalRuntime={runtime} />);

      // Expand the proposal
      const expandButton = screen.getByRole('button', { name: /ext/ });
      fireEvent.click(expandButton);

      expect(screen.getByText(/Unknown operation/)).toBeDefined();
      expect(screen.getByText('[timeline-patch/unknown-op]')).toBeDefined();
    });

    it('shows diagnostic severity icons', () => {
      const runtime = createMockProposalRuntime({
        proposals: [
          mockProposal({
            id: 'p1',
            source: 'ext',
            diagnostics: [
              {
                severity: 'error',
                code: 'timeline-patch/invalid-payload' as const,
                message: 'Invalid payload',
              },
              {
                severity: 'warning',
                code: 'timeline-patch/unknown-op' as const,
                message: 'Unknown op',
              },
              {
                severity: 'info',
                code: 'timeline-patch/deferred' as const,
                message: 'Deferred',
              },
            ],
          }),
        ],
      });

      render(<ProposalPanel proposalRuntime={runtime} />);

      const expandButton = screen.getByRole('button', { name: /ext/ });
      fireEvent.click(expandButton);

      const panel = screen.getByRole('region', { name: 'Proposal panel' });
      const diags = panel.querySelectorAll('[data-video-editor-proposal-diagnostic="true"]');
      expect(diags.length).toBe(3);
    });
  });

  describe('diff display', () => {
    it('shows diff section with entries when expanded', () => {
      const runtime = createMockProposalRuntime({
        proposals: [
          mockProposal({
            id: 'p1',
            source: 'ext',
            previewDiff: mockDiff({
              entries: [
                {
                  granularity: 'clip',
                  kind: 'added',
                  target: 'clip-abc',
                  op: 'clip.add',
                  after: { track: 'track-1', at: 0, clipType: 'video' },
                },
                {
                  granularity: 'track',
                  kind: 'modified',
                  target: 'track-1',
                  op: 'track.update',
                  before: { label: 'Old' },
                  after: { label: 'New' },
                },
              ],
              affectedObjectIds: ['clip-abc', 'track-1'],
            }),
          }),
        ],
      });

      render(<ProposalPanel proposalRuntime={runtime} />);

      const expandButton = screen.getByRole('button', { name: /ext/ });
      fireEvent.click(expandButton);

      // Should show diff section
      expect(screen.getByText(/Diff/)).toBeDefined();
      // Should show entry kinds (use getAllByText since 'Added' may appear multiple times)
      const addedElements = screen.getAllByText('Added');
      expect(addedElements.length).toBeGreaterThanOrEqual(1);
      const modifiedElements = screen.getAllByText('Modified');
      expect(modifiedElements.length).toBeGreaterThanOrEqual(1);
    });

    it('shows diff before/after sparse summaries', () => {
      const runtime = createMockProposalRuntime({
        proposals: [
          mockProposal({
            id: 'p1',
            source: 'ext',
            previewDiff: mockDiff({
              entries: [
                {
                  granularity: 'clip',
                  kind: 'modified',
                  target: 'clip-1',
                  op: 'clip.update',
                  before: { at: 0, duration: 30 },
                  after: { at: 10, duration: 60 },
                },
              ],
              affectedObjectIds: ['clip-1'],
            }),
          }),
        ],
      });

      render(<ProposalPanel proposalRuntime={runtime} />);

      const expandButton = screen.getByRole('button', { name: /ext/ });
      fireEvent.click(expandButton);

      // Should show sparse before/after
      expect(screen.getByText(/at=0, duration=30/)).toBeDefined();
      expect(screen.getByText(/at=10, duration=60/)).toBeDefined();
    });

    it('shows patch operation summary when expanded', () => {
      const runtime = createMockProposalRuntime({
        proposals: [
          mockProposal({
            id: 'p1',
            source: 'ext',
            patch: mockPatch({
              operations: [
                { op: 'clip.add', payload: { track: 't1', at: 0, clipType: 'video' } },
                { op: 'track.add', payload: { kind: 'audio' } },
              ],
            }),
          }),
        ],
      });

      render(<ProposalPanel proposalRuntime={runtime} />);

      const expandButton = screen.getByRole('button', { name: /ext/ });
      fireEvent.click(expandButton);

      expect(screen.getByText(/Patch Operations/)).toBeDefined();
      expect(screen.getByText('clip.add')).toBeDefined();
      expect(screen.getByText('track.add')).toBeDefined();
    });
  });

  describe('actions', () => {
    it('shows preview/accept/reject buttons for pending proposals', () => {
      const runtime = createMockProposalRuntime({
        proposals: [
          mockProposal({ id: 'p1', source: 'ext', state: 'pending' }),
        ],
      });

      render(<ProposalPanel proposalRuntime={runtime} />);

      const expandButton = screen.getByRole('button', { name: /ext/ });
      fireEvent.click(expandButton);

      const panel = screen.getByRole('region', { name: 'Proposal panel' });
      expect(panel.querySelector('[data-video-editor-proposal-action="preview"]')).toBeTruthy();
      expect(panel.querySelector('[data-video-editor-proposal-action="accept"]')).toBeTruthy();
      expect(panel.querySelector('[data-video-editor-proposal-action="reject"]')).toBeTruthy();
    });

    it('calls preview on the runtime when preview button clicked', () => {
      const previewSpy = vi.fn().mockReturnValue(mockPreviewResult());
      const runtime = createMockProposalRuntime({
        proposals: [mockProposal({ id: 'p1', source: 'ext', state: 'pending' })],
      });
      const origPreview = runtime.preview;
      runtime.preview = previewSpy;

      render(<ProposalPanel proposalRuntime={runtime} />);

      const expandButton = screen.getByRole('button', { name: /ext/ });
      fireEvent.click(expandButton);

      const previewBtn = screen.getByRole('button', { name: /Preview proposal from ext/ });
      fireEvent.click(previewBtn);

      expect(previewSpy).toHaveBeenCalledWith('p1');
    });

    it('calls accept on the runtime when accept button clicked', () => {
      const acceptSpy = vi.fn().mockReturnValue(mockDiff());
      const runtime = createMockProposalRuntime({
        proposals: [mockProposal({ id: 'p1', source: 'ext', state: 'pending' })],
      });
      const origAccept = runtime.accept;
      runtime.accept = acceptSpy;

      render(<ProposalPanel proposalRuntime={runtime} />);

      const expandButton = screen.getByRole('button', { name: /ext/ });
      fireEvent.click(expandButton);

      const acceptBtn = screen.getByRole('button', { name: /Accept proposal from ext/ });
      fireEvent.click(acceptBtn);

      expect(acceptSpy).toHaveBeenCalledWith('p1');
    });

    it('calls reject on the runtime when reject button clicked', () => {
      const rejectSpy = vi.fn();
      const runtime = createMockProposalRuntime({
        proposals: [mockProposal({ id: 'p1', source: 'ext', state: 'pending' })],
      });
      const origReject = runtime.reject;
      runtime.reject = rejectSpy;

      render(<ProposalPanel proposalRuntime={runtime} />);

      const expandButton = screen.getByRole('button', { name: /ext/ });
      fireEvent.click(expandButton);

      const rejectBtn = screen.getByRole('button', { name: /Reject proposal from ext/ });
      fireEvent.click(rejectBtn);

      expect(rejectSpy).toHaveBeenCalledWith('p1', 'Rejected by user');
    });

    it('shows stale message and re-preview button for stale proposals', () => {
      const runtime = createMockProposalRuntime({
        proposals: [
          mockProposal({ id: 'p1', source: 'ext', state: 'stale' }),
        ],
      });

      render(<ProposalPanel proposalRuntime={runtime} />);

      const expandButton = screen.getByRole('button', { name: /ext/ });
      fireEvent.click(expandButton);

      expect(screen.getByText(/Proposal is stale/)).toBeDefined();
      expect(screen.getByRole('button', { name: /Re-preview stale proposal from ext/ })).toBeDefined();
    });

    it('does not show action buttons for accepted proposals', () => {
      const runtime = createMockProposalRuntime({
        proposals: [
          mockProposal({ id: 'p1', source: 'ext', state: 'accepted' }),
        ],
      });

      render(<ProposalPanel proposalRuntime={runtime} />);

      const expandButton = screen.getByRole('button', { name: /ext/ });
      fireEvent.click(expandButton);

      const panel = screen.getByRole('region', { name: 'Proposal panel' });
      expect(panel.querySelector('[data-video-editor-proposal-action="accept"]')).toBeFalsy();
      expect(panel.querySelector('[data-video-editor-proposal-action="reject"]')).toBeFalsy();
    });

    it('shows error status when accept fails', () => {
      const runtime = createMockProposalRuntime({
        proposals: [mockProposal({ id: 'p1', source: 'ext', state: 'pending' })],
        acceptError: new Error('Base version mismatch'),
      });

      render(<ProposalPanel proposalRuntime={runtime} />);

      const expandButton = screen.getByRole('button', { name: /ext/ });
      fireEvent.click(expandButton);

      const acceptBtn = screen.getByRole('button', { name: /Accept proposal from ext/ });
      fireEvent.click(acceptBtn);

      expect(screen.getByText(/Base version mismatch/)).toBeDefined();
    });
  });

  describe('filtering', () => {
    it('hides accepted proposals when toggled off', () => {
      const runtime = createMockProposalRuntime({
        proposals: [
          mockProposal({ id: 'p1', source: 'ext.a', state: 'pending' }),
          mockProposal({ id: 'p2', source: 'ext.b', state: 'accepted' }),
        ],
      });

      render(<ProposalPanel proposalRuntime={runtime} />);

      // Toggle accepted off
      const acceptedToggle = screen.getByRole('button', { name: /Hide accepted proposals/ });
      fireEvent.click(acceptedToggle);

      // ext.b (accepted) should no longer be visible
      expect(screen.queryByText('ext.b')).toBeFalsy();
      // ext.a (pending) should still be visible
      expect(screen.getByText('ext.a')).toBeDefined();
    });

    it('shows rejected proposals when toggled on', () => {
      const runtime = createMockProposalRuntime({
        proposals: [
          mockProposal({ id: 'p1', source: 'ext.a', state: 'pending' }),
          mockProposal({ id: 'p2', source: 'ext.c', state: 'rejected' }),
        ],
      });

      render(<ProposalPanel proposalRuntime={runtime} />);

      // ext.c (rejected) should initially be hidden
      expect(screen.queryByText('ext.c')).toBeFalsy();

      // Toggle rejected on
      const rejectedToggle = screen.getByRole('button', { name: /Show rejected proposals/ });
      fireEvent.click(rejectedToggle);

      expect(screen.getByText('ext.c')).toBeDefined();
    });
  });

  describe('subscription reactivity', () => {
    it('updates when a new proposal is created on the runtime', () => {
      const runtime = createMockProposalRuntime({
        proposals: [mockProposal({ id: 'p1', source: 'ext.a' })],
      });

      const { rerender } = render(<ProposalPanel proposalRuntime={runtime} />);

      expect(screen.getByText('ext.a')).toBeDefined();

      // Create a new proposal through the runtime
      runtime.create({
        source: 'ext.b',
        rationale: 'New proposal',
        patch: mockPatch(),
        baseVersion: 5,
      });

      rerender(<ProposalPanel proposalRuntime={runtime} />);

      expect(screen.getByText('ext.b')).toBeDefined();
    });

    it('updates when a proposal state changes', () => {
      const runtime = createMockProposalRuntime({
        proposals: [mockProposal({ id: 'p1', source: 'ext.a', state: 'pending' })],
      });

      const { rerender } = render(<ProposalPanel proposalRuntime={runtime} />);

      expect(screen.getAllByText('Pending').length).toBeGreaterThanOrEqual(1);

      // Accept the proposal through the runtime
      runtime.accept('p1');

      rerender(<ProposalPanel proposalRuntime={runtime} />);

      expect(screen.getAllByText('Accepted').length).toBeGreaterThanOrEqual(1);
    });
  });

  describe('accessibility', () => {
    it('has region role with accessible label', () => {
      const runtime = createMockProposalRuntime({
        proposals: [mockProposal({ id: 'p1', source: 'ext' })],
      });

      render(<ProposalPanel proposalRuntime={runtime} />);

      expect(screen.getByRole('region', { name: 'Proposal panel' })).toBeDefined();
    });

    it('has aria-expanded on proposal items', () => {
      const runtime = createMockProposalRuntime({
        proposals: [mockProposal({ id: 'p1', source: 'ext' })],
      });

      render(<ProposalPanel proposalRuntime={runtime} />);

      const expandButton = screen.getByRole('button', { name: /ext/ });
      expect(expandButton.getAttribute('aria-expanded')).toBe('false');

      fireEvent.click(expandButton);
      expect(expandButton.getAttribute('aria-expanded')).toBe('true');
    });

    it('has aria-live region for status updates', () => {
      const runtime = createMockProposalRuntime({
        proposals: [mockProposal({ id: 'p1', source: 'ext', state: 'pending' })],
      });

      render(<ProposalPanel proposalRuntime={runtime} />);

      const expandButton = screen.getByRole('button', { name: /ext/ });
      fireEvent.click(expandButton);

      const previewBtn = screen.getByRole('button', { name: /Preview proposal from ext/ });
      fireEvent.click(previewBtn);

      // Should show a status message with role="status"
      const status = screen.getByRole('status');
      expect(status).toBeDefined();
      expect(status.textContent).toContain('Preview');
    });

    it('has data-testid attributes on key elements', () => {
      const runtime = createMockProposalRuntime({
        proposals: [
          mockProposal({ id: 'p1', source: 'ext', state: 'pending' }),
        ],
      });

      render(<ProposalPanel proposalRuntime={runtime} />);

      const panel = screen.getByRole('region', { name: 'Proposal panel' });
      expect(panel.getAttribute('data-video-editor-proposal-panel')).toBe('true');

      const expandButton = screen.getByRole('button', { name: /ext/ });
      fireEvent.click(expandButton);

      const proposalItem = panel.querySelector('[data-video-editor-proposal-item="true"]');
      expect(proposalItem).toBeTruthy();
      expect(proposalItem!.getAttribute('data-video-editor-proposal-state')).toBe('pending');
      expect(proposalItem!.getAttribute('data-video-editor-proposal-id')).toBe('p1');
    });
  });

  describe('close behavior', () => {
    it('calls onClose when close button clicked', () => {
      const onClose = vi.fn();
      const runtime = createMockProposalRuntime({
        proposals: [mockProposal({ id: 'p1', source: 'ext' })],
      });

      render(<ProposalPanel proposalRuntime={runtime} onClose={onClose} />);

      const closeBtn = screen.getByRole('button', { name: 'Close proposal panel' });
      fireEvent.click(closeBtn);

      expect(onClose).toHaveBeenCalledTimes(1);
    });

    it('does not render close button when onClose not provided', () => {
      const runtime = createMockProposalRuntime({
        proposals: [mockProposal({ id: 'p1', source: 'ext' })],
      });

      render(<ProposalPanel proposalRuntime={runtime} />);

      expect(screen.queryByRole('button', { name: 'Close proposal panel' })).toBeFalsy();
    });
  });
});

  describe('expanded proposal views by state', () => {
    it('shows full diff and no action buttons for accepted proposals when expanded', () => {
      const runtime = createMockProposalRuntime({
        proposals: [
          mockProposal({
            id: 'p1',
            source: 'ext',
            state: 'accepted',
            previewDiff: mockDiff({
              entries: [
                {
                  granularity: 'clip',
                  kind: 'added',
                  target: 'clip-1',
                  op: 'clip.add',
                  after: { track: 't1', at: 0, clipType: 'video' },
                },
              ],
              affectedObjectIds: ['clip-1'],
              version: 3,
            }),
          }),
        ],
      });

      render(<ProposalPanel proposalRuntime={runtime} />);

      const expandButton = screen.getByRole('button', { name: /ext/ });
      fireEvent.click(expandButton);

      // Should show accepted badge
      expect(screen.getAllByText('Accepted').length).toBeGreaterThanOrEqual(2);

      // Diff section should be present
      expect(screen.getByText(/Diff/)).toBeDefined();
      expect(screen.getByText('Added')).toBeDefined();

      // No action buttons
      const panel = screen.getByRole('region', { name: 'Proposal panel' });
      expect(panel.querySelector('[data-video-editor-proposal-action="accept"]')).toBeFalsy();
      expect(panel.querySelector('[data-video-editor-proposal-action="reject"]')).toBeFalsy();
      expect(panel.querySelector('[data-video-editor-proposal-action="preview"]')).toBeFalsy();
    });

    it('shows rejected badge and no action buttons for rejected proposals when expanded', () => {
      const runtime = createMockProposalRuntime({
        proposals: [
          mockProposal({
            id: 'p1',
            source: 'ext',
            state: 'rejected',
            rationale: 'Rejected rationale',
          }),
        ],
      });

      render(<ProposalPanel proposalRuntime={runtime} />);

      // Rejected proposals are hidden by default; toggle them on
      const rejectedToggle = screen.getByRole('button', { name: /Show rejected proposals/ });
      fireEvent.click(rejectedToggle);

      const expandButton = screen.getByRole('button', { name: /ext/ });
      fireEvent.click(expandButton);

      // Should show rejected badge
      expect(screen.getAllByText('Rejected').length).toBeGreaterThanOrEqual(2);

      // Rationale visible
      expect(screen.getByText('Rejected rationale')).toBeDefined();

      // No action buttons
      const panel = screen.getByRole('region', { name: 'Proposal panel' });
      expect(panel.querySelector('[data-video-editor-proposal-action="accept"]')).toBeFalsy();
      expect(panel.querySelector('[data-video-editor-proposal-action="reject"]')).toBeFalsy();
      expect(panel.querySelector('[data-video-editor-proposal-action="preview"]')).toBeFalsy();
    });

    it('shows stale message, clock icon, and re-preview button for stale proposals expanded', () => {
      const runtime = createMockProposalRuntime({
        proposals: [
          mockProposal({
            id: 'p1',
            source: 'ext',
            state: 'stale',
            rationale: 'Stale proposal',
            previewable: false,
          }),
        ],
      });

      render(<ProposalPanel proposalRuntime={runtime} />);

      const expandButton = screen.getByRole('button', { name: /ext/ });
      fireEvent.click(expandButton);

      // Stale message shown
      expect(screen.getByText(/Proposal is stale/)).toBeDefined();

      // Re-preview button present
      expect(screen.getByRole('button', { name: /Re-preview stale proposal from ext/ })).toBeDefined();

      // Clock icon present
      const panel = screen.getByRole('region', { name: 'Proposal panel' });
      const staleIcon = panel.querySelector('[data-video-editor-proposal-stale="true"]');
      expect(staleIcon).toBeTruthy();
    });

    it('does not show diff section for non-previewable pending proposal when expanded', () => {
      const runtime = createMockProposalRuntime({
        proposals: [
          mockProposal({
            id: 'p1',
            source: 'ext',
            state: 'pending',
            previewable: false,
            previewDiff: undefined,
            diagnostics: [
              {
                severity: 'error',
                code: 'timeline-patch/invalid-payload' as const,
                message: 'Missing required field',
              },
            ],
          }),
        ],
      });

      render(<ProposalPanel proposalRuntime={runtime} />);

      const expandButton = screen.getByRole('button', { name: /ext/ });
      fireEvent.click(expandButton);

      // Diff section should NOT be present (no previewDiff)
      expect(screen.queryByText(/^Diff/)).toBeFalsy();

      // Diagnostics should be present
      expect(screen.getByText(/Missing required field/)).toBeDefined();

      // Not-previewable icon
      const panel = screen.getByRole('region', { name: 'Proposal panel' });
      const notPreviewableIcon = panel.querySelector('[data-video-editor-proposal-not-previewable="true"]');
      expect(notPreviewableIcon).toBeTruthy();
    });

    it('shows diff section for previewable pending proposal after preview', () => {
      const runtime = createMockProposalRuntime({
        proposals: [
          mockProposal({
            id: 'p1',
            source: 'ext',
            state: 'pending',
            previewable: true,
            previewDiff: mockDiff({
              entries: [
                {
                  granularity: 'clip',
                  kind: 'modified',
                  target: 'clip-5',
                  op: 'clip.update',
                  before: { at: 0 },
                  after: { at: 10 },
                },
              ],
              affectedObjectIds: ['clip-5'],
            }),
          }),
        ],
      });

      render(<ProposalPanel proposalRuntime={runtime} />);

      const expandButton = screen.getByRole('button', { name: /ext/ });
      fireEvent.click(expandButton);

      // Diff section visible
      expect(screen.getByText(/Diff/)).toBeDefined();
      expect(screen.getByText('Modified')).toBeDefined();

      // Previewable icon
      const panel = screen.getByRole('region', { name: 'Proposal panel' });
      const previewableIcon = panel.querySelector('[data-video-editor-proposal-previewable="true"]');
      expect(previewableIcon).toBeTruthy();
    });
  });

  describe('diff rendering detail', () => {
    it('shows "more changes" button when diff has more than 5 entries', () => {
      const entries = Array.from({ length: 8 }, (_, i) => ({
        granularity: 'clip' as const,
        kind: 'added' as const,
        target: `clip-${i}`,
        op: 'clip.add' as const,
        after: { track: 't1', at: i, clipType: 'video' },
      }));

      const runtime = createMockProposalRuntime({
        proposals: [
          mockProposal({
            id: 'p1',
            source: 'ext',
            state: 'pending',
            previewDiff: mockDiff({
              entries,
              affectedObjectIds: entries.map((e) => e.target),
            }),
          }),
        ],
      });

      render(<ProposalPanel proposalRuntime={runtime} />);

      const expandButton = screen.getByRole('button', { name: /ext/ });
      fireEvent.click(expandButton);

      // Should show "+3 more changes…" (8 entries, 5 visible)
      expect(screen.getByText('+3 more changes…')).toBeDefined();

      // First 5 entries visible
      expect(screen.getByText('clip-0')).toBeDefined();
      expect(screen.getByText('clip-4')).toBeDefined();
      // 6th entry (clip-5) should not be visible yet
      expect(screen.queryByText('clip-5')).toBeFalsy();
    });

    it('expands to show all entries and "Show less" when "more changes" clicked', () => {
      const entries = Array.from({ length: 8 }, (_, i) => ({
        granularity: 'clip' as const,
        kind: 'added' as const,
        target: `clip-${i}`,
        op: 'clip.add' as const,
        after: { track: 't1', at: i, clipType: 'video' },
      }));

      const runtime = createMockProposalRuntime({
        proposals: [
          mockProposal({
            id: 'p1',
            source: 'ext',
            state: 'pending',
            previewDiff: mockDiff({
              entries,
              affectedObjectIds: entries.map((e) => e.target),
            }),
          }),
        ],
      });

      render(<ProposalPanel proposalRuntime={runtime} />);

      const expandButton = screen.getByRole('button', { name: /ext/ });
      fireEvent.click(expandButton);

      // Click "+3 more changes…"
      const moreBtn = screen.getByText('+3 more changes…');
      fireEvent.click(moreBtn);

      // Now all 8 should be visible
      expect(screen.getByText('clip-5')).toBeDefined();
      expect(screen.getByText('clip-7')).toBeDefined();

      // "Show less" should appear
      expect(screen.getByText('Show less')).toBeDefined();

      // Click "Show less" to collapse
      fireEvent.click(screen.getByText('Show less'));
      expect(screen.queryByText('clip-5')).toBeFalsy();
      expect(screen.getByText('+3 more changes…')).toBeDefined();
    });

    it('displays affected object IDs in diff', () => {
      const runtime = createMockProposalRuntime({
        proposals: [
          mockProposal({
            id: 'p1',
            source: 'ext',
            state: 'pending',
            previewDiff: mockDiff({
              entries: [
                {
                  granularity: 'clip',
                  kind: 'added',
                  target: 'clip-a',
                  op: 'clip.add',
                  after: { track: 't1', at: 0, clipType: 'video' },
                },
              ],
              affectedObjectIds: ['clip-a', 'track-1', 'asset-img'],
            }),
          }),
        ],
      });

      render(<ProposalPanel proposalRuntime={runtime} />);

      const expandButton = screen.getByRole('button', { name: /ext/ });
      fireEvent.click(expandButton);

      // Affected IDs shown
      expect(screen.getByText(/Affected:/)).toBeDefined();
      expect(screen.getByText(/clip-a, track-1, asset-img/)).toBeDefined();
    });

    it('truncates affected object IDs list beyond 5', () => {
      const ids = ['a', 'b', 'c', 'd', 'e', 'f', 'g'];
      const runtime = createMockProposalRuntime({
        proposals: [
          mockProposal({
            id: 'p1',
            source: 'ext',
            state: 'pending',
            previewDiff: mockDiff({
              entries: [
                {
                  granularity: 'clip',
                  kind: 'added',
                  target: 'clip-x',
                  op: 'clip.add',
                  after: { track: 't1', at: 0, clipType: 'video' },
                },
              ],
              affectedObjectIds: ids,
            }),
          }),
        ],
      });

      render(<ProposalPanel proposalRuntime={runtime} />);

      const expandButton = screen.getByRole('button', { name: /ext/ });
      fireEvent.click(expandButton);

      // Should show first 5 + "+2 more"
      expect(screen.getByText(/a, b, c, d, e/)).toBeDefined();
      expect(screen.getByText(/\+2 more/)).toBeDefined();
    });

    it('displays diff version when expanded', () => {
      const runtime = createMockProposalRuntime({
        proposals: [
          mockProposal({
            id: 'p1',
            source: 'ext',
            state: 'pending',
            previewDiff: mockDiff({
              entries: [
                {
                  granularity: 'clip',
                  kind: 'added',
                  target: 'clip-1',
                  op: 'clip.add',
                  after: { track: 't1', at: 0, clipType: 'video' },
                },
              ],
              version: 42,
              affectedObjectIds: ['clip-1'],
            }),
          }),
        ],
      });

      render(<ProposalPanel proposalRuntime={runtime} />);

      const expandButton = screen.getByRole('button', { name: /ext/ });
      fireEvent.click(expandButton);

      // v42 visible in the diff header
      expect(screen.getByText('v42')).toBeDefined();
    });
  });

  describe('state transitions via accept/reject', () => {
    it('accepts a pending proposal and shows accepted badge with no actions', () => {
      const runtime = createMockProposalRuntime({
        proposals: [
          mockProposal({ id: 'p1', source: 'ext', state: 'pending' }),
        ],
      });

      const { rerender } = render(<ProposalPanel proposalRuntime={runtime} />);

      const expandButton = screen.getByRole('button', { name: /ext/ });
      fireEvent.click(expandButton);

      // Accept button present before accept
      expect(screen.getByRole('button', { name: /Accept proposal from ext/ })).toBeDefined();

      // Accept via runtime
      runtime.accept('p1');
      rerender(<ProposalPanel proposalRuntime={runtime} />);

      // Now shows Accepted badge (re-expand since collapsed on rerender)
      const expandAfter = screen.getByRole('button', { name: /ext/ });
      fireEvent.click(expandAfter);

      expect(screen.getAllByText('Accepted').length).toBeGreaterThanOrEqual(2);

      // No accept/reject/preview buttons
      const panel = screen.getByRole('region', { name: 'Proposal panel' });
      expect(panel.querySelector('[data-video-editor-proposal-action="accept"]')).toBeFalsy();
      expect(panel.querySelector('[data-video-editor-proposal-action="reject"]')).toBeFalsy();
      expect(panel.querySelector('[data-video-editor-proposal-action="preview"]')).toBeFalsy();
    });

    it('rejects a pending proposal and shows rejected badge with no actions', () => {
      const runtime = createMockProposalRuntime({
        proposals: [
          mockProposal({ id: 'p1', source: 'ext', state: 'pending' }),
        ],
      });

      const { rerender } = render(<ProposalPanel proposalRuntime={runtime} />);

      const expandButton = screen.getByRole('button', { name: /ext/ });
      fireEvent.click(expandButton);

      // Reject via runtime
      runtime.reject('p1', 'User rejected');
      rerender(<ProposalPanel proposalRuntime={runtime} />);

      // Rejected hidden by default; toggle on
      const rejectedToggle = screen.getByRole('button', { name: /Show rejected proposals/ });
      fireEvent.click(rejectedToggle);

      const expandAfter = screen.getByRole('button', { name: /ext/ });
      fireEvent.click(expandAfter);

      expect(screen.getAllByText('Rejected').length).toBeGreaterThanOrEqual(2);

      // No action buttons
      const panel = screen.getByRole('region', { name: 'Proposal panel' });
      expect(panel.querySelector('[data-video-editor-proposal-action="accept"]')).toBeFalsy();
      expect(panel.querySelector('[data-video-editor-proposal-action="reject"]')).toBeFalsy();
    });

    it('shows timed status feedback after preview button click', () => {
      const runtime = createMockProposalRuntime({
        proposals: [
          mockProposal({ id: 'p1', source: 'ext', state: 'pending' }),
        ],
      });

      render(<ProposalPanel proposalRuntime={runtime} />);

      const expandButton = screen.getByRole('button', { name: /ext/ });
      fireEvent.click(expandButton);

      const previewBtn = screen.getByRole('button', { name: /Preview proposal from ext/ });
      fireEvent.click(previewBtn);

      // Status message should appear
      const status = screen.getByRole('status');
      expect(status).toBeDefined();
      expect(status.textContent).toContain('Preview');
    });

    it('shows timed status feedback after accept button click', () => {
      const runtime = createMockProposalRuntime({
        proposals: [
          mockProposal({ id: 'p1', source: 'ext', state: 'pending' }),
        ],
      });

      render(<ProposalPanel proposalRuntime={runtime} />);

      const expandButton = screen.getByRole('button', { name: /ext/ });
      fireEvent.click(expandButton);

      const acceptBtn = screen.getByRole('button', { name: /Accept proposal from ext/ });
      fireEvent.click(acceptBtn);

      // Status message should appear
      const status = screen.getByRole('status');
      expect(status).toBeDefined();
      expect(status.textContent).toContain('Accepted');
    });

    it('shows timed status feedback after reject button click', () => {
      const runtime = createMockProposalRuntime({
        proposals: [
          mockProposal({ id: 'p1', source: 'ext', state: 'pending' }),
        ],
      });

      render(<ProposalPanel proposalRuntime={runtime} />);

      const expandButton = screen.getByRole('button', { name: /ext/ });
      fireEvent.click(expandButton);

      const rejectBtn = screen.getByRole('button', { name: /Reject proposal from ext/ });
      fireEvent.click(rejectBtn);

      // Status message should appear
      const status = screen.getByRole('status');
      expect(status).toBeDefined();
      expect(status.textContent).toContain('rejected');
    });

    it('shows error status when preview throws', () => {
      const runtime = createMockProposalRuntime({
        proposals: [mockProposal({ id: 'p1', source: 'ext', state: 'pending' })],
        previewError: new Error('Stale base version'),
      });

      render(<ProposalPanel proposalRuntime={runtime} />);

      const expandButton = screen.getByRole('button', { name: /ext/ });
      fireEvent.click(expandButton);

      const previewBtn = screen.getByRole('button', { name: /Preview proposal from ext/ });
      fireEvent.click(previewBtn);

      expect(screen.getByText(/Stale base version/)).toBeDefined();

      const status = screen.getByRole('status');
      expect(status.textContent).toContain('Preview failed');
    });

    it('shows error status when reject throws', () => {
      const runtime = createMockProposalRuntime({
        proposals: [mockProposal({ id: 'p1', source: 'ext', state: 'pending' })],
        rejectError: new Error('Cannot reject accepted'),
      });

      render(<ProposalPanel proposalRuntime={runtime} />);

      const expandButton = screen.getByRole('button', { name: /ext/ });
      fireEvent.click(expandButton);

      const rejectBtn = screen.getByRole('button', { name: /Reject proposal from ext/ });
      fireEvent.click(rejectBtn);

      expect(screen.getByText(/Cannot reject accepted/)).toBeDefined();

      const status = screen.getByRole('status');
      expect(status.textContent).toContain('Reject failed');
    });
  });

  describe('mixed-state proposal list rendering', () => {
    it('renders mixed pending, accepted, stale, and rejected proposals with correct ordering', () => {
      const runtime = createMockProposalRuntime({
        proposals: [
          mockProposal({ id: 'p1', source: 'ext.a', state: 'accepted', updatedAt: 1004 }),
          mockProposal({ id: 'p2', source: 'ext.b', state: 'pending', updatedAt: 1003 }),
          mockProposal({ id: 'p3', source: 'ext.c', state: 'stale', updatedAt: 1002 }),
          mockProposal({ id: 'p4', source: 'ext.d', state: 'rejected', updatedAt: 1001 }),
          mockProposal({ id: 'p5', source: 'ext.e', state: 'pending', updatedAt: 1000 }),
        ],
      });

      render(<ProposalPanel proposalRuntime={runtime} />);

      // Show rejected
      const rejectedToggle = screen.getByRole('button', { name: /Show rejected proposals/ });
      fireEvent.click(rejectedToggle);

      // Order should be: pending, pending, stale, accepted, rejected (by state order, then newest first)
      const items = screen.getAllByRole('button', { name: /Proposal from ext\./ });
      expect(items.length).toBe(5);

      // First two should be pending (ext.b before ext.e by updatedAt)
      const firstLabel = items[0].getAttribute('aria-label') ?? '';
      expect(firstLabel).toContain('ext.b');
      const secondLabel = items[1].getAttribute('aria-label') ?? '';
      expect(secondLabel).toContain('ext.e');

      // Third should be stale (ext.c)
      const thirdLabel = items[2].getAttribute('aria-label') ?? '';
      expect(thirdLabel).toContain('ext.c');

      // Fourth should be accepted (ext.a)
      const fourthLabel = items[3].getAttribute('aria-label') ?? '';
      expect(fourthLabel).toContain('ext.a');

      // Fifth should be rejected (ext.d)
      const fifthLabel = items[4].getAttribute('aria-label') ?? '';
      expect(fifthLabel).toContain('ext.d');
    });

    it('shows correct counts for pending and stale across mixed proposals', () => {
      const runtime = createMockProposalRuntime({
        proposals: [
          mockProposal({ id: 'p1', source: 'ext.a', state: 'pending' }),
          mockProposal({ id: 'p2', source: 'ext.b', state: 'pending' }),
          mockProposal({ id: 'p3', source: 'ext.c', state: 'stale' }),
          mockProposal({ id: 'p4', source: 'ext.d', state: 'accepted' }),
        ],
      });

      render(<ProposalPanel proposalRuntime={runtime} />);

      // Total count badge: 4 (accepted filtered in by default)
      expect(screen.getByText('4')).toBeDefined();

      // Pending count: 2
      expect(screen.getByText('2 pending')).toBeDefined();

      // Stale count: 1
      expect(screen.getByText('1 stale')).toBeDefined();
    });

    it('all proposals have correct data-testid attributes', () => {
      const runtime = createMockProposalRuntime({
        proposals: [
          mockProposal({ id: 'p-a', source: 'ext.a', state: 'pending' }),
          mockProposal({ id: 'p-b', source: 'ext.b', state: 'accepted' }),
          mockProposal({ id: 'p-c', source: 'ext.c', state: 'stale' }),
        ],
      });

      render(<ProposalPanel proposalRuntime={runtime} />);

      const panel = screen.getByRole('region', { name: 'Proposal panel' });
      const items = panel.querySelectorAll('[data-video-editor-proposal-item="true"]');
      expect(items.length).toBe(3);

      const states = Array.from(items).map(
        (el) => el.getAttribute('data-video-editor-proposal-state'),
      );
      expect(states).toContain('pending');
      expect(states).toContain('accepted');
      expect(states).toContain('stale');

      const ids = Array.from(items).map(
        (el) => el.getAttribute('data-video-editor-proposal-id'),
      );
      expect(ids).toContain('p-a');
      expect(ids).toContain('p-b');
      expect(ids).toContain('p-c');
    });
  });

  describe('proposal diff rendering invariants', () => {
    it('renders diff entry kinds with correct data attributes', () => {
      const runtime = createMockProposalRuntime({
        proposals: [
          mockProposal({
            id: 'p1',
            source: 'ext',
            state: 'pending',
            previewDiff: mockDiff({
              entries: [
                {
                  granularity: 'clip',
                  kind: 'added',
                  target: 'clip-1',
                  op: 'clip.add',
                  after: { track: 't1', at: 0, clipType: 'video' },
                },
                {
                  granularity: 'track',
                  kind: 'removed',
                  target: 'track-2',
                  op: 'track.remove',
                  before: { id: 'track-2', kind: 'audio' },
                },
                {
                  granularity: 'clip',
                  kind: 'reordered',
                  target: 'clip-3',
                  op: 'clip.move',
                  before: { at: 0 },
                  after: { at: 10 },
                },
              ],
              affectedObjectIds: ['clip-1', 'track-2', 'clip-3'],
            }),
          }),
        ],
      });

      render(<ProposalPanel proposalRuntime={runtime} />);

      const expandButton = screen.getByRole('button', { name: /ext/ });
      fireEvent.click(expandButton);

      const panel = screen.getByRole('region', { name: 'Proposal panel' });
      const diffEntries = panel.querySelectorAll('[data-video-editor-proposal-diff-entry="true"]');
      expect(diffEntries.length).toBe(3);

      const kinds = Array.from(diffEntries).map(
        (el) => el.getAttribute('data-video-editor-proposal-diff-kind'),
      );
      expect(kinds).toEqual(['added', 'removed', 'reordered']);

      const granularities = Array.from(diffEntries).map(
        (el) => el.getAttribute('data-video-editor-proposal-diff-granularity'),
      );
      expect(granularities).toEqual(['clip', 'track', 'clip']);
    });

    it('shows before summary with arrow indicator and after summary with arrow indicator', () => {
      const runtime = createMockProposalRuntime({
        proposals: [
          mockProposal({
            id: 'p1',
            source: 'ext',
            state: 'pending',
            previewDiff: mockDiff({
              entries: [
                {
                  granularity: 'clip',
                  kind: 'modified',
                  target: 'clip-x',
                  op: 'clip.update',
                  before: { at: 0, duration: 30 },
                  after: { at: 15, duration: 45 },
                },
              ],
              affectedObjectIds: ['clip-x'],
            }),
          }),
        ],
      });

      render(<ProposalPanel proposalRuntime={runtime} />);

      const expandButton = screen.getByRole('button', { name: /ext/ });
      fireEvent.click(expandButton);

      // ← for before, → for after
      expect(screen.getByText(/← at=0, duration=30/)).toBeDefined();
      expect(screen.getByText(/→ at=15, duration=45/)).toBeDefined();
    });

    it('does not render stale re-preview button for non-stale proposals', () => {
      const runtime = createMockProposalRuntime({
        proposals: [
          mockProposal({ id: 'p1', source: 'ext', state: 'pending' }),
        ],
      });

      render(<ProposalPanel proposalRuntime={runtime} />);

      const expandButton = screen.getByRole('button', { name: /ext/ });
      fireEvent.click(expandButton);

      expect(screen.queryByRole('button', { name: /Re-preview stale/ })).toBeFalsy();
      expect(screen.queryByText(/Proposal is stale/)).toBeFalsy();
    });
  });
