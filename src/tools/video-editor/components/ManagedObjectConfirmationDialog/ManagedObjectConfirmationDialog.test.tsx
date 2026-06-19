/**
 * Tests for ManagedObjectConfirmationDialog.
 *
 * Covers:
 * - Dialog renders with managed clip info
 * - Cancel button dismisses and prevents mutation
 * - Edit Anyway (Detach) button calls onEditAnyway
 * - Open Source button calls onOpenSource (when source map available)
 * - Open Source button hidden when no source map
 * - Contribution ID and provenance display
 * - Track kind label
 * - No warning for user-authored or already-detached clips (null managedInfo)
 * - Cancel prevents mutation callbacks
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ManagedObjectConfirmationDialog } from '@/tools/video-editor/components/ManagedObjectConfirmationDialog/ManagedObjectConfirmationDialog';
import type { ManagedObjectInfo } from '@/tools/video-editor/lib/managed-object-guard';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeClipInfo(overrides: Partial<ManagedObjectInfo> = {}): ManagedObjectInfo {
  return {
    objectId: 'clip-1',
    kind: 'clip',
    managedBy: 'ext.dsl',
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('ManagedObjectConfirmationDialog', () => {
  // ── Null / empty state ───────────────────────────────────────────

  it('renders null when managedInfo is null', () => {
    const { container } = render(
      <ManagedObjectConfirmationDialog
        open={true}
        onOpenChange={() => {}}
        managedInfo={null}
        onEditAnyway={() => {}}
        onOpenSource={() => {}}
      />,
    );
    expect(container.firstChild).toBeNull();
  });

  it('renders nothing visible when managedInfo is null (no warning for unmanaged clips)', () => {
    const onEditAnyway = vi.fn();
    render(
      <ManagedObjectConfirmationDialog
        open={true}
        onOpenChange={() => {}}
        managedInfo={null}
        onEditAnyway={onEditAnyway}
        onOpenSource={() => {}}
      />,
    );
    // Dialog should not display any content — unmanaged clips bypass the warning
    expect(screen.queryByText('Managed Clip')).toBeNull();
    expect(screen.queryByText('Managed Track')).toBeNull();
  });

  // ── Basic rendering ──────────────────────────────────────────────

  it('renders dialog with managed clip info', () => {
    const info = makeClipInfo();
    render(
      <ManagedObjectConfirmationDialog
        open={true}
        onOpenChange={() => {}}
        managedInfo={info}
        onEditAnyway={() => {}}
        onOpenSource={() => {}}
      />,
    );

    expect(screen.getByText('Managed Clip')).toBeTruthy();
    expect(screen.getByText(/ext\.dsl/)).toBeTruthy();
    expect(screen.getByText('Edit Anyway (Detach)')).toBeTruthy();
  });

  it('renders track kind label', () => {
    const info = makeClipInfo({ kind: 'track' });
    render(
      <ManagedObjectConfirmationDialog
        open={true}
        onOpenChange={() => {}}
        managedInfo={info}
        onEditAnyway={() => {}}
        onOpenSource={() => {}}
      />,
    );

    expect(screen.getByText('Managed Track')).toBeTruthy();
  });

  it('shows contribution ID when present', () => {
    const info = makeClipInfo({ contributionId: 'gen-abc' });
    render(
      <ManagedObjectConfirmationDialog
        open={true}
        onOpenChange={() => {}}
        managedInfo={info}
        onEditAnyway={() => {}}
        onOpenSource={() => {}}
      />,
    );

    expect(screen.getByText(/gen-abc/)).toBeTruthy();
  });

  it('shows provenance when present', () => {
    const info = makeClipInfo({ provenance: { prompt: 'a test' } });
    render(
      <ManagedObjectConfirmationDialog
        open={true}
        onOpenChange={() => {}}
        managedInfo={info}
        onEditAnyway={() => {}}
        onOpenSource={() => {}}
      />,
    );

    expect(screen.getByText(/prompt/)).toBeTruthy();
  });

  // ── Open Source button availability ──────────────────────────────

  it('hides Open Source button when no source map entry', () => {
    const info = makeClipInfo();
    render(
      <ManagedObjectConfirmationDialog
        open={true}
        onOpenChange={() => {}}
        managedInfo={info}
        onEditAnyway={() => {}}
        onOpenSource={() => {}}
      />,
    );

    expect(screen.queryByTestId('managed-object-dialog-open-source')).toBeNull();
  });

  it('shows Open Source button when source map entry exists', () => {
    const info = makeClipInfo({ sourceMapEntryId: 'sme-1' });
    render(
      <ManagedObjectConfirmationDialog
        open={true}
        onOpenChange={() => {}}
        managedInfo={info}
        onEditAnyway={() => {}}
        onOpenSource={() => {}}
      />,
    );

    expect(screen.getByTestId('managed-object-dialog-open-source')).toBeTruthy();
  });

  it('shows Open Source button when sourceMapEntryId is a non-empty string', () => {
    const info = makeClipInfo({ sourceMapEntryId: 'entry-any-value' });
    render(
      <ManagedObjectConfirmationDialog
        open={true}
        onOpenChange={() => {}}
        managedInfo={info}
        onEditAnyway={() => {}}
        onOpenSource={() => {}}
      />,
    );

    expect(screen.getByTestId('managed-object-dialog-open-source')).toBeTruthy();
    expect(screen.getByText('Open Source')).toBeTruthy();
  });

  it('Open Source button has accessible label', () => {
    const info = makeClipInfo({ sourceMapEntryId: 'sme-1' });
    render(
      <ManagedObjectConfirmationDialog
        open={true}
        onOpenChange={() => {}}
        managedInfo={info}
        onEditAnyway={() => {}}
        onOpenSource={() => {}}
      />,
    );

    const btn = screen.getByTestId('managed-object-dialog-open-source');
    expect(btn.textContent).toBe('Open Source');
  });

  // ── Cancel prevents mutation ─────────────────────────────────────

  it('closes dialog on Cancel', () => {
    const onOpenChange = vi.fn();
    const info = makeClipInfo();
    render(
      <ManagedObjectConfirmationDialog
        open={true}
        onOpenChange={onOpenChange}
        managedInfo={info}
        onEditAnyway={() => {}}
        onOpenSource={() => {}}
      />,
    );

    fireEvent.click(screen.getByText('Cancel'));
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it('does NOT call onEditAnyway when Cancel is clicked (mutation prevented)', () => {
    const onEditAnyway = vi.fn();
    const info = makeClipInfo();
    render(
      <ManagedObjectConfirmationDialog
        open={true}
        onOpenChange={() => {}}
        managedInfo={info}
        onEditAnyway={onEditAnyway}
        onOpenSource={() => {}}
      />,
    );

    fireEvent.click(screen.getByText('Cancel'));
    expect(onEditAnyway).not.toHaveBeenCalled();
  });

  it('does NOT call onOpenSource when Cancel is clicked (navigation prevented)', () => {
    const onOpenSource = vi.fn();
    const info = makeClipInfo({ sourceMapEntryId: 'sme-1' });
    render(
      <ManagedObjectConfirmationDialog
        open={true}
        onOpenChange={() => {}}
        managedInfo={info}
        onEditAnyway={() => {}}
        onOpenSource={onOpenSource}
      />,
    );

    fireEvent.click(screen.getByText('Cancel'));
    expect(onOpenSource).not.toHaveBeenCalled();
  });

  it('Cancel prevents both mutation and navigation simultaneously', () => {
    const onEditAnyway = vi.fn();
    const onOpenSource = vi.fn();
    const info = makeClipInfo({ sourceMapEntryId: 'sme-1' });
    render(
      <ManagedObjectConfirmationDialog
        open={true}
        onOpenChange={() => {}}
        managedInfo={info}
        onEditAnyway={onEditAnyway}
        onOpenSource={onOpenSource}
      />,
    );

    fireEvent.click(screen.getByText('Cancel'));
    expect(onEditAnyway).not.toHaveBeenCalled();
    expect(onOpenSource).not.toHaveBeenCalled();
  });

  it('Cancel prevents mutation when no source map is available', () => {
    const onEditAnyway = vi.fn();
    const info = makeClipInfo(); // no sourceMapEntryId
    render(
      <ManagedObjectConfirmationDialog
        open={true}
        onOpenChange={() => {}}
        managedInfo={info}
        onEditAnyway={onEditAnyway}
        onOpenSource={() => {}}
      />,
    );

    fireEvent.click(screen.getByText('Cancel'));
    expect(onEditAnyway).not.toHaveBeenCalled();
  });

  // ── Edit Anyway / Detach flow ────────────────────────────────────

  it('calls onEditAnyway when Edit Anyway (Detach) is clicked', () => {
    const onEditAnyway = vi.fn();
    const info = makeClipInfo();
    render(
      <ManagedObjectConfirmationDialog
        open={true}
        onOpenChange={() => {}}
        managedInfo={info}
        onEditAnyway={onEditAnyway}
        onOpenSource={() => {}}
      />,
    );

    fireEvent.click(screen.getByTestId('managed-object-dialog-edit-anyway'));
    expect(onEditAnyway).toHaveBeenCalledWith(info);
  });

  it('calls onEditAnyway with full managedInfo metadata for detach', () => {
    const onEditAnyway = vi.fn();
    const info = makeClipInfo({
      sourceMapEntryId: 'sme-1',
      contributionId: 'gen-1',
      provenance: { prompt: 'test' },
      generatedMeta: {
        extensionId: 'ext.dsl',
        contributionId: 'gen-1',
        generatedAt: 1700000000000,
        sourceMapEntryId: 'sme-1',
        provenance: { prompt: 'test' },
      },
    });
    render(
      <ManagedObjectConfirmationDialog
        open={true}
        onOpenChange={() => {}}
        managedInfo={info}
        onEditAnyway={onEditAnyway}
        onOpenSource={() => {}}
      />,
    );

    fireEvent.click(screen.getByTestId('managed-object-dialog-edit-anyway'));
    expect(onEditAnyway).toHaveBeenCalledWith(info);
    // Verify the full metadata is passed through for detach processing
    const calledWith = onEditAnyway.mock.calls[0][0];
    expect(calledWith.objectId).toBe('clip-1');
    expect(calledWith.managedBy).toBe('ext.dsl');
    expect(calledWith.contributionId).toBe('gen-1');
    expect(calledWith.sourceMapEntryId).toBe('sme-1');
  });

  it('closes dialog after Edit Anyway', () => {
    const onOpenChange = vi.fn();
    const info = makeClipInfo();
    render(
      <ManagedObjectConfirmationDialog
        open={true}
        onOpenChange={onOpenChange}
        managedInfo={info}
        onEditAnyway={() => {}}
        onOpenSource={() => {}}
      />,
    );

    fireEvent.click(screen.getByTestId('managed-object-dialog-edit-anyway'));
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it('Edit Anyway button is always visible regardless of source map', () => {
    // Without source map
    const infoNoSource = makeClipInfo();
    const { unmount } = render(
      <ManagedObjectConfirmationDialog
        open={true}
        onOpenChange={() => {}}
        managedInfo={infoNoSource}
        onEditAnyway={() => {}}
        onOpenSource={() => {}}
      />,
    );
    expect(screen.getByTestId('managed-object-dialog-edit-anyway')).toBeTruthy();
    unmount();

    // With source map
    const infoWithSource = makeClipInfo({ sourceMapEntryId: 'sme-1' });
    render(
      <ManagedObjectConfirmationDialog
        open={true}
        onOpenChange={() => {}}
        managedInfo={infoWithSource}
        onEditAnyway={() => {}}
        onOpenSource={() => {}}
      />,
    );
    expect(screen.getByTestId('managed-object-dialog-edit-anyway')).toBeTruthy();
  });

  // ── Open Source action ───────────────────────────────────────────

  it('calls onOpenSource when Open Source is clicked', () => {
    const onOpenSource = vi.fn();
    const info = makeClipInfo({ sourceMapEntryId: 'sme-1' });
    render(
      <ManagedObjectConfirmationDialog
        open={true}
        onOpenChange={() => {}}
        managedInfo={info}
        onEditAnyway={() => {}}
        onOpenSource={onOpenSource}
      />,
    );

    fireEvent.click(screen.getByTestId('managed-object-dialog-open-source'));
    expect(onOpenSource).toHaveBeenCalledWith(info);
  });

  it('closes dialog after Open Source', () => {
    const onOpenChange = vi.fn();
    const info = makeClipInfo({ sourceMapEntryId: 'sme-1' });
    render(
      <ManagedObjectConfirmationDialog
        open={true}
        onOpenChange={onOpenChange}
        managedInfo={info}
        onEditAnyway={() => {}}
        onOpenSource={() => {}}
      />,
    );

    fireEvent.click(screen.getByTestId('managed-object-dialog-open-source'));
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it('onOpenSource receives correct sourceMapEntryId', () => {
    const onOpenSource = vi.fn();
    const info = makeClipInfo({
      sourceMapEntryId: 'specific-entry-id',
      managedBy: 'ext.source',
    });
    render(
      <ManagedObjectConfirmationDialog
        open={true}
        onOpenChange={() => {}}
        managedInfo={info}
        onEditAnyway={() => {}}
        onOpenSource={onOpenSource}
      />,
    );

    fireEvent.click(screen.getByTestId('managed-object-dialog-open-source'));
    const calledWith = onOpenSource.mock.calls[0][0];
    expect(calledWith.sourceMapEntryId).toBe('specific-entry-id');
    expect(calledWith.managedBy).toBe('ext.source');
  });

  // ── No warning for user-authored / already-detached clips ───────

  it('dialog shows owner extension name prominently in the dialog title', () => {
    const info = makeClipInfo();
    render(
      <ManagedObjectConfirmationDialog
        open={true}
        onOpenChange={() => {}}
        managedInfo={info}
        onEditAnyway={() => {}}
        onOpenSource={() => {}}
      />,
    );

    // Title shows "Managed Clip" and the description shows the owner
    expect(screen.getByText('Managed Clip')).toBeTruthy();
    expect(screen.getByText(/ext\.dsl/)).toBeTruthy();
  });

  it('shows warning about potential overwrites', () => {
    const info = makeClipInfo();
    render(
      <ManagedObjectConfirmationDialog
        open={true}
        onOpenChange={() => {}}
        managedInfo={info}
        onEditAnyway={() => {}}
        onOpenSource={() => {}}
      />,
    );

    expect(
      screen.getByText(/Manual edits may be overwritten/),
    ).toBeTruthy();
  });

  it('dialog renders Cancel, Open Source (when mapped), and Edit Anyway buttons', () => {
    const info = makeClipInfo({ sourceMapEntryId: 'sme-1' });
    render(
      <ManagedObjectConfirmationDialog
        open={true}
        onOpenChange={() => {}}
        managedInfo={info}
        onEditAnyway={() => {}}
        onOpenSource={() => {}}
      />,
    );

    expect(screen.getByText('Cancel')).toBeTruthy();
    expect(screen.getByTestId('managed-object-dialog-open-source')).toBeTruthy();
    expect(screen.getByTestId('managed-object-dialog-edit-anyway')).toBeTruthy();
  });

  it('dialog renders only Cancel and Edit Anyway when no source map', () => {
    const info = makeClipInfo(); // no sourceMapEntryId
    render(
      <ManagedObjectConfirmationDialog
        open={true}
        onOpenChange={() => {}}
        managedInfo={info}
        onEditAnyway={() => {}}
        onOpenSource={() => {}}
      />,
    );

    expect(screen.getByText('Cancel')).toBeTruthy();
    expect(screen.queryByTestId('managed-object-dialog-open-source')).toBeNull();
    expect(screen.getByTestId('managed-object-dialog-edit-anyway')).toBeTruthy();
  });
});
