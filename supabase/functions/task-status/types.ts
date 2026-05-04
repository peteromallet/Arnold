// Response shape for the GET task-status endpoint, matching what
// reigh-app's banodoco poller (`pollBanodocoTaskStatus`) expects.
//
// The poller surface is documented at
// `supabase/functions/ai-timeline-agent/tools/delegateToBanodocoAgent.ts`
// (`BanodocoTaskStatusSnapshot`); see also Bug 1 in the cross-repo
// contract notes. We deliberately keep this lenient: extra fields are
// allowed in `result` and the worker may surface either snake_case or
// pass-through values in the `result_data` JSON column.
export interface TaskStatusResultEnvelope {
  config_version?: number;
  timeline_id?: string;
  // The poller treats `result` as an open record — workers may add more
  // fields without coordinating a schema bump.
  [key: string]: unknown;
}

export interface TaskStatusResponseBody {
  status: string;
  correlation_id?: string;
  message?: string;
  failure_code?: string;
  result?: TaskStatusResultEnvelope;
}
