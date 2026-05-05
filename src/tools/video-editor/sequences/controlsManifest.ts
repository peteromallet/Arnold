/**
 * Controls manifest for AI-generated sequence components.
 *
 * The agent emits this alongside the component code so the editor can render
 * user-facing controls without us hardcoding any parallel render path. Mirrors
 * the JSON-sequence param shape (defineClipType.ts) but adds:
 *   - a fixed enum of widget types (we do NOT let the agent invent new ones)
 *   - a `priority` field that drives layout: primary = own full-width row,
 *     secondary = grouped 2-3 per row.
 *
 * Backwards compat: existing AI sequences without a manifest are treated as
 * "no controls". We don't migrate; users can regenerate to get controls.
 */

export const CONTROL_TYPES = [
  'number',
  'boolean',
  'text',
  'color',
  'enum',
  'slider',
] as const;

export type ControlType = (typeof CONTROL_TYPES)[number];

export type ControlPriority = 'primary' | 'secondary';

export interface BaseControlManifestEntry {
  name: string;
  label: string;
  priority: ControlPriority;
  type: ControlType;
  description?: string;
}

export interface NumberControl extends BaseControlManifestEntry {
  type: 'number';
  default: number;
  min?: number;
  max?: number;
  step?: number;
}

export interface SliderControl extends BaseControlManifestEntry {
  type: 'slider';
  default: number;
  min: number;
  max: number;
  step?: number;
}

export interface BooleanControl extends BaseControlManifestEntry {
  type: 'boolean';
  default: boolean;
}

export interface TextControl extends BaseControlManifestEntry {
  type: 'text';
  default: string;
}

export interface ColorControl extends BaseControlManifestEntry {
  type: 'color';
  default: string;
}

export interface EnumControl extends BaseControlManifestEntry {
  type: 'enum';
  default: string;
  options: readonly string[];
}

export type ControlManifestEntry =
  | NumberControl
  | SliderControl
  | BooleanControl
  | TextControl
  | ColorControl
  | EnumControl;

export type ControlsManifest = readonly ControlManifestEntry[];

export interface ControlsManifestValidationError {
  controlName?: string;
  message: string;
}

export interface ValidateControlsManifestOptions {
  /**
   * The component source. When provided, we cross-check that every manifest
   * entry's `name` is referenced via `params.X` somewhere in the code AND
   * that every `params.X` referenced by the code has a manifest entry.
   *
   * Pass `undefined` to skip code coverage (e.g. when editing values only).
   */
  code?: string;
}

const NAME_RE = /^[A-Za-z_$][\w$]*$/;
const HEX_COLOR_RE = /^#[0-9a-fA-F]{3,8}$/;

const isFiniteNumber = (value: unknown): value is number =>
  typeof value === 'number' && Number.isFinite(value);

const isPlainObject = (value: unknown): value is Record<string, unknown> =>
  Boolean(value) && typeof value === 'object' && !Array.isArray(value);

