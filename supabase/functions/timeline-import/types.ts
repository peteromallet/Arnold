// deno-lint-ignore-file
export interface TimelineImportBody {
  project_id?: unknown;
  timeline_id?: unknown;
  timeline?: unknown;
  asset_registry?: unknown;
  expected_version?: unknown;
  create_if_missing?: unknown;
}

export interface TimelineImportSuccess {
  ok: true;
  config_version: number;
  created: boolean;
}

export interface TimelineImportConflict {
  ok: false;
  error: "version_mismatch";
  current_version: number | null;
}

export interface TimelineImportError {
  ok: false;
  error: string;
  details?: string;
}

export type TimelineImportResponseBody =
  | TimelineImportSuccess
  | TimelineImportConflict
  | TimelineImportError;
