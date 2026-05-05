import {
  getLineEnd,
  parseEnvelope,
  stripMarkdownFences,
} from '../_shared/promptEnvelope.ts';

export type EffectCategory = 'entrance' | 'exit' | 'continuous';

type ParameterType = 'number' | 'select' | 'boolean' | 'color' | 'audio-binding';

interface ParameterOption {
  label: string;
  value: string;
}

interface ParameterDefinition {
  name: string;
  label: string;
  description: string;
  type: ParameterType;
  default?: number | string | boolean | { source: string; min: number; max: number };
  min?: number;
  max?: number;
  step?: number;
  options?: ParameterOption[];
}

interface ExtractedEffectMeta {
  code: string;
  name: string;
  description: string;
  parameterSchema: ParameterDefinition[];
  message: string;
}

export interface BuildGenerateEffectMessagesInput {
  prompt: string;
  name?: string;
  category: EffectCategory;
  existingCode?: string;
  /** When set, the effect failed validation and needs a targeted fix. */
  validationError?: string;
}

const EFFECT_COMPONENT_CONTRACT = `EffectComponentProps interface:
type EffectComponentProps = {
  children: React.ReactNode;
  durationInFrames: number;
  effectFrames?: number;
  intensity?: number;
  params?: Record<string, unknown>;
};`;

export const AVAILABLE_GLOBALS = `Available globals at runtime (use EXACTLY these names — no variations):
- React
- useCurrentFrame (NOT useCurrentFrames, NOT useFrame)
- useVideoConfig
- interpolate(value, inputRange, outputRange, options?)
- spring({ frame, fps, durationInFrames?, config? })
- AbsoluteFill
- useAudioReactive() -> { amplitude, bass, mid, treble, isBeat, frequencyBins }
- useAudioParam(binding) -> number`;

const OUTPUT_RULES = `Output requirements:
- Return only executable JavaScript/TypeScript component code
- Do not wrap the answer in markdown fences
- Do not include import statements
- Do not include export statements
- Begin with a single metadata line: // NAME: <fun, playful, creative effect name — be witty and memorable, like naming a cocktail or a wrestling move, 2-4 words>
- Follow with: // DESCRIPTION: <one concise effect description>
- Follow with: // PARAMS: <JSON array of parameter definitions>
- Follow with: // MESSAGE: <brief note>
- Use [] for // PARAMS when the effect does not need user-adjustable controls
- Each parameter definition must include name, label, description, type, and default
- Number params may include min, max, and step
- Select params must include options as [{ "label": string, "value": string }]
- Audio-binding params must use type: "audio-binding" and default: { "source": "bass" | "mid" | "treble" | "amplitude", "min": number, "max": number }
- Use React.createElement(...) instead of JSX
- Set the component using exports.default = ComponentName
- The default export must be a function component compatible with EffectComponentProps
- CRITICAL: The children (video/image) must ALWAYS remain visible as the primary content.
  The standard pattern is: render children FIRST as the base layer, then add effect
  overlays (particles, glows, borders, etc.) on top with pointerEvents:'none'.
  You may also apply CSS transforms (scale, rotate, translate) or filters (blur,
  brightness, hue-rotate) to the children wrapper div — but children must be visible.
  Do NOT bury children inside complex blend-mode chains that obscure them.
- Read user-adjustable values from the params prop (e.g. params?.drift ?? 1), NOT as top-level props
- Children may be images, videos, or complex elements — NOT just text.
  CSS \`color\` only affects text foreground; it does NOT tint images or videos.
  For color-channel effects (chromatic aberration, RGB split, color isolation),
  use CSS mix-blend-mode:multiply with colored overlay divs to isolate channels
  (e.g. multiply with #ff0000 keeps only the red channel). Wrap each channel layer
  in isolation:isolate to scope the blend. IMPORTANT: children may have transparent
  areas (objectFit:contain letterboxing). Always add a black backdrop div (position:
  absolute, inset:0, background:#000) BEFORE children inside each blend layer —
  without this, multiply against transparent produces the overlay color, not black,
  and screen-combining colored channels produces white bars.
  Do NOT use SVG feColorMatrix (blocked on cross-origin images) or CSS \`color\`
  (only affects text, not images/videos).
- Use useVideoConfig() to get width/height, and express spatial values (offsets,
  drift, blur radius) as a percentage of the composition width — NOT fixed pixels.
  The preview renders at 320×320 but the timeline renders at 1920×1080+.
  Fixed pixel values that look dramatic in preview will be invisible on timeline.
- NEVER use Math.random() in the render path — Remotion renders each frame
  independently, so random values change between renders making output
  non-deterministic. Use deterministic math based on frame number instead
  (e.g. Math.sin(frame * seed), or a simple hash on an index).
  The ONLY safe place for Math.random() is inside React.useMemo(() => ..., [])
  for one-time values like unique SVG filter IDs.
- If using inline SVG filter IDs, generate unique IDs with React.useMemo to avoid
  collisions when multiple clips use the same effect (e.g. React.useMemo(() =>
  "myeffect-" + Math.random().toString(36).slice(2,8), [])).`;

