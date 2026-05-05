import { parseEnvelope } from '../_shared/promptEnvelope.ts';
import { validateSequenceComponentCode } from './sequence-component-validation.ts';

export interface ExistingSequenceComponent {
  code: string;
  schema: object;
  defaults: object;
}

export interface BuildGenerateSequenceComponentMessagesInput {
  prompt: string;
  name?: string;
  themeId?: string;
  existingComponent?: ExistingSequenceComponent;
  allowedAssetKeys: readonly string[];
  selectedClips?: unknown;
  attachedClips?: unknown;
  theme?: unknown;
  themeOverrides?: unknown;
  /** When set, the component failed validation and needs a targeted fix. */
  validationError?: string;
}

interface ExtractedSequenceComponentMeta {
  code: string;
  name: string;
  description: string;
  schemaJson: object;
  defaultsJson: object;
  message: string;
}

const SEQUENCE_COMPONENT_CONTRACT = `Sequence component contract:
- Default-export a React function component via \`exports.default = ComponentName\`.
- The component receives props: { clip, params, theme, fps }.
  - clip: a ResolvedTimelineClip describing the clip's timing, asset, and metadata.
  - params: a Record<string, unknown> populated from the SCHEMA you generate (see DEFAULTS).
  - theme: an optional RuntimeTheme. Read it via the useTheme() global, do NOT inline theme tokens.
  - fps: the composition fps (number).
- JSX is allowed (transpiled at runtime).
- Do NOT import or export anything (no import/export statements at all).
- Components must be deterministic per frame — no Date.now(), performance.now(), or crypto.getRandomValues().
- Math.random() is allowed ONLY inside React.useMemo(() => …, []) for one-time values like SVG filter IDs.`;

export const AVAILABLE_SEQUENCE_GLOBALS = `Available globals at runtime (use EXACTLY these names — no imports needed):
- React
- useCurrentFrame
- useVideoConfig
- interpolate(value, inputRange, outputRange, options?)
- spring({ frame, fps, durationInFrames?, config? })
- AbsoluteFill
- Sequence
- Series
- Img
- Video
- Audio
- Easing
- useTheme  (returns RuntimeTheme; tokens like theme.tokens.color, theme.tokens.font)
- composeAnimations`;

const OUTPUT_RULES = `Output requirements:
- Return only executable component code — no markdown fences, no prose.
- Do not include import or export statements.
- Begin with these metadata lines, in order:
  // NAME: <fun, memorable component name (2-4 words)>
  // DESCRIPTION: <one concise sentence describing the visual>
  // SCHEMA: { "type": "object", "properties": { ... }, "required": [...] }
  // DEFAULTS: { ... }
  // MESSAGE: <brief note for the user>
- SCHEMA is JSON Schema (a JSON object). Every \`params.X\` access in your code MUST appear in SCHEMA.properties.
- DEFAULTS is a JSON object with one entry per SCHEMA property; values must be valid for the schema.
- After the metadata, write the component definition and assign it via \`exports.default = ComponentName\`.
- The default export MUST be a function component compatible with the contract above.
- Use useVideoConfig() and the fps prop to express timing in frames; do NOT use wall-clock APIs.
- Read all user-tunable values from the params prop (e.g. params.duration, params.color), never as top-level props.
- Express spatial values as percentages of the composition width — preview is small, timeline can be 1920×1080+.`;

const ASSET_KEY_CONTRACT = `Asset-key contract:
- The host injects a list of allowed asset keys (image and video) per generation.
- Declare keys in your SCHEMA + DEFAULTS as:
    params.imageAssetKeys: string[]   (one or more entries from the allowed list)
    params.videoAssetKeys: string[]   (likewise)
- At render time the host populates SIBLING URL arrays the component should READ FROM:
    params.images: string[]           (resolved URLs for imageAssetKeys, in order)
    params.videos: string[]           (resolved URLs for videoAssetKeys, in order)
  Render images via <Img src={(params.images ?? [])[0]} ... /> (and similarly for videos).
  NEVER read params.imageAssetKeys at render — those are keys the host translates into URLs.
- NEVER inline raw URLs in params or in code. The host resolves keys → URLs at render time.
- **If allowed asset keys are non-empty (the user attached/selected media), the component
  MUST visually display at least one of those assets as a primary, foreground visual element
  — not merely as a faint backdrop or placeholder.** A glow / vignette / particle field on its
  own is NOT enough; the user's image (or video) must be rendered prominently and visibly.
- If the user did not select assets, omit imageAssetKeys / videoAssetKeys from params; default to [].
- This mirrors how built-in sequence components like ImageJumpSequence consume images
  (declares imageAssetKeys, renders from params.images URL array).`;

const VALIDATION_RULES = `Validation rules (the host will reject your output if violated):
- The code must contain \`exports.default =\`.
- The code must NOT contain import or export statements.
- The code must NOT call Date.now(), performance.now(), or crypto.getRandomValues().
- Math.random() is allowed only inside React.useMemo(() => …, []).
- Every \`params.X\` reference must be present in SCHEMA.properties AND DEFAULTS.`;

