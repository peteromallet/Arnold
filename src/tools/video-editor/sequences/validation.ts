import {
  TRUSTED_CLIP_TYPE_METADATA,
  getTrustedClipTypeRegistration,
} from '../clip-types/registry.ts';
import type { TrustedSequenceClipType, TrustedSequenceMetadata } from './metadata.ts';
import type { ClipTypeSequenceParamDefinition as SequenceParamMetadata } from '../clip-types/defineClipType.ts';

export type SequenceDraftParams = Record<string, string | readonly string[]>;

export type ValidatedSequenceDraft = {
  clipType: TrustedSequenceClipType | (string & {});
  hold: number;
  params: SequenceDraftParams;
};

export type SequenceDraftValidationError = {
  path: string;
  code: string;
  message: string;
};

export type SequenceDraftValidationResult =
  | { ok: true; draft: ValidatedSequenceDraft }
  | { ok: false; errors: SequenceDraftValidationError[] };

export type ValidateSequenceDraftOptions = {
  allowedClipTypes?: readonly string[];
  allowedAssetKeys?: readonly string[];
  metadata?: readonly TrustedSequenceMetadata[];
  /** T7: extension clip type IDs considered valid even without trusted metadata. */
  extensionClipTypeIds?: ReadonlySet<string>;
};

