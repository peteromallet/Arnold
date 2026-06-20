import { useMemo } from 'react';
import { SchemaForm } from '@/tools/video-editor/components/SchemaForm/SchemaForm';
import { createSchemaDefaults, type SidecarWidgetSchema } from './sidecar-editing';

export interface EditableCue {
  readonly id: string;
  readonly start: number;
  readonly end: number;
  readonly text: string;
  readonly fields?: Record<string, unknown>;
}

export interface CueListEditorProps {
  cues: readonly EditableCue[];
  schema: SidecarWidgetSchema;
  onChange: (cues: EditableCue[]) => void;
  disabled?: boolean;
}

function createCue(id: string, fields: Record<string, unknown>): EditableCue {
  return { id, start: 0, end: 1, text: '', fields };
}

export function CueListEditor({ cues, schema, onChange, disabled = false }: CueListEditorProps) {
  const defaults = useMemo(() => createSchemaDefaults(schema), [schema]);

  const updateCue = (index: number, patch: Partial<EditableCue>) => {
    onChange(cues.map((cue, cueIndex) => (cueIndex === index ? { ...cue, ...patch } : cue)));
  };

  const updateCueField = (index: number, name: string, value: unknown) => {
    const cue = cues[index];
    if (!cue) return;
    updateCue(index, { fields: { ...defaults, ...(cue.fields ?? {}), [name]: value } });
  };

  return (
    <section aria-label="Cue list editor">
      {cues.length === 0 ? <p>No cues.</p> : null}
      {cues.map((cue, index) => (
        <article key={cue.id} aria-label={`Cue ${index + 1}`}>
          <label>
            Start
            <input
              aria-label={`Cue ${index + 1} start`}
              type="number"
              value={cue.start}
              disabled={disabled}
              onChange={(event) => updateCue(index, { start: Number(event.target.value) })}
            />
          </label>
          <label>
            End
            <input
              aria-label={`Cue ${index + 1} end`}
              type="number"
              value={cue.end}
              disabled={disabled}
              onChange={(event) => updateCue(index, { end: Number(event.target.value) })}
            />
          </label>
          <label>
            Text
            <textarea
              aria-label={`Cue ${index + 1} text`}
              value={cue.text}
              disabled={disabled}
              onChange={(event) => updateCue(index, { text: event.target.value })}
            />
          </label>
          <SchemaForm
            schema={schema}
            values={{ ...defaults, ...(cue.fields ?? {}) }}
            onChange={(name, value) => updateCueField(index, name, value)}
            disabled={disabled}
          />
          <button
            type="button"
            disabled={disabled}
            onClick={() => onChange(cues.filter((_, cueIndex) => cueIndex !== index))}
          >
            Remove cue
          </button>
        </article>
      ))}
      <button
        type="button"
        disabled={disabled}
        onClick={() => onChange([...cues, createCue(`cue-${cues.length + 1}`, defaults)])}
      >
        Add cue
      </button>
    </section>
  );
}
