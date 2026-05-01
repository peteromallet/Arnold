import type { SelectedClipPayload } from "../../ai-timeline-agent/types.ts";
import {
  callAgentUntilSettled,
  callAgentOnce,
  getAdminSupabaseClient,
  signInHarnessUser,
  type AgentCallResponse,
  type TestUserAuth,
} from "./client.ts";
import {
  cleanupTestData,
  createTestSession,
  createTestTimeline,
  getOrCreateTestUser,
  type TestTimelineFixture,
} from "./fixtures.ts";
import {
  diffSnapshots,
  snapshotState,
  summarizeDiff,
  type HarnessSnapshot,
  type SnapshotDiff,
} from "./snapshot.ts";
import {
  extractNewTaskIds,
  waitForCreditsLedger,
  waitForGenerations,
  waitForTaskCompletion,
} from "./waiter.ts";

export * from "./client.ts";
export * from "./cases.ts";
export * from "./env.ts";
export * from "./evaluate.ts";
export * from "./fixtures.ts";
export * from "./snapshot.ts";
export * from "./waiter.ts";

export interface HarnessSetupResult {
  timelineId: string;
  sessionId: string;
  projectId: string;
  userId: string;
}

export interface WaitForSideEffectsOptions {
  beforeSnapshot?: HarnessSnapshot;
  afterSnapshot?: HarnessSnapshot;
  taskIds?: string[];
  taskTimeoutMs?: number;
  generationTimeoutMs?: number;
  creditsTimeoutMs?: number;
}

interface HarnessState extends HarnessSetupResult {
  jwt: string;
}

interface PendingSideEffectsContext {
  beforeSnapshot: HarnessSnapshot;
  afterSnapshot: HarnessSnapshot;
  taskIds: string[];
  responses: AgentCallResponse[];
}

export class TestHarness {
  private state: HarnessState | null = null;
  private pendingSideEffects: PendingSideEffectsContext | null = null;

  constructor(
    private readonly options?: {
      timelineConfig?: TestTimelineFixture["config"];
      userAuth?: TestUserAuth;
    },
  ) {}

  async setup(): Promise<HarnessSetupResult> {
    if (this.state) {
      return this.publicState();
    }

    const auth = this.options?.userAuth ?? await getOrCreateTestUser();
    const timeline = await createTestTimeline(auth.userId, this.options?.timelineConfig);
    const session = await createTestSession(timeline.timelineId, auth.userId);

    this.state = {
      timelineId: timeline.timelineId,
      sessionId: session.sessionId,
      projectId: timeline.projectId,
      userId: auth.userId,
      jwt: auth.jwt,
    };

    return this.publicState();
  }

  async sendMessage(
    message: string,
    selectedClips?: SelectedClipPayload[],
  ): Promise<AgentCallResponse[]> {
    const state = await this.ensureState();
    const beforeSnapshot = await this.snapshot();
    const responses = await callAgentUntilSettled(
      state.sessionId,
      message,
      selectedClips,
      { jwt: state.jwt },
    );
    const afterSnapshot = await this.snapshot();

    this.pendingSideEffects = {
      beforeSnapshot,
      afterSnapshot,
      taskIds: extractNewTaskIds(beforeSnapshot, afterSnapshot),
      responses,
    };

    return responses;
  }

  async waitForSideEffects(options?: WaitForSideEffectsOptions): Promise<void> {
    const context = await this.resolveWaitContext(options);
    if (context.taskIds.length === 0) {
      return;
    }

    await waitForTaskCompletion(
      context.taskIds,
      options?.taskTimeoutMs,
    );
    await waitForGenerations(
      context.taskIds,
      options?.generationTimeoutMs,
    );
    await waitForCreditsLedger(
      context.taskIds,
      options?.creditsTimeoutMs,
    );
  }

  async snapshot(): Promise<HarnessSnapshot> {
    const state = await this.ensureState();
    return await snapshotState(state.timelineId, state.projectId, state.userId);
  }

  diff(before: HarnessSnapshot, after: HarnessSnapshot): SnapshotDiff {
    return diffSnapshots(before, after);
  }

  summarizeDiff(diff: SnapshotDiff): string {
    return summarizeDiff(diff);
  }

  async teardown(): Promise<void> {
    if (!this.state) {
      return;
    }

    const projectId = this.state.projectId;
    this.pendingSideEffects = null;
    this.state = null;
    await cleanupTestData(projectId);
  }

  get pendingTaskIds(): string[] {
    return this.pendingSideEffects?.taskIds ?? [];
  }

  get lastResponses(): AgentCallResponse[] {
    return this.pendingSideEffects?.responses ?? [];
  }

  async callAgentOnce(
    userMessage?: string,
    selectedClips?: SelectedClipPayload[],
  ): Promise<AgentCallResponse> {
    const state = await this.ensureState();
    return await callAgentOnce({
      sessionId: state.sessionId,
      jwt: state.jwt,
      userMessage,
      selectedClips,
    });
  }

  async refreshAuth(): Promise<TestUserAuth> {
    const auth = await signInHarnessUser(true);
    if (this.state) {
      this.state.jwt = auth.jwt;
      this.state.userId = auth.userId;
    }
    return auth;
  }

  adminClient() {
    return getAdminSupabaseClient();
  }

  private async ensureState(): Promise<HarnessState> {
    if (this.state) {
      return this.state;
    }

    await this.setup();
    if (!this.state) {
      throw new Error("Harness setup did not produce state.");
    }

    return this.state;
  }

  private publicState(): HarnessSetupResult {
    if (!this.state) {
      throw new Error("Harness state is not initialized.");
    }

    return {
      timelineId: this.state.timelineId,
      sessionId: this.state.sessionId,
      projectId: this.state.projectId,
      userId: this.state.userId,
    };
  }

  private async resolveWaitContext(options?: WaitForSideEffectsOptions): Promise<PendingSideEffectsContext> {
    if (options?.taskIds?.length) {
      const beforeSnapshot = options.beforeSnapshot ?? await this.snapshot();
      const afterSnapshot = options.afterSnapshot ?? beforeSnapshot;
      return {
        beforeSnapshot,
        afterSnapshot,
        taskIds: Array.from(new Set(options.taskIds)),
        responses: this.pendingSideEffects?.responses ?? [],
      };
    }

    if (options?.beforeSnapshot && options?.afterSnapshot) {
      return {
        beforeSnapshot: options.beforeSnapshot,
        afterSnapshot: options.afterSnapshot,
        taskIds: extractNewTaskIds(options.beforeSnapshot, options.afterSnapshot),
        responses: this.pendingSideEffects?.responses ?? [],
      };
    }

    if (this.pendingSideEffects) {
      return this.pendingSideEffects;
    }

    throw new Error(
      "waitForSideEffects requires either a prior sendMessage() call, explicit taskIds, or both beforeSnapshot and afterSnapshot.",
    );
  }
}
