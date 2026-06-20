// @vitest-environment jsdom

import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { BatchLabelPanel, type BatchLabelItem } from './BatchLabelPanel';
import { CueListEditor, type EditableCue } from './CueListEditor';
import { SegmentCaptionEditor, type EditableCaptionSegment } from './SegmentCaptionEditor';
import type { SidecarWidgetSchema } from './sidecar-editing';

const cueSchema: SidecarWidgetSchema = [
  { name: 'speaker', label: 'Speaker', description: 'Cue speaker', type: 'string', default: 'Host' },
  { name: 'confidence', label: 'Confidence', description: 'Cue confidence', type: 'number', default: 0.75 },
];

const labelSchema: SidecarWidgetSchema = {
  type: 'object',
  required: ['category'],
  properties: {
    category: { type: 'string', title: 'Category', default: 'review' },
    reviewed: { type: 'boolean', title: 'Reviewed', default: false },
  },
};

describe('sidecar editing widgets', () => {
  it('edits cue-list entries through structured cue state and schema fields', () => {
    const onChange = vi.fn();
    const cues: EditableCue[] = [{ id: 'cue-a', start: 1, end: 2, text: 'hello', fields: { speaker: 'A' } }];
    render(<CueListEditor cues={cues} schema={cueSchema} onChange={onChange} />);

    fireEvent.change(screen.getByLabelText('Cue 1 text'), { target: { value: 'updated cue' } });
    expect(onChange).toHaveBeenLastCalledWith([
      expect.objectContaining({ id: 'cue-a', text: 'updated cue', fields: { speaker: 'A' } }),
    ]);

    fireEvent.change(screen.getByTestId('schema-form-widget-speaker'), { target: { value: 'Narrator' } });
    expect(onChange).toHaveBeenLastCalledWith([
      expect.objectContaining({
        id: 'cue-a',
        fields: expect.objectContaining({ confidence: 0.75, speaker: 'Narrator' }),
      }),
    ]);

    fireEvent.click(screen.getByRole('button', { name: 'Add cue' }));
    expect(onChange).toHaveBeenLastCalledWith([
      cues[0],
      expect.objectContaining({ id: 'cue-2', fields: { speaker: 'Host', confidence: 0.75 } }),
    ]);
  });

  it('edits segment captions without parsing or serializing a caption file format', () => {
    const onChange = vi.fn();
    const segments: EditableCaptionSegment[] = [
      { id: 'seg-a', start: 3, end: 5, caption: 'first', fields: { speaker: 'Guest' } },
    ];
    render(<SegmentCaptionEditor segments={segments} schema={cueSchema} onChange={onChange} />);

    fireEvent.change(screen.getByLabelText('Segment 1 start'), { target: { value: '4.5' } });
    expect(onChange).toHaveBeenLastCalledWith([
      expect.objectContaining({ id: 'seg-a', start: 4.5, caption: 'first' }),
    ]);

    fireEvent.change(screen.getByLabelText('Segment 1 caption'), { target: { value: 'second caption' } });
    expect(onChange).toHaveBeenLastCalledWith([
      expect.objectContaining({ id: 'seg-a', caption: 'second caption' }),
    ]);

    fireEvent.click(screen.getByRole('button', { name: 'Remove segment' }));
    expect(onChange).toHaveBeenLastCalledWith([]);
  });

  it('applies declarative batch label fields only to selected labels', () => {
    const onChange = vi.fn();
    const items: BatchLabelItem[] = [
      { id: 'label-a', label: 'Intro', selected: true, fields: { category: 'draft' } },
      { id: 'label-b', label: 'Outro', selected: false, fields: { category: 'final' } },
    ];
    render(<BatchLabelPanel items={items} schema={labelSchema} onChange={onChange} />);

    const batchFields = screen.getByLabelText('Batch label fields');
    fireEvent.change(within(batchFields).getByTestId('schema-form-widget-category'), {
      target: { value: 'approved' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Apply to selected labels' }));

    expect(onChange).toHaveBeenLastCalledWith([
      expect.objectContaining({ id: 'label-a', fields: expect.objectContaining({ category: 'approved' }) }),
      expect.objectContaining({ id: 'label-b', fields: { category: 'final' } }),
    ]);
  });
});
