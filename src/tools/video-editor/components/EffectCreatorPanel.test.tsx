import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import type {
  ButtonHTMLAttributes,
  ComponentType,
  InputHTMLAttributes,
  ReactNode,
  TextareaHTMLAttributes,
} from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { EffectCreatorPanel } from '@/tools/video-editor/components/EffectCreatorPanel';
import {
  createVideoEditorEffectCatalog,
  EffectCatalogProvider,
  type EffectResource,
} from '@/tools/video-editor/hooks/useEffectResources';

const mocks = vi.hoisted(() => ({
  invokeSupabaseEdgeFunction: vi.fn(),
  tryCompileEffectAsync: vi.fn(),
}));

vi.mock('@/integrations/supabase/functions/invokeSupabaseEdgeFunction', () => ({
  invokeSupabaseEdgeFunction: mocks.invokeSupabaseEdgeFunction,
}));

vi.mock('@/tools/video-editor/effects/compileEffect.tsx', () => ({
  tryCompileEffectAsync: mocks.tryCompileEffectAsync,
}));

vi.mock('@/shared/components/ui/button.tsx', () => ({
  Button: ({ children, ...props }: ButtonHTMLAttributes<HTMLButtonElement>) => (
    <button {...props}>{children}</button>
  ),
}));

vi.mock('@/shared/components/ui/dialog.tsx', () => ({
  Dialog: ({ open, children }: { open: boolean; children: ReactNode }) => (open ? <div>{children}</div> : null),
  DialogContent: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  DialogHeader: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  DialogTitle: ({ children }: { children: ReactNode }) => <h2>{children}</h2>,
  DialogDescription: ({ children }: { children: ReactNode }) => <p>{children}</p>,
}));

vi.mock('@/shared/components/ui/input.tsx', () => ({
  Input: (props: InputHTMLAttributes<HTMLInputElement>) => <input {...props} />,
}));

vi.mock('@/shared/components/ui/textarea.tsx', () => ({
  Textarea: ({
    voiceInput: _voiceInput,
    voiceContext: _voiceContext,
    voiceTask: _voiceTask,
    onVoiceResult: _onVoiceResult,
    ...props
  }: TextareaHTMLAttributes<HTMLTextAreaElement> & {
    voiceInput?: boolean;
    voiceContext?: string;
    voiceTask?: string;
    onVoiceResult?: (result: { transcription: string }) => void;
  }) => <textarea {...props} />,
}));

vi.mock('@/shared/components/ui/select.tsx', () => ({
  Select: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  SelectContent: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  SelectItem: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  SelectTrigger: ({ children }: { children: ReactNode }) => <button type="button">{children}</button>,
  SelectValue: () => <span />,
}));

vi.mock('@/shared/components/ui/slider.tsx', () => ({
  Slider: () => <input type="range" />,
}));

vi.mock('@/shared/components/ui/switch.tsx', () => ({
  Switch: ({ checked, onCheckedChange }: { checked: boolean; onCheckedChange: (checked: boolean) => void }) => (
    <input
      type="checkbox"
      checked={checked}
      onChange={(event) => onCheckedChange(event.currentTarget.checked)}
    />
  ),
}));

vi.mock('@/shared/components/ui/toast.tsx', () => ({
  toast: vi.fn(),
}));

vi.mock('@/tools/video-editor/components/ParameterControls.tsx', () => ({
  ParameterControls: () => <div data-testid="parameter-controls" />,
  getDefaultValues: (schema: Array<{ name: string; default?: unknown }>) =>
    schema.reduce<Record<string, unknown>>((defaults, parameter) => {
      defaults[parameter.name] = parameter.default;
      return defaults;
    }, {}),
}));

