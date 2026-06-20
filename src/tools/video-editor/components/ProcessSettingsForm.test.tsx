// @vitest-environment jsdom

import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { VideoEditorProcessDescriptor } from '@/tools/video-editor/runtime/extensionSurface.ts';
import { buildProcessSpawnConfig, ProcessSettingsForm, validateProcessSettings } from './ProcessSettingsForm';

function processDescriptor(): VideoEditorProcessDescriptor {
  return {
    id: 'process.transcode',
    extensionId: 'ext.process',
    processId: 'transcode',
    label: 'Transcode process',
    spec: {
      id: 'transcode',
      label: 'Transcode process',
      protocol: 'stdio-jsonrpc',
      spawn: { command: 'ffmpeg', args: ['-version'], env: { BASE: '1' } },
      env: [
        {
          key: 'FFMPEG_PATH',
          label: 'FFmpeg path',
          required: true,
          defaultValue: '/usr/bin/ffmpeg',
          platformDefaults: { darwin: '/opt/homebrew/bin/ffmpeg' },
        },
        { key: 'CACHE_DIR', label: 'Cache directory', defaultValue: '$TMPDIR/reigh-cache' },
      ],
      operations: [],
    },
    protocol: 'stdio-jsonrpc',
    operations: [],
    availableRoutes: [],
    requiredBy: [],
    blockers: [],
    nextActions: [],
  };
}

describe('ProcessSettingsForm', () => {
  it('renders env/path settings with variable hints and platform defaults', () => {
    render(<ProcessSettingsForm process={processDescriptor()} platform="darwin" />);

    expect(screen.getByLabelText('Command')).toHaveValue('ffmpeg');
    expect(screen.getByLabelText('FFmpeg path')).toHaveValue('/opt/homebrew/bin/ffmpeg');
    expect(screen.getByText('Use CACHE_DIR from the process environment when left blank.')).toBeInTheDocument();
    expect(screen.getByLabelText('Cache directory')).toHaveAttribute('placeholder', '$TMPDIR/reigh-cache');
  });

  it('validates required settings and propagates saved settings into spawn config', () => {
    const process = processDescriptor();
    expect(validateProcessSettings(process, { command: 'ffmpeg', FFMPEG_PATH: '' }, [{ key: 'command', label: 'Command', required: true }]))
      .toEqual(['FFmpeg path is required.']);
    expect(buildProcessSpawnConfig(process, { command: '/bin/ffmpeg', FFMPEG_PATH: '/custom/ffmpeg' }, 'darwin')).toMatchObject({
      command: '/bin/ffmpeg',
      env: {
        BASE: '1',
        FFMPEG_PATH: '/custom/ffmpeg',
        CACHE_DIR: '$TMPDIR/reigh-cache',
      },
    });
  });

  it('saves settings with merged spawn config', () => {
    const onSave = vi.fn();
    render(<ProcessSettingsForm process={processDescriptor()} savedSettings={{ FFMPEG_PATH: '/saved/ffmpeg' }} onSave={onSave} />);

    fireEvent.change(screen.getByLabelText('Command'), { target: { value: '/saved/runner' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save process settings' }));

    expect(onSave).toHaveBeenCalledWith(
      expect.objectContaining({ command: '/saved/runner', FFMPEG_PATH: '/saved/ffmpeg' }),
      expect.objectContaining({
        command: '/saved/runner',
        env: expect.objectContaining({ FFMPEG_PATH: '/saved/ffmpeg' }),
      }),
    );
  });
});
