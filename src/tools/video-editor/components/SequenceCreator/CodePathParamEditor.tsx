import { useCallback, useMemo } from 'react';
import { Input } from '@/shared/components/ui/input.tsx';
import { NumberInput } from '@/shared/components/ui/number-input.tsx';
import { Switch } from '@/shared/components/ui/switch.tsx';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select.tsx';
import { cn } from '@/shared/components/ui/contracts/cn.ts';

export interface CodePathParamEditorAsset {
  key: string;
  url: string;
  mediaType: string;
  label?: string;
}

export interface CodePathParamEditorProps {
  schemaJson: object;
  values: Record<string, unknown>;
  allowedAssetKeys?: readonly string[];
  allowedAssets?: readonly CodePathParamEditorAsset[];
  onChange: (next: Record<string, unknown>) => void;
}

type JsonSchemaProperty = {
  type?: string | string[];
  title?: string;
  description?: string;
  enum?: unknown[];
  minimum?: number;
  maximum?: number;
  multipleOf?: number;
  format?: string;
  items?: JsonSchemaProperty;
};

type JsonSchemaObject = {
  type?: string;
  properties?: Record<string, JsonSchemaProperty>;
};

const COLOR_HEX_RE = /^#[0-9a-f]{3,8}$/i;

const humanize = (key: string): string => {
  const spaced = key
    .replace(/[_-]+/g, ' ')
    .replace(/([a-z0-9])([A-Z])/g, '$1 $2')
    .replace(/\s+/g, ' ')
    .trim();
  if (!spaced) return key;
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
};

const propertyType = (prop: JsonSchemaProperty): string | undefined => {
  if (Array.isArray(prop.type)) {
    return prop.type.find((t) => t !== 'null');
  }
  return prop.type;
};

const isAssetKeyArray = (
  propertyName: string,
  prop: JsonSchemaProperty,
): boolean => {
  if (propertyName === 'imageAssetKeys' || propertyName === 'videoAssetKeys') return true;
  if (prop.items && prop.items.format === 'asset-key') return true;
  return false;
};

const looksLikeColor = (
  propertyName: string,
  prop: JsonSchemaProperty,
  value: unknown,
): boolean => {
  if (prop.format === 'color') return true;
  if (/color|colour/i.test(propertyName)) return true;
  if (typeof value === 'string' && COLOR_HEX_RE.test(value)) return true;
  return false;
};

const toNumber = (value: unknown): number | null => {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value === 'string' && value.trim() !== '') {
    const n = Number(value);
    return Number.isFinite(n) ? n : null;
  }
  return null;
};

const toString = (value: unknown): string => {
  if (typeof value === 'string') return value;
  if (value === null || value === undefined) return '';
  return String(value);
};

const toBoolean = (value: unknown): boolean => {
  if (typeof value === 'boolean') return value;
  if (typeof value === 'string') return value === 'true';
  return Boolean(value);
};

const toStringArray = (value: unknown): string[] => {
  if (Array.isArray(value)) return value.map((v) => toString(v));
  return [];
};

