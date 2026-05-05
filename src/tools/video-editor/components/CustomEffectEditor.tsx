import { useEffect, useMemo, useState } from 'react';
import { Button } from '@/shared/components/ui/button.tsx';
import { Input } from '@/shared/components/ui/input.tsx';
import { Textarea } from '@/shared/components/ui/textarea.tsx';
import { toast } from '@/shared/components/ui/toast.tsx';
import { useVideoEditorRuntime } from '@/tools/video-editor/contexts/DataProviderContext.tsx';
import { deleteDraftEffect, loadDraftEffects, saveDraftEffect } from '@/tools/video-editor/effects/effect-store.ts';
import { getEffectPromptTemplate } from '@/tools/video-editor/effects/effectPromptTemplate.ts';
import { useEffects } from '@/tools/video-editor/hooks/useEffects.ts';
import type { CustomEffectEntry } from '@/tools/video-editor/types/index.ts';

interface CustomEffectEditorProps {
  category: CustomEffectEntry['category'];
  initialSlug?: string;
  onApply: (slug: string, category: NonNullable<CustomEffectEntry['category']>) => void;
}

const TEMPLATE = `export default function Effect({ children, durationInFrames, effectFrames = 20, intensity = 0.5 }) {\n  const frame = useCurrentFrame();\n  const opacity = interpolate(frame, [0, effectFrames], [0, 1], { extrapolateRight: 'clamp' });\n\n  return (\n    <AbsoluteFill style={{ opacity }}>\n      {children}\n    </AbsoluteFill>\n  );\n}`;

export function CustomEffectEditor({ category, initialSlug, onApply }: CustomEffectEditorProps) {
  const { userId } = useVideoEditorRuntime();
  const effects = useEffects(userId);
  const existingEffect = useMemo(
    () => effects.data?.find((effect) => effect.slug === initialSlug) ?? null,
    [effects.data, initialSlug],
  );
  const [name, setName] = useState(existingEffect?.name ?? initialSlug ?? '');
  const [slug, setSlug] = useState(existingEffect?.slug ?? initialSlug ?? '');
  const [description, setDescription] = useState(existingEffect?.description ?? '');
  const [code, setCode] = useState(existingEffect?.code ?? loadDraftEffects()[initialSlug ?? ''] ?? TEMPLATE);

  useEffect(() => {
    if (!existingEffect) {
      return;
    }

    setName(existingEffect.name ?? existingEffect.slug);
    setSlug(existingEffect.slug);
    setDescription(existingEffect.description ?? '');
    setCode(existingEffect.code);
  }, [existingEffect]);

  return (
    <div className="space-y-3 rounded-lg border border-border bg-card/70 p-3">
      <div className="space-y-2">
        <Input
          value={name}
          placeholder="Effect name"
          onChange={(event) => {
            const nextName = event.target.value;
            setName(nextName);
            if (!slug) {
              setSlug(nextName.toLowerCase().trim().replace(/[^a-z0-9]+/g, '-'));
            }
          }}
        />
        <Input
          value={slug}
          placeholder="slug"
          onChange={(event) => setSlug(event.target.value.toLowerCase().trim().replace(/[^a-z0-9-]+/g, '-'))}
        />
        <Textarea
          value={description}
          placeholder="Describe what this effect should do"
          onChange={(event) => setDescription(event.target.value)}
          rows={2}
        />
      </div>
      <Textarea
        value={code}
        onChange={(event) => setCode(event.target.value)}
        rows={12}
        className="font-mono text-xs"
      />
      <div className="rounded-md border border-border bg-background/50 p-2 text-[11px] text-muted-foreground whitespace-pre-wrap">
        {getEffectPromptTemplate(description || 'Create a tasteful animated effect.')}
      </div>
      <div className="flex flex-wrap gap-2">
        <Button
          type="button"
          size="sm"
          variant="secondary"
          onClick={() => {
            if (!slug) {
              toast({ title: 'Missing slug', description: 'Choose a slug before saving a draft.', variant: 'destructive' });
              return;
            }
            saveDraftEffect(slug, code);
            toast.success('Draft effect saved');
          }}
        >
          Test Draft
        </Button>
        <Button
          type="button"
          size="sm"
          onClick={async () => {
            if (!name || !slug) {
              toast({ title: 'Missing fields', description: 'Name and slug are required.', variant: 'destructive' });
              return;
            }

            await effects.upsertEffect.mutateAsync({
              id: existingEffect?.id,
              name,
              slug,
              code,
              category: category ?? 'continuous',
              description: description || null,
            });
            deleteDraftEffect(slug);
            onApply(slug, category ?? 'continuous');
            toast.success('Effect saved');
          }}
          disabled={effects.upsertEffect.isPending}
        >
          Save
        </Button>
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={() => {
            if (slug) {
              deleteDraftEffect(slug);
            }
            setCode(existingEffect?.code ?? TEMPLATE);
          }}
        >
          Discard
        </Button>
      </div>
    </div>
  );
}
