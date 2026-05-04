import { Input } from '@/shared/components/ui/input';
import { Textarea } from '@/shared/components/ui/textarea';
import { getRegisteredClipTypeDescriptor, getSequenceDescriptorParams } from '@/tools/video-editor/clip-types/runtime';
import type { AvailableSequenceMetadata } from '@/tools/video-editor/sequences/registry';
import type { ResolvedTimelineConfig } from '@/tools/video-editor/types';

type SequenceParamEditorProps = {
  clipType?: string;
  metadata?: AvailableSequenceMetadata;
  params: Record<string, unknown> | undefined;
  registry: ResolvedTimelineConfig['registry'];
  onChange: (params: Record<string, unknown>) => void;
};

const PARAMS_WITH_TEXTAREA = new Set(['subtitle', 'caption', 'detail', 'action', 'note']);

const asAssetKeys = (value: unknown): string[] => {
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is string => typeof item === 'string');
};

type AssetKeyCount = {
  key: string;
  count: number;
};

const countAssetKeys = (keys: readonly string[]): AssetKeyCount[] => {
  const counts = new Map<string, number>();
  const orderedKeys: string[] = [];
  for (const key of keys) {
    if (!counts.has(key)) {
      orderedKeys.push(key);
      counts.set(key, 0);
    }
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  return orderedKeys.map((key) => ({ key, count: counts.get(key) ?? 0 }));
};

const setParam = (
  current: Record<string, unknown> | undefined,
  key: string,
  value: unknown,
): Record<string, unknown> => ({
  ...(current ?? {}),
  [key]: value,
});

const parseAssetKeysInput = (
  value: string,
  registry: ResolvedTimelineConfig['registry'],
): string[] => (
  value
    .split(',')
    .map((item) => item.trim())
    .filter((item) => item.length > 0 && Object.prototype.hasOwnProperty.call(registry, item))
);

export function SequenceParamEditor({
  clipType,
  metadata,
  params,
  registry,
  onChange,
}: SequenceParamEditorProps) {
  const resolvedClipType = clipType ?? metadata?.clipType;
  const descriptor = resolvedClipType
    ? getRegisteredClipTypeDescriptor(resolvedClipType)
    : undefined;
  const descriptorParams = getSequenceDescriptorParams(descriptor);
  const sequenceParams = descriptorParams.length > 0 ? descriptorParams : (metadata?.params ?? []);
  const label = descriptor?.label ?? metadata?.label ?? resolvedClipType ?? 'Sequence';
  const description = descriptor?.description ?? metadata?.description ?? 'Sequence parameters.';

  if (sequenceParams.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-amber-400/40 bg-amber-500/10 p-3 text-sm text-amber-100">
        This clip type does not expose editable sequence params in the current registry view.
      </div>
    );
  }

  return (
    <div className="space-y-3 rounded-xl border border-border bg-card/60 p-3">
      <div>
        <div className="text-sm font-medium text-foreground">{label}</div>
        <div className="text-xs text-muted-foreground">{description}</div>
      </div>

      {sequenceParams.map((param) => {
        const value = params?.[param.key] ?? param.defaultValue ?? (param.kind === 'asset-list' ? [] : '');

        if (param.kind === 'asset-list') {
          const keys = asAssetKeys(value);
          const assetKeyCounts = countAssetKeys(keys);
          const uniqueKeys = assetKeyCounts.map((entry) => entry.key);
          return (
            <div key={param.key} className="space-y-2 rounded-lg border border-border/70 bg-background/60 p-3">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="text-sm font-medium text-foreground">{param.label}</div>
                  <div className="text-xs text-muted-foreground">{param.description}</div>
                </div>
                {typeof param.maxItems === 'number' && (
                  <div className="shrink-0 text-right text-xs text-muted-foreground">
                    <div>{keys.length}/{param.maxItems} uses</div>
                    {uniqueKeys.length !== keys.length && (
                      <div>{uniqueKeys.length} asset{uniqueKeys.length === 1 ? '' : 's'}</div>
                    )}
                  </div>
                )}
              </div>
              <Input
                value={uniqueKeys.join(', ')}
                placeholder="asset-key-a, asset-key-b"
                onChange={(event) => {
                  const nextKeys = parseAssetKeysInput(event.target.value, registry);
                  onChange(setParam(params, param.key, typeof param.maxItems === 'number' ? nextKeys.slice(0, param.maxItems) : nextKeys));
                }}
              />
              {keys.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {assetKeyCounts.map(({ key, count }) => (
                    <span
                      key={key}
                      className="max-w-full truncate rounded-md border border-border/70 bg-muted px-2 py-1 text-[11px] text-muted-foreground"
                      title={registry[key]?.src ?? registry[key]?.file ?? key}
                    >
                      {key}{count > 1 ? ` x${count}` : ''}
                    </span>
                  ))}
                </div>
              )}
            </div>
          );
        }

        const stringValue = typeof value === 'string' ? value : '';
        return (
          <div key={param.key} className="space-y-2 rounded-lg border border-border/70 bg-background/60 p-3">
            <div>
              <div className="text-sm font-medium text-foreground">
                {param.label}{param.required ? ' *' : ''}
              </div>
              <div className="text-xs text-muted-foreground">{param.description}</div>
            </div>
            {PARAMS_WITH_TEXTAREA.has(param.key) ? (
              <Textarea
                value={stringValue}
                rows={3}
                onChange={(event) => onChange(setParam(params, param.key, event.target.value))}
              />
            ) : (
              <Input
                value={stringValue}
                onChange={(event) => onChange(setParam(params, param.key, event.target.value))}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}
