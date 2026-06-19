import { render, screen, fireEvent, within } from '@testing-library/react';
import type { ComponentProps } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { KeyframeInspector } from '@/tools/video-editor/components/KeyframeInspector/KeyframeInspector';
import type { ClipKeyframe, ParameterSchema } from '@/tools/video-editor/types';

// ---------------------------------------------------------------------------
// UI component mocks
// ---------------------------------------------------------------------------

vi.mock('@/shared/components/ui/input', () => ({
  Input: ({ onChange, value, ...props }: ComponentProps<'input'>) => (
    <input value={value} onChange={onChange} {...props} />
  ),
}));

// ---------------------------------------------------------------------------
// Shared test fixtures
// ---------------------------------------------------------------------------

const numberParamSchema: ParameterSchema = [
  {
    name: 'opacity',
    label: 'Opacity',
    description: 'Clip opacity 0-1',
    type: 'number',
    default: 0.5,
    min: 0,
    max: 1,
    step: 0.05,
  },
];

const multiParamSchema: ParameterSchema = [
  {
    name: 'speed',
    label: 'Speed',
    description: 'Adjust playback speed',
    type: 'number',
    default: 1,
    min: 0.1,
    max: 5,
    step: 0.1,
  },
  {
    name: 'enabled',
    label: 'Enabled',
    description: 'Whether the effect is active',
    type: 'boolean',
    default: true,
  },
  {
    name: 'mode',
    label: 'Mode',
    description: 'Effect mode',
    type: 'select',
    default: 'normal',
    options: [
      { label: 'Normal', value: 'normal' },
      { label: 'Vivid', value: 'vivid' },
      { label: 'Muted', value: 'muted' },
    ],
  },
  {
    name: 'tint',
    label: 'Tint Color',
    description: 'Color tint',
    type: 'color',
    default: '#ffffff',
  },
];

