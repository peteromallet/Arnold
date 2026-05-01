// deno-lint-ignore-file
export type SequenceDraftParams = Record<string, string | readonly string[]>;

export type ValidatedSequenceDraft = {
  clipType: "section-hook" | "art-card" | "resource-card" | "cta-card";
  hold: number;
  params: SequenceDraftParams;
};

type SequenceParam = {
  key: string;
  kind: "string" | "asset-list";
  required?: boolean;
  maxItems?: number;
  componentParam?: string;
};

type SequenceMetadata = {
  clipType: ValidatedSequenceDraft["clipType"];
  hold: {
    minSeconds: number;
    maxSeconds: number;
  };
  params: SequenceParam[];
};

export type SequenceDraftValidationError = {
  path: string;
  code: string;
  message: string;
};

export type SequenceDraftValidationResult =
  | { ok: true; draft: ValidatedSequenceDraft }
  | { ok: false; errors: SequenceDraftValidationError[] };

export const TRUSTED_SEQUENCE_METADATA: SequenceMetadata[] = [
  {
    clipType: "section-hook",
    hold: { minSeconds: 1, maxSeconds: 12 },
    params: [
      { key: "kicker", kind: "string" },
      { key: "title", kind: "string", required: true },
      { key: "subtitle", kind: "string" },
    ],
  },
  {
    clipType: "art-card",
    hold: { minSeconds: 1, maxSeconds: 12 },
    params: [
      { key: "title", kind: "string", required: true },
      { key: "caption", kind: "string" },
      { key: "credit", kind: "string" },
    ],
  },
  {
    clipType: "resource-card",
    hold: { minSeconds: 1, maxSeconds: 12 },
    params: [
      { key: "label", kind: "string" },
      { key: "title", kind: "string", required: true },
      { key: "detail", kind: "string" },
      { key: "metric", kind: "string" },
      { key: "previewAssetKeys", kind: "asset-list", maxItems: 3, componentParam: "previews" },
    ],
  },
  {
    clipType: "cta-card",
    hold: { minSeconds: 1, maxSeconds: 12 },
    params: [
      { key: "title", kind: "string", required: true },
      { key: "action", kind: "string" },
      { key: "note", kind: "string" },
    ],
  },
];

