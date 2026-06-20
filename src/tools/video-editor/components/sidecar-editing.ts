import type { ParameterDefinition, ParameterSchema } from '@/tools/video-editor/types/index.ts';
import type { SchemaFormSchema, StandardSchema } from '@/tools/video-editor/components/SchemaForm/SchemaForm';

export type SidecarWidgetSchema = SchemaFormSchema;

export interface SidecarSchemaField {
  readonly name: string;
  readonly default?: unknown;
}

export function createSchemaDefaults(schema: SidecarWidgetSchema): Record<string, unknown> {
  if (Array.isArray(schema)) {
    return schema.reduce<Record<string, unknown>>((defaults, field: ParameterDefinition) => {
      defaults[field.name] = field.default ?? fallbackForType(field.type);
      return defaults;
    }, {});
  }

  return Object.entries((schema as StandardSchema).properties).reduce<Record<string, unknown>>(
    (defaults, [name, field]) => {
      defaults[name] = field.default ?? fallbackForType(field.type);
      return defaults;
    },
    {},
  );
}

export function updateObjectField<T extends object, K extends keyof T>(
  object: T,
  key: K,
  value: T[K],
): T {
  return { ...object, [key]: value };
}

function fallbackForType(type: string): unknown {
  switch (type) {
    case 'number':
      return 0;
    case 'boolean':
      return false;
    case 'color':
      return '#000000';
    case 'select':
    case 'string':
    default:
      return '';
  }
}

export type { ParameterSchema };