const CATEGORY_GUIDANCE: Record<EffectCategory, string> = {
  entrance: `Category guidance: entrance
- Animate the content into view during the opening effectFrames
- Treat effectFrames as the primary animation window
- After the entrance completes, keep the content stable for the rest of durationInFrames
- Clamp progress so the entrance does not continue past effectFrames`,
  exit: `Category guidance: exit
- Animate the content out during the final effectFrames of the clip
- Keep the content stable before the exit window begins
- Compute the exit window from the tail of durationInFrames
- A common pattern is deriving exitStart = Math.max(0, durationInFrames - (effectFrames ?? fallback))`,
  continuous: `Category guidance: continuous
- Animate across the full durationInFrames instead of only the start or end
- Use durationInFrames as the primary timeline span
- effectFrames is optional for accents, but the main motion should read across the whole clip
- The content should remain visible and animated throughout the clip`,
};

const VALIDATION_RULES = `Validation rules:
- The code must contain exports.default =
- The code must not contain import or export statements
- The code must use React.createElement or React.Fragment instead of JSX syntax`;

export function buildGenerateEffectMessages(input: BuildGenerateEffectMessagesInput): {
  systemMsg: string;
  userMsg: string;
} {
  const { prompt, name, category, existingCode, validationError } = input;

  let modeInstructions: string;

  if (validationError && existingCode?.trim()) {
    // Retry mode: the previous generation failed validation
    modeInstructions = `Fix mode:
- The code below was generated for this effect but FAILED validation with this error:

  ERROR: ${validationError}

- Fix ONLY the issue described in the error. Keep everything else the same.
- The rest of the effect logic, structure, and component name are fine — just fix the specific problem.
- Make sure the fix follows the output requirements and validation rules above.

Code that needs fixing:
\`\`\`ts
${existingCode.trim()}
\`\`\``;
  } else if (existingCode?.trim()) {
    modeInstructions = `Edit mode:
- You are making a TARGETED EDIT to an existing, working effect
- CRITICAL: Start from the existing code below and modify ONLY what the user asked for
- Do NOT rewrite the effect from scratch — preserve the existing structure, variable names, and logic
- If the user asks to change one aspect (e.g. direction, speed, color), change ONLY that aspect
- The existing code is already valid and working — your job is to apply a surgical edit
- Keep the same component name and overall approach

Existing code (modify this, do not replace it):
\`\`\`ts
${existingCode.trim()}
\`\`\``;
  } else {
    modeInstructions = `Creation mode:
- Generate a new custom effect from scratch
- Pick a clear component name that matches the effect`;
  }

  const systemMsg = `You are an AI assistant for a video effect creation tool.

TRIAGE:
- First decide whether the user's latest request is a QUESTION MODE request or an EFFECT MODE request.
- QUESTION MODE: The user is asking for an explanation, advice, clarification, brainstorming help, or other conversational guidance instead of asking you to create or edit effect code.
- EFFECT MODE: The user wants a new effect, a revision to an existing effect, or a fix to effect code.
- QUESTION MODE example: "What kind of entrance effect would feel energetic for a sports intro?"
- EFFECT MODE example: "Make the shake faster and add a cyan glow."
- In QUESTION MODE, do NOT generate code. Respond with:
  // QUESTION_RESPONSE
  <your conversational answer for the user>
- In EFFECT MODE, follow all EFFECT MODE rules below and return code with the required metadata.

EFFECT MODE rules:

${EFFECT_COMPONENT_CONTRACT}

${AVAILABLE_GLOBALS}

${OUTPUT_RULES}

${VALIDATION_RULES}`;

  const userMsg = `User request for a ${category} effect${name ? ` called "${name}"` : ''}:
"${prompt}"

${CATEGORY_GUIDANCE[category]}

${modeInstructions}

Implementation guidance:
- The effect should be production-ready and visually clear on a generic clip
- Keep the logic self-contained in one component
- Prefer readable math and interpolation ranges
- Use effectFrames fallback values when needed so the effect works if the prop is undefined
- Avoid browser APIs or unsupported globals

If this is QUESTION MODE, return only the conversational response.
If this is EFFECT MODE, return only the final code plus the required metadata lines.`;

  return { systemMsg, userMsg };
}