const ROOT_KEYS = new Set(["clipType", "hold", "params"]);
const GENERATED_CODE_KEYS = new Set(["code", "component", "jsx", "tsx", "html", "script", "imports", "source", "render"]);
const ANIMATION_KEYS = new Set(["animation", "animations", "animationRefs", "entrance", "exit", "transition", "transitions"]);
const RAW_URL_PATTERN = /(?:https?:\/\/|data:|blob:|www\.)/i;
const CODE_STRING_PATTERN = /(?:^\s*(?:import|export)\s|<\/?[A-Z][A-Za-z0-9]*\b|React\.createElement|function\s+[A-Za-z_$][\w$]*\s*\(|=>\s*<)/;

const isRecord = (value: unknown): value is Record<string, unknown> => {
  return typeof value === "object" && value !== null && !Array.isArray(value);
};

const addError = (
  errors: SequenceDraftValidationError[],
  path: string,
  code: string,
  message: string,
): void => {
  errors.push({ path, code, message });
};

const metadataFor = (clipType: string): SequenceMetadata | undefined => {
  return TRUSTED_SEQUENCE_METADATA.find((entry) => entry.clipType === clipType);
};

export const validateSequenceDraft = (
  input: unknown,
  options: {
    allowedClipTypes?: readonly string[];
    allowedAssetKeys?: readonly string[];
  } = {},
): SequenceDraftValidationResult => {
  const errors: SequenceDraftValidationError[] = [];
  if (!isRecord(input)) {
    return { ok: false, errors: [{ path: "$", code: "invalid_draft", message: "Expected a sequence draft object." }] };
  }

  for (const key of Object.keys(input)) {
    if (GENERATED_CODE_KEYS.has(key)) {
      addError(errors, `$.${key}`, "generated_code_field", "Generated code fields are not accepted.");
    } else if (ANIMATION_KEYS.has(key)) {
      addError(errors, `$.${key}`, "animation_ref", "Animation refs are not AI-editable in v1.");
    } else if (!ROOT_KEYS.has(key)) {
      addError(errors, `$.${key}`, "unknown_field", "Unknown top-level fields are not accepted.");
    }
  }

  const allowedClipTypes = new Set(options.allowedClipTypes ?? TRUSTED_SEQUENCE_METADATA.map((entry) => entry.clipType));
  const allowedAssetKeys = new Set(options.allowedAssetKeys ?? []);
  const clipType = input.clipType;
  const metadata = typeof clipType === "string" ? metadataFor(clipType) : undefined;
  if (typeof clipType !== "string") {
    addError(errors, "$.clipType", "invalid_clip_type", "clipType must be a string.");
  } else if (!metadata) {
    addError(errors, "$.clipType", "unknown_clip_type", "clipType is not trusted.");
  } else if (!allowedClipTypes.has(clipType)) {
    addError(errors, "$.clipType", "clip_type_not_allowed", "clipType is not allowed in this request.");
  }

  const hold = input.hold;
  if (typeof hold !== "number" || !Number.isFinite(hold) || hold <= 0) {
    addError(errors, "$.hold", "invalid_hold", "hold must be a positive finite number.");
  } else if (metadata && (hold < metadata.hold.minSeconds || hold > metadata.hold.maxSeconds)) {
    addError(errors, "$.hold", "hold_out_of_range", "hold is outside the allowed range.");
  }

  const params = input.params;
  const normalizedParams: SequenceDraftParams = {};
  if (!isRecord(params)) {
    addError(errors, "$.params", "invalid_params", "params must be an object.");
  } else if (metadata) {
    const paramsByKey = new Map(metadata.params.map((param) => [param.key, param]));
    const componentParams = new Map(
      metadata.params
        .filter((param) => param.componentParam)
        .map((param) => [param.componentParam as string, param.key]),
    );
    for (const [key, value] of Object.entries(params)) {
      const path = `$.params.${key}`;
      if (GENERATED_CODE_KEYS.has(key)) {
        addError(errors, path, "generated_code_field", "Generated code fields are not accepted.");
        continue;
      }
      if (ANIMATION_KEYS.has(key)) {
        addError(errors, path, "animation_ref", "Animation refs are not AI-editable in v1.");
        continue;
      }
      const componentSource = componentParams.get(key);
      if (componentSource) {
        addError(errors, path, "reserved_component_param", `Use ${componentSource} instead of ${key}.`);
        continue;
      }
      const param = paramsByKey.get(key);
      if (!param) {
        addError(errors, path, "unknown_param", "Unknown params are not accepted.");
        continue;
      }
      if (param.kind === "string") {
        if (typeof value !== "string") {
          addError(errors, path, "invalid_param_value", "Expected a string value.");
        } else if (RAW_URL_PATTERN.test(value)) {
          addError(errors, path, "raw_url", "Raw URLs are not accepted.");
        } else if (CODE_STRING_PATTERN.test(value)) {
          addError(errors, path, "generated_code", "Generated code is not accepted.");
        } else {
          normalizedParams[key] = value;
        }
      } else if (param.kind === "asset-list") {
        if (!Array.isArray(value)) {
          addError(errors, path, "invalid_param_value", "Expected a list of asset keys.");
          continue;
        }
        if (param.maxItems && value.length > param.maxItems) {
          addError(errors, path, "too_many_assets", `Expected at most ${param.maxItems} asset keys.`);
          continue;
        }
        const keys: string[] = [];
        value.forEach((item, index) => {
          if (typeof item !== "string") {
            addError(errors, `${path}.${index}`, "invalid_asset_key", "Expected an asset key string.");
          } else if (RAW_URL_PATTERN.test(item)) {
            addError(errors, `${path}.${index}`, "raw_url", "Asset params must use registry keys.");
          } else if (!allowedAssetKeys.has(item)) {
            addError(errors, `${path}.${index}`, "asset_not_allowed", "Asset key is not allowed.");
          } else {
            keys.push(item);
          }
        });
        normalizedParams[key] = keys;
      }
    }
    for (const param of metadata.params) {
      if (param.required && !Object.prototype.hasOwnProperty.call(params, param.key)) {
        addError(errors, `$.params.${param.key}`, "missing_required_param", "Required param is missing.");
      }
    }
  }

  if (errors.length > 0) {
    return { ok: false, errors };
  }
  return {
    ok: true,
    draft: {
      clipType: clipType as ValidatedSequenceDraft["clipType"],
      hold: hold as number,
      params: normalizedParams,
    },
  };
};
