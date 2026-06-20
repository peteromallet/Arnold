import type {
  DiagnosticSeverity,
  DiagnosticSourceRange,
  ShaderColorSpace,
  ShaderTextureFilter,
  ShaderTextureSourceKind,
  ShaderTextureWrap,
  ShaderUniformType,
} from '@reigh/editor-sdk';

export const SHADER_DIAGNOSTIC_CODES = {
  UNIFORM_UNSUPPORTED: 'shader/uniform-unsupported',
  TEXTURE_UNSUPPORTED: 'shader/texture-unsupported',
  COMPILE_ERROR: 'shader/compile-error',
  LINK_ERROR: 'shader/link-error',
} as const;

export type ShaderDiagnosticCode =
  (typeof SHADER_DIAGNOSTIC_CODES)[keyof typeof SHADER_DIAGNOSTIC_CODES];

export type ShaderCompileDiagnosticPhase = 'vertex' | 'fragment' | 'link';

export interface ShaderDiagnostic {
  readonly id: string;
  readonly severity: DiagnosticSeverity;
  readonly code: ShaderDiagnosticCode;
  readonly message: string;
  readonly extensionId?: string;
  readonly contributionId?: string;
  readonly sourceRange?: DiagnosticSourceRange;
  readonly detail?: Record<string, unknown>;
}

export interface ShaderValidationContext {
  readonly shaderId?: string;
  readonly extensionId?: string;
  readonly contributionId?: string;
}

export interface WebGLInfoLogParseOptions extends ShaderValidationContext {
  readonly phase?: ShaderCompileDiagnosticPhase;
  readonly source?: string;
}

const SUPPORTED_UNIFORM_TYPES = new Set<ShaderUniformType>([
  'float',
  'int',
  'bool',
  'vec2',
  'vec3',
  'vec4',
  'color',
  'enum',
  'textureRef',
  'frame',
  'time',
]);

const SUPPORTED_TEXTURE_SOURCE_KINDS = new Set<ShaderTextureSourceKind>([
  'clip-frame',
  'static-image-asset',
  'live-generated-frame',
]);

const SUPPORTED_COLOR_SPACES = new Set<ShaderColorSpace>(['srgb', 'linear']);
const SUPPORTED_TEXTURE_FILTERS = new Set<ShaderTextureFilter>(['nearest', 'linear']);
const SUPPORTED_TEXTURE_WRAPS = new Set<ShaderTextureWrap>([
  'clamp-to-edge',
  'repeat',
  'mirrored-repeat',
]);

const WEBGL_LOG_PATTERNS = [
  /^(ERROR|WARNING):\s*(\d+):(\d+)(?::(\d+)|\((\d+)\))?:\s*(.*)$/i,
  /^(\d+):(\d+)(?::(\d+)|\((\d+)\))?:\s*(ERROR|WARNING)?\s*:?\s*(.*)$/i,
  /^(ERROR|WARNING):\s*(.*)$/i,
];

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0;
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value);
}

function isFiniteNumberVector(value: unknown, length: number): value is readonly number[] {
  return Array.isArray(value) && value.length === length && value.every(isFiniteNumber);
}

function freezeDiagnostic(diagnostic: ShaderDiagnostic): ShaderDiagnostic {
  return Object.freeze({
    ...diagnostic,
    ...(diagnostic.sourceRange ? { sourceRange: Object.freeze({ ...diagnostic.sourceRange }) } : {}),
    ...(diagnostic.detail ? { detail: Object.freeze({ ...diagnostic.detail }) } : {}),
  });
}

