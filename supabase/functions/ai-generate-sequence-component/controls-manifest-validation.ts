// Server-side validator for the CONTROLS manifest emitted by the agent.
//
// Mirrors src/tools/video-editor/sequences/controlsManifest.ts. Kept as a
// Deno-flavored copy because edge functions can't reach into src/. Both
// validators MUST stay in sync — they enforce the same contract surfaced to
// the model in templates.ts (Controls manifest contract section).

const CONTROL_TYPES = ['number', 'boolean', 'text', 'color', 'enum', 'slider'] as const;
const NAME_RE = /^[A-Za-z_$][\w$]*$/;
const HEX_COLOR_RE = /^#[0-9a-fA-F]{3,8}$/;

/** params.X / params["X"] / params['X'] — covers what the model will emit. */
const PARAMS_REFERENCE_RE = /\bparams\s*(?:\.\s*([A-Za-z_$][\w$]*)|\[\s*"([^"\\]+)"\s*\]|\[\s*'([^'\\]+)'\s*\])/g;

/** Asset-key/URL-array params are managed by the asset picker, not CONTROLS. */
const RESERVED_NON_CONTROL_PARAMS = new Set([
  'imageAssetKeys',
  'videoAssetKeys',
  'images',
  'videos',
]);

const isFiniteNumber = (value: unknown): value is number =>
  typeof value === 'number' && Number.isFinite(value);

const isPlainObject = (value: unknown): value is Record<string, unknown> =>
  Boolean(value) && typeof value === 'object' && !Array.isArray(value);

function collectParamReferences(code: string): Set<string> {
  const refs = new Set<string>();
  let match: RegExpExecArray | null;
  while ((match = PARAMS_REFERENCE_RE.exec(code)) !== null) {
    const name = match[1] ?? match[2] ?? match[3];
    if (name) refs.add(name);
  }
  return refs;
}

function validateEntry(
  entry: unknown,
  index: number,
  errors: string[],
  seenNames: Set<string>,
): void {
  if (!isPlainObject(entry)) {
    errors.push(`Control at index ${index} is not an object`);
    return;
  }

  const name = entry.name;
  if (typeof name !== 'string' || name.trim().length === 0) {
    errors.push(`Control at index ${index} is missing a non-empty name`);
    return;
  }
  if (!NAME_RE.test(name)) {
    errors.push(`Control name "${name}" must be a valid JS identifier`);
  }
  if (seenNames.has(name)) {
    errors.push(`Duplicate control name "${name}"`);
  }
  seenNames.add(name);

  if (typeof entry.label !== 'string' || entry.label.trim().length === 0) {
    errors.push(`Control "${name}" is missing a non-empty label`);
  }

  const priority = entry.priority;
  if (priority !== 'primary' && priority !== 'secondary') {
    errors.push(`Control "${name}" must declare priority as "primary" or "secondary" (got ${JSON.stringify(priority)})`);
  }

  const type = entry.type;
  if (typeof type !== 'string' || !(CONTROL_TYPES as readonly string[]).includes(type)) {
    errors.push(`Control "${name}" has invalid type "${String(type)}". Allowed: ${CONTROL_TYPES.join(', ')}`);
    return;
  }

  if (!Object.prototype.hasOwnProperty.call(entry, 'default')) {
    errors.push(`Control "${name}" is missing a default value`);
    return;
  }
  const def = entry.default;

  switch (type) {
    case 'number': {
      if (!isFiniteNumber(def)) errors.push(`Control "${name}" default must be a finite number`);
      if (entry.min !== undefined && !isFiniteNumber(entry.min)) errors.push(`Control "${name}" min must be a finite number when set`);
      if (entry.max !== undefined && !isFiniteNumber(entry.max)) errors.push(`Control "${name}" max must be a finite number when set`);
      if (entry.step !== undefined && !isFiniteNumber(entry.step)) errors.push(`Control "${name}" step must be a finite number when set`);
      if (isFiniteNumber(entry.min) && isFiniteNumber(entry.max) && entry.min > entry.max) {
        errors.push(`Control "${name}" min is greater than max`);
      }
      break;
    }
    case 'slider': {
      if (!isFiniteNumber(def)) errors.push(`Slider "${name}" default must be a finite number`);
      if (!isFiniteNumber(entry.min)) errors.push(`Slider "${name}" requires a finite min`);
      if (!isFiniteNumber(entry.max)) errors.push(`Slider "${name}" requires a finite max`);
      if (entry.step !== undefined && !isFiniteNumber(entry.step)) errors.push(`Slider "${name}" step must be a finite number when set`);
      if (isFiniteNumber(entry.min) && isFiniteNumber(entry.max) && (entry.min as number) > (entry.max as number)) {
        errors.push(`Slider "${name}" min is greater than max`);
      }
      break;
    }
    case 'boolean': {
      if (typeof def !== 'boolean') errors.push(`Control "${name}" default must be a boolean`);
      break;
    }
    case 'text': {
      if (typeof def !== 'string') errors.push(`Control "${name}" default must be a string`);
      break;
    }
    case 'color': {
      if (typeof def !== 'string' || !HEX_COLOR_RE.test(def)) {
        errors.push(`Control "${name}" default must be a hex color like "#rrggbb"`);
      }
      break;
    }
    case 'enum': {
      const options = entry.options;
      if (!Array.isArray(options) || options.length === 0) {
        errors.push(`Enum "${name}" requires a non-empty options array`);
      } else if (!options.every((o) => typeof o === 'string' && o.length > 0)) {
        errors.push(`Enum "${name}" options must be non-empty strings`);
      } else if (typeof def !== 'string' || !options.includes(def)) {
        errors.push(`Enum "${name}" default must be one of its options`);
      }
      break;
    }
  }
}

/**
 * Validates the CONTROLS manifest standalone AND cross-checks it against the
 * component code: every manifest entry must be read as `params.X`, and every
 * `params.X` access (excluding asset-key/URL fields) must have a manifest
 * entry. Throws on first failure (matches the existing validator style in
 * sequence-component-validation.ts).
 */
export function validateControlsManifestForCode(
  manifest: unknown,
  code: string,
): void {
  if (!Array.isArray(manifest)) {
    throw new Error('CONTROLS must be a JSON array');
  }

  const errors: string[] = [];
  const seenNames = new Set<string>();
  manifest.forEach((entry, index) => validateEntry(entry, index, errors, seenNames));

  if (errors.length === 0) {
    const codeRefs = collectParamReferences(code);
    for (const name of seenNames) {
      if (!codeRefs.has(name)) {
        errors.push(`Control "${name}" is declared but never read as params.${name} in the component code`);
      }
    }
    for (const ref of codeRefs) {
      if (RESERVED_NON_CONTROL_PARAMS.has(ref)) continue;
      if (!seenNames.has(ref)) {
        errors.push(`Component reads params.${ref} but no controls manifest entry declares "${ref}"`);
      }
    }
  }

  if (errors.length > 0) {
    throw new Error(`Invalid CONTROLS manifest: ${errors.join('; ')}`);
  }
}
