// @vitest-environment jsdom
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { DiagnosticPanel } from '@/tools/video-editor/components/DiagnosticPanel/DiagnosticPanel';
import { createDiagnosticCollection } from '@reigh/editor-sdk';
import type { DiagnosticCollection, Diagnostic } from '@reigh/editor-sdk';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function seedCollection(col: DiagnosticCollection) {
  // Error from extension A, contribution X
  col.publish({
    id: 'err-1',
    severity: 'error',
    code: 'render/contribution-error',
    message: 'Render failed in slot header',
    extensionId: 'com.example.a',
    contributionId: 'contrib.x',
    sourceRange: { startLine: 10, startCol: 5, endLine: 10, endCol: 20 },
  });

  // Warning from extension A, contribution X
  col.publish({
    id: 'warn-1',
    severity: 'warning',
    code: 'lifecycle/no-renderer',
    message: 'No renderer registered for renderId "missing-renderer"',
    extensionId: 'com.example.a',
    contributionId: 'contrib.x',
  });

  // Info from extension A, contribution Y
  col.publish({
    id: 'info-1',
    severity: 'info',
    code: 'schema/unknown-type',
    message: 'Unsupported schema type "vector3"',
    extensionId: 'com.example.a',
    contributionId: 'contrib.y',
    sourceRange: { startLine: 42, startCol: 1, endLine: 42, endCol: 10 },
    detail: { schemaType: 'vector3' },
  });

  // Error from extension B, contribution Z
  col.publish({
    id: 'err-2',
    severity: 'error',
    code: 'compile/syntax-error',
    message: 'Unexpected token at line 5',
    extensionId: 'com.example.b',
    contributionId: 'contrib.z',
    sourceRange: { startLine: 5, startCol: 1, endLine: 5, endCol: 15 },
  });

  // Info with no extension (host)
  col.publish({
    id: 'info-host',
    severity: 'info',
    code: 'runtime/extension-activated',
    message: 'Extension activated successfully',
    contributionId: 'lifecycle',
  });

  // Warning with milestone
  col.publish({
    id: 'warn-milestone',
    severity: 'warning',
    code: 'runtime/contribution-kind-not-yet-bridged',
    message: 'Contribution kind "effect" is reserved for M3',
    extensionId: 'com.example.a',
    contributionId: 'future.effect',
    milestone: 'M3',
  });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('DiagnosticPanel', () => {
  describe('subscription via useSyncExternalStore', () => {
    it('renders diagnostics from the collection snapshot', () => {
      const collection = createDiagnosticCollection();
      seedCollection(collection);

      render(<DiagnosticPanel diagnosticCollection={collection} />);

      // The panel should show the total count
      expect(screen.getByText('6')).toBeDefined();

      // Expand extension com.example.a (use the aria-label to be specific)
      const extA = screen.getByRole('button', { name: /com\.example\.a/ });
      fireEvent.click(extA);

      // Should see the extension's diagnostics count (the badge next to the name)
      const extBadges = screen.getAllByText('4');
      expect(extBadges.length).toBeGreaterThanOrEqual(1);
    });

    it('updates when new diagnostics are published', () => {
      const collection = createDiagnosticCollection();
      seedCollection(collection);

      const { rerender } = render(<DiagnosticPanel diagnosticCollection={collection} />);

      // Initially 6 diagnostics
      expect(screen.getByText('6')).toBeDefined();

      // Publish a new diagnostic
      collection.publish({
        id: 'new-err',
        severity: 'error',
        code: 'test/new-error',
        message: 'A new error appeared',
        extensionId: 'com.example.c',
        contributionId: 'contrib.new',
      });

      rerender(<DiagnosticPanel diagnosticCollection={collection} />);

      // Now 7 diagnostics
      expect(screen.getByText('7')).toBeDefined();
    });

    it('updates when diagnostics are removed', () => {
      const collection = createDiagnosticCollection();
      seedCollection(collection);

      const { rerender } = render(<DiagnosticPanel diagnosticCollection={collection} />);

      expect(screen.getByText('6')).toBeDefined();

      // Remove all errors
      collection.remove((d) => d.severity === 'error');

      rerender(<DiagnosticPanel diagnosticCollection={collection} />);

      // 6 - 2 errors = 4
      expect(screen.getByText('4')).toBeDefined();
    });

    it('updates when collection is cleared', () => {
      const collection = createDiagnosticCollection();
      seedCollection(collection);

      const { rerender } = render(<DiagnosticPanel diagnosticCollection={collection} />);

      expect(screen.getByText('6')).toBeDefined();

      collection.clear();

      rerender(<DiagnosticPanel diagnosticCollection={collection} />);

      expect(screen.getByText('No diagnostics.')).toBeDefined();
    });

    it('renders provider-collected effect registry diagnostics without source-specific panel wiring', () => {
      const collection = createDiagnosticCollection();
      collection.publish({
        id: 'effect-registry-duplicate-effect',
        severity: 'warning',
        code: 'effect-registry/duplicate-effect',
        message: 'Effect "custom:glow" was replaced by a newer registry record.',
        extensionId: 'com.example.registry',
        contributionId: 'effects.custom-glow',
        detail: {
          source: 'effect-registry',
          effectId: 'custom:glow',
          ownerExtensionId: 'com.example.registry',
        },
      });

      render(<DiagnosticPanel diagnosticCollection={collection} />);

      fireEvent.click(screen.getByText('com.example.registry'));
      fireEvent.click(screen.getByText('effects.custom-glow'));

      const item = screen.getByText('Effect "custom:glow" was replaced by a newer registry record.')
        .closest('[data-video-editor-diagnostic-item]');
      expect(item).toBeTruthy();
      expect(item!.getAttribute('data-video-editor-diagnostic-code')).toBe('effect-registry/duplicate-effect');
      expect(screen.getByText(/source=effect-registry/)).toBeDefined();
      expect(screen.getByText(/effectId=custom:glow/)).toBeDefined();
    });
  });

  describe('grouping and filtering', () => {
    it('groups diagnostics by extension then contribution', () => {
      const collection = createDiagnosticCollection();
      seedCollection(collection);

      render(<DiagnosticPanel diagnosticCollection={collection} />);

      // Extensions should be visible (use role queries to avoid dropdown option collisions)
      expect(screen.getByRole('button', { name: /com\.example\.a/ })).toBeDefined();
      expect(screen.getByRole('button', { name: /com\.example\.b/ })).toBeDefined();
    });

    it('filters by severity', () => {
      const collection = createDiagnosticCollection();
      seedCollection(collection);

      render(<DiagnosticPanel diagnosticCollection={collection} />);

      // Toggle off warnings and info — only errors should remain
      const warningBtn = screen.getByRole('button', { name: /warning diagnostics/ });
      fireEvent.click(warningBtn);

      const infoBtn = screen.getByRole('button', { name: /info diagnostics/ });
      fireEvent.click(infoBtn);

      // Only 2 errors should be visible
      expect(screen.getByText('2')).toBeDefined();
    });

    it('shows empty state when severity filter excludes everything', () => {
      const collection = createDiagnosticCollection();
      seedCollection(collection);

      render(<DiagnosticPanel diagnosticCollection={collection} />);

      // Toggle off all severities
      fireEvent.click(screen.getByRole('button', { name: /error diagnostics/ }));
      fireEvent.click(screen.getByRole('button', { name: /warning diagnostics/ }));
      fireEvent.click(screen.getByRole('button', { name: /info diagnostics/ }));

      expect(screen.getByText('No diagnostics match the current filters.')).toBeDefined();
    });

    it('filters by extension via dropdown', () => {
      const collection = createDiagnosticCollection();
      seedCollection(collection);

      render(<DiagnosticPanel diagnosticCollection={collection} />);

      const select = screen.getByLabelText('Filter by extension') as HTMLSelectElement;
      fireEvent.change(select, { target: { value: 'com.example.b' } });

      // Only extension B's diagnostics should be visible — com.example.b has 1 diagnostic
      const extBButton = screen.getByRole('button', { name: /com\.example\.b/ });
      expect(extBButton).toBeDefined();
    });

    it('clear filters button restores all diagnostics', () => {
      const collection = createDiagnosticCollection();
      seedCollection(collection);

      render(<DiagnosticPanel diagnosticCollection={collection} />);

      // Apply a severity filter
      fireEvent.click(screen.getByRole('button', { name: /info diagnostics/ }));
      fireEvent.click(screen.getByRole('button', { name: /warning diagnostics/ }));

      // Should be filtered
      expect(screen.getByText('2')).toBeDefined();

      // Clear filters
      fireEvent.click(screen.getByText('Clear filters'));

      // All 6 should be back
      expect(screen.getByText('6')).toBeDefined();
    });
  });

  describe('source range display', () => {
    it('displays source ranges verbatim (1-based)', () => {
      const collection = createDiagnosticCollection();
      collection.publish({
        id: 'src-1',
        severity: 'error',
        code: 'test/source',
        message: 'Source range test',
        extensionId: 'com.example.test',
        contributionId: 'test.contrib',
        sourceRange: { startLine: 10, startCol: 5, endLine: 10, endCol: 20 },
      });

      render(<DiagnosticPanel diagnosticCollection={collection} />);

      // Expand extension
      fireEvent.click(screen.getByText('com.example.test'));

      // Expand contribution
      fireEvent.click(screen.getByText('test.contrib'));

      // Source range should be displayed verbatim: "10:5–10:20"
      const rangeEl = screen.getByText('10:5–10:20');
      expect(rangeEl).toBeDefined();
      expect(rangeEl.getAttribute('data-video-editor-diagnostic-source-range')).toBe('true');
    });

    it('displays single-position source ranges correctly', () => {
      const collection = createDiagnosticCollection();
      collection.publish({
        id: 'src-single',
        severity: 'warning',
        code: 'test/single-pos',
        message: 'Single position test',
        extensionId: 'com.example.test',
        contributionId: 'test.contrib',
        sourceRange: { startLine: 1, startCol: 1, endLine: 1, endCol: 1 },
      });

      render(<DiagnosticPanel diagnosticCollection={collection} />);

      fireEvent.click(screen.getByText('com.example.test'));
      fireEvent.click(screen.getByText('test.contrib'));

      // For a single position, format should be "1:1" not "1:1–1:1"
      expect(screen.getByText('1:1')).toBeDefined();
    });

    it('displays related ranges count when present', () => {
      const collection = createDiagnosticCollection();
      collection.publish({
        id: 'src-related',
        severity: 'error',
        code: 'test/related',
        message: 'Related ranges test',
        extensionId: 'com.example.test',
        contributionId: 'test.contrib',
        sourceRange: { startLine: 1, startCol: 1, endLine: 1, endCol: 5 },
        relatedRanges: [
          { startLine: 5, startCol: 1, endLine: 5, endCol: 10 },
          { startLine: 10, startCol: 1, endLine: 10, endCol: 3 },
        ],
      });

      render(<DiagnosticPanel diagnosticCollection={collection} />);

      fireEvent.click(screen.getByText('com.example.test'));
      fireEvent.click(screen.getByText('test.contrib'));

      expect(screen.getByText('+2 related')).toBeDefined();
    });
  });

  describe('initialFilter for fallback entry points', () => {
    it('starts filtered to specified extension when initialFilter is provided', () => {
      const collection = createDiagnosticCollection();
      seedCollection(collection);

      render(
        <DiagnosticPanel
          diagnosticCollection={collection}
          initialFilter={{ extensionId: 'com.example.b' }}
        />,
      );

      // Only com.example.b should be visible — check its expand button exists
      expect(screen.getByRole('button', { name: /com\.example\.b/ })).toBeDefined();
      // The extension filter dropdown should show com.example.b selected
      const select = screen.getByLabelText('Filter by extension') as HTMLSelectElement;
      expect(select.value).toBe('com.example.b');
    });

    it('starts filtered to specified extension and contribution', () => {
      const collection = createDiagnosticCollection();
      seedCollection(collection);

      render(
        <DiagnosticPanel
          diagnosticCollection={collection}
          initialFilter={{
            extensionId: 'com.example.a',
            contributionId: 'contrib.x',
          }}
        />,
      );

      // com.example.a + contrib.x has 2 diagnostics (1 error + 1 warning)
      // The extension com.example.a should be auto-expanded and show the contrib
      const extButton = screen.getByRole('button', { name: /com\.example\.a/ });
      expect(extButton.getAttribute('aria-expanded')).toBe('true');
    });

    it('auto-expands the filtered extension', () => {
      const collection = createDiagnosticCollection();
      seedCollection(collection);

      render(
        <DiagnosticPanel
          diagnosticCollection={collection}
          initialFilter={{ extensionId: 'com.example.a' }}
        />,
      );

      // The extension com.example.a should be expanded
      const extButton = screen.getByRole('button', { name: /com\.example\.a/ });
      expect(extButton.getAttribute('aria-expanded')).toBe('true');
    });
  });

  describe('focus and live-region behavior', () => {
    it('panel has role="region" with accessible label', () => {
      const collection = createDiagnosticCollection();

      render(<DiagnosticPanel diagnosticCollection={collection} />);

      const region = screen.getByRole('region', { name: 'Diagnostics panel' });
      expect(region).toBeDefined();
    });

    it('diagnostics list has role="log" and aria-live="polite"', () => {
      const collection = createDiagnosticCollection();
      seedCollection(collection);

      render(<DiagnosticPanel diagnosticCollection={collection} />);

      const log = screen.getByRole('log');
      expect(log).toBeDefined();
      expect(log.getAttribute('aria-live')).toBe('polite');
      expect(log.getAttribute('aria-relevant')).toBe('additions removals');
    });

    it('panel container is focusable with tabIndex=-1', () => {
      const collection = createDiagnosticCollection();

      render(<DiagnosticPanel diagnosticCollection={collection} />);

      const panel = screen.getByRole('region', { name: 'Diagnostics panel' });
      expect(panel.getAttribute('tabindex')).toBe('-1');
    });

    it('renders accessible diagnostic items with data attributes', () => {
      const collection = createDiagnosticCollection();
      collection.publish({
        id: 'a11y-test',
        severity: 'error',
        code: 'test/a11y',
        message: 'Accessibility test diagnostic',
        extensionId: 'com.example.a11y',
        contributionId: 'a11y.contrib',
      });

      render(<DiagnosticPanel diagnosticCollection={collection} />);

      fireEvent.click(screen.getByText('com.example.a11y'));
      fireEvent.click(screen.getByText('a11y.contrib'));

      const item = screen.getByText('Accessibility test diagnostic').closest('[data-video-editor-diagnostic-item]');
      expect(item).toBeTruthy();
      expect(item!.getAttribute('data-video-editor-diagnostic-severity')).toBe('error');
      expect(item!.getAttribute('data-video-editor-diagnostic-code')).toBe('test/a11y');
    });

    it('severity toggle buttons have aria-pressed state', () => {
      const collection = createDiagnosticCollection();

      render(<DiagnosticPanel diagnosticCollection={collection} />);

      const errorBtn = screen.getByRole('button', { name: /error diagnostics/ });
      expect(errorBtn.getAttribute('aria-pressed')).toBe('true');

      fireEvent.click(errorBtn);
      expect(errorBtn.getAttribute('aria-pressed')).toBe('false');
    });

    it('extension and contribution expand buttons have aria-expanded', () => {
      const collection = createDiagnosticCollection();
      seedCollection(collection);

      render(<DiagnosticPanel diagnosticCollection={collection} />);

      const extBtn = screen.getByRole('button', { name: /com\.example\.a/ });
      expect(extBtn.getAttribute('aria-expanded')).toBe('false');

      fireEvent.click(extBtn);
      expect(extBtn.getAttribute('aria-expanded')).toBe('true');
    });
  });

  describe('onClose callback', () => {
    it('calls onClose when close button is clicked', () => {
      const collection = createDiagnosticCollection();
      const onClose = vi.fn();

      render(<DiagnosticPanel diagnosticCollection={collection} onClose={onClose} />);

      const closeBtn = screen.getByLabelText('Close diagnostics panel');
      fireEvent.click(closeBtn);

      expect(onClose).toHaveBeenCalledTimes(1);
    });

    it('does not render close button when onClose is not provided', () => {
      const collection = createDiagnosticCollection();

      render(<DiagnosticPanel diagnosticCollection={collection} />);

      expect(screen.queryByLabelText('Close diagnostics panel')).toBeNull();
    });
  });

  describe('detail and milestone display', () => {
    it('renders detail fields on diagnostic items', () => {
      const collection = createDiagnosticCollection();
      collection.publish({
        id: 'detail-test',
        severity: 'info',
        code: 'test/detail',
        message: 'Detail test',
        extensionId: 'com.example.test',
        contributionId: 'test.contrib',
        detail: { key1: 'value1', key2: 42 },
      });

      render(<DiagnosticPanel diagnosticCollection={collection} />);

      fireEvent.click(screen.getByText('com.example.test'));
      fireEvent.click(screen.getByText('test.contrib'));

      // Detail should show scalar fields
      expect(screen.getByText(/key1=value1/)).toBeDefined();
      expect(screen.getByText(/key2=42/)).toBeDefined();
    });

    it('renders milestone badge', () => {
      const collection = createDiagnosticCollection();
      collection.publish({
        id: 'milestone-test',
        severity: 'warning',
        code: 'test/milestone',
        message: 'Milestone test',
        extensionId: 'com.example.test',
        contributionId: 'test.contrib',
        milestone: 'M3',
      });

      render(<DiagnosticPanel diagnosticCollection={collection} />);

      fireEvent.click(screen.getByText('com.example.test'));
      fireEvent.click(screen.getByText('test.contrib'));

      expect(screen.getByText('M3')).toBeDefined();
    });
  });

  describe('no-owner diagnostics', () => {
    it('groups diagnostics without extensionId under (no-owner)', () => {
      const collection = createDiagnosticCollection();
      collection.publish({
        id: 'no-owner-test',
        severity: 'info',
        code: 'test/no-owner',
        message: 'No owner diagnostic',
        contributionId: 'some.contrib',
      });

      render(<DiagnosticPanel diagnosticCollection={collection} />);

      expect(screen.getByText('(no-owner)')).toBeDefined();
    });
  });

  describe('data attribute on panel root', () => {
    it('sets data-video-editor-diagnostic-panel on the root element', () => {
      const collection = createDiagnosticCollection();

      render(<DiagnosticPanel diagnosticCollection={collection} />);

      const panel = document.querySelector('[data-video-editor-diagnostic-panel="true"]');
      expect(panel).toBeTruthy();
    });
  });
});

  describe('source-map stale indicators', () => {
    it('renders stale source-map badge when diagnostic clipId is in sourceMapStaleTargetIds', () => {
      const collection = createDiagnosticCollection();
      collection.publish({
        id: 'sm-diag-1',
        severity: 'warning',
        code: 'source-map/stale-entry',
        message: 'Source map entry is stale for this clip',
        extensionId: 'com.example.sm',
        contributionId: 'sm.contrib',
        detail: { clipId: 'clip-stale-1' },
      });

      render(
        <DiagnosticPanel
          diagnosticCollection={collection}
          sourceMapStaleTargetIds={new Set(['clip-stale-1'])}
        />,
      );

      fireEvent.click(screen.getByText('com.example.sm'));
      fireEvent.click(screen.getByText('sm.contrib'));

      expect(screen.getByText('Source map stale')).toBeDefined();
      const badge = document.querySelector('[data-video-editor-diagnostic-source-map-stale-badge="true"]');
      expect(badge).toBeTruthy();
      expect(badge!.textContent).toBe('Source map stale');
    });

    it('does not render stale badge when clipId is not in sourceMapStaleTargetIds', () => {
      const collection = createDiagnosticCollection();
      collection.publish({
        id: 'sm-diag-2',
        severity: 'warning',
        code: 'source-map/stale-entry',
        message: 'Source map entry is stale for this clip',
        extensionId: 'com.example.sm',
        contributionId: 'sm.contrib',
        detail: { clipId: 'clip-fresh-1' },
      });

      render(
        <DiagnosticPanel
          diagnosticCollection={collection}
          sourceMapStaleTargetIds={new Set(['clip-something-else'])}
        />,
      );

      fireEvent.click(screen.getByText('com.example.sm'));
      fireEvent.click(screen.getByText('sm.contrib'));

      expect(screen.queryByText('Source map stale')).toBeNull();
      const badge = document.querySelector('[data-video-editor-diagnostic-source-map-stale-badge="true"]');
      expect(badge).toBeNull();
    });

    it('does not render stale badge when sourceMapStaleTargetIds is not provided', () => {
      const collection = createDiagnosticCollection();
      collection.publish({
        id: 'sm-diag-3',
        severity: 'warning',
        code: 'source-map/stale-entry',
        message: 'Source map entry is stale for this clip',
        extensionId: 'com.example.sm',
        contributionId: 'sm.contrib',
        detail: { clipId: 'clip-stale-3' },
      });

      render(<DiagnosticPanel diagnosticCollection={collection} />);

      fireEvent.click(screen.getByText('com.example.sm'));
      fireEvent.click(screen.getByText('sm.contrib'));

      expect(screen.queryByText('Source map stale')).toBeNull();
    });

    it('renders stale badges for multiple diagnostics with mixed stale states', () => {
      const collection = createDiagnosticCollection();
      collection.publish({
        id: 'sm-multi-1',
        severity: 'warning',
        code: 'source-map/stale-entry',
        message: 'First stale diagnostic',
        extensionId: 'com.example.multi',
        contributionId: 'multi.contrib',
        detail: { clipId: 'clip-a' },
      });
      collection.publish({
        id: 'sm-multi-2',
        severity: 'error',
        code: 'source-map/stale-entry',
        message: 'Second stale diagnostic',
        extensionId: 'com.example.multi',
        contributionId: 'multi.contrib',
        detail: { clipId: 'clip-b' },
      });
      collection.publish({
        id: 'sm-multi-3',
        severity: 'info',
        code: 'source-map/ok',
        message: 'Third non-stale diagnostic',
        extensionId: 'com.example.multi',
        contributionId: 'multi.contrib',
        detail: { clipId: 'clip-c' },
      });

      render(
        <DiagnosticPanel
          diagnosticCollection={collection}
          sourceMapStaleTargetIds={new Set(['clip-a', 'clip-b'])}
        />,
      );

      fireEvent.click(screen.getByText('com.example.multi'));
      fireEvent.click(screen.getByText('multi.contrib'));

      const staleBadges = document.querySelectorAll('[data-video-editor-diagnostic-source-map-stale-badge="true"]');
      expect(staleBadges).toHaveLength(2);

      expect(screen.getByText('First stale diagnostic')).toBeDefined();
      expect(screen.getByText('Second stale diagnostic')).toBeDefined();
      expect(screen.getByText('Third non-stale diagnostic')).toBeDefined();
    });

    it('sets data-video-editor-diagnostic-source-map-stale attribute on diagnostic items', () => {
      const collection = createDiagnosticCollection();
      collection.publish({
        id: 'sm-attr-1',
        severity: 'warning',
        code: 'source-map/stale-entry',
        message: 'Stale entry diagnostic',
        extensionId: 'com.example.attr',
        contributionId: 'attr.contrib',
        detail: { clipId: 'clip-stale-attr' },
      });
      collection.publish({
        id: 'sm-attr-2',
        severity: 'info',
        code: 'source-map/ok',
        message: 'Fresh entry diagnostic',
        extensionId: 'com.example.attr',
        contributionId: 'attr.contrib',
        detail: { clipId: 'clip-fresh-attr' },
      });

      render(
        <DiagnosticPanel
          diagnosticCollection={collection}
          sourceMapStaleTargetIds={new Set(['clip-stale-attr'])}
        />,
      );

      fireEvent.click(screen.getByText('com.example.attr'));
      fireEvent.click(screen.getByText('attr.contrib'));

      const items = document.querySelectorAll('[data-video-editor-diagnostic-item]');
      expect(items).toHaveLength(2);

      const staleItem = document.querySelector('[data-video-editor-diagnostic-source-map-stale="true"]');
      const freshItem = document.querySelector('[data-video-editor-diagnostic-source-map-stale="false"]');

      expect(staleItem).toBeTruthy();
      expect(freshItem).toBeTruthy();
      expect(staleItem!.textContent).toContain('Stale entry diagnostic');
      expect(freshItem!.textContent).toContain('Fresh entry diagnostic');
    });

    it('does not render stale badge when diagnostic has no detail', () => {
      const collection = createDiagnosticCollection();
      collection.publish({
        id: 'sm-no-detail',
        severity: 'warning',
        code: 'source-map/generic',
        message: 'Generic diagnostic without detail',
        extensionId: 'com.example.nodetail',
        contributionId: 'nodetail.contrib',
      });

      render(
        <DiagnosticPanel
          diagnosticCollection={collection}
          sourceMapStaleTargetIds={new Set(['any-clip'])}
        />,
      );

      fireEvent.click(screen.getByText('com.example.nodetail'));
      fireEvent.click(screen.getByText('nodetail.contrib'));

      expect(screen.queryByText('Source map stale')).toBeNull();
    });

    it('does not render stale badge when detail has no clipId', () => {
      const collection = createDiagnosticCollection();
      collection.publish({
        id: 'sm-no-clipid',
        severity: 'warning',
        code: 'source-map/other',
        message: 'Diagnostic with non-clipId detail',
        extensionId: 'com.example.noclipid',
        contributionId: 'noclipid.contrib',
        detail: { otherKey: 'otherValue' },
      });

      render(
        <DiagnosticPanel
          diagnosticCollection={collection}
          sourceMapStaleTargetIds={new Set(['any-clip'])}
        />,
      );

      fireEvent.click(screen.getByText('com.example.noclipid'));
      fireEvent.click(screen.getByText('noclipid.contrib'));

      expect(screen.queryByText('Source map stale')).toBeNull();
    });
  });
