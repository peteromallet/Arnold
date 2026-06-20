import { describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { GenerationSessionPanel } from '@/tools/video-editor/components/GenerationSessionPanel/GenerationSessionPanel';
import type { StandardSchema } from '@/tools/video-editor/components/SchemaForm/SchemaForm';
import type { AgentToolSessionEntry } from '@/tools/video-editor/runtime/agentToolRegistry';
import type {
  GenerationSession,
  LiveChannelDescriptor,
  LiveSourceDiagnostic,
  SteeringDecision,
} from '@reigh/editor-sdk';

function makeSession(overrides?: Partial<GenerationSession>): GenerationSession {
  return {
    id: 'session-1',
    progress: 42,
    progressLabel: 'Generating frames...',
    cancelled: false,
    done: false,
    diagnostics: [],
    liveDelivery: undefined,
    finalRefs: undefined,
    bakedRefs: undefined,
    onProgress: vi.fn().mockReturnValue({ dispose: vi.fn() }),
    cancel: vi.fn(),
    getSampleChannel: vi.fn().mockReturnValue('channel:sample' as LiveChannelDescriptor),
    onSample: vi.fn().mockReturnValue({ dispose: vi.fn() }),
    getSteeringLineage: vi.fn().mockReturnValue(undefined),
    complete: vi.fn(),
    ...overrides,
  };
}

function makeDecision(kind: SteeringDecision['kind'], overrides?: Partial<SteeringDecision>): SteeringDecision {
  return {
    kind,
    sessionId: 'session-1',
    reason: `${kind} requested`,
    lineage: {
      generationIndex: 3,
      steerHash: `hash-${kind}`,
      parentRefs: ['attempt-1'],
      producerVersion: '1.2.3',
      provenance: {
        prompt: 'make a brighter shot',
        model: 'test-model',
        seed: 123,
        tags: ['hot:param.exposure', 'non-hot:param.model'],
      },
    },
    ...overrides,
  };
}

function makeEntry(overrides?: Partial<AgentToolSessionEntry>): AgentToolSessionEntry {
  return {
    session: makeSession(),
    toolId: 'tool.generate',
    extensionId: 'ext.generate',
    createdAt: 100,
    ...overrides,
  };
}

const steeringSchema: StandardSchema = {
  type: 'object',
  properties: {
    prompt: { type: 'string', title: 'Prompt', default: 'make a brighter shot' },
  },
};

describe('GenerationSessionPanel', () => {
  it('renders an empty state without sessions', () => {
    render(<GenerationSessionPanel sessions={[]} />);

    expect(screen.getByText('No generation sessions.')).toBeTruthy();
    expect(document.querySelector('[data-video-editor-generation-session-empty="true"]')).toBeTruthy();
  });

  it('renders agent-origin progress and cancellation', () => {
    const cancel = vi.fn();
    const entry = makeEntry({
      session: makeSession({ cancel }),
      liveDelivery: {
        origin: 'agent-tool',
        activeChannels: ['host-channel' as LiveChannelDescriptor],
        progress: 64,
        cancelled: false,
        steeringDecision: makeDecision('supersede'),
        generationIndex: 3,
        steerHash: 'hash-supersede',
        parentRefs: ['attempt-1'],
        finalRefs: ['asset-final'],
        bakedRefs: ['asset-baked'],
        sampleCount: 2,
        canActivate: true,
        diagnostics: [],
      },
    });

    render(<GenerationSessionPanel sessions={[entry]} onCancelAll={vi.fn()} />);

    expect(screen.getByText('Active Sessions (1)')).toBeTruthy();
    expect(screen.getByText('agent')).toBeTruthy();
    expect(screen.getByText('Supersede')).toBeTruthy();
    expect(screen.getByText('live active')).toBeTruthy();
    expect(screen.getByRole('progressbar').getAttribute('aria-valuenow')).toBe('64');
    expect(screen.getByText(/Channels host-channel/)).toBeTruthy();
    expect(screen.getByText('Attempt 3')).toBeTruthy();
    expect(screen.getByText('asset-final')).toBeTruthy();
    expect(screen.getByText('asset-baked')).toBeTruthy();

    fireEvent.click(screen.getByLabelText('Cancel session session-1'));
    expect(cancel).toHaveBeenCalledTimes(1);
  });

  it('renders live and process origins with fork links', () => {
    const liveEntry = makeEntry({
      session: makeSession({ id: 'live-session' }),
      liveDelivery: {
        origin: 'live',
        activeChannels: ['live-channel' as LiveChannelDescriptor],
        progress: 25,
        cancelled: false,
        steeringDecision: makeDecision('fork', { sessionId: 'live-session' }),
        generationIndex: 3,
        steerHash: 'hash-fork',
        parentRefs: ['fork-parent'],
        sampleCount: 0,
        canActivate: true,
        diagnostics: [],
      },
    });
    const processEntry = makeEntry({
      session: makeSession({ id: 'process-session', progress: 8 }),
      liveDelivery: {
        origin: 'process',
        activeChannels: [],
        progress: 8,
        cancelled: false,
        steeringDecision: makeDecision('supersede', { sessionId: 'process-session' }),
        generationIndex: 4,
        steerHash: 'hash-process',
        sampleCount: 0,
        canActivate: true,
        diagnostics: [],
      },
    });

    render(<GenerationSessionPanel sessions={[liveEntry, processEntry]} />);

    expect(screen.getByText('live')).toBeTruthy();
    expect(screen.getByText('process')).toBeTruthy();
    expect(screen.getByText('Fork')).toBeTruthy();
    expect(screen.getByText('Forked generation branch')).toBeTruthy();
    expect(screen.getByText('fork-parent')).toBeTruthy();
  });

  it('renders reject diagnostics and hot/non-hot detail from the resolver', () => {
    const diagnostics: LiveSourceDiagnostic[] = [
      {
        severity: 'error',
        code: 'live/steering-rejected',
        message: 'Rejected non-hot model change.',
        detail: {
          hotChanges: 'params.exposure',
          nonHotChanges: 'params.model',
        },
      },
    ];
    const entry = makeEntry({
      liveDelivery: {
        origin: 'agent-tool',
        activeChannels: [],
        progress: 0,
        cancelled: false,
        steeringDecision: makeDecision('reject'),
        generationIndex: 3,
        steerHash: 'hash-reject',
        sampleCount: 0,
        canActivate: false,
        diagnostics,
      },
    });

    render(<GenerationSessionPanel sessions={[entry]} />);

    expect(screen.getByText('Reject')).toBeTruthy();
    expect(screen.getByText('live blocked')).toBeTruthy();
    expect(screen.getByText(/Rejected non-hot model change/)).toBeTruthy();
    expect(screen.getByText(/hotChanges: params.exposure/)).toBeTruthy();
    expect(screen.getByText(/nonHotChanges: params.model/)).toBeTruthy();
  });

  it('renders SchemaForm steerable parameters', () => {
    const onChange = vi.fn();
    render(
      <GenerationSessionPanel
        sessions={[makeEntry()]}
        steeringSchema={steeringSchema}
        steeringValues={{ prompt: 'current prompt' }}
        onSteeringChange={onChange}
      />,
    );

    expect(document.querySelector('[data-video-editor-generation-session-steering="true"]')).toBeTruthy();
    const input = screen.getByTestId('schema-form-widget-prompt') as HTMLInputElement;
    expect(input.value).toBe('current prompt');
    fireEvent.change(input, { target: { value: 'next prompt' } });
    expect(onChange).toHaveBeenCalledWith('prompt', 'next prompt');
  });
});
