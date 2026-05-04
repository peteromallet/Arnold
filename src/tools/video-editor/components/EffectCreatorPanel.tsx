import { useCallback, useMemo, useRef, useState, type FC } from 'react';
import { Loader2, RotateCcw, Save, Sparkles, Pencil, Globe, Lock, X } from 'lucide-react';
import { Player } from '@remotion/player';
import { AbsoluteFill } from 'remotion';
import { Button } from '@/shared/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/shared/components/ui/dialog';
import { Input } from '@/shared/components/ui/input';
import { Slider } from '@/shared/components/ui/slider';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select';
import { Switch } from '@/shared/components/ui/switch';
import { Textarea } from '@/shared/components/ui/textarea';
import { toast } from '@/shared/components/ui/toast';
import { invokeSupabaseEdgeFunction } from '@/integrations/supabase/functions/invokeSupabaseEdgeFunction';
import { ParameterControls, getDefaultValues } from '@/tools/video-editor/components/ParameterControls';
import { SyntheticAudioProvider } from '@/tools/video-editor/compositions/AudioAnalysisProvider';
import { tryCompileEffectAsync, type CompileResult } from '@/tools/video-editor/effects/compileEffect';
import { wrapWithEffect } from '@/tools/video-editor/effects';
import type { EffectComponentProps } from '@/tools/video-editor/effects/entrances';
import {
  type EffectCategory,
  type EffectResource,
  useEffectResources,
} from '@/tools/video-editor/hooks/useEffectResources';
import type { ParameterSchema } from '@/tools/video-editor/types';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface EffectCreatorPanelProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** When editing an existing resource-based effect */
  editingEffect?: EffectResource | null;
  /** Called after a successful save with the resource id */
  onSaved?: (resourceId: string, category: EffectCategory, defaultParams: Record<string, unknown>) => void;
  /** URL of the clip's image/video to use as preview background */
  previewAssetSrc?: string | null;
  /** Timeline FPS for preview timing fidelity; falls back to 30 */
  timelineFps?: number;
}

type CompileStatus = 'idle' | 'compiling' | 'success' | 'error';

interface GenerateEffectResponse {
  code?: string;
  name?: string;
  description: string;
  parameterSchema?: ParameterSchema;
  message?: string;
  isQuestionResponse?: boolean;
  model: string;
}

// ---------------------------------------------------------------------------
// Preview composition — colored rectangle wrapped by the effect component
// ---------------------------------------------------------------------------

const PREVIEW_SIZE = 320;

interface PreviewParams {
  durationSeconds: number;
  effectSeconds: number;
  intensity: number;
}

const DEFAULT_PREVIEW_PARAMS: PreviewParams = {
  durationSeconds: 3,
  effectSeconds: 0.7,
  intensity: 0.5,
};

function PreviewRect({ assetSrc }: { assetSrc?: string | null }) {
  if (assetSrc) {
    const isVideo = /\.(mp4|mov|webm|m4v)(\?|$)/i.test(assetSrc);
    return (
      <AbsoluteFill>
        {isVideo ? (
          <video
            src={assetSrc}
            muted
            loop
            autoPlay
            playsInline
            style={{ width: '100%', height: '100%', objectFit: 'cover' }}
          />
        ) : (
          <img
            src={assetSrc}
            alt=""
            style={{ width: '100%', height: '100%', objectFit: 'cover' }}
          />
        )}
      </AbsoluteFill>
    );
  }

  return (
    <AbsoluteFill
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'linear-gradient(135deg, #6366f1 0%, #8b5cf6 50%, #a78bfa 100%)',
      }}
    >
      <div
        style={{
          width: '60%',
          height: '60%',
          borderRadius: 16,
          background: 'rgba(255,255,255,0.15)',
          backdropFilter: 'blur(8px)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: '#fff',
          fontSize: 24,
          fontWeight: 600,
          letterSpacing: 1,
        }}
      >
        Effect Preview
      </div>
    </AbsoluteFill>
  );
}

