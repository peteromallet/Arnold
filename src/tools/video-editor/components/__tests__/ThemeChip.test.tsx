// @vitest-environment jsdom
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { ThemeChip } from '@/tools/video-editor/components/ThemeChip';

describe('ThemeChip (Sprint 3, SD-019 read-only)', () => {
  it('renders nothing when timeline has no theme', () => {
    const { container } = render(<ThemeChip timeline={{}} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders nothing when timeline is null', () => {
    const { container } = render(<ThemeChip timeline={null} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders Theme: <id> (not installed) when registry is empty', () => {
    render(<ThemeChip timeline={{ theme: '2rp' }} />);
    const chip = screen.getByTestId('theme-chip');
    expect(chip.getAttribute('data-theme-installed')).toBe('false');
    expect(chip.textContent).toContain('Theme: 2rp (not installed)');
  });

  it('renders Theme: <id> (no suffix) when theme is in registry', () => {
    render(
      <ThemeChip
        timeline={{ theme: '2rp' }}
        registry={{ '2rp': { id: '2rp' } }}
      />,
    );
    const chip = screen.getByTestId('theme-chip');
    expect(chip.getAttribute('data-theme-installed')).toBe('true');
    expect(chip.textContent).toContain('Theme: 2rp');
    expect(chip.textContent).not.toContain('not installed');
  });

  it('expands a JSON view on click for an installed theme', () => {
    render(
      <ThemeChip
        timeline={{
          theme: '2rp',
          theme_overrides: { visual: { canvas: { fps: 60 } } },
        }}
        registry={{ '2rp': { id: '2rp', visual: { canvas: { fps: 30, width: 1920 } } } }}
      />,
    );
    fireEvent.click(screen.getByTestId('theme-chip'));
    const json = screen.getByTestId('theme-chip-json');
    expect(json.textContent).toContain('"fps": 60');
    expect(json.textContent).toContain('"width": 1920');
  });

  it('shows a fallback message when not installed and no overrides', () => {
    render(<ThemeChip timeline={{ theme: '2rp' }} />);
    fireEvent.click(screen.getByTestId('theme-chip'));
    expect(screen.getByText(/install @banodoco\/timeline-theme-2rp/)).toBeTruthy();
  });

  it('shows raw overrides when not installed but overrides present', () => {
    render(
      <ThemeChip
        timeline={{
          theme: 'cinema-noir',
          theme_overrides: { visual: { canvas: { fps: 30 } } },
        }}
      />,
    );
    fireEvent.click(screen.getByTestId('theme-chip'));
    const json = screen.getByTestId('theme-chip-json');
    expect(json.textContent).toContain('"theme": "cinema-noir"');
    expect(json.textContent).toContain('"theme_overrides"');
  });

  it('does not expose any picker / edit form (SD-018)', () => {
    render(<ThemeChip timeline={{ theme: '2rp' }} />);
    fireEvent.click(screen.getByTestId('theme-chip'));
    // No input / select / textarea inside the dialog content.
    const inputs = document.querySelectorAll('input, select, textarea');
    expect(inputs.length).toBe(0);
  });
});
