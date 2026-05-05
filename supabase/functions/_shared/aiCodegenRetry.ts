// Self-invoke retry helper for AI codegen edge functions.
//
// When an LLM returns code that fails extraction or validation, the calling
// edge function can ask itself for a fixed version by re-invoking its own
// HTTP endpoint with retry context (`_retryDepth`, `_retryError`,
// `_retryFailedCode`) layered onto the original request payload.
//
// This helper encapsulates that pattern so each codegen function does not
// reimplement the SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY / Authorization
// forwarding logic. Returns the proxied retry response when retry depth is
// available, or `null` when the depth budget is exhausted (caller surfaces
// its own error in that case).

export interface SelfInvokeRetryArgs {
  req: Request;
  functionName: string;
  retryDepth: number;
  maxDepth: number;
  /** Original request payload to forward; the helper layers retry fields on top. */
  payload: Record<string, unknown>;
  parseError: string;
  rawOutput: string;
  logger: { info: (msg: string) => void; flush?: () => Promise<void> };
}

export async function attemptSelfInvokeRetry(
  args: SelfInvokeRetryArgs,
): Promise<Response | null> {
  const { req, functionName, retryDepth, maxDepth, payload, parseError, rawOutput, logger } = args;

  if (retryDepth >= maxDepth) {
    return null;
  }

  const supabaseUrl = Deno.env.get('SUPABASE_URL');
  const serviceKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY');
  if (!supabaseUrl || !serviceKey) {
    return null;
  }

  logger.info(`[${functionName}] spawning retry invocation (depth ${retryDepth + 1})`);
  await logger.flush?.();

  const authHeader = req.headers.get('Authorization') ?? `Bearer ${serviceKey}`;

  const retryBody = {
    ...payload,
    _retryDepth: retryDepth + 1,
    _retryError: parseError,
    _retryFailedCode: rawOutput,
  };

  const retryResponse = await fetch(`${supabaseUrl}/functions/v1/${functionName}`, {
    method: 'POST',
    headers: {
      Authorization: authHeader,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(retryBody),
  });

  const retryText = await retryResponse.text();
  return new Response(retryText, {
    status: retryResponse.status,
    headers: {
      'Content-Type': 'application/json',
      'Access-Control-Allow-Origin': '*',
    },
  });
}