const sampleKeyframes: Record<string, ClipKeyframe[]> = {
  opacity: [
    { time: 0, value: 0, interpolation: 'linear' },
    { time: 1, value: 1, interpolation: 'linear' },
    { time: 3, value: 0.5, interpolation: 'hold' },
  ],
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('KeyframeInspector', () => {
  it('renders parameter sections for each schema entry', () => {
    render(
      <KeyframeInspector
        schema={numberParamSchema}
        keyframes={{}}
        currentTime={0}
        onChange={() => {}}
      />,
    );

    expect(screen.getByText('Opacity')).toBeInTheDocument();
    expect(screen.getByText('Clip opacity 0-1')).toBeInTheDocument();
    expect(screen.getByTestId('keyframe-parameter-section')).toBeInTheDocument();
  });

  it('shows empty state when schema is empty', () => {
    render(
      <KeyframeInspector
        schema={[]}
        keyframes={{}}
        currentTime={0}
        onChange={() => {}}
      />,
    );

    expect(screen.getByText(/No keyframe-able parameters/)).toBeInTheDocument();
  });

  it('renders existing keyframe rows', () => {
    render(
      <KeyframeInspector
        schema={numberParamSchema}
        keyframes={sampleKeyframes}
        currentTime={1.5}
        onChange={() => {}}
      />,
    );

    const rows = screen.getAllByTestId('keyframe-row');
    expect(rows).toHaveLength(3);
  });

  it('shows the current interpolated value at the playhead', () => {
    render(
      <KeyframeInspector
        schema={numberParamSchema}
        keyframes={sampleKeyframes}
        currentTime={0.5}
        onChange={() => {}}
      />,
    );

    // At t=0.5 between keyframes at 0 (value=0) and 1 (value=1), linear gives 0.5
    // The interpolated value appears in the "At playhead:" section with a mono font
    const section = screen.getByTestId('keyframe-parameter-section');
    const playheadValue = within(section).getByText('0.5');
    expect(playheadValue).toBeInTheDocument();
    expect(playheadValue).toHaveClass('font-mono');
  });

  it('shows the playhead time in the add button', () => {
    render(
      <KeyframeInspector
        schema={numberParamSchema}
        keyframes={{}}
        currentTime={2.35}
        onChange={() => {}}
      />,
    );

    // The add button text contains the playhead time
    const addButton = screen.getByRole('button', { name: /Add keyframe at 2\.35s/ });
    expect(addButton).toBeInTheDocument();
  });

  it('calls onChange when adding a keyframe at playhead', () => {
    const onChange = vi.fn();
    render(
      <KeyframeInspector
        schema={numberParamSchema}
        keyframes={{}}
        currentTime={1.5}
        onChange={onChange}
      />,
    );

    fireEvent.click(screen.getByText(/Add keyframe at 1\.50s/));
    expect(onChange).toHaveBeenCalledTimes(1);

    const updatedKeyframes = onChange.mock.calls[0][0] as Record<string, ClipKeyframe[]>;
    expect(updatedKeyframes.opacity).toHaveLength(1);
    expect(updatedKeyframes.opacity[0]).toMatchObject({
      time: 1.5,
      interpolation: 'linear',
    });
  });

  it('calls onChange when removing a keyframe', () => {
    const onChange = vi.fn();
    render(
      <KeyframeInspector
        schema={numberParamSchema}
        keyframes={sampleKeyframes}
        currentTime={0}
        onChange={onChange}
      />,
    );

    const removeButtons = screen.getAllByLabelText(/Remove keyframe/);
    fireEvent.click(removeButtons[1]); // Remove the second keyframe

    expect(onChange).toHaveBeenCalledTimes(1);
    const updatedKeyframes = onChange.mock.calls[0][0] as Record<string, ClipKeyframe[]>;
    expect(updatedKeyframes.opacity).toHaveLength(2);
  });

  it('calls onChange when editing a keyframe value', () => {
    const onChange = vi.fn();
    render(
      <KeyframeInspector
        schema={numberParamSchema}
        keyframes={sampleKeyframes}
        currentTime={0}
        onChange={onChange}
      />,
    );

    // NumberInput renders textboxes with aria-roledescription="Number field"
    const numberInputs = screen.getAllByRole('textbox');
    // First two textboxes are time inputs, next are value inputs
    // For three keyframes with 2 number inputs each (time + value), that's 6 textboxes
    // The second textbox (index 1) is the value input for keyframe #0
    const valueInput = numberInputs[1];
    fireEvent.change(valueInput, { target: { value: '0.75' } });

    expect(onChange).toHaveBeenCalled();
  });

  it('shows validation errors for invalid keyframes', () => {
    const invalidKeyframes: Record<string, ClipKeyframe[]> = {
      opacity: [
        { time: 0, value: 'not-a-number' as unknown as number, interpolation: 'linear' },
      ],
    };

    render(
      <KeyframeInspector
        schema={numberParamSchema}
        keyframes={invalidKeyframes}
        currentTime={0}
        onChange={() => {}}
      />,
    );

    // Should show a validation error
    expect(screen.getByText(/expected finite number/)).toBeInTheDocument();
  });

  it('renders multiple parameters when schema has multiple entries', () => {
    render(
      <KeyframeInspector
        schema={multiParamSchema}
        keyframes={{}}
        currentTime={0}
        onChange={() => {}}
      />,
    );

    expect(screen.getByText('Speed')).toBeInTheDocument();
    expect(screen.getByText('Enabled')).toBeInTheDocument();
    expect(screen.getByText('Mode')).toBeInTheDocument();
    expect(screen.getByText('Tint Color')).toBeInTheDocument();

    const sections = screen.getAllByTestId('keyframe-parameter-section');
    expect(sections).toHaveLength(4);
  });

  it('shows boolean select for boolean parameters', () => {
    const boolKeyframes: Record<string, ClipKeyframe[]> = {
      enabled: [{ time: 0, value: true, interpolation: 'hold' }],
    };

    render(
      <KeyframeInspector
        schema={[multiParamSchema[1]]} // enabled boolean param
        keyframes={boolKeyframes}
        currentTime={0}
        onChange={() => {}}
      />,
    );

    // The interpolated value shows 'true', and the select trigger also shows 'true'
    const trueElements = screen.getAllByText('true');
    expect(trueElements.length).toBeGreaterThanOrEqual(1);
  });

  it('shows color input for color parameters', () => {
    const colorKeyframes: Record<string, ClipKeyframe[]> = {
      tint: [{ time: 0, value: '#ff0000', interpolation: 'linear' }],
    };

    const { container } = render(
      <KeyframeInspector
        schema={[multiParamSchema[3]]} // tint color param
        keyframes={colorKeyframes}
        currentTime={0}
        onChange={() => {}}
      />,
    );

    // Should have a color input
    const colorInputs = container.querySelectorAll('input[type="color"]');
    expect(colorInputs.length).toBeGreaterThan(0);
  });

  it('shows interpolation mode selector for each keyframe', () => {
    render(
      <KeyframeInspector
        schema={numberParamSchema}
        keyframes={sampleKeyframes}
        currentTime={0}
        onChange={() => {}}
      />,
    );

    // The third keyframe (index 2) uses 'hold' interpolation
    expect(screen.getByText('hold')).toBeInTheDocument();
    // Other keyframes use 'linear'
    const linearElements = screen.getAllByText('linear');
    expect(linearElements.length).toBeGreaterThan(0);
  });

  it('disables controls when disabled prop is true', () => {
    render(
      <KeyframeInspector
        schema={numberParamSchema}
        keyframes={sampleKeyframes}
        currentTime={0}
        onChange={() => {}}
        disabled={true}
      />,
    );

    const addButton = screen.getByText(/Add keyframe/);
    expect(addButton).toBeDisabled();
  });

  it('removes parameter key from keyframes record when all keyframes are removed', () => {
    const singleKeyframe: Record<string, ClipKeyframe[]> = {
      opacity: [{ time: 0, value: 0.5, interpolation: 'linear' }],
    };

    const onChange = vi.fn();
    render(
      <KeyframeInspector
        schema={numberParamSchema}
        keyframes={singleKeyframe}
        currentTime={0}
        onChange={onChange}
      />,
    );

    fireEvent.click(screen.getByLabelText(/Remove keyframe/));
    expect(onChange).toHaveBeenCalledTimes(1);

    const updatedKeyframes = onChange.mock.calls[0][0] as Record<string, ClipKeyframe[]>;
    expect(updatedKeyframes.opacity).toBeUndefined();
  });
});
