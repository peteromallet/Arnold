import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { __resetOverlayStackForTests, useOverlayStackApi } from '@/shared/state/overlayStack';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
} from './dropdown-menu';

describe('DropdownMenu overlay bridge', () => {
  afterEach(() => {
    cleanup();
    __resetOverlayStackForTests();
    document.body.innerHTML = '';
  });

  it('registers DropdownMenuContent with the overlay stack and layers it from stack state', () => {
    render(
      <DropdownMenu open onOpenChange={() => {}}>
        <DropdownMenuContent data-testid="menu-content">
          <DropdownMenuItem>Open</DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>,
    );

    const popup = screen.getByTestId('menu-content');
    const overlay = useOverlayStackApi().getState().getTopOverlay();

    expect(overlay?.type).toBe('menu');
    expect(overlay?.elements).toContain(popup);
    expect(popup.parentElement?.style.zIndex).toBe('1011');
    expect(popup.className).not.toContain('z-50');
  });

  it('registers DropdownMenuSubContent as its own overlay layer without numeric z-index classes', () => {
    render(
      <DropdownMenu open onOpenChange={() => {}}>
        <DropdownMenuContent>
          <DropdownMenuSub open onOpenChange={() => {}}>
            <DropdownMenuSubTrigger>More</DropdownMenuSubTrigger>
            <DropdownMenuSubContent
              data-testid="submenu-content"
              side="right"
              align="start"
              sideOffset={8}
              collisionPadding={12}
            >
              <DropdownMenuItem>Nested action</DropdownMenuItem>
            </DropdownMenuSubContent>
          </DropdownMenuSub>
        </DropdownMenuContent>
      </DropdownMenu>,
    );

    const popup = screen.getByTestId('submenu-content');
    const overlays = useOverlayStackApi().getState().overlays;

    expect(overlays.map((overlay) => overlay.type)).toEqual(['menu', 'menu-submenu']);
    expect(overlays.at(-1)?.elements).toContain(popup);
    expect(popup.className).not.toContain('z-50');
    expect(popup.parentElement?.style.zIndex).toBe('1021');
  });
});