const QUESTION_RESPONSE_MARKER = /^\s*\/\/\s*QUESTION_RESPONSE\s*$/im;

function sanitizeParameterSchema(value: unknown): ParameterDefinition[] {
  if (!Array.isArray(value)) {
    return [];
  }

  return value.filter((entry): entry is ParameterDefinition => {
    return typeof entry === 'object' && entry !== null && typeof (entry as { name?: unknown }).name === 'string';
  });
}

export function extractQuestionResponse(responseText: string): { isQuestion: true; message: string } | null {
  const normalized = stripMarkdownFences(responseText);
  const match = QUESTION_RESPONSE_MARKER.exec(normalized);

  if (!match || match.index === undefined) {
    return null;
  }

  const markerEnd = getLineEnd(normalized, match.index);

  return {
    isQuestion: true,
    message: normalized.slice(markerEnd).trim(),
  };
}

export function extractEffectCodeAndMeta(responseText: string): ExtractedEffectMeta {
  const { values, jsonValues, codeBody } = parseEnvelope(
    responseText,
    ['NAME', 'DESCRIPTION', 'PARAMS', 'MESSAGE'],
    { jsonArrayFields: ['PARAMS'] },
  );

  // Auto-fix common LLM typos before validation
  const code = codeBody
    .replace(/\buseCurrentFrames\b/g, 'useCurrentFrame')
    .replace(/\buseFrame\b(?!s)/g, 'useCurrentFrame')
    .replace(/\buseConfig\b/g, 'useVideoConfig')
    .replace(/\bAbsoluteFills\b/g, 'AbsoluteFill')
    .replace(/\buseAudioReactives\b/g, 'useAudioReactive')
    .replace(/\binterpolates\b/g, 'interpolate');

  validateExtractedEffectCode(code);

  return {
    code,
    name: values.NAME ?? '',
    description: values.DESCRIPTION ?? '',
    parameterSchema: sanitizeParameterSchema(jsonValues.PARAMS),
    message: values.MESSAGE ?? '',
  };
}

export function extractEffectCode(responseText: string): string {
  return extractEffectCodeAndMeta(responseText).code;
}

const KNOWN_TYPOS: Array<[RegExp, string]> = [
  [/\buseCurrentFrames\b/, 'useCurrentFrames should be useCurrentFrame (no "s")'],
  [/\buseFrame\b(?!s)/, 'useFrame should be useCurrentFrame'],
  [/\buseConfig\b/, 'useConfig should be useVideoConfig'],
  [/\bAbsoluteFills\b/, 'AbsoluteFills should be AbsoluteFill (no "s")'],
  [/\buseAudioReactives\b/, 'useAudioReactives should be useAudioReactive (no trailing "s")'],
  [/\binterpolates\b/, 'interpolates should be interpolate (no "s")'],
];

export function validateExtractedEffectCode(code: string): void {
  if (!code.trim()) {
    throw new Error('Effect generation returned empty code');
  }

  if (!code.includes('exports.default')) {
    throw new Error('Generated effect code must assign the component with exports.default = ComponentName');
  }

  if (/\bimport\s.+from\s/m.test(code) || /^\s*import\s/m.test(code)) {
    throw new Error('Generated effect code must not include import statements');
  }

  if (/^\s*export\s/m.test(code)) {
    throw new Error('Generated effect code must not include export statements');
  }

  if (!code.includes('React.createElement')) {
    throw new Error('Generated effect code must use React.createElement instead of JSX');
  }

  // Math.random() creates non-deterministic renders — each frame capture gets
  // different values, causing flicker and inconsistent output.
  // Allow it only inside React.useMemo (for one-time IDs like SVG filter IDs).
  const codeWithoutMemos = code.replace(/React\.useMemo\([^)]*Math\.random\(\)[^)]*\)/g, '');
  if (/\bMath\.random\s*\(/.test(codeWithoutMemos)) {
    throw new Error('Generated effect must not use Math.random() — use deterministic math based on frame number instead');
  }

  for (const [pattern, message] of KNOWN_TYPOS) {
    if (pattern.test(code)) {
      throw new Error(`Generated code contains a typo: ${message}`);
    }
  }
}