const ROOT_KEYS = new Set(['clipType', 'hold', 'params']);
const GENERATED_CODE_KEYS = new Set([
  'code',
  'component',
  'jsx',
  'tsx',
  'html',
  'script',
  'imports',
  'source',
  'render',
]);
const ANIMATION_KEYS = new Set([
  'animation',
  'animations',
  'animationRefs',
  'entrance',
  'exit',
  'transition',
  'transitions',
]);
const RAW_URL_PATTERN = /(?:https?:\/\/|data:|blob:|www\.)/i;
const CODE_STRING_PATTERN = /(?:^\s*(?:import|export)\s|<\/?[A-Z][A-Za-z0-9]*\b|React\.createElement|function\s+[A-Za-z_$][\w$]*\s*\(|=>\s*<)/;

const isRecord = (value: unknown): value is Record<string, unknown> => {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
};

const addError = (
  errors: SequenceDraftValidationError[],
  path: string,
  code: string,
  message: string,
): void => {
  errors.push({ path, code, message });
};

const findMetadata = (
  metadata: readonly TrustedSequenceMetadata[],
  clipType: string,
): TrustedSequenceMetadata | undefined => {
  return metadata.find((entry) => entry.clipType === clipType);
};

const isJsonSerializable = (value: unknown): boolean => {
  if (
    value === null
    || typeof value === 'string'
    || typeof value === 'boolean'
  ) {
    return true;
  }
  if (typeof value === 'number') {
    return Number.isFinite(value);
  }
  if (Array.isArray(value)) {
    return value.every(isJsonSerializable);
  }
  if (isRecord(value)) {
    return Object.values(value).every(isJsonSerializable);
  }
  return false;
};

const validateStringValue = (
  value: unknown,
  path: string,
  param: SequenceParamMetadata,
  errors: SequenceDraftValidationError[],
): string | undefined => {
  if (typeof value !== 'string') {
    addError(errors, path, 'invalid_param_value', 'Expected a string value.');
    return undefined;
  }
  if (RAW_URL_PATTERN.test(value)) {
    addError(errors, path, 'raw_url', 'Raw URLs are not accepted in sequence drafts.');
    return undefined;
  }
  if (CODE_STRING_PATTERN.test(value)) {
    addError(errors, path, 'generated_code', 'Generated code is not accepted in sequence drafts.');
    return undefined;
  }
  if (param.options && !param.options.includes(value)) {
    addError(errors, path, 'invalid_param_option', `Expected one of: ${param.options.join(', ')}.`);
    return undefined;
  }
  return value;
};

const validateAssetListValue = (
  value: unknown,
  path: string,
  allowedAssetKeys: ReadonlySet<string>,
  param: SequenceParamMetadata,
  errors: SequenceDraftValidationError[],
): readonly string[] | undefined => {
  if (!Array.isArray(value)) {
    addError(errors, path, 'invalid_param_value', 'Expected a list of registry asset keys.');
    return undefined;
  }
  const maxItems = param.maxItems;
  if (typeof maxItems === 'number' && value.length > maxItems) {
    addError(errors, path, 'too_many_assets', `Expected at most ${maxItems} asset keys.`);
    return undefined;
  }
  const assetKeys: string[] = [];
  for (let index = 0; index < value.length; index += 1) {
    const itemPath = `${path}.${index}`;
    const item = value[index];
    if (typeof item !== 'string') {
      addError(errors, itemPath, 'invalid_asset_key', 'Expected a registry asset key string.');
      continue;
    }
    if (RAW_URL_PATTERN.test(item)) {
      addError(errors, itemPath, 'raw_url', 'Asset-valued params must use registry asset keys, not URLs.');
      continue;
    }
    if (!allowedAssetKeys.has(item)) {
      addError(errors, itemPath, 'asset_not_allowed', 'Asset key is not selected or currently attached.');
      continue;
    }
    assetKeys.push(item);
  }
  return assetKeys;
};

export const validateSequenceDraft = (
  input: unknown,
  options: ValidateSequenceDraftOptions = {},
): SequenceDraftValidationResult => {
  const errors: SequenceDraftValidationError[] = [];
  const metadata = options.metadata ?? TRUSTED_CLIP_TYPE_METADATA;
  const allowedClipTypes = new Set(options.allowedClipTypes ?? metadata.map((entry) => entry.clipType));
  const allowedAssetKeys = new Set(options.allowedAssetKeys ?? []);

  if (!isRecord(input)) {
    return {
      ok: false,
      errors: [{ path: '$', code: 'invalid_draft', message: 'Expected a sequence draft object.' }],
    };
  }

  for (const key of Object.keys(input)) {
    if (GENERATED_CODE_KEYS.has(key)) {
      addError(errors, `$.${key}`, 'generated_code_field', 'Generated code fields are not accepted.');
    } else if (ANIMATION_KEYS.has(key)) {
      addError(errors, `$.${key}`, 'animation_ref', 'Animation refs are not AI-editable in v1.');
    } else if (!ROOT_KEYS.has(key)) {
      addError(errors, `$.${key}`, 'unknown_field', 'Unknown top-level fields are not accepted.');
    }
  }

  const clipType = input.clipType;
  if (typeof clipType !== 'string') {
    addError(errors, '$.clipType', 'invalid_clip_type', 'clipType must be a string.');
  }

  const isExtensionClipType = typeof clipType === 'string'
    && options.extensionClipTypeIds?.has(clipType) === true;

  const sequenceMetadata = typeof clipType === 'string' && !isExtensionClipType
    ? (options.metadata
      ? findMetadata(metadata, clipType)
      : getTrustedClipTypeRegistration(clipType)?.metadata)
    : undefined;

  if (typeof clipType === 'string' && !sequenceMetadata && !isExtensionClipType) {
    addError(errors, '$.clipType', 'unknown_clip_type', 'clipType is not a trusted sequence type.');
  }
  if (typeof clipType === 'string' && !allowedClipTypes.has(clipType) && !isExtensionClipType) {
    addError(errors, '$.clipType', 'clip_type_not_allowed', 'clipType is not allowed in this context.');
  }

  const hold = input.hold;
  if (typeof hold !== 'number' || !Number.isFinite(hold) || hold <= 0) {
    addError(errors, '$.hold', 'invalid_hold', 'hold must be a positive finite number.');
  } else if (sequenceMetadata && (hold < sequenceMetadata.hold.minSeconds || hold > sequenceMetadata.hold.maxSeconds)) {
    addError(errors, '$.hold', 'hold_out_of_range', 'hold is outside the allowed timing range.');
  }

  const rawParams = input.params;
  if (!isRecord(rawParams)) {
    addError(errors, '$.params', 'invalid_params', 'params must be an object.');
  }

  const normalizedParams: SequenceDraftParams = {};
  if (sequenceMetadata && isRecord(rawParams)) {
    const paramsByKey = new Map(sequenceMetadata.params.map((param) => [param.key, param]));
    const reservedComponentParams = new Map(
      sequenceMetadata.params
        .filter((param) => typeof param.componentParam === 'string')
        .map((param) => [param.componentParam as string, param.key]),
    );

    for (const [key, value] of Object.entries(rawParams)) {
      const path = `$.params.${key}`;
      if (GENERATED_CODE_KEYS.has(key)) {
        addError(errors, path, 'generated_code_field', 'Generated code fields are not accepted.');
        continue;
      }
      if (ANIMATION_KEYS.has(key)) {
        addError(errors, path, 'animation_ref', 'Animation refs are not AI-editable in v1.');
        continue;
      }
      const reservedFor = reservedComponentParams.get(key);
      if (reservedFor) {
        addError(errors, path, 'reserved_component_param', `Use ${reservedFor} instead of component-facing ${key}.`);
        continue;
      }
      const param = paramsByKey.get(key);
      if (!param) {
        addError(errors, path, 'unknown_param', 'Unknown params are not accepted.');
        continue;
      }
      if (!isJsonSerializable(value)) {
        addError(errors, path, 'non_serializable', 'Param value must be JSON-serializable.');
        continue;
      }
      if (param.kind === 'string') {
        const normalized = validateStringValue(value, path, param, errors);
        if (normalized !== undefined) {
          normalizedParams[key] = normalized;
        }
      } else if (param.kind === 'asset-list') {
        const normalized = validateAssetListValue(value, path, allowedAssetKeys, param, errors);
        if (normalized !== undefined) {
          normalizedParams[key] = normalized;
        }
      }
    }

    for (const param of sequenceMetadata.params) {
      if (param.required && !Object.prototype.hasOwnProperty.call(rawParams, param.key)) {
        addError(errors, `$.params.${param.key}`, 'missing_required_param', 'Required param is missing.');
      }
    }
  }

  if (errors.length > 0) {
    return { ok: false, errors };
  }

  return {
    ok: true,
    draft: {
      clipType: clipType as TrustedSequenceClipType,
      hold: hold as number,
      params: normalizedParams,
    },
  };
};

export const validateSequenceDrafts = (
  inputs: readonly unknown[],
  options: ValidateSequenceDraftOptions = {},
): SequenceDraftValidationResult[] => {
  return inputs.map((input) => validateSequenceDraft(input, options));
};