export function buildGenerateSequenceComponentMessages(
  input: BuildGenerateSequenceComponentMessagesInput,
): { systemMsg: string; userMsg: string } {
  const {
    prompt,
    name,
    themeId,
    existingComponent,
    allowedAssetKeys,
    selectedClips,
    attachedClips,
    theme,
    themeOverrides,
    validationError,
  } = input;

  let modeInstructions: string;
  if (validationError && existingComponent?.code) {
    modeInstructions = `Fix mode:
- The previous component generation FAILED validation:

  ERROR: ${validationError}

- Fix ONLY the issue described in the error. Keep everything else the same — same SCHEMA fields,
  same DEFAULTS values, same component name.
- Re-emit the full envelope (NAME / DESCRIPTION / SCHEMA / DEFAULTS / MESSAGE) followed by the fixed code.

Code that needs fixing:
\`\`\`tsx
${existingComponent.code.trim()}
\`\`\`

Existing SCHEMA: ${JSON.stringify(existingComponent.schema)}
Existing DEFAULTS: ${JSON.stringify(existingComponent.defaults)}`;
  } else if (existingComponent?.code) {
    modeInstructions = `Edit mode:
- You are making a TARGETED EDIT to an existing, working sequence component.
- Start from the existing code below and modify ONLY what the user asked for.
- Preserve component name, structure, and existing SCHEMA fields unless the user's request
  requires changing them.
- Re-emit the full envelope (NAME / DESCRIPTION / SCHEMA / DEFAULTS / MESSAGE) followed by the
  edited code.

Existing code:
\`\`\`tsx
${existingComponent.code.trim()}
\`\`\`

Existing SCHEMA: ${JSON.stringify(existingComponent.schema)}
Existing DEFAULTS: ${JSON.stringify(existingComponent.defaults)}`;
  } else {
    modeInstructions = `Creation mode:
- Generate a new sequence component from scratch.
- Pick a clear component name that matches the visual idea.
- Define a small, opinionated SCHEMA — only the params the user is likely to tweak.`;
  }

  const assetKeysBlock = allowedAssetKeys.length > 0
    ? `Allowed asset keys (use these in params.imageAssetKeys / params.videoAssetKeys, never inline URLs):
${JSON.stringify([...allowedAssetKeys])}`
    : 'No allowed asset keys for this generation. Do not reference media assets in params or code.';

  const contextBlock = [
    selectedClips ? `Selected clips: ${JSON.stringify(selectedClips).slice(0, 2000)}` : null,
    attachedClips ? `Attached clips: ${JSON.stringify(attachedClips).slice(0, 2000)}` : null,
    theme ? `Theme: ${JSON.stringify(theme).slice(0, 1500)}` : null,
    themeOverrides ? `Theme overrides: ${JSON.stringify(themeOverrides).slice(0, 1500)}` : null,
    themeId ? `Theme id: ${themeId}` : null,
  ].filter(Boolean).join('\n');

  const systemMsg = `You are an AI assistant that generates Reigh sequence components.

A sequence component is a React component that renders inside a Remotion timeline clip. The host
compiles your code at runtime via Sucrase + new Function and renders it for the duration of the clip.

${SEQUENCE_COMPONENT_CONTRACT}

${AVAILABLE_SEQUENCE_GLOBALS}

${ASSET_KEY_CONTRACT}

${OUTPUT_RULES}

${VALIDATION_RULES}`;

  const userMsg = `User request${name ? ` for a sequence component called "${name}"` : ''}:
"${prompt}"

${assetKeysBlock}

${contextBlock || ''}

${modeInstructions}

Implementation guidance:
- Keep the component self-contained in a single function.
- Read every tunable from params; surface every params.X in SCHEMA + DEFAULTS.
- Prefer interpolate / spring for animation; avoid setInterval, requestAnimationFrame, etc.
- Use useTheme() for theme-aware tokens; do not inline theme color values.

Return only the metadata lines plus the final code.`;

  return { systemMsg, userMsg };
}

export function extractSequenceComponentCodeAndMeta(
  responseText: string,
): ExtractedSequenceComponentMeta {
  const { values, jsonValues, codeBody } = parseEnvelope(
    responseText,
    ['NAME', 'DESCRIPTION', 'SCHEMA', 'DEFAULTS', 'MESSAGE'],
    { jsonObjectFields: ['SCHEMA', 'DEFAULTS'] },
  );

  const schemaJson = (jsonValues.SCHEMA && typeof jsonValues.SCHEMA === 'object'
    ? jsonValues.SCHEMA as object
    : null);
  const defaultsJson = (jsonValues.DEFAULTS && typeof jsonValues.DEFAULTS === 'object'
    ? jsonValues.DEFAULTS as object
    : null);

  if (!schemaJson) {
    throw new Error('Generated sequence component is missing a valid // SCHEMA: { ... } block');
  }
  if (!defaultsJson) {
    throw new Error('Generated sequence component is missing a valid // DEFAULTS: { ... } block');
  }

  validateSequenceComponentCode(codeBody, schemaJson, defaultsJson);

  return {
    code: codeBody,
    name: values.NAME ?? '',
    description: values.DESCRIPTION ?? '',
    schemaJson,
    defaultsJson,
    message: values.MESSAGE ?? '',
  };
}
