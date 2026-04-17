import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import CreateShotModal from './CreateShotModal';

const mocks = vi.hoisted(() => ({
  updateProject: vi.fn(),
  parseRatio: vi.fn(() => 1.0),
  cropImageToProjectAspectRatio: vi.fn(),
  normalizeAndPresentError: vi.fn(),
}));

vi.mock('@/shared/components/ui/input', () => ({
  Input: (props: React.ComponentProps<'input'>) => <input {...props} />,
}));

vi.mock('@/shared/components/ui/primitives/label', () => ({
  Label: ({ children, ...props }: React.ComponentProps<'label'>) => <label {...props}>{children}</label>,
}));

vi.mock('@/shared/components/ui/checkbox', () => ({
  Checkbox: ({
    id,
    checked,
    onCheckedChange,
  }: {
    id?: string;
    checked?: boolean;
    onCheckedChange?: (checked: boolean) => void;
  }) => (
    <input
      id={id}
      type="checkbox"
      checked={checked}
      onChange={(e) => onCheckedChange?.(e.target.checked)}
    />
  ),
}));

vi.mock('@/shared/components/FileInput', () => ({
  FileInput: ({ onFileChange }: { onFileChange: (files: File[]) => void }) => (
    <button
      type="button"
      data-testid="mock-file-input"
      onClick={() => onFileChange([new File(['img'], 'source.png', { type: 'image/png' })])}
    >
      add-file
    </button>
  ),
}));

vi.mock('@/shared/components/GenerationControls/AspectRatioSelector', () => ({
  AspectRatioSelector: ({
    value,
    onValueChange,
  }: {
    value: string;
    onValueChange: (value: string) => void;
  }) => (
    <button type="button" data-testid="aspect-ratio-selector" onClick={() => onValueChange('1:1')}>
      aspect:{value}
    </button>
  ),
}));

vi.mock('@/shared/contexts/ProjectContext', () => ({
  useProject: () => ({ updateProject: mocks.updateProject }),
  useProjectCrudContext: () => ({ updateProject: mocks.updateProject }),
}));

vi.mock('@/shared/components/ModalContainer', () => ({
  ModalContainer: ({
    open,
    children,
    footer,
  }: {
    open: boolean;
    children: React.ReactNode;
    footer: React.ReactNode;
  }) => (open ? <div data-testid="modal">{children}{footer}</div> : null),
  ModalFooterButtons: ({
    onCancel,
    onConfirm,
    confirmText,
  }: {
    onCancel: () => void;
    onConfirm: () => void;
    confirmText: string;
  }) => (
    <div>
      <button type="button" onClick={onCancel}>Cancel</button>
      <button type="button" onClick={onConfirm}>{confirmText}</button>
    </div>
  ),
}));

vi.mock('@/shared/lib/media/aspectRatios', () => ({
  parseRatio: (...args: unknown[]) => mocks.parseRatio(...args),
}));

vi.mock('@/shared/lib/media/imageCropper', () => ({
  cropImageToProjectAspectRatio: (...args: unknown[]) => mocks.cropImageToProjectAspectRatio(...args),
}));

vi.mock('@/shared/lib/errorHandling/runtimeError', () => ({
  normalizeAndPresentError: (...args: unknown[]) => mocks.normalizeAndPresentError(...args),
}));

describe('CreateShotModal', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.cropImageToProjectAspectRatio.mockResolvedValue({
      croppedFile: new File(['cropped'], 'cropped.png', { type: 'image/png' }),
    });
  });

  it('crops uploaded files, submits default name, and optionally updates project ratio', async () => {
    const onSubmit = vi.fn(async () => {});
    const onClose = vi.fn();

    render(
      <CreateShotModal
        isOpen
        onClose={onClose}
        onSubmit={onSubmit}
        defaultShotName="Default Shot"
        projectAspectRatio="16:9"
        initialAspectRatio="1:1"
        projectId="project-1"
      />,
    );

    fireEvent.click(screen.getByTestId('mock-file-input'));
    fireEvent.click(screen.getByLabelText('Update project aspect ratio to 1:1'));
    fireEvent.click(screen.getByRole('button', { name: 'New Shot' }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledTimes(1);
    });
    const submittedFiles = onSubmit.mock.calls[0][1] as File[];
    expect(onSubmit).toHaveBeenCalledWith('Default Shot', submittedFiles, '1:1');
    expect(submittedFiles[0].name).toBe('cropped.png');
    expect(mocks.parseRatio).toHaveBeenCalledWith('1:1');
    expect(mocks.updateProject).toHaveBeenCalledWith('project-1', { aspectRatio: '1:1' });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('skips cropping when disabled and clears form on cancel', async () => {
    const onSubmit = vi.fn(async () => {});
    const onClose = vi.fn();
    render(
      <CreateShotModal
        isOpen
        onClose={onClose}
        onSubmit={onSubmit}
        cropToProjectSize={false}
        projectAspectRatio="16:9"
      />,
    );

    fireEvent.click(screen.getByTestId('mock-file-input'));
    fireEvent.change(screen.getByPlaceholderText('e.g., My Awesome Shot'), {
      target: { value: 'Manual Shot' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'New Shot' }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledTimes(1);
    });
    const submittedFiles = onSubmit.mock.calls[0][1] as File[];
    expect(submittedFiles[0].name).toBe('source.png');
    expect(mocks.cropImageToProjectAspectRatio).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(onClose).toHaveBeenCalledTimes(2);
  });
});
