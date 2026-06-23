/**
 * Contract tests for ExtensionActivityRegion — M1 shallow placeholder.
 *
 * Covers:
 * - Renders nothing for empty statusEvents
 * - Renders status events with kind-colored badges and extension IDs
 * - Dismiss buttons call onDismiss with the correct eventId
 * - Collapsed summary shown when >3 events and isExpanded is false
 * - Timestamps rendered only when isExpanded is true
 * - Dismiss callback receives the correct eventId for each event
 * - Children-only rendering (no status events, children present)
 * - Events-plus-children mixed rendering
 * - Children rendered below status events in the DOM order
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import {
  ExtensionActivityRegion,
  type ExtensionStatusEvent,
} from '@/tools/video-editor/components/ExtensionActivityRegion';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeEvent(overrides: Partial<ExtensionStatusEvent> = {}): ExtensionStatusEvent {
  return {
    id: 'evt-1',
    extensionId: 'com.example.test',
    kind: 'info',
    message: 'Something happened.',
    timestamp: 1719000000000,
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('ExtensionActivityRegion', () => {
  // ── Empty state ────────────────────────────────────────────────────

  it('renders null when statusEvents is empty', () => {
    const onDismiss = vi.fn();
    const { container } = render(
      <ExtensionActivityRegion statusEvents={[]} onDismiss={onDismiss} />,
    );
    expect(container.firstChild).toBeNull();
    expect(onDismiss).not.toHaveBeenCalled();
  });

  // ── Basic rendering ────────────────────────────────────────────────

  it('renders a single status event with kind badge and extension ID', () => {
    const onDismiss = vi.fn();
    const event = makeEvent({ kind: 'error', extensionId: 'ext.broken' });

    render(
      <ExtensionActivityRegion statusEvents={[event]} onDismiss={onDismiss} />,
    );

    // Region root should be present.
    expect(
      screen.getByRole('region', { name: 'Extension activity' }),
    ).toBeInTheDocument();

    // Kind badge text.
    expect(screen.getByText('Error')).toBeInTheDocument();

    // Extension ID rendered.
    expect(screen.getByText('ext.broken')).toBeInTheDocument();

    // Event message.
    expect(screen.getByText(/Something happened/)).toBeInTheDocument();

    // Dismiss button exists.
    expect(
      screen.getByRole('button', { name: /Dismiss error event from ext\.broken/i }),
    ).toBeInTheDocument();
  });

  // ── Dismiss behaviour ─────────────────────────────────────────────

  it('calls onDismiss with the eventId when dismiss button is clicked', () => {
    const onDismiss = vi.fn();
    const event = makeEvent({ id: 'evt-dismiss-me', kind: 'warning' });

    render(
      <ExtensionActivityRegion statusEvents={[event]} onDismiss={onDismiss} />,
    );

    const dismissBtn = screen.getByRole('button', {
      name: /Dismiss warning event from com\.example\.test/i,
    });
    expect(dismissBtn).toBeInTheDocument();

    fireEvent.click(dismissBtn);

    expect(onDismiss).toHaveBeenCalledTimes(1);
    expect(onDismiss).toHaveBeenCalledWith('evt-dismiss-me');
  });

  it('calls onDismiss with the correct eventId for each of multiple events', () => {
    const onDismiss = vi.fn();
    const events: ExtensionStatusEvent[] = [
      makeEvent({ id: 'evt-a', kind: 'info', extensionId: 'ext.one' }),
      makeEvent({ id: 'evt-b', kind: 'error', extensionId: 'ext.two' }),
    ];

    render(
      <ExtensionActivityRegion statusEvents={events} onDismiss={onDismiss} />,
    );

    // Dismiss the second event.
    const dismissB = screen.getByRole('button', {
      name: /Dismiss error event from ext\.two/i,
    });
    fireEvent.click(dismissB);
    expect(onDismiss).toHaveBeenCalledTimes(1);
    expect(onDismiss).toHaveBeenCalledWith('evt-b');

    // Dismiss the first event.
    const dismissA = screen.getByRole('button', {
      name: /Dismiss info event from ext\.one/i,
    });
    fireEvent.click(dismissA);
    expect(onDismiss).toHaveBeenCalledTimes(2);
    expect(onDismiss).toHaveBeenCalledWith('evt-a');
  });

  // ── Collapsed summary ──────────────────────────────────────────────

  it('shows collapsed summary when >3 events and isExpanded is false', () => {
    const onDismiss = vi.fn();
    const events: ExtensionStatusEvent[] = [
      makeEvent({ id: 'e1', message: 'Event 1' }),
      makeEvent({ id: 'e2', message: 'Event 2' }),
      makeEvent({ id: 'e3', message: 'Event 3' }),
      makeEvent({ id: 'e4', message: 'Event 4' }),
      makeEvent({ id: 'e5', message: 'Event 5' }),
    ];

    render(
      <ExtensionActivityRegion
        statusEvents={events}
        onDismiss={onDismiss}
        isExpanded={false}
      />,
    );

    // Summary shows "+2 more events".
    expect(screen.getByText(/\+2 more events/)).toBeInTheDocument();

    // First 3 event messages should be visible.
    expect(screen.getByText(/Event 1/)).toBeInTheDocument();
    expect(screen.getByText(/Event 2/)).toBeInTheDocument();
    expect(screen.getByText(/Event 3/)).toBeInTheDocument();
  });

  it('shows singular "event" when only 1 extra event beyond 3', () => {
    const onDismiss = vi.fn();
    const events: ExtensionStatusEvent[] = [
      makeEvent({ id: 'e1', message: 'First' }),
      makeEvent({ id: 'e2', message: 'Second' }),
      makeEvent({ id: 'e3', message: 'Third' }),
      makeEvent({ id: 'e4', message: 'Fourth' }),
    ];

    render(
      <ExtensionActivityRegion
        statusEvents={events}
        onDismiss={onDismiss}
        isExpanded={false}
      />,
    );

    expect(screen.getByText(/\+1 more event/)).toBeInTheDocument();
    expect(screen.queryByText(/\+1 more events/)).not.toBeInTheDocument();
  });

  // ── Expanded mode ─────────────────────────────────────────────────

  it('renders timestamps when isExpanded is true', () => {
    const onDismiss = vi.fn();
    const event = makeEvent({
      id: 'evt-time',
      kind: 'success',
      timestamp: 1719000000000, // 2024-06-21T20:00:00.000Z
    });

    render(
      <ExtensionActivityRegion
        statusEvents={[event]}
        onDismiss={onDismiss}
        isExpanded={true}
      />,
    );

    // Timestamp rendered (locale-dependent, so check for time-like pattern).
    const timeText = screen.getByText(/\d{1,2}:\d{2}:\d{2}/);
    expect(timeText).toBeInTheDocument();
  });

  // ── Kind badge rendering ───────────────────────────────────────────

  it('renders correct kind badge for each severity', () => {
    const onDismiss = vi.fn();
    const events: ExtensionStatusEvent[] = [
      makeEvent({ id: 'info', kind: 'info', extensionId: 'ext.a' }),
      makeEvent({ id: 'warn', kind: 'warning', extensionId: 'ext.b' }),
      makeEvent({ id: 'err', kind: 'error', extensionId: 'ext.c' }),
      makeEvent({ id: 'ok', kind: 'success', extensionId: 'ext.d' }),
    ];

    render(
      <ExtensionActivityRegion statusEvents={events} onDismiss={onDismiss} />,
    );

    expect(screen.getByText('Info')).toBeInTheDocument();
    expect(screen.getByText('Warn')).toBeInTheDocument();
    expect(screen.getByText('Error')).toBeInTheDocument();
    expect(screen.getByText('OK')).toBeInTheDocument();
  });

  // ── Data attributes ────────────────────────────────────────────────

  it('sets data attributes on region and event containers', () => {
    const onDismiss = vi.fn();
    const event = makeEvent({ id: 'evt-attrs', kind: 'warning' });

    render(
      <ExtensionActivityRegion statusEvents={[event]} onDismiss={onDismiss} />,
    );

    const region = screen.getByRole('region', { name: 'Extension activity' });
    expect(region).toHaveAttribute('data-video-editor-activity-region', 'true');

    const eventEl = region.querySelector('[data-video-editor-activity-event="evt-attrs"]');
    expect(eventEl).not.toBeNull();
    expect(eventEl).toHaveAttribute('data-video-editor-activity-event-kind', 'warning');

    const dismissBtn = region.querySelector('[data-video-editor-activity-dismiss="evt-attrs"]');
    expect(dismissBtn).not.toBeNull();
  });

  // ── Children slot ──────────────────────────────────────────────────

  it('renders region with children when statusEvents is empty but children are provided', () => {
    const onDismiss = vi.fn();

    render(
      <ExtensionActivityRegion statusEvents={[]} onDismiss={onDismiss}>
        <div data-testid="child-panel">Panel Content</div>
      </ExtensionActivityRegion>,
    );

    // Region should be present (not null).
    const region = screen.getByRole('region', { name: 'Extension activity' });
    expect(region).toBeInTheDocument();

    // Children should be rendered.
    expect(screen.getByTestId('child-panel')).toBeInTheDocument();
    expect(screen.getByText('Panel Content')).toBeInTheDocument();

    // No status events should be visible.
    expect(
      region.querySelector('[data-video-editor-activity-event]'),
    ).toBeNull();

    // onDismiss should not have been called.
    expect(onDismiss).not.toHaveBeenCalled();

    // Children wrapper data attribute.
    expect(
      region.querySelector('[data-video-editor-activity-children="true"]'),
    ).toBeInTheDocument();
  });

  it('renders both status events and children when both are provided', () => {
    const onDismiss = vi.fn();
    const event = makeEvent({ id: 'evt-mixed', kind: 'warning', message: 'Warning event' });

    render(
      <ExtensionActivityRegion statusEvents={[event]} onDismiss={onDismiss}>
        <div data-testid="child-panel">Panel Below</div>
      </ExtensionActivityRegion>,
    );

    const region = screen.getByRole('region', { name: 'Extension activity' });
    expect(region).toBeInTheDocument();

    // Status event is rendered.
    expect(screen.getByText('Warning event')).toBeInTheDocument();
    expect(screen.getByText('Warn')).toBeInTheDocument();

    // Dismiss button works.
    const dismissBtn = screen.getByRole('button', {
      name: /Dismiss warning event from com\.example\.test/i,
    });
    expect(dismissBtn).toBeInTheDocument();

    // Children are rendered.
    expect(screen.getByTestId('child-panel')).toBeInTheDocument();
    expect(screen.getByText('Panel Below')).toBeInTheDocument();
  });

  it('renders children below status events in DOM order', () => {
    const onDismiss = vi.fn();
    const event = makeEvent({ id: 'evt-order', kind: 'info', message: 'Status message' });

    render(
      <ExtensionActivityRegion statusEvents={[event]} onDismiss={onDismiss}>
        <div data-testid="child-panel">Child content</div>
      </ExtensionActivityRegion>,
    );

    const region = screen.getByRole('region', { name: 'Extension activity' });

    // Get all direct children of the region.
    const directChildren = Array.from(region.children);

    // First child should be the status events container (event div).
    const eventEl = directChildren[0] as HTMLElement;
    expect(eventEl).toHaveAttribute('data-video-editor-activity-event', 'evt-order');

    // Last child should be the children wrapper.
    const childrenWrapper = directChildren[directChildren.length - 1] as HTMLElement;
    expect(childrenWrapper).toHaveAttribute('data-video-editor-activity-children', 'true');
    expect(childrenWrapper.querySelector('[data-testid="child-panel"]')).toBeInTheDocument();
  });

  it('preserves dismiss behavior when children are also rendered', () => {
    const onDismiss = vi.fn();
    const event = makeEvent({ id: 'evt-dismiss-with-kids', kind: 'error', message: 'Error!' });

    render(
      <ExtensionActivityRegion statusEvents={[event]} onDismiss={onDismiss}>
        <span>Some panel</span>
      </ExtensionActivityRegion>,
    );

    const dismissBtn = screen.getByRole('button', {
      name: /Dismiss error event from com\.example\.test/i,
    });
    fireEvent.click(dismissBtn);

    expect(onDismiss).toHaveBeenCalledTimes(1);
    expect(onDismiss).toHaveBeenCalledWith('evt-dismiss-with-kids');
  });

  it('renders children when multiple status events are present', () => {
    const onDismiss = vi.fn();
    const events = [
      makeEvent({ id: 'e1', kind: 'info', message: 'First' }),
      makeEvent({ id: 'e2', kind: 'warning', message: 'Second' }),
      makeEvent({ id: 'e3', kind: 'error', message: 'Third' }),
      makeEvent({ id: 'e4', kind: 'success', message: 'Fourth' }),
    ];

    render(
      <ExtensionActivityRegion statusEvents={events} onDismiss={onDismiss} isExpanded={false}>
        <div data-testid="panel">Panel with 4 events above</div>
      </ExtensionActivityRegion>,
    );

    // All 4 events rendered.
    expect(screen.getByText('First')).toBeInTheDocument();
    expect(screen.getByText('Second')).toBeInTheDocument();
    expect(screen.getByText('Third')).toBeInTheDocument();
    expect(screen.getByText('Fourth')).toBeInTheDocument();

    // Collapsed summary shown (4 > 3).
    expect(screen.getByText(/\+1 more event/)).toBeInTheDocument();

    // Children rendered.
    expect(screen.getByTestId('panel')).toBeInTheDocument();

    // Each event has a dismiss button.
    const dismissButtons = screen.getAllByRole('button');
    expect(dismissButtons).toHaveLength(4);
  });

  it('renders null when both statusEvents is empty and no children', () => {
    const onDismiss = vi.fn();
    const { container } = render(
      <ExtensionActivityRegion statusEvents={[]} onDismiss={onDismiss} />,
    );
    expect(container.firstChild).toBeNull();
    expect(onDismiss).not.toHaveBeenCalled();
  });
});