vi.mock('@/tools/video-editor/compositions/AudioAnalysisProvider.tsx', () => ({
  SyntheticAudioProvider: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

vi.mock('@remotion/player', async () => {
  const React = await import('react');

  return {
    Player: ({ component: Component }: { component: ComponentType }) => (
      <div data-testid="mock-player">
        <Component />
      </div>
    ),
  };
});

function renderWithCatalog(
  ui: ReactNode,
  catalog: ReturnType<typeof createVideoEditorEffectCatalog>,
) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <EffectCatalogProvider value={catalog}>
        {ui}
      </EffectCatalogProvider>
    </QueryClientProvider>,
  );
}

function makeEditingEffect(overrides: Partial<EffectResource> = {}): EffectResource {
  return {
    id: 'catalog-edit-effect',
    type: 'effect',
    name: 'Editable Wipe',
    slug: 'editable-wipe',
    code: 'export default function EditableWipe() { return null; }',
    category: 'exit',
    description: 'Editable resource effect',
    parameterSchema: [
      {
        name: 'amount',
        label: 'Amount',
        description: 'Effect amount',
        type: 'number',
        default: 0.5,
        min: 0,
        max: 1,
      },
    ],
    created_by: { is_you: true },
    is_public: false,
    ...overrides,
  };
}

describe('EffectCreatorPanel editable catalog integration', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.tryCompileEffectAsync.mockResolvedValue({
      ok: true,
      component: ({ children }: { children?: ReactNode }) => <div data-testid="compiled-effect">{children}</div>,
    });
  });

  it('creates generated effects through the injected catalog create API', async () => {
    const createEffect = vi.fn(async () => ({ id: 'catalog-created-effect' }));
    const onSaved = vi.fn();
    const onOpenChange = vi.fn();
    const catalog = createVideoEditorEffectCatalog({ createEffect });

    mocks.invokeSupabaseEdgeFunction.mockResolvedValue({
      code: 'export default function GeneratedEffect() { return null; }',
      name: 'Generated Pulse',
      description: 'Generated pulse effect',
      parameterSchema: [
        {
          name: 'intensity',
          label: 'Intensity',
          description: 'Effect intensity',
          type: 'number',
          default: 0.75,
          min: 0,
          max: 1,
        },
      ],
      model: 'test-model',
    });

    renderWithCatalog(
      <EffectCreatorPanel
        open
        onOpenChange={onOpenChange}
        onSaved={onSaved}
      />,
      catalog,
    );

    fireEvent.change(screen.getByPlaceholderText('My effect'), {
      target: { value: 'Generated Pulse' },
    });
    fireEvent.change(screen.getByPlaceholderText(/A glowing neon border/i), {
      target: { value: 'make it pulse' },
    });
    fireEvent.click(screen.getByRole('button', { name: /^Generate$/ }));

    await waitFor(() => {
      expect(mocks.invokeSupabaseEdgeFunction).toHaveBeenCalledWith('ai-generate-effect', expect.objectContaining({
        body: expect.objectContaining({
          prompt: 'make it pulse',
          name: 'Generated Pulse',
          category: 'entrance',
        }),
      }));
    });

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /^Save$/ })).not.toBeDisabled();
    });
    fireEvent.click(screen.getByRole('button', { name: /^Save$/ }));

    await waitFor(() => {
      expect(createEffect).toHaveBeenCalledWith({
        metadata: expect.objectContaining({
          name: 'Generated Pulse',
          slug: 'generated-pulse',
          code: 'export default function GeneratedEffect() { return null; }',
          category: 'entrance',
          description: 'Generated pulse effect',
          parameterSchema: expect.any(Array),
        }),
      });
    });
    expect(onSaved).toHaveBeenCalledWith('catalog-created-effect', 'entrance', { intensity: 0.75 });
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it('updates existing resource effects through the injected catalog update API', async () => {
    const updateEffect = vi.fn(async () => ({ id: 'catalog-edit-effect' }));
    const onSaved = vi.fn();
    const onOpenChange = vi.fn();
    const catalog = createVideoEditorEffectCatalog({ updateEffect });
    const editingEffect = makeEditingEffect();

    renderWithCatalog(
      <EffectCreatorPanel
        open
        onOpenChange={onOpenChange}
        editingEffect={editingEffect}
        onSaved={onSaved}
      />,
      catalog,
    );

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /^Update$/ })).not.toBeDisabled();
    });
    fireEvent.click(screen.getByRole('button', { name: /^Update$/ }));

    await waitFor(() => {
      expect(updateEffect).toHaveBeenCalledWith({
        id: 'catalog-edit-effect',
        metadata: expect.objectContaining({
          name: 'Editable Wipe',
          slug: 'editable-wipe',
          code: 'export default function EditableWipe() { return null; }',
          category: 'exit',
          description: 'Editable resource effect',
          parameterSchema: editingEffect.parameterSchema,
        }),
      });
    });
    expect(onSaved).toHaveBeenCalledWith('catalog-edit-effect', 'exit', { amount: 0.5 });
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });
});