function makeDiagnostic(
  context: ShaderValidationContext,
  code: ShaderDiagnosticCode,
  severity: DiagnosticSeverity,
  message: string,
  detail: Record<string, unknown>,
  idParts: readonly unknown[],
  sourceRange?: DiagnosticSourceRange,
): ShaderDiagnostic {
  return freezeDiagnostic({
    id: [
      'shader',
      code.replace(/^shader\//, ''),
      context.extensionId ?? 'host',
      context.contributionId ?? context.shaderId ?? 'anonymous',
      ...idParts.map((part) => String(part)),
    ].join(':'),
    severity,
    code,
    message,
    ...(context.extensionId ? { extensionId: context.extensionId } : {}),
    ...(context.contributionId ? { contributionId: context.contributionId } : {}),
    ...(sourceRange ? { sourceRange } : {}),
    detail: {
      ...(context.shaderId ? { shaderId: context.shaderId } : {}),
      ...detail,
    },
  });
}

function pushUnsupportedUniform(
  diagnostics: ShaderDiagnostic[],
  context: ShaderValidationContext,
  index: number | 'root',
  reason: string,
  detail: Record<string, unknown> = {},
): void {
  diagnostics.push(makeDiagnostic(
    context,
    SHADER_DIAGNOSTIC_CODES.UNIFORM_UNSUPPORTED,
    'error',
    `Unsupported shader uniform schema at ${index === 'root' ? 'uniforms' : `uniforms[${index}]`}: ${reason}.`,
    {
      index,
      reason,
      ...detail,
    },
    [index, reason],
  ));
}

function pushUnsupportedTexture(
  diagnostics: ShaderDiagnostic[],
  context: ShaderValidationContext,
  index: number | 'root',
  reason: string,
  detail: Record<string, unknown> = {},
): void {
  diagnostics.push(makeDiagnostic(
    context,
    SHADER_DIAGNOSTIC_CODES.TEXTURE_UNSUPPORTED,
    'error',
    `Unsupported shader texture schema at ${index === 'root' ? 'textures' : `textures[${index}]`}: ${reason}.`,
    {
      index,
      reason,
      ...detail,
    },
    [index, reason],
  ));
}

function validateOptionalNumber(
  value: unknown,
  field: string,
  diagnostics: ShaderDiagnostic[],
  context: ShaderValidationContext,
  index: number,
): void {
  if (value !== undefined && !isFiniteNumber(value)) {
    pushUnsupportedUniform(diagnostics, context, index, `${field} must be a finite number`, {
      field,
      actualType: typeof value,
    });
  }
}

function validateUniformDefault(
  uniform: Record<string, unknown>,
  diagnostics: ShaderDiagnostic[],
  context: ShaderValidationContext,
  index: number,
): void {
  if (uniform.default === undefined) return;

  const defaultValue = uniform.default;
  const type = uniform.type;
  let valid = false;
  let expected = '';

  switch (type) {
    case 'float':
    case 'frame':
    case 'time':
      valid = isFiniteNumber(defaultValue);
      expected = 'a finite number';
      break;
    case 'int':
      valid = Number.isInteger(defaultValue);
      expected = 'an integer';
      break;
    case 'bool':
      valid = typeof defaultValue === 'boolean';
      expected = 'a boolean';
      break;
    case 'vec2':
      valid = isFiniteNumberVector(defaultValue, 2);
      expected = 'a 2-number vector';
      break;
    case 'vec3':
      valid = isFiniteNumberVector(defaultValue, 3);
      expected = 'a 3-number vector';
      break;
    case 'vec4':
    case 'color':
      valid = isFiniteNumberVector(defaultValue, 4);
      expected = 'a 4-number vector';
      break;
    case 'enum':
      valid = typeof defaultValue === 'string';
      expected = 'an enum string value';
      break;
    case 'textureRef':
      valid = isRecord(defaultValue)
        && SUPPORTED_TEXTURE_SOURCE_KINDS.has(defaultValue.kind as ShaderTextureSourceKind)
        && (defaultValue.ref === undefined || typeof defaultValue.ref === 'string');
      expected = 'a textureRef object with a supported kind';
      break;
    default:
      return;
  }

  if (!valid) {
    pushUnsupportedUniform(diagnostics, context, index, `default for ${String(type)} must be ${expected}`, {
      field: 'default',
      uniformName: uniform.name,
      uniformType: type,
      expected,
    });
  }
}

function validateEnumOptions(
  uniform: Record<string, unknown>,
  diagnostics: ShaderDiagnostic[],
  context: ShaderValidationContext,
  index: number,
): void {
  if (uniform.type !== 'enum') return;
  if (!Array.isArray(uniform.options) || uniform.options.length === 0) {
    pushUnsupportedUniform(diagnostics, context, index, 'enum uniforms require at least one option', {
      field: 'options',
      uniformName: uniform.name,
    });
    return;
  }

  uniform.options.forEach((option, optionIndex) => {
    if (!isRecord(option) || !isNonEmptyString(option.label) || typeof option.value !== 'string') {
      pushUnsupportedUniform(diagnostics, context, index, 'enum options must include label and value strings', {
        field: `options[${optionIndex}]`,
        uniformName: uniform.name,
      });
    }
  });
}

export function validateShaderUniformSchema(
  uniforms: unknown,
  context: ShaderValidationContext = {},
): readonly ShaderDiagnostic[] {
  if (uniforms === undefined) return Object.freeze([]);

  const diagnostics: ShaderDiagnostic[] = [];
  if (!Array.isArray(uniforms)) {
    pushUnsupportedUniform(diagnostics, context, 'root', 'uniforms must be an array', {
      actualType: typeof uniforms,
    });
    return Object.freeze(diagnostics);
  }

  uniforms.forEach((uniform, index) => {
    if (!isRecord(uniform)) {
      pushUnsupportedUniform(diagnostics, context, index, 'uniform entries must be objects', {
        actualType: Array.isArray(uniform) ? 'array' : typeof uniform,
      });
      return;
    }

    if (!isNonEmptyString(uniform.name)) {
      pushUnsupportedUniform(diagnostics, context, index, 'uniform name must be a non-empty string', {
        field: 'name',
      });
    }
    if (!isNonEmptyString(uniform.label)) {
      pushUnsupportedUniform(diagnostics, context, index, 'uniform label must be a non-empty string', {
        field: 'label',
        uniformName: uniform.name,
      });
    }
    if (!SUPPORTED_UNIFORM_TYPES.has(uniform.type as ShaderUniformType)) {
      pushUnsupportedUniform(diagnostics, context, index, `uniform type "${String(uniform.type)}" is not supported`, {
        field: 'type',
        uniformName: uniform.name,
        uniformType: uniform.type,
        supportedTypes: [...SUPPORTED_UNIFORM_TYPES],
      });
      return;
    }

    validateOptionalNumber(uniform.min, 'min', diagnostics, context, index);
    validateOptionalNumber(uniform.max, 'max', diagnostics, context, index);
    validateOptionalNumber(uniform.step, 'step', diagnostics, context, index);
    validateUniformDefault(uniform, diagnostics, context, index);
    validateEnumOptions(uniform, diagnostics, context, index);
  });

  return Object.freeze(diagnostics);
}

export function validateShaderTextureSchema(
  textures: unknown,
  context: ShaderValidationContext = {},
): readonly ShaderDiagnostic[] {
  if (textures === undefined) return Object.freeze([]);

  const diagnostics: ShaderDiagnostic[] = [];
  if (!Array.isArray(textures)) {
    pushUnsupportedTexture(diagnostics, context, 'root', 'textures must be an array', {
      actualType: typeof textures,
    });
    return Object.freeze(diagnostics);
  }

  textures.forEach((texture, index) => {
    if (!isRecord(texture)) {
      pushUnsupportedTexture(diagnostics, context, index, 'texture entries must be objects', {
        actualType: Array.isArray(texture) ? 'array' : typeof texture,
      });
      return;
    }

    if (!isNonEmptyString(texture.name)) {
      pushUnsupportedTexture(diagnostics, context, index, 'texture name must be a non-empty string', {
        field: 'name',
      });
    }
    if (texture.label !== undefined && typeof texture.label !== 'string') {
      pushUnsupportedTexture(diagnostics, context, index, 'texture label must be a string when provided', {
        field: 'label',
        textureName: texture.name,
      });
    }
    if (texture.uniform !== undefined && !isNonEmptyString(texture.uniform)) {
      pushUnsupportedTexture(diagnostics, context, index, 'texture uniform must be a non-empty string when provided', {
        field: 'uniform',
        textureName: texture.name,
      });
    }
    if (!SUPPORTED_TEXTURE_SOURCE_KINDS.has(texture.sourceKind as ShaderTextureSourceKind)) {
      pushUnsupportedTexture(diagnostics, context, index, `texture source kind "${String(texture.sourceKind)}" is not supported`, {
        field: 'sourceKind',
        textureName: texture.name,
        sourceKind: texture.sourceKind,
        supportedSourceKinds: [...SUPPORTED_TEXTURE_SOURCE_KINDS],
      });
    }
    if (texture.required !== undefined && typeof texture.required !== 'boolean') {
      pushUnsupportedTexture(diagnostics, context, index, 'texture required must be a boolean when provided', {
        field: 'required',
        textureName: texture.name,
      });
    }
    if (texture.colorSpace !== undefined && !SUPPORTED_COLOR_SPACES.has(texture.colorSpace as ShaderColorSpace)) {
      pushUnsupportedTexture(diagnostics, context, index, `texture color space "${String(texture.colorSpace)}" is not supported`, {
        field: 'colorSpace',
        textureName: texture.name,
        colorSpace: texture.colorSpace,
        supportedColorSpaces: [...SUPPORTED_COLOR_SPACES],
      });
    }
    if (texture.filter !== undefined && !SUPPORTED_TEXTURE_FILTERS.has(texture.filter as ShaderTextureFilter)) {
      pushUnsupportedTexture(diagnostics, context, index, `texture filter "${String(texture.filter)}" is not supported`, {
        field: 'filter',
        textureName: texture.name,
        filter: texture.filter,
        supportedFilters: [...SUPPORTED_TEXTURE_FILTERS],
      });
    }
    if (texture.wrap !== undefined && !SUPPORTED_TEXTURE_WRAPS.has(texture.wrap as ShaderTextureWrap)) {
      pushUnsupportedTexture(diagnostics, context, index, `texture wrap "${String(texture.wrap)}" is not supported`, {
        field: 'wrap',
        textureName: texture.name,
        wrap: texture.wrap,
        supportedWraps: [...SUPPORTED_TEXTURE_WRAPS],
      });
    }
  });

  return Object.freeze(diagnostics);
}

function lineLengthAt(source: string | undefined, line: number): number | undefined {
  if (!source) return undefined;
  const lineText = source.split(/\r\n|\r|\n/)[Math.max(0, line - 1)];
  return lineText?.length;
}

function toSourceRange(
  line: number | undefined,
  column: number | undefined,
  source: string | undefined,
): DiagnosticSourceRange | undefined {
  if (!line || line < 1) return undefined;
  const startCol = column && column > 0 ? column : 1;
  const lineLength = lineLengthAt(source, line);
  const endCol = lineLength === undefined
    ? startCol + 1
    : Math.max(startCol + 1, Math.min(lineLength + 1, startCol + 1));

  return Object.freeze({
    startLine: line,
    startCol,
    endLine: line,
    endCol,
  });
}

function severityFrom(value: string | undefined, message: string): DiagnosticSeverity {
  if (value?.toLowerCase() === 'warning' || /\bwarning\b/i.test(message)) return 'warning';
  return 'error';
}

function parseLogLine(
  rawLine: string,
): { severity: DiagnosticSeverity; line?: number; column?: number; message: string } {
  const trimmed = rawLine.trim();
  const prefixed = trimmed.match(WEBGL_LOG_PATTERNS[0]);
  if (prefixed) {
    const [, severityToken, , lineRaw, colonColumnRaw, parenColumnRaw, messageRaw] = prefixed;
    return {
      severity: severityFrom(severityToken, messageRaw),
      line: Number(lineRaw),
      column: colonColumnRaw || parenColumnRaw ? Number(colonColumnRaw ?? parenColumnRaw) : undefined,
      message: messageRaw.trim() || trimmed,
    };
  }

  const locationFirst = trimmed.match(WEBGL_LOG_PATTERNS[1]);
  if (locationFirst) {
    const [, , lineRaw, colonColumnRaw, parenColumnRaw, severityToken, messageRaw] = locationFirst;
    return {
      severity: severityFrom(severityToken, messageRaw),
      line: Number(lineRaw),
      column: colonColumnRaw || parenColumnRaw ? Number(colonColumnRaw ?? parenColumnRaw) : undefined,
      message: messageRaw.trim() || trimmed,
    };
  }

  const severityOnly = trimmed.match(WEBGL_LOG_PATTERNS[2]);
  if (severityOnly) {
    const [, severityToken, messageRaw] = severityOnly;
    return {
      severity: severityFrom(severityToken, messageRaw),
      message: messageRaw.trim() || trimmed,
    };
  }

  return {
    severity: severityFrom(undefined, trimmed),
    message: trimmed,
  };
}

export function parseWebGLInfoLog(
  infoLog: string | null | undefined,
  options: WebGLInfoLogParseOptions = {},
): readonly ShaderDiagnostic[] {
  const lines = (infoLog ?? '')
    .split(/\r\n|\r|\n/)
    .map((line) => line.trim())
    .filter(Boolean);

  if (lines.length === 0) return Object.freeze([]);

  const phase = options.phase ?? 'fragment';
  const code = phase === 'link'
    ? SHADER_DIAGNOSTIC_CODES.LINK_ERROR
    : SHADER_DIAGNOSTIC_CODES.COMPILE_ERROR;

  return Object.freeze(lines.map((rawLine, index) => {
    const parsed = parseLogLine(rawLine);
    const sourceRange = toSourceRange(parsed.line, parsed.column, options.source);
    return makeDiagnostic(
      options,
      code,
      parsed.severity,
      parsed.message,
      {
        phase,
        infoLogLine: rawLine,
        ...(parsed.line ? { line: parsed.line } : {}),
        ...(parsed.column ? { column: parsed.column } : {}),
      },
      [phase, index, parsed.line ?? 'global', parsed.column ?? 'line'],
      sourceRange,
    );
  }));
}

export function validateShaderSchemas(
  input: { readonly uniforms?: unknown; readonly textures?: unknown },
  context: ShaderValidationContext = {},
): readonly ShaderDiagnostic[] {
  return Object.freeze([
    ...validateShaderUniformSchema(input.uniforms, context),
    ...validateShaderTextureSchema(input.textures, context),
  ]);
}