function validateEntry(
  entry: unknown,
  index: number,
  errors: ControlsManifestValidationError[],
  seenNames: Set<string>,
): void {
  if (!isPlainObject(entry)) {
    errors.push({ message: `Control at index ${index} is not an object` });
    return;
  }

  const name = entry.name;
  if (typeof name !== 'string' || name.trim().length === 0) {
    errors.push({ message: `Control at index ${index} is missing a non-empty name` });
    return;
  }
  if (!NAME_RE.test(name)) {
    errors.push({
      controlName: name,
      message: `Control name "${name}" must be a valid JS identifier ([A-Za-z_$][\\w$]*)`,
    });
  }
  if (seenNames.has(name)) {
    errors.push({ controlName: name, message: `Duplicate control name "${name}"` });
  }
  seenNames.add(name);

  const type = entry.type;
  if (typeof type !== 'string' || !(CONTROL_TYPES as readonly string[]).includes(type)) {
    errors.push({
      controlName: name,
      message: `Control "${name}" has invalid type "${String(type)}". Allowed: ${CONTROL_TYPES.join(', ')}`,
    });
    return;
  }

  if (typeof entry.label !== 'string' || entry.label.trim().length === 0) {
    errors.push({ controlName: name, message: `Control "${name}" is missing a non-empty label` });
  }

  const priority = entry.priority;
  if (priority !== 'primary' && priority !== 'secondary') {
    errors.push({
      controlName: name,
      message: `Control "${name}" must declare priority as "primary" or "secondary" (got ${JSON.stringify(priority)})`,
    });
  }

  if (!Object.prototype.hasOwnProperty.call(entry, 'default')) {
    errors.push({ controlName: name, message: `Control "${name}" is missing a default value` });
    return;
  }
  const def = entry.default;

  switch (type) {
    case 'number': {
      if (!isFiniteNumber(def)) {
        errors.push({ controlName: name, message: `Control "${name}" default must be a finite number` });
      }
      if (entry.min !== undefined && !isFiniteNumber(entry.min)) {
        errors.push({ controlName: name, message: `Control "${name}" min must be a finite number when set` });
      }
      if (entry.max !== undefined && !isFiniteNumber(entry.max)) {
        errors.push({ controlName: name, message: `Control "${name}" max must be a finite number when set` });
      }
      if (entry.step !== undefined && !isFiniteNumber(entry.step)) {
        errors.push({ controlName: name, message: `Control "${name}" step must be a finite number when set` });
      }
      if (
        isFiniteNumber(entry.min) && isFiniteNumber(entry.max) && entry.min > entry.max
      ) {
        errors.push({ controlName: name, message: `Control "${name}" min is greater than max` });
      }
      break;
    }
    case 'slider': {
      if (!isFiniteNumber(def)) {
        errors.push({ controlName: name, message: `Slider "${name}" default must be a finite number` });
      }
      if (!isFiniteNumber(entry.min)) {
        errors.push({ controlName: name, message: `Slider "${name}" requires a finite min` });
      }
      if (!isFiniteNumber(entry.max)) {
        errors.push({ controlName: name, message: `Slider "${name}" requires a finite max` });
      }
      if (entry.step !== undefined && !isFiniteNumber(entry.step)) {
        errors.push({ controlName: name, message: `Slider "${name}" step must be a finite number when set` });
      }
      if (
        isFiniteNumber(entry.min) && isFiniteNumber(entry.max) && (entry.min as number) > (entry.max as number)
      ) {
        errors.push({ controlName: name, message: `Slider "${name}" min is greater than max` });
      }
      break;
    }
    case 'boolean': {
      if (typeof def !== 'boolean') {
        errors.push({ controlName: name, message: `Control "${name}" default must be a boolean` });
      }
      break;
    }
    case 'text': {
      if (typeof def !== 'string') {
        errors.push({ controlName: name, message: `Control "${name}" default must be a string` });
      }
      break;
    }
    case 'color': {
      if (typeof def !== 'string' || !HEX_COLOR_RE.test(def)) {
        errors.push({
          controlName: name,
          message: `Control "${name}" default must be a hex color like "#rrggbb"`,
        });
      }
      break;
    }
    case 'enum': {
      const options = entry.options;
      if (!Array.isArray(options) || options.length === 0) {
        errors.push({ controlName: name, message: `Enum "${name}" requires a non-empty options array` });
      } else if (!options.every((o) => typeof o === 'string' && o.length > 0)) {
        errors.push({ controlName: name, message: `Enum "${name}" options must be non-empty strings` });
      } else if (typeof def !== 'string' || !options.includes(def)) {
        errors.push({
          controlName: name,
          message: `Enum "${name}" default must be one of its options`,
        });
      }
      break;
    }
  }
}

const PARAMS_REFERENCE_RE = /\bparams\s*(?:\.\s*([A-Za-z_$][\w$]*)|\[\s*"([^"\\]+)"\s*\]|\[\s*'([^'\\]+)'\s*\])/g;

function collectParamReferences(code: string): Set<string> {
  const refs = new Set<string>();
  let match: RegExpExecArray | null;
  while ((match = PARAMS_REFERENCE_RE.exec(code)) !== null) {
    const name = match[1] ?? match[2] ?? match[3];
    if (name) refs.add(name);
  }
  return refs;
}

/**
 * Validate a controls manifest. Returns ok=true with a typed manifest, or
 * ok=false with a list of human-readable errors. When `code` is provided,
 * also enforces that every manifest entry is consumed in the component code
 * AND every code-side `params.X` access has a matching manifest entry.
 */
export function validateControlsManifest(
  manifest: unknown,
  options: ValidateControlsManifestOptions = {},
):
  | { ok: true; manifest: ControlsManifest }
  | { ok: false; errors: ControlsManifestValidationError[] } {
  const errors: ControlsManifestValidationError[] = [];

  if (!Array.isArray(manifest)) {
    return { ok: false, errors: [{ message: 'Controls manifest must be a JSON array' }] };
  }

  const seenNames = new Set<string>();
  manifest.forEach((entry, index) => validateEntry(entry, index, errors, seenNames));

  if (errors.length === 0 && options.code !== undefined) {
    const codeRefs = collectParamReferences(options.code);
    const manifestNames = new Set(seenNames);
    for (const name of manifestNames) {
      if (!codeRefs.has(name)) {
        errors.push({
          controlName: name,
          message: `Control "${name}" is declared but never read as params.${name} in the component code`,
        });
      }
    }
    for (const ref of codeRefs) {
      if (!manifestNames.has(ref)) {
        errors.push({
          controlName: ref,
          message: `Component reads params.${ref} but no controls manifest entry declares "${ref}"`,
        });
      }
    }
  }

  if (errors.length > 0) {
    return { ok: false, errors };
  }
  return { ok: true, manifest: manifest as ControlsManifest };
}

/**
 * Build the default values map from a validated manifest. Use this to seed
 * `params` for a freshly-generated component.
 */
export function buildDefaultsFromManifest(manifest: ControlsManifest): Record<string, unknown> {
  const defaults: Record<string, unknown> = {};
  for (const entry of manifest) {
    defaults[entry.name] = entry.default;
  }
  return defaults;
}

export function isPrimaryControl(entry: ControlManifestEntry): boolean {
  return entry.priority === 'primary';
}

export function isSecondaryControl(entry: ControlManifestEntry): boolean {
  return entry.priority === 'secondary';
}
