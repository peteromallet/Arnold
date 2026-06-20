import { useMemo, useState } from 'react';
import { SchemaForm } from '@/tools/video-editor/components/SchemaForm/SchemaForm';
import { createSchemaDefaults, type SidecarWidgetSchema } from './sidecar-editing';

export interface BatchLabelItem {
  readonly id: string;
  readonly label: string;
  readonly selected?: boolean;
  readonly fields?: Record<string, unknown>;
}

export interface BatchLabelPanelProps {
  items: readonly BatchLabelItem[];
  schema: SidecarWidgetSchema;
  onChange: (items: BatchLabelItem[]) => void;
  disabled?: boolean;
}

export function BatchLabelPanel({ items, schema, onChange, disabled = false }: BatchLabelPanelProps) {
  const defaults = useMemo(() => createSchemaDefaults(schema), [schema]);
  const [batchValues, setBatchValues] = useState<Record<string, unknown>>(defaults);

  const updateItem = (id: string, patch: Partial<BatchLabelItem>) => {
    onChange(items.map((item) => (item.id === id ? { ...item, ...patch } : item)));
  };

  const applyBatchValues = () => {
    onChange(items.map((item) => (
      item.selected
        ? { ...item, fields: { ...defaults, ...(item.fields ?? {}), ...batchValues } }
        : item
    )));
  };

  return (
    <section aria-label="Batch label panel">
      <div aria-label="Batch label fields">
        <SchemaForm
          schema={schema}
          values={batchValues}
          onChange={(name, value) => setBatchValues((next) => ({ ...next, [name]: value }))}
          disabled={disabled}
        />
        <button type="button" disabled={disabled} onClick={applyBatchValues}>
          Apply to selected labels
        </button>
      </div>
      {items.map((item) => (
        <article key={item.id} aria-label={`Label ${item.label}`}>
          <label>
            <input
              aria-label={`Select ${item.label}`}
              type="checkbox"
              checked={Boolean(item.selected)}
              disabled={disabled}
              onChange={(event) => updateItem(item.id, { selected: event.target.checked })}
            />
            {item.label}
          </label>
          <SchemaForm
            schema={schema}
            values={{ ...defaults, ...(item.fields ?? {}) }}
            onChange={(name, value) => updateItem(item.id, {
              fields: { ...defaults, ...(item.fields ?? {}), [name]: value },
            })}
            disabled={disabled}
          />
        </article>
      ))}
    </section>
  );
}
