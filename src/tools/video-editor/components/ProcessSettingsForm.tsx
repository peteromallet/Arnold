import { useMemo, useState } from 'react';
import type { ProcessEnvFieldSpec, ProcessSpawnConfig } from '@reigh/editor-sdk';
import type { VideoEditorProcessDescriptor } from '@/tools/video-editor/runtime/extensionSurface.ts';

export type ProcessSettingsPlatform = 'darwin' | 'linux' | 'win32';

export interface ProcessSettingPathField {
  key: 'command' | 'cwd';
  label: string;
  required?: boolean;
  defaultValue?: string;
  platformDefaults?: Partial<Record<ProcessSettingsPlatform, string>>;
}

export interface ProcessSettingsFormProps {
  process: VideoEditorProcessDescriptor;
  savedSettings?: Record<string, string | undefined>;
  platform?: ProcessSettingsPlatform;
  pathFields?: readonly ProcessSettingPathField[];
  onSave?: (settings: Record<string, string>, spawnConfig: ProcessSpawnConfig) => void;
}

function defaultFor(
  field: Pick<ProcessEnvFieldSpec | ProcessSettingPathField, 'defaultValue' | 'platformDefaults'>,
  platform: ProcessSettingsPlatform,
): string {
  return field.platformDefaults?.[platform] ?? field.defaultValue ?? '';
}

function initialValue(
  key: string,
  savedSettings: Record<string, string | undefined>,
  fallback: string,
): string {
  return savedSettings[key] ?? fallback;
}

export function buildProcessSpawnConfig(
  process: VideoEditorProcessDescriptor,
  savedSettings: Record<string, string | undefined> = {},
  platform: ProcessSettingsPlatform = 'darwin',
  pathFields: readonly ProcessSettingPathField[] = [],
): ProcessSpawnConfig {
  const env = { ...(process.spec.spawn.env ?? {}) };
  for (const field of process.spec.env ?? []) {
    const value = initialValue(field.key, savedSettings, defaultFor(field, platform));
    if (value) env[field.key] = value;
  }
  const commandField = pathFields.find((field) => field.key === 'command');
  const cwdField = pathFields.find((field) => field.key === 'cwd');
  return {
    ...process.spec.spawn,
    command: initialValue('command', savedSettings, commandField ? defaultFor(commandField, platform) : process.spec.spawn.command),
    ...(cwdField || savedSettings.cwd
      ? { cwd: initialValue('cwd', savedSettings, cwdField ? defaultFor(cwdField, platform) : process.spec.spawn.cwd ?? '') || undefined }
      : {}),
    env,
  };
}

export function validateProcessSettings(
  process: VideoEditorProcessDescriptor,
  settings: Record<string, string | undefined>,
  pathFields: readonly ProcessSettingPathField[] = [],
): string[] {
  const errors: string[] = [];
  for (const field of pathFields) {
    if (field.required && !settings[field.key]) errors.push(`${field.label} is required.`);
  }
  for (const field of process.spec.env ?? []) {
    if (field.required && !settings[field.key]) errors.push(`${field.label ?? field.key} is required.`);
  }
  return errors;
}

export function ProcessSettingsForm({
  process,
  savedSettings = {},
  platform = 'darwin',
  pathFields = [
    { key: 'command', label: 'Command', required: true, defaultValue: process.spec.spawn.command },
    { key: 'cwd', label: 'Working directory', defaultValue: process.spec.spawn.cwd },
  ],
  onSave,
}: ProcessSettingsFormProps) {
  const fields = useMemo(() => [
    ...pathFields.map((field) => ({
      key: field.key,
      label: field.label,
      description: `Default: ${defaultFor(field, platform) || 'none'}`,
      required: field.required,
      secret: false,
      defaultValue: defaultFor(field, platform),
    })),
    ...(process.spec.env ?? []).map((field) => ({
      key: field.key,
      label: field.label ?? field.key,
      description: field.description ?? `Use ${field.key} from the process environment when left blank.`,
      required: field.required,
      secret: field.secret,
      defaultValue: defaultFor(field, platform),
    })),
  ], [pathFields, platform, process.spec.env]);
  const [settings, setSettings] = useState<Record<string, string>>(() => Object.fromEntries(
    fields.map((field) => [field.key, initialValue(field.key, savedSettings, field.defaultValue)]),
  ));
  const errors = validateProcessSettings(process, settings, pathFields);

  return (
    <form
      aria-label={`${process.label} process settings`}
      onSubmit={(event) => {
        event.preventDefault();
        if (errors.length > 0) return;
        onSave?.(settings, buildProcessSpawnConfig(process, settings, platform, pathFields));
      }}
    >
      <h3>{process.label}</h3>
      {fields.map((field) => (
        <label key={field.key}>
          {field.label}
          <input
            aria-label={field.label}
            type={field.secret ? 'password' : 'text'}
            value={settings[field.key] ?? ''}
            placeholder={field.defaultValue}
            required={field.required}
            onChange={(event) => setSettings((next) => ({ ...next, [field.key]: event.target.value }))}
          />
          <span>{field.description}</span>
        </label>
      ))}
      {errors.map((error) => <p key={error}>{error}</p>)}
      <button type="submit" disabled={errors.length > 0}>Save process settings</button>
    </form>
  );
}