function makePreviewComposition(
  EffectComponent: FC<EffectComponentProps> | null,
  category: EffectCategory,
  params: PreviewParams,
  effectParams: Record<string, unknown>,
  fps: number,
  schema?: ParameterSchema,
  assetSrc?: string | null,
) {
  const durationInFrames = Math.max(1, Math.round(params.durationSeconds * fps));
  const effectFrames = category === 'continuous'
    ? durationInFrames
    : Math.max(1, Math.round(params.effectSeconds * fps));

  return function EffectPreviewComposition() {
    const fallback = <PreviewRect assetSrc={assetSrc} />;
    const content = !EffectComponent
      ? fallback
      : wrapWithEffect(
        <AbsoluteFill style={{ overflow: 'hidden' }}>
          <PreviewRect assetSrc={assetSrc} />
        </AbsoluteFill>,
        EffectComponent,
        {
          effectName: 'preview',
          durationInFrames,
          effectFrames,
          intensity: params.intensity,
          params: effectParams,
          schema,
        },
      );

    return (
      <SyntheticAudioProvider fps={fps} durationInFrames={durationInFrames}>
        {content}
      </SyntheticAudioProvider>
    );
  };
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function EffectCreatorPanel({
  open,
  onOpenChange,
  editingEffect,
  onSaved,
  previewAssetSrc,
  timelineFps,
}: EffectCreatorPanelProps) {
  const previewFps = timelineFps ?? 30;
  const isEditing = Boolean(editingEffect);

  // Form state
  const [name, setName] = useState(editingEffect?.name ?? '');
  const [category, setCategory] = useState<EffectCategory>(editingEffect?.category ?? 'entrance');
  const [prompt, setPrompt] = useState('');
  const [code, setCode] = useState(editingEffect?.code ?? '');
  const [isPublic, setIsPublic] = useState(editingEffect?.is_public ?? true);
  const [parameterSchema, setParameterSchema] = useState<ParameterSchema>(editingEffect?.parameterSchema ?? []);
  const [previewParamValues, setPreviewParamValues] = useState<Record<string, unknown>>(
    () => getDefaultValues(editingEffect?.parameterSchema ?? []),
  );
  const [generatedDescription, setGeneratedDescription] = useState(editingEffect?.description ?? '');

  // Generation / compile state
  const [isGenerating, setIsGenerating] = useState(false);
  const [compileStatus, setCompileStatus] = useState<CompileStatus>(editingEffect?.code ? 'success' : 'idle');
  const [compileError, setCompileError] = useState<string | null>(null);
  const [previewComponent, setPreviewComponent] = useState<FC<EffectComponentProps> | null>(null);
  const [showCode, setShowCode] = useState(false);
  const [previewParams, setPreviewParams] = useState<PreviewParams>(DEFAULT_PREVIEW_PARAMS);
  const [agentMessage, setAgentMessage] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  const effectCatalog = useEffectResources();
  const canSaveEffect = isEditing
    ? effectCatalog.canUpdateEffect
    : effectCatalog.canCreateEffect;

  // Track abort for generation requests
  const abortRef = useRef<AbortController | null>(null);

  // Reset state when dialog opens with a new/different effect
  const resetForm = useCallback((effect?: EffectResource | null) => {
    const nextSchema = effect?.parameterSchema ?? [];
    setName(effect?.name ?? '');
    setCategory(effect?.category ?? 'entrance');
    setPrompt('');
    setCode(effect?.code ?? '');
    setIsPublic(effect?.is_public ?? true);
    setParameterSchema(nextSchema);
    setPreviewParamValues(getDefaultValues(nextSchema));
    setGeneratedDescription(effect?.description ?? '');
    setCompileStatus(effect?.code ? 'success' : 'idle');
    setCompileError(null);
    setPreviewComponent(null);
    setShowCode(false);
    setPreviewParams(DEFAULT_PREVIEW_PARAMS);
    setAgentMessage(null);
    setIsGenerating(false);
  }, []);

  // When the dialog opens or the editingEffect changes, reset
  const prevEditingIdRef = useRef<string | undefined>(undefined);
  if (open && editingEffect?.id !== prevEditingIdRef.current) {
    prevEditingIdRef.current = editingEffect?.id;
    resetForm(editingEffect);
    // If editing and there is code, compile it for preview
    if (editingEffect?.code) {
      void tryCompileEffectAsync(editingEffect.code).then((result) => {
        if (result.ok) {
          setPreviewComponent(() => result.component);
          setCompileStatus('success');
        } else {
          setCompileError(result.error);
          setCompileStatus('error');
        }
      });
    }
  }
  if (!open && prevEditingIdRef.current !== undefined) {
    prevEditingIdRef.current = undefined;
  }

  // Compile code and update preview
  const compileCode = useCallback(async (codeToCompile: string) => {
    setCompileStatus('compiling');
    setCompileError(null);
    const result: CompileResult = await tryCompileEffectAsync(codeToCompile);
    if (result.ok) {
      setPreviewComponent(() => result.component);
      setCompileStatus('success');
      setCompileError(null);
    } else {
      setPreviewComponent(null);
      setCompileStatus('error');
      setCompileError(result.error);
    }
    return result;
  }, []);

  // Generate effect via edge function
  const handleGenerate = useCallback(async () => {
    if (!prompt.trim()) {
      toast({ title: 'Prompt required', description: 'Describe the effect you want to create.', variant: 'destructive' });
      return;
    }

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setAgentMessage(null);
    setIsGenerating(true);
    setCompileStatus('idle');
    setCompileError(null);

    try {
      const response = await invokeSupabaseEdgeFunction<GenerateEffectResponse>(
        'ai-generate-effect',
        {
          body: {
            prompt: prompt.trim(),
            name: name.trim(),
            category,
            existingCode: code || undefined,
          },
          timeoutMs: 120_000,
          signal: controller.signal,
        },
      );

      if (controller.signal.aborted) return;

      if (response.isQuestionResponse) {
        setAgentMessage(response.message?.trim() || null);
        setPrompt('');
        return;
      }

      if (!response.code?.trim()) {
        throw new Error('Effect generation returned no code.');
      }

      const nextSchema = response.parameterSchema ?? [];
      setAgentMessage(response.message?.trim() || null);
      setCode(response.code);
      setParameterSchema(nextSchema);
      setPreviewParamValues(getDefaultValues(nextSchema));
      setGeneratedDescription(response.description.trim() || prompt.trim());
      setPrompt('');
      if (!name.trim() && response.name?.trim()) {
        setName(response.name.trim());
      }

      // Auto-compile
      await compileCode(response.code);
    } catch (err) {
      if ((err as Error).name === 'AbortError') return;
      const message = err instanceof Error ? err.message : 'Generation failed';
      toast({ title: 'Effect generation failed', description: message, variant: 'destructive' });
      setCompileStatus('error');
      setCompileError(message);
    } finally {
      setIsGenerating(false);
    }
  }, [name, prompt, category, code, compileCode]);

  // Save effect as a resource
  const handleSave = useCallback(async () => {
    if (!name.trim()) {
      toast({ title: 'Name required', description: 'Give your effect a name.', variant: 'destructive' });
      return;
    }
    if (!code.trim()) {
      toast({ title: 'No code', description: 'Generate or write the effect code first.', variant: 'destructive' });
      return;
    }
    if (compileStatus !== 'success') {
      // Try compiling first
      const result = await compileCode(code);
      if (!result.ok) {
        toast({ title: 'Compile error', description: 'Fix the compile error before saving.', variant: 'destructive' });
        return;
      }
    }

    const slug = name.toLowerCase().trim().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
    const metadata = {
      name: name.trim(),
      slug,
      code,
      category,
      description: generatedDescription.trim() || prompt.trim(),
      parameterSchema: parameterSchema.length > 0 ? parameterSchema : undefined,
      created_by: { is_you: true },
      is_public: isPublic,
    };

    const defaultParams = getDefaultValues(parameterSchema);

    try {
      setIsSaving(true);
      if (isEditing && editingEffect) {
        if (!effectCatalog.updateEffect) {
          throw new Error('This editor host does not support updating custom effects.');
        }
        await effectCatalog.updateEffect({ id: editingEffect.id, metadata });
        onSaved?.(editingEffect.id, category, defaultParams);
      } else {
        if (!effectCatalog.createEffect) {
          throw new Error('This editor host does not support creating custom effects.');
        }
        const resource = await effectCatalog.createEffect({ metadata });
        onSaved?.(resource.id, category, defaultParams);
      }
      onOpenChange(false);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Save failed';
      toast({ title: 'Save failed', description: message, variant: 'destructive' });
    } finally {
      setIsSaving(false);
    }
  }, [name, code, category, generatedDescription, parameterSchema, prompt, isPublic, compileStatus, compileCode, isEditing, editingEffect, effectCatalog, onSaved, onOpenChange]);

  // Preview composition memoized on the component ref
  const previewDurationFrames = Math.max(1, Math.round(previewParams.durationSeconds * previewFps));
  const PreviewComposition = useMemo(
    () => makePreviewComposition(previewComponent, category, previewParams, previewParamValues, previewFps, parameterSchema, previewAssetSrc),
    [category, previewComponent, previewParams, previewParamValues, previewFps, parameterSchema, previewAssetSrc],
  );

  const hasGeneratedCode = Boolean(code.trim());

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          {hasGeneratedCode ? (
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0 flex-1">
                <Input
                  value={name}
                  placeholder="Effect name"
                  onChange={(e) => setName(e.target.value)}
                  className="h-7 border-none bg-transparent px-0 text-lg font-semibold shadow-none focus-visible:ring-0"
                />
                <DialogDescription>
                  How would you like to edit this animation?
                </DialogDescription>
              </div>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="shrink-0 text-xs text-muted-foreground"
                onClick={() => resetForm()}
              >
                <RotateCcw className="mr-1 h-3 w-3" />
                Start over
              </Button>
            </div>
          ) : (
            <>
              <DialogTitle>
                {isEditing ? 'Edit Custom Effect' : 'Create Custom Effect'}
              </DialogTitle>
              <DialogDescription>
                {isEditing
                  ? 'Describe how you want to change this effect.'
                  : 'Describe the effect you want, and AI will generate it for you.'}
              </DialogDescription>
            </>
          )}
        </DialogHeader>

        <div className="space-y-4">
          {/* Name + Category — shown before first generation */}
          {!hasGeneratedCode && (
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-muted-foreground">Name</label>
                <Input
                  value={name}
                  placeholder="My effect"
                  onChange={(e) => setName(e.target.value)}
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-muted-foreground">Category</label>
                <Select value={category} onValueChange={(v) => setCategory(v as EffectCategory)}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="entrance">Entrance</SelectItem>
                    <SelectItem value="exit">Exit</SelectItem>
                    <SelectItem value="continuous">Continuous</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          )}

          {/* Preview — shown above prompt when code exists */}
          {hasGeneratedCode && (compileStatus === 'success' || previewComponent) && (
            <div className="space-y-2">
              {generatedDescription.trim() && (
                <div className="rounded-lg border border-border bg-muted/40 px-3 py-2">
                  <div className="text-[10px] font-medium uppercase tracking-[0.14em] text-muted-foreground">
                    Effect Description
                  </div>
                  <div className="mt-1 text-sm text-foreground">{generatedDescription.trim()}</div>
                </div>
              )}
              <div className="overflow-hidden rounded-lg border border-border bg-black">
                <Player
                  component={PreviewComposition}
                  compositionWidth={PREVIEW_SIZE}
                  compositionHeight={PREVIEW_SIZE}
                  durationInFrames={previewDurationFrames}
                  fps={previewFps}
                  style={{ width: '100%', aspectRatio: '1' }}
                  loop
                  autoPlay
                  controls
                />
              </div>
              <div className="grid gap-3 sm:grid-cols-3">
                <div className="space-y-1">
                  <label className="text-[10px] text-muted-foreground">Duration: {previewParams.durationSeconds.toFixed(1)}s</label>
                  <Slider
                    value={[previewParams.durationSeconds]}
                    min={0.5}
                    max={10}
                    step={0.5}
                    onValueChange={(v) => setPreviewParams((p) => ({ ...p, durationSeconds: v }))}
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-[10px] text-muted-foreground">Effect length: {previewParams.effectSeconds.toFixed(1)}s</label>
                  <Slider
                    value={[previewParams.effectSeconds]}
                    min={0.1}
                    max={Math.min(5, previewParams.durationSeconds)}
                    step={0.1}
                    onValueChange={(v) => setPreviewParams((p) => ({ ...p, effectSeconds: v }))}
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-[10px] text-muted-foreground">Intensity: {(previewParams.intensity * 100).toFixed(0)}%</label>
                  <Slider
                    value={[previewParams.intensity]}
                    min={0}
                    max={1}
                    step={0.05}
                    onValueChange={(v) => setPreviewParams((p) => ({ ...p, intensity: v }))}
                  />
                </div>
              </div>
              {parameterSchema.length > 0 && (
                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-muted-foreground">Preview Parameters</label>
                  <ParameterControls
                    schema={parameterSchema}
                    values={previewParamValues}
                    onChange={(paramName, value) => {
                      setPreviewParamValues((current) => ({
                        ...current,
                        [paramName]: value,
                      }));
                    }}
                  />
                </div>
              )}
            </div>
          )}

          {/* Compile error */}
          {compileStatus === 'error' && compileError && (
            <div className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-xs text-destructive">
              Compile error: {compileError}
            </div>
          )}

          {agentMessage && !isGenerating && (
            <div className="flex gap-2 rounded-lg border border-border bg-muted/40 px-3 py-2">
              <Sparkles className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
              <div className="min-w-0 flex-1 text-sm text-foreground">{agentMessage}</div>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="h-6 w-6 shrink-0 text-muted-foreground"
                aria-label="Dismiss agent message"
                onClick={() => setAgentMessage(null)}
              >
                <X className="h-3.5 w-3.5" />
              </Button>
            </div>
          )}

          {/* Prompt / edit instructions */}
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-muted-foreground">
              {hasGeneratedCode ? 'Edit instructions' : 'Describe your effect'}
            </label>
            <Textarea
              value={prompt}
              placeholder={hasGeneratedCode
                ? "e.g. 'Make it slower and add a slight rotation'"
                : "e.g. 'A glowing neon border that pulses in and out'"
              }
              onChange={(e) => setPrompt(e.target.value)}
              rows={2}
              voiceInput
              onVoiceResult={(result) => setPrompt(result.transcription)}
              voiceContext={hasGeneratedCode
                ? "The user is describing changes they want to make to an existing visual animation effect in a video editor. Transcribe their edit instructions accurately."
                : "The user is describing a visual animation effect for a video editor. They are specifying how a clip should animate (entrance, exit, or continuous effect). Transcribe their description accurately."
              }
              voiceTask="transcribe_only"
            />
          </div>

          {/* Generate / update button */}
          <div className="flex items-center gap-2">
            <Button
              type="button"
              onClick={handleGenerate}
              disabled={isGenerating || !prompt.trim()}
              className="gap-1.5"
            >
              {isGenerating ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  {hasGeneratedCode ? 'Updating...' : 'Generating...'}
                </>
              ) : (
                <>
                  <Sparkles className="h-4 w-4" />
                  {hasGeneratedCode ? 'Update effect' : 'Generate'}
                </>
              )}
            </Button>
            {hasGeneratedCode && (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="gap-1 text-xs text-muted-foreground"
                onClick={() => setShowCode((v) => !v)}
              >
                <Pencil className="h-3 w-3" />
                {showCode ? 'Hide code' : 'View code'}
              </Button>
            )}
          </div>

          {/* Code editor — hidden by default */}
          {showCode && (
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <label className="text-xs font-medium text-muted-foreground">Effect Code</label>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="h-6 text-xs"
                  onClick={() => void compileCode(code)}
                  disabled={compileStatus === 'compiling'}
                >
                  {compileStatus === 'compiling' ? (
                    <Loader2 className="mr-1 h-3 w-3 animate-spin" />
                  ) : null}
                  Recompile
                </Button>
              </div>
              <Textarea
                value={code}
                onChange={(e) => {
                  setCode(e.target.value);
                  setCompileStatus('idle');
                }}
                rows={10}
                className="font-mono text-xs"
              />
            </div>
          )}

          {/* Public/private toggle + Save */}
          <div className="flex items-center justify-between border-t border-border pt-4">
            <div className="flex items-center gap-2">
              <Switch
                checked={isPublic}
                onCheckedChange={setIsPublic}
              />
              <span className="flex items-center gap-1 text-xs text-muted-foreground">
                {isPublic ? <Globe className="h-3.5 w-3.5" /> : <Lock className="h-3.5 w-3.5" />}
                {isPublic ? 'Public' : 'Private'}
              </span>
            </div>
            <div className="flex gap-2">
              {!canSaveEffect && (
                <div className="self-center text-right text-xs text-muted-foreground">
                  This host is read-only for custom effect publishing.
                </div>
              )}
              <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
                Cancel
              </Button>
              <Button
                type="button"
                onClick={handleSave}
                disabled={isSaving || !name.trim() || !code.trim() || !canSaveEffect}
                className="gap-1.5"
              >
                {isSaving ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Save className="h-4 w-4" />
                )}
                {isEditing ? 'Update' : 'Save'}
              </Button>
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
