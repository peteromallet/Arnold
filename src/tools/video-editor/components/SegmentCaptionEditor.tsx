import { useMemo } from 'react';
import { SchemaForm } from '@/tools/video-editor/components/SchemaForm/SchemaForm';
import { createSchemaDefaults, type SidecarWidgetSchema } from './sidecar-editing';

export interface EditableCaptionSegment {
  readonly id: string;
  readonly start: number;
  readonly end: number;
  readonly caption: string;
  readonly fields?: Record<string, unknown>;
}

export interface SegmentCaptionEditorProps {
  segments: readonly EditableCaptionSegment[];
  schema: SidecarWidgetSchema;
  onChange: (segments: EditableCaptionSegment[]) => void;
  disabled?: boolean;
}

function createSegment(id: string, fields: Record<string, unknown>): EditableCaptionSegment {
  return { id, start: 0, end: 1, caption: '', fields };
}

export function SegmentCaptionEditor({
  segments,
  schema,
  onChange,
  disabled = false,
}: SegmentCaptionEditorProps) {
  const defaults = useMemo(() => createSchemaDefaults(schema), [schema]);

  const updateSegment = (index: number, patch: Partial<EditableCaptionSegment>) => {
    onChange(segments.map((segment, segmentIndex) => (
      segmentIndex === index ? { ...segment, ...patch } : segment
    )));
  };

  const updateSegmentField = (index: number, name: string, value: unknown) => {
    const segment = segments[index];
    if (!segment) return;
    updateSegment(index, { fields: { ...defaults, ...(segment.fields ?? {}), [name]: value } });
  };

  return (
    <section aria-label="Segment caption editor">
      {segments.length === 0 ? <p>No caption segments.</p> : null}
      {segments.map((segment, index) => (
        <article key={segment.id} aria-label={`Segment ${index + 1}`}>
          <label>
            Start
            <input
              aria-label={`Segment ${index + 1} start`}
              type="number"
              value={segment.start}
              disabled={disabled}
              onChange={(event) => updateSegment(index, { start: Number(event.target.value) })}
            />
          </label>
          <label>
            End
            <input
              aria-label={`Segment ${index + 1} end`}
              type="number"
              value={segment.end}
              disabled={disabled}
              onChange={(event) => updateSegment(index, { end: Number(event.target.value) })}
            />
          </label>
          <label>
            Caption
            <textarea
              aria-label={`Segment ${index + 1} caption`}
              value={segment.caption}
              disabled={disabled}
              onChange={(event) => updateSegment(index, { caption: event.target.value })}
            />
          </label>
          <SchemaForm
            schema={schema}
            values={{ ...defaults, ...(segment.fields ?? {}) }}
            onChange={(name, value) => updateSegmentField(index, name, value)}
            disabled={disabled}
          />
          <button
            type="button"
            disabled={disabled}
            onClick={() => onChange(segments.filter((_, segmentIndex) => segmentIndex !== index))}
          >
            Remove segment
          </button>
        </article>
      ))}
      <button
        type="button"
        disabled={disabled}
        onClick={() => onChange([...segments, createSegment(`segment-${segments.length + 1}`, defaults)])}
      >
        Add segment
      </button>
    </section>
  );
}
