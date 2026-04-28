// deno-lint-ignore-file
import { describe, expect, it, vi } from "vitest";
import { handleTimelineImport } from "./handler.ts";
import type { TimelineImportBody } from "./types.ts";

const PROJECT_ID = "11111111-1111-1111-1111-111111111111";
const TIMELINE_ID = "22222222-2222-2222-2222-222222222222";
const USER_ID = "33333333-3333-3333-3333-333333333333";

interface FakeRow {
  id: string;
  project_id: string;
  config_version: number;
}

function createSupabaseAdminMock(options: {
  existing?: FakeRow | null;
  rpcResult?: { data: Array<{ config_version: number }>; error: null } | { data: null; error: { message: string } };
  insertResult?: { data: { config_version: number } | null; error: { message: string } | null };
}) {
  const maybeSingle = vi.fn().mockResolvedValue({
    data: options.existing ?? null,
    error: null,
  });
  const eq = vi.fn().mockReturnValue({ maybeSingle });
  const select = vi.fn().mockReturnValue({ eq });

  const insertSingle = vi.fn().mockResolvedValue(
    options.insertResult ?? { data: { config_version: 1 }, error: null },
  );
  const insertSelect = vi.fn().mockReturnValue({ single: insertSingle });
  const insert = vi.fn().mockReturnValue({ select: insertSelect });

  const from = vi.fn().mockReturnValue({ select, insert });
  const rpc = vi.fn().mockResolvedValue(
    options.rpcResult ?? { data: [{ config_version: 2 }], error: null },
  );

  return {
    supabaseAdmin: { from, rpc } as unknown as Parameters<typeof handleTimelineImport>[0]["supabaseAdmin"],
    mocks: { from, rpc, insert, select, eq, maybeSingle, insertSingle },
  };
}

const baseLogger = {
  info: vi.fn(),
  warn: vi.fn(),
  error: vi.fn(),
};

const baseTimeline = {
  theme: "banodoco-default",
  clips: [
    { id: "c1", at: 0, track: "v1", clipType: "media" },
  ],
};

function makeBody(overrides: Partial<TimelineImportBody> = {}): TimelineImportBody {
  return {
    project_id: PROJECT_ID,
    timeline_id: TIMELINE_ID,
    timeline: baseTimeline,
    asset_registry: { assets: {} },
    expected_version: 1,
    create_if_missing: false,
    ...overrides,
  };
}

describe("handleTimelineImport", () => {
  it("rejects malformed project_id", async () => {
    const { supabaseAdmin } = createSupabaseAdminMock({});
    const result = await handleTimelineImport({
      body: makeBody({ project_id: "not-a-uuid" }),
      userId: USER_ID,
      supabaseAdmin,
      logger: baseLogger,
      verifyOwnership: vi.fn(),
    });
    expect(result.status).toBe(400);
    expect(result.body.ok).toBe(false);
  });

  it("rejects payload that fails Zod validation", async () => {
    const { supabaseAdmin } = createSupabaseAdminMock({});
    const result = await handleTimelineImport({
      body: makeBody({ timeline: { theme: "x" } }), // missing clips
      userId: USER_ID,
      supabaseAdmin,
      logger: baseLogger,
      verifyOwnership: vi.fn(),
    });
    expect(result.status).toBe(400);
    if (result.body.ok === false) {
      expect(result.body.error).toMatch(/schema/i);
    }
  });

  it("returns 403 when ownership verification fails", async () => {
    const { supabaseAdmin } = createSupabaseAdminMock({});
    const verify = vi.fn().mockResolvedValue({ success: false, error: "Forbidden", statusCode: 403 });
    const result = await handleTimelineImport({
      body: makeBody(),
      userId: USER_ID,
      supabaseAdmin,
      logger: baseLogger,
      verifyOwnership: verify,
    });
    expect(verify).toHaveBeenCalledWith(PROJECT_ID, USER_ID);
    expect(result.status).toBe(403);
  });

  it("returns 404 when timeline missing and create_if_missing=false", async () => {
    const { supabaseAdmin } = createSupabaseAdminMock({ existing: null });
    const result = await handleTimelineImport({
      body: makeBody(),
      userId: USER_ID,
      supabaseAdmin,
      logger: baseLogger,
      verifyOwnership: vi.fn().mockResolvedValue({ success: true }),
    });
    expect(result.status).toBe(404);
  });

  it("inserts a new timeline when create_if_missing=true and the row is absent", async () => {
    const { supabaseAdmin, mocks } = createSupabaseAdminMock({
      existing: null,
      insertResult: { data: { config_version: 1 }, error: null },
    });
    const result = await handleTimelineImport({
      body: makeBody({ create_if_missing: true }),
      userId: USER_ID,
      supabaseAdmin,
      logger: baseLogger,
      verifyOwnership: vi.fn().mockResolvedValue({ success: true }),
    });
    expect(result.status).toBe(201);
    expect(mocks.insert).toHaveBeenCalledWith(expect.objectContaining({
      id: TIMELINE_ID,
      project_id: PROJECT_ID,
      config_version: 1,
    }));
    if (result.body.ok === true) {
      expect(result.body.created).toBe(true);
    }
  });

  it("calls update_timeline_versioned with the right args when asset_registry is present", async () => {
    const { supabaseAdmin, mocks } = createSupabaseAdminMock({
      existing: { id: TIMELINE_ID, project_id: PROJECT_ID, config_version: 5 },
      rpcResult: { data: [{ config_version: 6 }], error: null },
    });
    const result = await handleTimelineImport({
      body: makeBody({ expected_version: 5 }),
      userId: USER_ID,
      supabaseAdmin,
      logger: baseLogger,
      verifyOwnership: vi.fn().mockResolvedValue({ success: true }),
    });
    expect(mocks.rpc).toHaveBeenCalledWith(
      "update_timeline_versioned",
      expect.objectContaining({
        p_timeline_id: TIMELINE_ID,
        p_expected_version: 5,
      }),
    );
    expect(result.status).toBe(200);
  });

  it("returns 409 with current_version when the RPC returns no rows", async () => {
    const { supabaseAdmin } = createSupabaseAdminMock({
      existing: { id: TIMELINE_ID, project_id: PROJECT_ID, config_version: 7 },
      rpcResult: { data: [], error: null },
    });
    const result = await handleTimelineImport({
      body: makeBody({ expected_version: 3 }),
      userId: USER_ID,
      supabaseAdmin,
      logger: baseLogger,
      verifyOwnership: vi.fn().mockResolvedValue({ success: true }),
    });
    expect(result.status).toBe(409);
    if (result.body.ok === false && result.body.error === "version_mismatch") {
      expect(result.body.current_version).toBe(7);
    } else {
      throw new Error("expected version_mismatch");
    }
  });

  it("--force path: omits expected_version, edge function uses current as expected", async () => {
    const { supabaseAdmin, mocks } = createSupabaseAdminMock({
      existing: { id: TIMELINE_ID, project_id: PROJECT_ID, config_version: 9 },
      rpcResult: { data: [{ config_version: 10 }], error: null },
    });
    const body = makeBody();
    delete body.expected_version;
    const result = await handleTimelineImport({
      body,
      userId: USER_ID,
      supabaseAdmin,
      logger: baseLogger,
      verifyOwnership: vi.fn().mockResolvedValue({ success: true }),
    });
    expect(result.status).toBe(200);
    expect(mocks.rpc).toHaveBeenCalledWith(
      "update_timeline_versioned",
      expect.objectContaining({ p_expected_version: 9 }),
    );
  });
});
