// @vitest-environment jsdom

import * as React from 'react';
import { act, cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { __resetOverlayStackForTests, useOverlayStackApi } from '@/shared/state/overlayStack';
import { Dialog, DialogContent, DialogTitle } from './dialog';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem } from './dropdown-menu';
import { Popover, PopoverContent } from './popover';

function DialogPopoverSequenceHarness() {
  const [dialogOpen, setDialogOpen] = React.useState(false);
  const [popoverOpen, setPopoverOpen] = React.useState(false);

  React.useEffect(() => {
    dialogPopoverControls.openDialog = () => setDialogOpen(true);
    dialogPopoverControls.openPopover = () => setPopoverOpen(true);
    dialogPopoverControls.closeDialog = () => setDialogOpen(false);
    dialogPopoverControls.closePopover = () => setPopoverOpen(false);

    return () => {
      dialogPopoverControls.openDialog = undefined;
      dialogPopoverControls.openPopover = undefined;
      dialogPopoverControls.closeDialog = undefined;
      dialogPopoverControls.closePopover = undefined;
    };
  }, []);

  return (
    <>
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent data-testid="dialog-content">
          <DialogTitle>Dialog A</DialogTitle>
        </DialogContent>
      </Dialog>

      <Popover modal open={popoverOpen} onOpenChange={setPopoverOpen}>
        <PopoverContent data-testid="popover-content">Popover B</PopoverContent>
      </Popover>
    </>
  );
}

function MenuDialogSequenceHarness() {
  const [menuOpen, setMenuOpen] = React.useState(false);
  const [dialogOpen, setDialogOpen] = React.useState(false);

  React.useEffect(() => {
    menuDialogControls.openMenu = () => setMenuOpen(true);
    menuDialogControls.openDialog = () => setDialogOpen(true);
    menuDialogControls.closeMenu = () => setMenuOpen(false);
    menuDialogControls.closeDialog = () => setDialogOpen(false);

    return () => {
      menuDialogControls.openMenu = undefined;
      menuDialogControls.openDialog = undefined;
      menuDialogControls.closeMenu = undefined;
      menuDialogControls.closeDialog = undefined;
    };
  }, []);

  return (
    <>
      <DropdownMenu open={menuOpen} onOpenChange={setMenuOpen}>
        <DropdownMenuContent data-testid="menu-content">
          <DropdownMenuItem>Menu A</DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent data-testid="dialog-content">
          <DialogTitle>Dialog B</DialogTitle>
        </DialogContent>
      </Dialog>
    </>
  );
}

const dialogPopoverControls: Record<
  'openDialog' | 'openPopover' | 'closeDialog' | 'closePopover',
  (() => void) | undefined
> = {
  openDialog: undefined,
  openPopover: undefined,
  closeDialog: undefined,
  closePopover: undefined,
};

const menuDialogControls: Record<
  'openMenu' | 'openDialog' | 'closeMenu' | 'closeDialog',
  (() => void) | undefined
> = {
  openMenu: undefined,
  openDialog: undefined,
  closeMenu: undefined,
  closeDialog: undefined,
};

describe('overlay close-order sequences', () => {
  afterEach(() => {
    cleanup();
    __resetOverlayStackForTests();
    document.body.innerHTML = '';
  });

  // Note: body pointer-events are managed natively by Base UI's Dialog
  // primitive (including close-animation timing), not by our overlay stack.
  // These tests verify stack-ordering + DOM presence only; body pointer-events
  // is Base UI's responsibility alone.
  it('tracks dialog + popover stack through open A -> open B -> close A -> close B', async () => {
    render(<DialogPopoverSequenceHarness />);

    act(() => {
      dialogPopoverControls.openDialog?.();
    });
    await waitFor(() => {
      expect(screen.getByTestId('dialog-content')).toBeInTheDocument();
    });

    act(() => {
      dialogPopoverControls.openPopover?.();
    });
    await waitFor(() => {
      expect(screen.getByTestId('popover-content')).toBeInTheDocument();
    });
    expect(useOverlayStackApi().getState().overlays.map((overlay) => overlay.type)).toEqual([
      'dialog',
      'popover',
    ]);

    act(() => {
      dialogPopoverControls.closeDialog?.();
    });
    await waitFor(() => {
      expect(screen.queryByTestId('dialog-content')).toBeNull();
    });
    expect(screen.getByTestId('popover-content')).toBeInTheDocument();

    act(() => {
      dialogPopoverControls.closePopover?.();
    });
    await waitFor(() => {
      expect(screen.queryByTestId('popover-content')).toBeNull();
    });
    expect(useOverlayStackApi().getState().overlays).toHaveLength(0);
  });

  it('tracks menu + dialog stack through open A -> open B -> close A -> close B', async () => {
    render(<MenuDialogSequenceHarness />);

    act(() => {
      menuDialogControls.openMenu?.();
    });
    await waitFor(() => {
      expect(screen.getByTestId('menu-content')).toBeInTheDocument();
    });

    act(() => {
      menuDialogControls.openDialog?.();
    });
    await waitFor(() => {
      expect(screen.getByTestId('dialog-content')).toBeInTheDocument();
    });
    expect(useOverlayStackApi().getState().overlays.map((overlay) => overlay.type)).toEqual([
      'menu',
      'dialog',
    ]);

    act(() => {
      menuDialogControls.closeMenu?.();
    });
    await waitFor(() => {
      expect(screen.queryByTestId('menu-content')).toBeNull();
    });
    expect(screen.getByTestId('dialog-content')).toBeInTheDocument();

    act(() => {
      menuDialogControls.closeDialog?.();
    });
    await waitFor(() => {
      expect(screen.queryByTestId('dialog-content')).toBeNull();
    });
    expect(useOverlayStackApi().getState().overlays).toHaveLength(0);
  });
});