export function CodePathParamEditor({
  schemaJson,
  values,
  allowedAssetKeys,
  allowedAssets,
  onChange,
}: CodePathParamEditorProps) {
  const schema = schemaJson as JsonSchemaObject;
  const properties = useMemo(() => schema.properties ?? {}, [schema.properties]);
  const propertyEntries = useMemo(
    () => Object.entries(properties),
    [properties],
  );

  const assetByKey = useMemo(() => {
    const map = new Map<string, CodePathParamEditorAsset>();
    (allowedAssets ?? []).forEach((asset) => map.set(asset.key, asset));
    return map;
  }, [allowedAssets]);

  const setField = useCallback(
    (name: string, nextValue: unknown) => {
      onChange({ ...values, [name]: nextValue });
    },
    [onChange, values],
  );

  if (propertyEntries.length === 0) {
    return (
      <div className="rounded-lg border border-border bg-card/60 p-3 text-xs text-muted-foreground">
        This component has no editable parameters.
      </div>
    );
  }

  return (
    <div className="space-y-3 rounded-lg border border-border bg-card/60 p-3">
      {propertyEntries.map(([name, rawProp]) => {
        const prop: JsonSchemaProperty = rawProp ?? {};
        const label = prop.title ?? humanize(name);
        const description = prop.description;
        const value = values[name];
        const type = propertyType(prop);

        let control: JSX.Element;

        if (type === 'number' || type === 'integer') {
          const step = type === 'integer' ? 1 : prop.multipleOf ?? 0.01;
          control = (
            <NumberInput
              value={toNumber(value)}
              min={prop.minimum}
              max={prop.maximum}
              step={step}
              onChange={(next) => setField(name, next ?? 0)}
            />
          );
        } else if (type === 'boolean') {
          control = (
            <div className="flex items-center justify-between rounded-md border border-input bg-background px-3 py-2">
              <span className="text-xs text-muted-foreground">
                {toBoolean(value) ? 'Enabled' : 'Disabled'}
              </span>
              <Switch
                checked={toBoolean(value)}
                onCheckedChange={(checked) => setField(name, checked)}
              />
            </div>
          );
        } else if (type === 'string' && Array.isArray(prop.enum) && prop.enum.length > 0) {
          const stringEnum = prop.enum.map((entry) => toString(entry));
          control = (
            <Select
              value={toString(value)}
              onValueChange={(next) => setField(name, next)}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select an option" />
              </SelectTrigger>
              <SelectContent>
                {stringEnum.map((option) => (
                  <SelectItem key={`${name}:${option}`} value={option}>
                    {option}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          );
        } else if (type === 'string' && looksLikeColor(name, prop, value)) {
          const colorValue = toString(value) || '#000000';
          control = (
            <div className="flex items-center gap-2">
              <input
                type="color"
                value={colorValue}
                onChange={(event) => setField(name, event.target.value)}
                className={cn(
                  'h-10 w-14 cursor-pointer rounded-md border border-input bg-background p-1',
                  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
                )}
              />
              <Input
                value={colorValue}
                onChange={(event) => setField(name, event.target.value)}
                className="flex-1"
              />
            </div>
          );
        } else if (type === 'string') {
          control = (
            <Input
              value={toString(value)}
              onChange={(event) => setField(name, event.target.value)}
            />
          );
        } else if (type === 'array' && prop.items?.type === 'string') {
          if (isAssetKeyArray(name, prop)) {
            const selected = new Set(toStringArray(value));
            const candidates = (allowedAssets ?? []).filter((asset) => {
              if (allowedAssetKeys && !allowedAssetKeys.includes(asset.key)) return false;
              return true;
            });
            if (candidates.length === 0) {
              control = (
                <div className="rounded-md border border-input bg-background px-3 py-2 text-xs text-muted-foreground">
                  Attach images in the prompt area to pick assets here.
                </div>
              );
            } else {
              control = (
                <div className="flex flex-wrap gap-1.5">
                  {candidates.map((asset) => {
                    const isSelected = selected.has(asset.key);
                    return (
                      <button
                        key={asset.key}
                        type="button"
                        onClick={() => {
                          const nextSelected = new Set(selected);
                          if (isSelected) nextSelected.delete(asset.key);
                          else nextSelected.add(asset.key);
                          // Preserve schema order across allowed assets so
                          // re-toggles produce stable arrays for the preview.
                          const nextArray = (allowedAssets ?? [])
                            .map((a) => a.key)
                            .filter((key) => nextSelected.has(key));
                          setField(name, nextArray);
                        }}
                        className={cn(
                          'rounded-md border px-2 py-1 text-xs transition-colors',
                          isSelected
                            ? 'border-primary bg-primary/10 text-foreground'
                            : 'border-border bg-background text-muted-foreground hover:bg-muted',
                        )}
                      >
                        {asset.label ?? asset.key}
                      </button>
                    );
                  })}
                </div>
              );
            }
          } else {
            const arrayValue = toStringArray(value);
            control = (
              <Input
                value={arrayValue.join(', ')}
                onChange={(event) => {
                  const next = event.target.value
                    .split(',')
                    .map((part) => part.trim())
                    .filter((part) => part.length > 0);
                  setField(name, next);
                }}
              />
            );
          }
        } else {
          // Fallback: edit the value as JSON. Silently keep last good value
          // on parse failure so users don't lose mid-edit state.
          control = (
            <Input
              defaultValue={JSON.stringify(value ?? null)}
              onChange={(event) => {
                try {
                  const parsed: unknown = JSON.parse(event.target.value);
                  setField(name, parsed);
                } catch {
                  // ignore malformed input mid-typing
                }
              }}
            />
          );
        }

        return (
          <div key={name} className="space-y-1">
            <label className="text-xs font-medium text-foreground">{label}</label>
            {control}
            {description && (
              <p className="text-xs text-muted-foreground">{description}</p>
            )}
          </div>
        );
      })}
    </div>
  );
}
