import { render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ControlsManifestLayout } from './ControlsManifestLayout.tsx';
import { AIInputModeProvider } from '@/shared/contexts/AIInputModeContext.tsx';
import type { ControlsManifest } from '@/tools/video-editor/sequences/controlsManifest.ts';

const renderWithProviders = (ui: React.ReactElement) =>
  render(<AIInputModeProvider>{ui}</AIInputModeProvider>);

const MIXED_MANIFEST: ControlsManifest = [
  { name: 'duration', label: 'Duration', priority: 'primary', type: 'number', default: 30 },
  { name: 'mode', label: 'Mode', priority: 'primary', type: 'enum', default: 'a', options: ['a', 'b'] },
  { name: 'showLabel', label: 'Show label', priority: 'secondary', type: 'boolean', default: true },
  { name: 'caption', label: 'Caption', priority: 'secondary', type: 'text', default: 'hi' },
  { name: 'tint', label: 'Tint', priority: 'secondary', type: 'color', default: '#ff00aa' },
];

describe('ControlsManifestLayout', () => {
  it('places each primary control in its own full-width row and groups secondary controls together', () => {
    renderWithProviders(
      <ControlsManifestLayout
        manifest={MIXED_MANIFEST}
        values={{}}
        onChange={vi.fn()}
      />,
    );

    const primaryGroup = screen.getByTestId('controls-manifest-primary');
    const secondaryGroup = screen.getByTestId('controls-manifest-secondary');

    // Primary: each control becomes its OWN row.
    expect(within(primaryGroup).getByTestId('primary-row-duration')).toBeTruthy();
    expect(within(primaryGroup).getByTestId('primary-row-mode')).toBeTruthy();
    expect(within(primaryGroup).queryByTestId('secondary-cell-showLabel')).toBeNull();

    // Secondary: all together in one grid container.
    expect(within(secondaryGroup).getByTestId('secondary-cell-showLabel')).toBeTruthy();
    expect(within(secondaryGroup).getByTestId('secondary-cell-caption')).toBeTruthy();
    expect(within(secondaryGroup).getByTestId('secondary-cell-tint')).toBeTruthy();
    expect(within(secondaryGroup).queryByTestId('primary-row-duration')).toBeNull();

    // Grid uses Tailwind responsive grid for 1 / 2 / 3 columns.
    expect(secondaryGroup.className).toMatch(/grid/);
    expect(secondaryGroup.className).toMatch(/grid-cols-1/);
    expect(secondaryGroup.className).toMatch(/grid-cols-2/);
    expect(secondaryGroup.className).toMatch(/grid-cols-3/);
  });

  it('renders the empty state when the manifest has no entries', () => {
    renderWithProviders(<ControlsManifestLayout manifest={[]} values={{}} onChange={vi.fn()} />);
    expect(screen.queryByTestId('controls-manifest-primary')).toBeNull();
    expect(screen.queryByTestId('controls-manifest-secondary')).toBeNull();
    expect(screen.getByText(/declares no editable controls/i)).toBeTruthy();
  });

  it('renders only the primary block when no secondary controls exist', () => {
    renderWithProviders(
      <ControlsManifestLayout
        manifest={[
          { name: 'duration', label: 'Duration', priority: 'primary', type: 'number', default: 30 },
        ]}
        values={{}}
        onChange={vi.fn()}
      />,
    );
    expect(screen.getByTestId('controls-manifest-primary')).toBeTruthy();
    expect(screen.queryByTestId('controls-manifest-secondary')).toBeNull();
  });

  it('renders only the secondary block when no primary controls exist', () => {
    renderWithProviders(
      <ControlsManifestLayout
        manifest={[
          { name: 'caption', label: 'Caption', priority: 'secondary', type: 'text', default: 'hi' },
        ]}
        values={{}}
        onChange={vi.fn()}
      />,
    );
    expect(screen.queryByTestId('controls-manifest-primary')).toBeNull();
    expect(screen.getByTestId('controls-manifest-secondary')).toBeTruthy();
  });
});
