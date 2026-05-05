import { useCallback, useMemo } from 'react';
import { Input } from '@/shared/components/ui/input.tsx';
import { NumberInput } from '@/shared/components/ui/number-input.tsx';
import { Slider } from '@/shared/components/ui/slider.tsx';
import { Switch } from '@/shared/components/ui/switch.tsx';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select.tsx';
import { cn } from '@/shared/components/ui/contracts/cn.ts';
import type { ControlManifestEntry, ControlsManifest } from '@/tools/video-editor/sequences/controlsManifest.ts';

export interface ControlsManifestLayoutProps {
  manifest: ControlsManifest;
  values: Record<string, unknown>;
  onChange: (next: Record<string, unknown>) => void;
}

const SECONDARY_GRID_CLASS = '@container grid grid-cols-1 gap-3 @sm:grid-cols-2 @lg:grid-cols-3';

function ControlField({
  entry,
  value,
  onChange,
}: {
  entry: ControlManifestEntry;
  value: unknown;
  onChange: (next: unknown) => void;
}) {
  switch (entry.type) {
    case 'number': {
      const numeric = typeof value === 'number' && Number.isFinite(value) ? value : entry.default;
      return (
        <NumberInput
          value={numeric}
          min={entry.min}
          max={entry.max}
          step={entry.step ?? 1}
          onChange={(next) => onChange(next ?? entry.default)}
        />
      );
    }
    case 'slider': {
      const numeric = typeof value === 'number' && Number.isFinite(value) ? value : entry.default;
      return (
        <Slider
          value={[numeric]}
          min={entry.min}
          max={entry.max}
          step={entry.step ?? (entry.max - entry.min) / 100}
          onValueChange={(next) => onChange(next)}
        />
      );
    }
    case 'boolean': {
      const checked = typeof value === 'boolean' ? value : entry.default;
      return (
        <div className="flex items-center justify-between rounded-md border border-input bg-background px-3 py-2">
          <span className="text-xs text-muted-foreground">{checked ? 'Enabled' : 'Disabled'}</span>
          <Switch checked={checked} onCheckedChange={(next) => onChange(next)} />
        </div>
      );
    }
    case 'text': {
      const stringValue = typeof value === 'string' ? value : entry.default;
      return (
        <Input value={stringValue} onChange={(event) => onChange(event.target.value)} />
      );
    }
    case 'color': {
      const colorValue = typeof value === 'string' && value ? value : entry.default;
      return (
        <div className="flex items-center gap-2">
          <input
            type="color"
            value={colorValue}
            onChange={(event) => onChange(event.target.value)}
            className={cn(
              'h-10 w-14 cursor-pointer rounded-md border border-input bg-background p-1',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
            )}
          />
          <Input
            value={colorValue}
            onChange={(event) => onChange(event.target.value)}
            className="flex-1"
          />
        </div>
      );
    }
    case 'enum': {
      const stringValue = typeof value === 'string' && value ? value : entry.default;
      return (
        <Select value={stringValue} onValueChange={(next) => onChange(next)}>
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {entry.options.map((option) => (
              <SelectItem key={`${entry.name}:${option}`} value={option}>
                {option}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      );
    }
  }
}

function ControlRow({
  entry,
  value,
  onChange,
}: {
  entry: ControlManifestEntry;
  value: unknown;
  onChange: (next: unknown) => void;
}) {
  return (
    <div className="space-y-1">
      <label className="text-xs font-medium text-foreground">{entry.label}</label>
      <ControlField entry={entry} value={value} onChange={onChange} />
      {entry.description && (
        <p className="text-xs text-muted-foreground">{entry.description}</p>
      )}
    </div>
  );
}

export function ControlsManifestLayout({ manifest, values, onChange }: ControlsManifestLayoutProps) {
  const setField = useCallback(
    (name: string, next: unknown) => onChange({ ...values, [name]: next }),
    [onChange, values],
  );

  const { primary, secondary } = useMemo(() => {
    const primaryList: ControlManifestEntry[] = [];
    const secondaryList: ControlManifestEntry[] = [];
    for (const entry of manifest) {
      if (entry.priority === 'primary') primaryList.push(entry);
      else secondaryList.push(entry);
    }
    return { primary: primaryList, secondary: secondaryList };
  }, [manifest]);

  if (manifest.length === 0) {
    return (
      <div className="rounded-lg border border-border bg-card/60 p-3 text-xs text-muted-foreground">
        This component declares no editable controls.
      </div>
    );
  }

  return (
    <div className="space-y-3 rounded-lg border border-border bg-card/60 p-3" data-testid="controls-manifest-layout">
      {primary.length > 0 && (
        <div className="space-y-3" data-testid="controls-manifest-primary">
          {primary.map((entry) => (
            <div key={entry.name} className="w-full" data-testid={`primary-row-${entry.name}`}>
              <ControlRow
                entry={entry}
                value={values[entry.name]}
                onChange={(next) => setField(entry.name, next)}
              />
            </div>
          ))}
        </div>
      )}
      {secondary.length > 0 && (
        <div className={SECONDARY_GRID_CLASS} data-testid="controls-manifest-secondary">
          {secondary.map((entry) => (
            <div key={entry.name} data-testid={`secondary-cell-${entry.name}`}>
              <ControlRow
                entry={entry}
                value={values[entry.name]}
                onChange={(next) => setField(entry.name, next)}
              />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
