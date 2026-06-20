import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { ExtensionsSection } from "./ExtensionsSection";
import type { ExtensionDisplayInfo, SettingsFieldInfo, MigrationSummaryDisplayInfo } from "../types";
import type { ExtensionReferenceReport, ExtensionReference, ReferenceKind } from "@/tools/video-editor/runtime/extensionReferenceReport";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeExtension(
  overrides: Partial<ExtensionDisplayInfo> = {},
): ExtensionDisplayInfo {
  return {
    extensionId: "com.example.test",
    name: "Test Extension",
    version: "1.0.0",
    source: "local",
    enabled: true,
    status: "active",
    trustWarning: false,
    diagnosticsCount: 0,
    hasConflict: false,
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------


// ---------------------------------------------------------------------------
// T23: Reference report helpers
// ---------------------------------------------------------------------------

function makeReference(
  overrides: Partial<ExtensionReference> = {},
): ExtensionReference {
  return {
    kind: "effect",
    referenceId: "com.example.ext.myEffect",
    label: "Effect myEffect used in Timeline A",
    location: "Timeline A > Clip 1",
    ownerExtensionId: "com.example.ext",
    ...overrides,
  };
}

function makeReferenceReport(
  extensionId: string,
  overrides: Partial<ExtensionReferenceReport> = {},
): ExtensionReferenceReport {
  return {
    extensionId,
    totalReferenceCount: 0,
    referencesByKind: {},
    hasReferences: false,
    scanIsComplete: true,
    ...overrides,
  };
}

function makeReferenceReportWithRefs(
  extensionId: string,
  count: number = 3,
): ExtensionReferenceReport {
  const refs: ExtensionReference[] = Array.from({ length: count }, (_, i) =>
    makeReference({
      referenceId: `com.example.ext.effect${i}`,
      label: `Effect effect${i} used in Timeline`,
      location: `Timeline > Clip ${i}`,
    }),
  );

  return {
    extensionId,
    totalReferenceCount: count,
    referencesByKind: {
      effect: refs,
    },
    hasReferences: true,
    scanIsComplete: true,
  };
}

describe("ExtensionsSection", () => {
  // ---- Empty state ----

  it("renders empty state when no extensions provided", () => {
    render(<ExtensionsSection isMobile={false} />);
    expect(screen.getByText("No extensions configured")).toBeTruthy();
  });

  it("renders empty state when extensions array is empty", () => {
    render(<ExtensionsSection isMobile={false} extensions={[]} />);
    expect(screen.getByText("No extensions configured")).toBeTruthy();
  });

  // ---- Loading state ----

  it("renders loading skeletons when isLoading is true", () => {
    const { container } = render(
      <ExtensionsSection isMobile={false} isLoading={true} />,
    );
    // Loading skeletons should have animate-pulse class
    const skeletons = container.querySelectorAll(".animate-pulse");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  // ---- Basic extension row ----

  it("renders extension name and version", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[makeExtension({ name: "My Ext", version: "2.3.1" })]}
      />,
    );
    expect(screen.getByText("My Ext")).toBeTruthy();
    expect(screen.getByText("v2.3.1")).toBeTruthy();
  });

  it("renders extension ID in the details row", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[makeExtension({ extensionId: "com.example.foo" })]}
      />,
    );
    expect(screen.getByText("com.example.foo")).toBeTruthy();
  });

  it("renders description when provided", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({ description: "A helpful extension for testing." }),
        ]}
      />,
    );
    expect(screen.getByText("A helpful extension for testing.")).toBeTruthy();
  });

  it("does not render description when not provided", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[makeExtension({ description: undefined })]}
      />,
    );
    // Should not crash; description is optional
    expect(screen.getByText("Test Extension")).toBeTruthy();
  });

  // ---- Status badges ----

  it.each([
    ["active", "Active"],
    ["blocked", "Blocked"],
    ["degraded", "Degraded"],
    ["disabled", "Disabled"],
    ["error", "Error"],
  ] as const)("renders %s status badge", (status, expectedLabel) => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[makeExtension({ status })]}
      />,
    );
    expect(screen.getByText(expectedLabel)).toBeTruthy();
  });

  // ---- Source badges ----

  it("renders Workspace badge for local extensions", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[makeExtension({ source: "local" })]}
      />,
    );
    expect(screen.getByText("Workspace")).toBeTruthy();
  });

  it("renders Installed badge for installed extensions", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[makeExtension({ source: "installed" })]}
      />,
    );
    expect(screen.getByText("Installed")).toBeTruthy();
  });

  // ---- Enabled state ----

  it("shows enabled Yes when extension is enabled", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[makeExtension({ enabled: true })]}
      />,
    );
    expect(screen.getByText("Yes")).toBeTruthy();
  });

  it("shows enabled No when extension is disabled", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[makeExtension({ enabled: false })]}
      />,
    );
    expect(screen.getByText("No")).toBeTruthy();
  });

  // ---- Trust warning ----

  it("shows trust warning for extensions with trustWarning", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            source: "installed",
            trustWarning: true,
            trustWarningReason: "Missing publisher",
          }),
        ]}
      />,
    );
    // Should show unverified publisher warning for installed extensions
    expect(screen.getByText("Unverified publisher")).toBeTruthy();
  });

  it("shows no license warning for installed extensions without license", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            source: "installed",
            trustWarning: true,
            license: undefined,
          }),
        ]}
      />,
    );
    expect(screen.getByText("No license")).toBeTruthy();
  });

  it("shows publisher when provided", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            source: "installed",
            publisher: "Acme Corp",
            trustWarning: false,
          }),
        ]}
      />,
    );
    expect(screen.getByText("Publisher: Acme Corp")).toBeTruthy();
  });

  it("shows license when provided", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            source: "installed",
            license: "MIT",
            trustWarning: false,
          }),
        ]}
      />,
    );
    expect(screen.getByText("License: MIT")).toBeTruthy();
  });

  // ---- Diagnostics count ----

  it("shows diagnostics count when greater than zero", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[makeExtension({ diagnosticsCount: 3 })]}
      />,
    );
    expect(screen.getByText("3 diagnostics")).toBeTruthy();
  });

  it("shows singular diagnostic label", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[makeExtension({ diagnosticsCount: 1 })]}
      />,
    );
    expect(screen.getByText("1 diagnostic")).toBeTruthy();
  });

  it("does not show diagnostics when count is zero", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[makeExtension({ diagnosticsCount: 0 })]}
      />,
    );
    expect(screen.queryByText(/diagnostic/)).toBeNull();
  });

  // ---- Conflict state ----

  it("shows conflict state when hasConflict is true", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            hasConflict: true,
            conflictStrategy: "installed-wins",
          }),
        ]}
      />,
    );
    expect(screen.getByText(/Conflict: installed-wins/)).toBeTruthy();
  });

  it("does not show conflict state when hasConflict is false", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[makeExtension({ hasConflict: false })]}
      />,
    );
    expect(screen.queryByText(/Conflict:/)).toBeNull();
  });

  // ---- Multiple extensions ----

  it("renders multiple extensions", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            extensionId: "ext.one",
            name: "First",
            source: "local",
          }),
          makeExtension({
            extensionId: "ext.two",
            name: "Second",
            source: "installed",
          }),
        ]}
      />,
    );
    expect(screen.getByText("First")).toBeTruthy();
    expect(screen.getByText("Second")).toBeTruthy();
    expect(screen.getByText("Workspace")).toBeTruthy();
    expect(screen.getByText("Installed")).toBeTruthy();
  });

  // ---- Summary bar ----

  it("renders extension count in summary bar", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({ extensionId: "a" }),
          makeExtension({ extensionId: "b" }),
        ]}
      />,
    );
    expect(screen.getByText("2 extensions")).toBeTruthy();
  });

  it("renders singular extension count", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[makeExtension()]}
      />,
    );
    expect(screen.getByText("1 extension")).toBeTruthy();
  });

  it("renders workspace count in summary", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({ extensionId: "a", source: "local" }),
          makeExtension({ extensionId: "b", source: "installed" }),
        ]}
      />,
    );
    expect(screen.getByText("1 workspace")).toBeTruthy();
    expect(screen.getByText("1 installed")).toBeTruthy();
  });

  it("renders disabled count in summary", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({ extensionId: "a", enabled: false }),
          makeExtension({ extensionId: "b", enabled: true }),
        ]}
      />,
    );
    expect(screen.getByText("1 disabled")).toBeTruthy();
  });

  it("renders untrusted count in summary", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({ extensionId: "a", trustWarning: true }),
          makeExtension({ extensionId: "b", trustWarning: false }),
        ]}
      />,
    );
    expect(screen.getByText("1 untrusted")).toBeTruthy();
  });

  // ---- Trust & Security note ----

  it("shows trust and security note when extensions are present", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[makeExtension()]}
      />,
    );
    expect(screen.getByText("Trust & Security")).toBeTruthy();
  });

  it("does not show trust note when no extensions", () => {
    render(<ExtensionsSection isMobile={false} extensions={[]} />);
    expect(screen.queryByText("Trust & Security")).toBeNull();
  });

  // ---- Mobile layout ----

  it("renders in mobile mode without crashing", () => {
    render(
      <ExtensionsSection
        isMobile={true}
        extensions={[makeExtension()]}
      />,
    );
    expect(screen.getByText("Test Extension")).toBeTruthy();
  });
});

// ---------------------------------------------------------------------------
// T19: Manager actions — enable, disable, install
// ---------------------------------------------------------------------------

describe("ExtensionsSection manager actions", () => {
  // ---- Enable / Disable buttons ----

  it("renders Enable button when onEnableExtension is provided and extension is disabled", () => {
    const onEnable = vi.fn();
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[makeExtension({ enabled: false, status: "disabled" })]}
        onEnableExtension={onEnable}
      />,
    );
    const btn = screen.getByText("Enable");
    expect(btn).toBeTruthy();
    fireEvent.click(btn);
    expect(onEnable).toHaveBeenCalledWith("com.example.test");
  });

  it("renders Disable button when onDisableExtension is provided and extension is enabled", () => {
    const onDisable = vi.fn();
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[makeExtension({ enabled: true, status: "active" })]}
        onDisableExtension={onDisable}
      />,
    );
    const btn = screen.getByText("Disable");
    expect(btn).toBeTruthy();
    fireEvent.click(btn);
    expect(onDisable).toHaveBeenCalledWith("com.example.test");
  });

  it("does not render Enable/Disable buttons when no callbacks provided", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[makeExtension()]}
      />,
    );
    expect(screen.queryByText("Enable")).toBeNull();
    expect(screen.queryByText("Disable")).toBeNull();
  });

  it("disables action buttons when isPerformingAction is true", () => {
    const onEnable = vi.fn();
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[makeExtension({ enabled: false })]}
        onEnableExtension={onEnable}
        isPerformingAction={true}
      />,
    );
    const btn = screen.getByText("Enable");
    expect((btn as HTMLButtonElement).disabled).toBe(true);
  });

  it("calls onEnableExtension with correct extensionId after click", () => {
    const onEnable = vi.fn();
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({ extensionId: "ext.a", enabled: false }),
          makeExtension({ extensionId: "ext.b", enabled: true }),
        ]}
        onEnableExtension={onEnable}
      />,
    );
    // Click the Enable button (only rendered for disabled extensions)
    const buttons = screen.getAllByText("Enable");
    expect(buttons.length).toBe(1);
    fireEvent.click(buttons[0]);
    expect(onEnable).toHaveBeenCalledTimes(1);
    expect(onEnable).toHaveBeenCalledWith("ext.a");
  });

  it("calls onDisableExtension with correct extensionId after click", () => {
    const onDisable = vi.fn();
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({ extensionId: "ext.a", enabled: false }),
          makeExtension({ extensionId: "ext.b", enabled: true }),
        ]}
        onDisableExtension={onDisable}
      />,
    );
    const buttons = screen.getAllByText("Disable");
    expect(buttons.length).toBe(1);
    fireEvent.click(buttons[0]);
    expect(onDisable).toHaveBeenCalledTimes(1);
    expect(onDisable).toHaveBeenCalledWith("ext.b");
  });

  it("supports async enable callback", async () => {
    let resolveEnable: () => void;
    const promise = new Promise<void>((resolve) => { resolveEnable = resolve; });
    const onEnable = vi.fn().mockReturnValue(promise);

    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[makeExtension({ enabled: false })]}
        onEnableExtension={onEnable}
      />,
    );
    const btn = screen.getByText("Enable");
    fireEvent.click(btn);
    expect(onEnable).toHaveBeenCalledTimes(1);

    // Resolve the promise
    resolveEnable!();
    await promise;
  });

  // ---- Trusted Local Code badge ----

  it("renders Trusted Local Code badge when trustedLocalCode is true on installed source", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            source: "installed",
            trustedLocalCode: true,
            trustWarning: false,
          }),
        ]}
      />,
    );
    expect(screen.getByText("Trusted Local Code")).toBeTruthy();
  });

  it("does not render Trusted Local Code badge for workspace/local extensions", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            source: "local",
            trustedLocalCode: true,
          }),
        ]}
      />,
    );
    expect(screen.queryByText("Trusted Local Code")).toBeNull();
  });

  it("does not render Trusted Local Code badge when trustedLocalCode is false", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            source: "installed",
            trustedLocalCode: false,
          }),
        ]}
      />,
    );
    expect(screen.queryByText("Trusted Local Code")).toBeNull();
  });

  it("does not render Trusted Local Code badge when trustedLocalCode is undefined", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            source: "installed",
            trustedLocalCode: undefined,
          }),
        ]}
      />,
    );
    expect(screen.queryByText("Trusted Local Code")).toBeNull();
  });

  // ---- Install section ----

  it("renders install section when onInstallExtension is provided", () => {
    const onInstall = vi.fn();
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[makeExtension()]}
        onInstallExtension={onInstall}
      />,
    );
    expect(screen.getByText("Trusted Local Pack Installation")).toBeTruthy();
    expect(screen.getByText("Install Trusted Local Pack")).toBeTruthy();
  });

  it("calls onInstallExtension when install button is clicked", () => {
    const onInstall = vi.fn();
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[makeExtension()]}
        onInstallExtension={onInstall}
      />,
    );
    const btn = screen.getByText("Install Trusted Local Pack");
    fireEvent.click(btn);
    expect(onInstall).toHaveBeenCalledTimes(1);
  });

  it("disables install button when isPerformingAction is true", () => {
    const onInstall = vi.fn();
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[makeExtension()]}
        onInstallExtension={onInstall}
        isPerformingAction={true}
      />,
    );
    const btn = screen.getByText("Install Trusted Local Pack");
    expect((btn as HTMLButtonElement).disabled).toBe(true);
  });

  it("does not render install section when onInstallExtension is not provided", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[makeExtension()]}
      />,
    );
    expect(screen.queryByText("Trusted Local Pack Installation")).toBeNull();
    expect(screen.queryByText("Install Trusted Local Pack")).toBeNull();
  });

  it("renders install section even when no extensions are listed", () => {
    const onInstall = vi.fn();
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[]}
        onInstallExtension={onInstall}
      />,
    );
    // Even with no extensions, install section should show
    expect(screen.getByText("Trusted Local Pack Installation")).toBeTruthy();
  });

  // ---- Updated trust note ----

  it("trust note mentions Trusted Local Code when extensions are present", () => {
    const onInstall = vi.fn();
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            source: "installed",
            trustedLocalCode: true,
          }),
        ]}
        onInstallExtension={onInstall}
      />,
    );
    const trustSection = screen.getByText("Trust & Security");
    expect(trustSection).toBeTruthy();
    // The trust note should mention Trusted Local Code
    expect(
      screen.getByText(/Trusted Local Code come from the local development environment/),
    ).toBeTruthy();
  });

  // ---- Persistence scenario (via callbacks) ----

  it("enable/disable callbacks can be wired to repository persistence", async () => {
    // Simulate what a consumer would do: call repository methods in the callback
    const persistedActions: string[] = [];

    const onEnable = vi.fn().mockImplementation(async (extensionId: string) => {
      persistedActions.push(`enabled:${extensionId}`);
    });
    const onDisable = vi.fn().mockImplementation(async (extensionId: string) => {
      persistedActions.push(`disabled:${extensionId}`);
    });

    const { rerender } = render(
      <ExtensionsSection
        isMobile={false}
        extensions={[makeExtension({ extensionId: "ext.persist", enabled: true })]}
        onDisableExtension={onDisable}
      />,
    );

    // Click Disable
    fireEvent.click(screen.getByText("Disable"));
    expect(onDisable).toHaveBeenCalledWith("ext.persist");

    // Simulate what happens after repository persistence succeeds:
    // the consumer updates the extensions prop with enabled: false
    await onDisable.mock.results[0].value;
    expect(persistedActions).toContain("disabled:ext.persist");

    // Rerender with enabled=false (like after repo update)
    rerender(
      <ExtensionsSection
        isMobile={false}
        extensions={[makeExtension({ extensionId: "ext.persist", enabled: false, status: "disabled" })]}
        onEnableExtension={onEnable}
      />,
    );

    // Now Enable button should appear
    expect(screen.getByText("Enable")).toBeTruthy();

    // Click Enable
    fireEvent.click(screen.getByText("Enable"));
    expect(onEnable).toHaveBeenCalledWith("ext.persist");

    await onEnable.mock.results[0].value;
    expect(persistedActions).toContain("enabled:ext.persist");
  });

  // ---- Install persistence scenario ----

  it("install callback can be wired to repository persistence", async () => {
    const installedPacks: string[] = [];

    const onInstall = vi.fn().mockImplementation(async () => {
      installedPacks.push("trusted-local-pack-1");
    });

    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({ extensionId: "existing.ext", source: "local" }),
        ]}
        onInstallExtension={onInstall}
      />,
    );

    const btn = screen.getByText("Install Trusted Local Pack");
    fireEvent.click(btn);
    expect(onInstall).toHaveBeenCalledTimes(1);

    await onInstall.mock.results[0].value;
    expect(installedPacks).toContain("trusted-local-pack-1");
  });
});

// ---------------------------------------------------------------------------
// T20: Conflict override actions — Use Local Source / Revert to Installed
// ---------------------------------------------------------------------------

describe("ExtensionsSection conflict override actions", () => {
  // ---- "Use Local Source" button visibility ----

  it("shows 'Use Local Source' button for conflicting extension when installed wins", () => {
    const onUseLocal = vi.fn();
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            hasConflict: true,
            conflictStrategy: "installed-wins",
            conflictWinner: "installed",
            source: "installed",
          }),
        ]}
        onUseLocalSource={onUseLocal}
      />,
    );
    expect(screen.getByText("Use Local Source")).toBeTruthy();
    expect(screen.queryByText("Revert to Installed")).toBeNull();
  });

  it("shows 'Use Local Source' button when conflictWinner is undefined (default installed-wins)", () => {
    const onUseLocal = vi.fn();
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            hasConflict: true,
            conflictStrategy: "installed-wins",
            conflictWinner: undefined,
            source: "installed",
          }),
        ]}
        onUseLocalSource={onUseLocal}
      />,
    );
    // conflictWinner !== "local" is true when undefined, so Use Local Source should appear
    expect(screen.getByText("Use Local Source")).toBeTruthy();
  });

  it("shows 'Use Local Source' button when conflictWinner is null (no winner yet)", () => {
    const onUseLocal = vi.fn();
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            hasConflict: true,
            conflictStrategy: "installed-wins",
            conflictWinner: null,
            source: "installed",
          }),
        ]}
        onUseLocalSource={onUseLocal}
      />,
    );
    // conflictWinner !== "local" is true when null, so Use Local Source should appear
    expect(screen.getByText("Use Local Source")).toBeTruthy();
  });

  // ---- "Revert to Installed" button visibility ----

  it("shows 'Revert to Installed' button for conflicting extension when local wins (dev override active)", () => {
    const onRevert = vi.fn();
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            hasConflict: true,
            conflictStrategy: "local-wins",
            conflictWinner: "local",
            source: "local",
          }),
        ]}
        onRevertToInstalled={onRevert}
      />,
    );
    expect(screen.getByText("Revert to Installed")).toBeTruthy();
    expect(screen.queryByText("Use Local Source")).toBeNull();
  });

  it("shows 'Revert to Installed' for disabled-installed-fallback when local is winner", () => {
    const onRevert = vi.fn();
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            hasConflict: true,
            conflictStrategy: "installed-disabled-fallback",
            conflictWinner: "local",
            source: "local",
          }),
        ]}
        onRevertToInstalled={onRevert}
      />,
    );
    expect(screen.getByText("Revert to Installed")).toBeTruthy();
  });

  // ---- Buttons do not appear without conflict ----

  it("does not show conflict buttons when hasConflict is false", () => {
    const onUseLocal = vi.fn();
    const onRevert = vi.fn();
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            hasConflict: false,
            source: "installed",
          }),
        ]}
        onUseLocalSource={onUseLocal}
        onRevertToInstalled={onRevert}
      />,
    );
    expect(screen.queryByText("Use Local Source")).toBeNull();
    expect(screen.queryByText("Revert to Installed")).toBeNull();
  });

  it("does not show conflict buttons when callbacks are not provided", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            hasConflict: true,
            conflictWinner: "installed",
            source: "installed",
          }),
        ]}
      />,
    );
    expect(screen.queryByText("Use Local Source")).toBeNull();
    expect(screen.queryByText("Revert to Installed")).toBeNull();
  });

  // ---- Callback dispatch ----

  it("calls onUseLocalSource with correct extensionId when 'Use Local Source' is clicked", () => {
    const onUseLocal = vi.fn();
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            extensionId: "com.conflict.ext",
            hasConflict: true,
            conflictWinner: "installed",
            source: "installed",
          }),
        ]}
        onUseLocalSource={onUseLocal}
      />,
    );
    const btn = screen.getByText("Use Local Source");
    fireEvent.click(btn);
    expect(onUseLocal).toHaveBeenCalledTimes(1);
    expect(onUseLocal).toHaveBeenCalledWith("com.conflict.ext");
  });

  it("calls onRevertToInstalled with correct extensionId when 'Revert to Installed' is clicked", () => {
    const onRevert = vi.fn();
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            extensionId: "com.conflict.ext",
            hasConflict: true,
            conflictWinner: "local",
            source: "local",
          }),
        ]}
        onRevertToInstalled={onRevert}
      />,
    );
    const btn = screen.getByText("Revert to Installed");
    fireEvent.click(btn);
    expect(onRevert).toHaveBeenCalledTimes(1);
    expect(onRevert).toHaveBeenCalledWith("com.conflict.ext");
  });

  it("handles multiple conflicting extensions with independent callbacks", () => {
    const onUseLocal = vi.fn();
    const onRevert = vi.fn();
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            extensionId: "ext.installed-wins",
            hasConflict: true,
            conflictWinner: "installed",
            source: "installed",
          }),
          makeExtension({
            extensionId: "ext.local-wins",
            hasConflict: true,
            conflictWinner: "local",
            source: "local",
          }),
        ]}
        onUseLocalSource={onUseLocal}
        onRevertToInstalled={onRevert}
      />,
    );

    // Click Use Local Source on first extension
    const useLocalBtn = screen.getByText("Use Local Source");
    fireEvent.click(useLocalBtn);
    expect(onUseLocal).toHaveBeenCalledWith("ext.installed-wins");

    // Click Revert to Installed on second extension
    const revertBtn = screen.getByText("Revert to Installed");
    fireEvent.click(revertBtn);
    expect(onRevert).toHaveBeenCalledWith("ext.local-wins");
  });

  // ---- Disabled state during action ----

  it("disables 'Use Local Source' button when isPerformingAction is true", () => {
    const onUseLocal = vi.fn();
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            hasConflict: true,
            conflictWinner: "installed",
            source: "installed",
          }),
        ]}
        onUseLocalSource={onUseLocal}
        isPerformingAction={true}
      />,
    );
    const btn = screen.getByText("Use Local Source") as HTMLButtonElement;
    expect(btn.disabled).toBe(true);
  });

  it("disables 'Revert to Installed' button when isPerformingAction is true", () => {
    const onRevert = vi.fn();
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            hasConflict: true,
            conflictWinner: "local",
            source: "local",
          }),
        ]}
        onRevertToInstalled={onRevert}
        isPerformingAction={true}
      />,
    );
    const btn = screen.getByText("Revert to Installed") as HTMLButtonElement;
    expect(btn.disabled).toBe(true);
  });

  // ---- Override persistence: Use Local Source → putDevOverride ----

  it("onUseLocalSource can be wired to repository putDevOverride (preferLocalSource: true)", async () => {
    const overrides: Record<string, { preferLocalSource: boolean }> = {};

    const onUseLocal = vi.fn().mockImplementation(async (extensionId: string) => {
      // Simulate putDevOverride({ extensionId, preferLocalSource: true, setAt: new Date().toISOString() })
      overrides[extensionId] = { preferLocalSource: true };
    });

    const { rerender } = render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            extensionId: "ext.override-test",
            hasConflict: true,
            conflictStrategy: "installed-wins",
            conflictWinner: "installed",
            source: "installed",
          }),
        ]}
        onUseLocalSource={onUseLocal}
      />,
    );

    // Click Use Local Source
    const btn = screen.getByText("Use Local Source");
    fireEvent.click(btn);
    expect(onUseLocal).toHaveBeenCalledWith("ext.override-test");

    await onUseLocal.mock.results[0].value;

    // Verify the override was persisted
    expect(overrides["ext.override-test"]).toEqual({ preferLocalSource: true });

    // After successful override, re-render with conflictWinner changed to "local"
    // (simulating what the consumer does after repository update)
    rerender(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            extensionId: "ext.override-test",
            hasConflict: true,
            conflictStrategy: "local-wins",
            conflictWinner: "local",
            source: "local",
          }),
        ]}
        onRevertToInstalled={vi.fn()}
      />,
    );

    // Now "Revert to Installed" should be visible (local is winner)
    expect(screen.getByText("Revert to Installed")).toBeTruthy();
    // And "Use Local Source" should NOT be visible (local is winner)
    expect(screen.queryByText("Use Local Source")).toBeNull();
  });

  // ---- Override persistence: Revert to Installed → deleteDevOverride ----

  it("onRevertToInstalled can be wired to repository deleteDevOverride", async () => {
    const overrides: Record<string, { preferLocalSource: boolean }> = {
      "ext.revert-test": { preferLocalSource: true },
    };

    const onRevert = vi.fn().mockImplementation(async (extensionId: string) => {
      // Simulate deleteDevOverride(extensionId)
      delete overrides[extensionId];
    });

    const { rerender } = render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            extensionId: "ext.revert-test",
            hasConflict: true,
            conflictStrategy: "local-wins",
            conflictWinner: "local",
            source: "local",
          }),
        ]}
        onRevertToInstalled={onRevert}
      />,
    );

    // Click Revert to Installed
    const btn = screen.getByText("Revert to Installed");
    fireEvent.click(btn);
    expect(onRevert).toHaveBeenCalledWith("ext.revert-test");

    await onRevert.mock.results[0].value;

    // Verify the override was removed
    expect(overrides["ext.revert-test"]).toBeUndefined();

    // After successful revert, re-render with conflictWinner changed to "installed"
    // (simulating revert-to-installed default behavior)
    rerender(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            extensionId: "ext.revert-test",
            hasConflict: true,
            conflictStrategy: "installed-wins",
            conflictWinner: "installed",
            source: "installed",
          }),
        ]}
        onUseLocalSource={vi.fn()}
      />,
    );

    // Now "Use Local Source" should be visible (installed is winner again)
    expect(screen.getByText("Use Local Source")).toBeTruthy();
    // And "Revert to Installed" should NOT be visible
    expect(screen.queryByText("Revert to Installed")).toBeNull();
  });

  // ---- Row state changes: full cycle test ----

  it("supports full override cycle: installed-wins → use-local → local-wins → revert → installed-wins", async () => {
    const persistedOverrides: Record<string, boolean> = {};
    const useLocalFn = vi.fn().mockImplementation(async (extId: string) => {
      persistedOverrides[extId] = true;
    });
    const revertFn = vi.fn().mockImplementation(async (extId: string) => {
      delete persistedOverrides[extId];
    });

    // Phase 1: Installed wins by default
    const { rerender } = render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            extensionId: "ext.cycle",
            hasConflict: true,
            conflictStrategy: "installed-wins",
            conflictWinner: "installed",
            source: "installed",
          }),
        ]}
        onUseLocalSource={useLocalFn}
      />,
    );
    expect(screen.getByText("Use Local Source")).toBeTruthy();
    expect(screen.queryByText("Revert to Installed")).toBeNull();

    // Phase 2: Click Use Local Source → override persisted, re-render shows local-wins
    fireEvent.click(screen.getByText("Use Local Source"));
    await useLocalFn.mock.results[0].value;
    expect(persistedOverrides["ext.cycle"]).toBe(true);

    rerender(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            extensionId: "ext.cycle",
            hasConflict: true,
            conflictStrategy: "local-wins",
            conflictWinner: "local",
            source: "local",
          }),
        ]}
        onRevertToInstalled={revertFn}
      />,
    );
    expect(screen.getByText("Revert to Installed")).toBeTruthy();
    expect(screen.queryByText("Use Local Source")).toBeNull();

    // Phase 3: Click Revert to Installed → override deleted, re-render shows installed-wins
    fireEvent.click(screen.getByText("Revert to Installed"));
    await revertFn.mock.results[0].value;
    expect(persistedOverrides["ext.cycle"]).toBeUndefined();

    rerender(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            extensionId: "ext.cycle",
            hasConflict: true,
            conflictStrategy: "installed-wins",
            conflictWinner: "installed",
            source: "installed",
          }),
        ]}
        onUseLocalSource={useLocalFn}
      />,
    );
    // Back to installed-wins
    expect(screen.getByText("Use Local Source")).toBeTruthy();
    expect(screen.queryByText("Revert to Installed")).toBeNull();
  });

  // ---- Conflict winner label in details row ----

  it("shows conflict winner label next to conflict strategy", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            hasConflict: true,
            conflictStrategy: "installed-wins",
            conflictWinner: "installed",
          }),
        ]}
      />,
    );
    // The conflict strategy should still be visible
    expect(screen.getByText(/Conflict: installed-wins/)).toBeTruthy();
  });

  // ---- Conflict buttons do not interfere with enable/disable buttons ----

  it("renders both enable/disable and conflict buttons for conflicting extensions", () => {
    const onDisable = vi.fn();
    const onUseLocal = vi.fn();
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            enabled: true,
            hasConflict: true,
            conflictWinner: "installed",
            source: "installed",
          }),
        ]}
        onDisableExtension={onDisable}
        onUseLocalSource={onUseLocal}
      />,
    );
    // Both buttons should be present
    expect(screen.getByText("Disable")).toBeTruthy();
    expect(screen.getByText("Use Local Source")).toBeTruthy();
  });

  // ---- Async callback support ----

  it("supports async onUseLocalSource callback", async () => {
    let resolveUseLocal: () => void;
    const promise = new Promise<void>((resolve) => { resolveUseLocal = resolve; });
    const onUseLocal = vi.fn().mockReturnValue(promise);

    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            hasConflict: true,
            conflictWinner: "installed",
            source: "installed",
          }),
        ]}
        onUseLocalSource={onUseLocal}
      />,
    );
    const btn = screen.getByText("Use Local Source");
    fireEvent.click(btn);
    expect(onUseLocal).toHaveBeenCalledTimes(1);

    resolveUseLocal!();
    await promise;
  });

  it("supports async onRevertToInstalled callback", async () => {
    let resolveRevert: () => void;
    const promise = new Promise<void>((resolve) => { resolveRevert = resolve; });
    const onRevert = vi.fn().mockReturnValue(promise);

    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            hasConflict: true,
            conflictWinner: "local",
            source: "local",
          }),
        ]}
        onRevertToInstalled={onRevert}
      />,
    );
    const btn = screen.getByText("Revert to Installed");
    fireEvent.click(btn);
    expect(onRevert).toHaveBeenCalledTimes(1);

    resolveRevert!();
    await promise;
  });

// T21 tests to append to ExtensionsSection.test.tsx

// ---------------------------------------------------------------------------
// T21: Dependency badges
// ---------------------------------------------------------------------------

describe("ExtensionsSection dependency badges", () => {
  it("renders dependency badge with satisfied count when all deps are satisfied", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            dependencies: {
              totalCount: 3,
              satisfiedCount: 3,
              missingRequiredCount: 0,
              missingOptionalCount: 0,
              versionMismatchCount: 0,
              degraded: false,
              inCycle: false,
            },
          }),
        ]}
      />,
    );
    // Should show "3d" (3 deps) without error indicators
    expect(screen.getByText(/3d/)).toBeTruthy();
    // Should not show error count
    expect(screen.queryByText(/✗/)).toBeNull();
  });

  it("renders dependency badge with error count when required deps are missing", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            dependencies: {
              totalCount: 4,
              satisfiedCount: 2,
              missingRequiredCount: 2,
              missingOptionalCount: 0,
              versionMismatchCount: 0,
              degraded: false,
              inCycle: false,
            },
          }),
        ]}
      />,
    );
    expect(screen.getByText(/4d/)).toBeTruthy();
    // Should show ✗2 (2 missing required)
    expect(screen.getByText(/✗2/)).toBeTruthy();
  });

  it("renders dependency badge with warning for degraded extensions", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            status: "degraded",
            dependencies: {
              totalCount: 3,
              satisfiedCount: 2,
              missingRequiredCount: 0,
              missingOptionalCount: 1,
              versionMismatchCount: 0,
              degraded: true,
              inCycle: false,
            },
          }),
        ]}
      />,
    );
    expect(screen.getByText(/3d/)).toBeTruthy();
    // Should show warning indicator
    expect(screen.getByText(/⚠/)).toBeTruthy();
  });

  it("renders dependency badge with error for cycle-blocked extensions", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            status: "blocked",
            dependencies: {
              totalCount: 2,
              satisfiedCount: 0,
              missingRequiredCount: 0,
              missingOptionalCount: 0,
              versionMismatchCount: 0,
              degraded: false,
              inCycle: true,
            },
          }),
        ]}
      />,
    );
    expect(screen.getByText(/2d/)).toBeTruthy();
    // Should show ✗1 (1 for cycle)
    expect(screen.getByText(/✗1/)).toBeTruthy();
  });

  it("renders dependency badge with version mismatch count", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            dependencies: {
              totalCount: 5,
              satisfiedCount: 3,
              missingRequiredCount: 0,
              missingOptionalCount: 0,
              versionMismatchCount: 2,
              degraded: false,
              inCycle: false,
            },
          }),
        ]}
      />,
    );
    expect(screen.getByText(/5d/)).toBeTruthy();
    expect(screen.getByText(/✗2/)).toBeTruthy();
  });

  it("does not render dependency badge when no dependencies exist", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[makeExtension({ dependencies: undefined })]}
      />,
    );
    expect(screen.queryByText(/\bd\b/)).toBeNull();
  });

  it("does not render dependency badge when totalCount is 0", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            dependencies: {
              totalCount: 0,
              satisfiedCount: 0,
              missingRequiredCount: 0,
              missingOptionalCount: 0,
              versionMismatchCount: 0,
              degraded: false,
              inCycle: false,
            },
          }),
        ]}
      />,
    );
    // totalCount is 0, badge should not render
    expect(screen.queryByText(/0d/)).toBeNull();
  });

  it("shows blocked count in summary bar when extensions are blocked by deps", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            extensionId: "ext.a",
            dependencies: {
              totalCount: 2,
              satisfiedCount: 0,
              missingRequiredCount: 2,
              missingOptionalCount: 0,
              versionMismatchCount: 0,
              degraded: false,
              inCycle: false,
            },
          }),
          makeExtension({ extensionId: "ext.b", dependencies: undefined }),
        ]}
      />,
    );
    // Summary should show blocked count
    expect(screen.getByText("1 blocked")).toBeTruthy();
  });

  it("shows degraded count in summary bar when extensions are degraded", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            extensionId: "ext.a",
            status: "degraded",
            dependencies: {
              totalCount: 3,
              satisfiedCount: 2,
              missingRequiredCount: 0,
              missingOptionalCount: 1,
              versionMismatchCount: 0,
              degraded: true,
              inCycle: false,
            },
          }),
          makeExtension({ extensionId: "ext.b", dependencies: undefined }),
        ]}
      />,
    );
    expect(screen.getByText("1 degraded")).toBeTruthy();
  });
});

// ---------------------------------------------------------------------------
// T21: Degraded contribution inventory
// ---------------------------------------------------------------------------

describe("ExtensionsSection degraded contribution inventory", () => {
  it("renders degraded contribution section when contributions are present", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            status: "degraded",
            degradedContributions: [
              {
                contributionId: "command.myAction",
                dependencyId: "com.example.missing-dep",
                reason: "Optional dependency not found",
              },
            ],
          }),
        ]}
      />,
    );
    // Should show degraded contribution count
    expect(screen.getByText(/1 degraded contribution/)).toBeTruthy();
  });

  it("renders plural label for multiple degraded contributions", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            status: "degraded",
            degradedContributions: [
              {
                contributionId: "command.action1",
                dependencyId: "dep.a",
                reason: "Missing optional dep",
              },
              {
                contributionId: "effect.fx1",
                dependencyId: "dep.b",
                reason: "Version mismatch",
              },
            ],
          }),
        ]}
      />,
    );
    expect(screen.getByText(/2 degraded contributions/)).toBeTruthy();
  });

  it("expands degraded contribution inventory on click", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            status: "degraded",
            degradedContributions: [
              {
                contributionId: "command.testAction",
                dependencyId: "ext.missing",
                reason: "Optional dependency not found",
              },
            ],
          }),
        ]}
      />,
    );
    // Initially collapsed - contribution details not visible
    expect(screen.queryByText("command.testAction")).toBeNull();

    // Click to expand
    fireEvent.click(screen.getByText(/1 degraded contribution/));

    // Now should show contribution details
    expect(screen.getByText("command.testAction")).toBeTruthy();
    expect(screen.getByText("via ext.missing")).toBeTruthy();
    expect(screen.getByText("Optional dependency not found")).toBeTruthy();
  });

  it("does not render degraded section when contributions array is empty", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[makeExtension({ degradedContributions: [] })]}
      />,
    );
    expect(screen.queryByText(/degraded contribution/)).toBeNull();
  });

  it("does not render degraded section when contributions are undefined", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[makeExtension({ degradedContributions: undefined })]}
      />,
    );
    expect(screen.queryByText(/degraded contribution/)).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// T21: Per-extension lifecycle event log
// ---------------------------------------------------------------------------

describe("ExtensionsSection per-extension lifecycle event log", () => {
  const sampleEvents = [
    {
      kind: "install",
      timestamp: "2025-01-15T10:00:00Z",
      message: "Extension installed successfully.",
      isFailure: false,
    },
    {
      kind: "activation_success",
      timestamp: "2025-01-15T10:00:01Z",
      message: "Extension activated.",
      isFailure: false,
    },
    {
      kind: "integrity_pass",
      timestamp: "2025-01-15T10:00:00Z",
      message: "Bundle integrity verified.",
      isFailure: false,
    },
  ];

  it("shows lifecycle events section collapsed by default", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            lifecycleEvents: sampleEvents,
          }),
        ]}
      />,
    );
    // Header should be visible
    expect(screen.getByText(/Lifecycle Events \(3\)/)).toBeTruthy();
    // Collapsed view shows summary dots with labels
    expect(screen.getByText("Installed")).toBeTruthy();
    expect(screen.getByText("Activated")).toBeTruthy();
  });

  it("expands lifecycle events on click", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            lifecycleEvents: sampleEvents,
          }),
        ]}
      />,
    );
    // Click to expand
    fireEvent.click(screen.getByText("Lifecycle Events (3)"));

    // Should show detailed event messages
    expect(screen.getByText("Extension installed successfully.")).toBeTruthy();
    expect(screen.getByText("Extension activated.")).toBeTruthy();
    expect(screen.getByText("Bundle integrity verified.")).toBeTruthy();
  });

  it("shows failure events with red styling", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            lifecycleEvents: [
              {
                kind: "activation_failure",
                timestamp: "2025-01-15T10:00:02Z",
                message: "Activation failed: missing dependency.",
                isFailure: true,
              },
            ],
          }),
        ]}
      />,
    );
    expect(screen.getByText(/Lifecycle Events \(1\)/)).toBeTruthy();
    // Collapsed view should show the label
    expect(screen.getByText("Activation failed")).toBeTruthy();
  });

  it("shows migration events", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            lifecycleEvents: [
              {
                kind: "migration_start",
                timestamp: "2025-01-15T10:00:00Z",
                message: "Starting settings migration from v1 to v2.",
                isFailure: false,
              },
              {
                kind: "migration_success",
                timestamp: "2025-01-15T10:00:01Z",
                message: "Settings migrated successfully.",
                isFailure: false,
              },
            ],
          }),
        ]}
      />,
    );
    expect(screen.getByText(/Lifecycle Events \(2\)/)).toBeTruthy();
    expect(screen.getByText("Migration started")).toBeTruthy();
    expect(screen.getByText("Migration OK")).toBeTruthy();
  });

  it("shows migration failure event", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            lifecycleEvents: [
              {
                kind: "migration_failure",
                timestamp: "2025-01-15T10:00:01Z",
                message: "Settings migration failed: invalid schema.",
                isFailure: true,
              },
            ],
          }),
        ]}
      />,
    );
    expect(screen.getByText("Migration failed")).toBeTruthy();
  });

  it("shows disable and uninstall events", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            lifecycleEvents: [
              {
                kind: "disable",
                timestamp: "2025-01-15T11:00:00Z",
                message: "Extension disabled by user.",
                isFailure: false,
              },
              {
                kind: "uninstall",
                timestamp: "2025-01-15T12:00:00Z",
                message: "Extension uninstalled.",
                isFailure: false,
              },
            ],
          }),
        ]}
      />,
    );
    expect(screen.getByText("Disabled")).toBeTruthy();
    expect(screen.getByText("Uninstalled")).toBeTruthy();
  });

  it("shows integrity failure event", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            lifecycleEvents: [
              {
                kind: "integrity_fail",
                timestamp: "2025-01-15T10:00:00Z",
                message: "Bundle integrity check failed.",
                isFailure: true,
              },
            ],
          }),
        ]}
      />,
    );
    expect(screen.getByText("Integrity failed")).toBeTruthy();
  });

  it("handles more than 3 lifecycle events with 'more' indicator collapsed", () => {
    const manyEvents = Array.from({ length: 8 }, (_, i) => ({
      kind: "load" as const,
      timestamp: `2025-01-15T${String(i).padStart(2, "0")}:00:00Z`,
      message: `Load event ${i + 1}.`,
      isFailure: false,
    }));

    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            lifecycleEvents: manyEvents,
          }),
        ]}
      />,
    );
    expect(screen.getByText(/Lifecycle Events \(8\)/)).toBeTruthy();
    // Should show "+5 more events" when collapsed
    expect(screen.getByText("+5 more events")).toBeTruthy();
  });

  it("does not render lifecycle events section when no events", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[makeExtension({ lifecycleEvents: [] })]}
      />,
    );
    expect(screen.queryByText(/Lifecycle Events/)).toBeNull();
  });

  it("does not render lifecycle events section when undefined", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[makeExtension({ lifecycleEvents: undefined })]}
      />,
    );
    expect(screen.queryByText(/Lifecycle Events/)).toBeNull();
  });

  it("labels all lifecycle event kinds correctly", () => {
    const allKinds = [
      { kind: "install", label: "Installed" },
      { kind: "uninstall", label: "Uninstalled" },
      { kind: "enable", label: "Enabled" },
      { kind: "disable", label: "Disabled" },
      { kind: "load", label: "Loaded" },
      { kind: "unload", label: "Unloaded" },
      { kind: "activation_success", label: "Activated" },
      { kind: "activation_failure", label: "Activation failed" },
      { kind: "migration_start", label: "Migration started" },
      { kind: "migration_success", label: "Migration OK" },
      { kind: "migration_failure", label: "Migration failed" },
      { kind: "migration_reset", label: "Settings reset" },
      { kind: "integrity_pass", label: "Integrity OK" },
      { kind: "integrity_fail", label: "Integrity failed" },
      { kind: "dependency_blocked", label: "Dependency blocked" },
      { kind: "dependency_degraded", label: "Degraded" },
      { kind: "conflict_override_set", label: "Override set" },
      { kind: "conflict_override_cleared", label: "Override cleared" },
    ];

    const events = allKinds.map(({ kind }) => ({
      kind,
      timestamp: "2025-01-15T10:00:00Z",
      message: `Event: ${kind}`,
      isFailure: kind.includes("fail") || kind.includes("blocked"),
    }));

    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            extensionId: "ext.all-kinds",
            lifecycleEvents: events,
          }),
        ]}
      />,
    );

    // Expand to see all events
    fireEvent.click(screen.getByText(/Lifecycle Events/));

    for (const { label } of allKinds) {
      expect(screen.getByText(label)).toBeTruthy();
    }
  });
});

// ---------------------------------------------------------------------------
// T21: Aggregate lifecycle event log
// ---------------------------------------------------------------------------

describe("ExtensionsSection aggregate lifecycle event log", () => {
  const makeEvent = (
    extensionId: string,
    extensionName: string,
    kind: string,
    isFailure = false,
  ) => ({
    extensionId,
    extensionName,
    kind,
    timestamp: "2025-01-15T10:00:00Z",
    message: `${extensionName}: ${kind}`,
    isFailure,
  });

  it("renders aggregate event log when events are provided", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({ extensionId: "ext.a", name: "Alpha" }),
          makeExtension({ extensionId: "ext.b", name: "Beta" }),
        ]}
        allLifecycleEvents={[
          makeEvent("ext.a", "Alpha", "install"),
          makeEvent("ext.a", "Alpha", "activation_success"),
          makeEvent("ext.b", "Beta", "install"),
        ]}
      />,
    );
    expect(screen.getByText(/Event Log \(3 events\)/)).toBeTruthy();
  });

  it("shows failure count in aggregate log header", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[makeExtension()]}
        allLifecycleEvents={[
          makeEvent("ext.a", "Alpha", "install"),
          makeEvent("ext.a", "Alpha", "activation_failure", true),
          makeEvent("ext.a", "Alpha", "integrity_fail", true),
        ]}
      />,
    );
    expect(screen.getByText(/Event Log \(3 events, 2 failures\)/)).toBeTruthy();
  });

  it("expands aggregate log on click", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[makeExtension()]}
        allLifecycleEvents={[
          makeEvent("ext.a", "Alpha", "install"),
          makeEvent("ext.a", "Alpha", "activation_success"),
        ]}
      />,
    );
    // Collapsed view should show the aggregate log header
    expect(screen.getByText(/Event Log \(2 events\)/)).toBeTruthy();

    // Expand
    fireEvent.click(screen.getByText(/Event Log \(2 events\)/));

    // Should show full messages
    expect(screen.getByText("Alpha: install")).toBeTruthy();
    expect(screen.getByText("Alpha: activation_success")).toBeTruthy();
  });

  it("shows +N more events when collapsed with > 5 events", () => {
    const events = Array.from({ length: 10 }, (_, i) =>
      makeEvent(`ext.${i}`, `Extension ${i}`, "load"),
    );

    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[makeExtension()]}
        allLifecycleEvents={events}
      />,
    );
    expect(screen.getByText(/Event Log \(10 events\)/)).toBeTruthy();
    // Should show "+5 more events"
    expect(screen.getByText("+5 more events")).toBeTruthy();
  });

  it("does not render aggregate log when no events", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[makeExtension()]}
        allLifecycleEvents={[]}
      />,
    );
    expect(screen.queryByText(/Event Log/)).toBeNull();
  });

  it("does not render aggregate log when undefined", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[makeExtension()]}
        allLifecycleEvents={undefined}
      />,
    );
    expect(screen.queryByText(/Event Log/)).toBeNull();
  });

  it("renders aggregate log even with no extensions listed", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[]}
        allLifecycleEvents={[
          makeEvent("ext.uninstalled", "Old Extension", "uninstall"),
        ]}
      />,
    );
    expect(screen.getByText(/Event Log \(1 events\)/)).toBeTruthy();
  });
});

// ---------------------------------------------------------------------------
// T21: Combined views — all new features together
// ---------------------------------------------------------------------------

describe("ExtensionsSection combined T21 features", () => {
  it("renders dependency badge, degraded contributions, lifecycle log, and aggregate log together", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            extensionId: "ext.full",
            name: "Full Extension",
            status: "degraded",
            dependencies: {
              totalCount: 4,
              satisfiedCount: 2,
              missingRequiredCount: 0,
              missingOptionalCount: 2,
              versionMismatchCount: 0,
              degraded: true,
              inCycle: false,
            },
            degradedContributions: [
              {
                contributionId: "command.extraAction",
                dependencyId: "ext.missing-opt",
                reason: "Optional dependency not found",
              },
              {
                contributionId: "effect.specialFx",
                dependencyId: "ext.other-missing",
                reason: "Optional dependency version mismatch",
              },
            ],
            lifecycleEvents: [
              {
                kind: "install",
                timestamp: "2025-01-15T10:00:00Z",
                message: "Installed.",
                isFailure: false,
              },
              {
                kind: "load",
                timestamp: "2025-01-15T10:00:01Z",
                message: "Loaded in degraded mode.",
                isFailure: false,
              },
              {
                kind: "dependency_degraded",
                timestamp: "2025-01-15T10:00:01Z",
                message: "Optional deps missing.",
                isFailure: false,
              },
            ],
          }),
        ]}
        allLifecycleEvents={[
          {
            extensionId: "ext.full",
            extensionName: "Full Extension",
            kind: "install",
            timestamp: "2025-01-15T10:00:00Z",
            message: "Full Extension installed.",
            isFailure: false,
          },
          {
            extensionId: "ext.full",
            extensionName: "Full Extension",
            kind: "dependency_degraded",
            timestamp: "2025-01-15T10:00:01Z",
            message: "Full Extension degraded.",
            isFailure: false,
          },
        ]}
      />,
    );

    // Dependency badge
    expect(screen.getByText(/4d/)).toBeTruthy();

    // Degraded contributions header
    expect(screen.getByText(/2 degraded contributions/)).toBeTruthy();

    // Per-extension lifecycle log
    expect(screen.getByText(/Lifecycle Events \(3\)/)).toBeTruthy();

    // Aggregate log
    expect(screen.getByText(/Event Log \(2 events\)/)).toBeTruthy();

    // Summary bar: degraded count
    expect(screen.getByText("1 degraded")).toBeTruthy();
  });

  it("does not overwhelm UI when all panels are collapsed", () => {
    const { container } = render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            extensionId: "ext.complex",
            name: "Complex Extension",
            status: "degraded",
            dependencies: {
              totalCount: 3,
              satisfiedCount: 1,
              missingRequiredCount: 1,
              missingOptionalCount: 1,
              versionMismatchCount: 0,
              degraded: true,
              inCycle: false,
            },
            degradedContributions: [
              {
                contributionId: "cmd.a",
                dependencyId: "dep.x",
                reason: "Missing optional dep",
              },
            ],
            lifecycleEvents: [
              {
                kind: "install",
                timestamp: "2025-01-15T10:00:00Z",
                message: "Installed.",
                isFailure: false,
              },
              {
                kind: "activation_failure",
                timestamp: "2025-01-15T10:00:01Z",
                message: "Activation failed.",
                isFailure: true,
              },
            ],
          }),
        ]}
        allLifecycleEvents={[]}
      />,
    );

    // All panels should exist but be collapsed (no detailed content visible)
    expect(screen.getByText("Complex Extension")).toBeTruthy();
    expect(screen.getByText(/3d/)).toBeTruthy();
    expect(screen.getByText(/1 degraded contribution/)).toBeTruthy();
    expect(screen.getByText(/Lifecycle Events \(2\)/)).toBeTruthy();

    // But detailed content should NOT be visible (collapsed)
    expect(screen.queryByText("cmd.a")).toBeNull();
    expect(screen.queryByText("Activation failed.")).toBeNull();

    // Event log should NOT show because events array is empty
    expect(screen.queryByText(/Event Log/)).toBeNull();

    // The extension row should still be reasonably compact
    const rows = container.querySelectorAll(".bg-muted\\/30");
    expect(rows.length).toBe(1);
  });
});


// ---------------------------------------------------------------------------
// T22: Settings editor panel tests
// ---------------------------------------------------------------------------

describe("ExtensionsSection settings editor panel (T22)", () => {
  function makeStringField(overrides: Partial<SettingsFieldInfo> = {}): SettingsFieldInfo {
    return {
      key: "theme",
      label: "Theme",
      type: "string",
      currentValue: "dark",
      defaultValue: "light",
      ...overrides,
    };
  }

  function makeNumberField(overrides: Partial<SettingsFieldInfo> = {}): SettingsFieldInfo {
    return {
      key: "volume",
      label: "Volume",
      type: "number",
      currentValue: 75,
      defaultValue: 100,
      ...overrides,
    };
  }

  function makeBooleanField(overrides: Partial<SettingsFieldInfo> = {}): SettingsFieldInfo {
    return {
      key: "debugMode",
      label: "Debug Mode",
      type: "boolean",
      currentValue: false,
      defaultValue: false,
      ...overrides,
    };
  }

  function makeJsonField(overrides: Partial<SettingsFieldInfo> = {}): SettingsFieldInfo {
    return {
      key: "config",
      label: "Configuration",
      type: "json",
      currentValue: { nested: true, count: 42 },
      defaultValue: { nested: false, count: 0 },
      ...overrides,
    };
  }

  // ---- Settings editor panel visibility ----

  it("shows settings editor panel when settingsFields have entries", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            extensionId: "ext.a",
            settingsFields: [makeStringField()],
          }),
        ]}
      />,
    );

    // The panel header should be visible with field count
    expect(screen.getByText(/Settings \(1 field\)/)).toBeTruthy();
  });

  it("shows settings editor panel with plural label for multiple fields", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            extensionId: "ext.a",
            settingsFields: [makeStringField(), makeNumberField(), makeBooleanField()],
          }),
        ]}
      />,
    );

    expect(screen.getByText(/Settings \(3 fields\)/)).toBeTruthy();
  });

  it("does not render settings editor panel when settingsFields is null", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            extensionId: "ext.a",
            settingsFields: null,
          }),
        ]}
      />,
    );

    expect(screen.queryByText(/Settings/)).toBeNull();
  });

  it("does not render settings editor panel when settingsFields is empty array", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            extensionId: "ext.a",
            settingsFields: [],
          }),
        ]}
      />,
    );

    expect(screen.queryByText(/Settings/)).toBeNull();
  });

  it("does not render settings editor panel when settingsFields is undefined", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            extensionId: "ext.a",
          }),
        ]}
      />,
    );

    expect(screen.queryByText(/Settings/)).toBeNull();
  });

  // ---- Settings editor expansion ----

  it("settings editor starts collapsed", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            extensionId: "ext.a",
            settingsFields: [makeStringField()],
          }),
        ]}
      />,
    );

    // The panel header exists
    expect(screen.getByText(/Settings \(1 field\)/)).toBeTruthy();
    // But the field label should not be visible when collapsed
    expect(screen.queryByText("Theme")).toBeNull();
  });

  it("expands settings editor on click and shows field labels", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            extensionId: "ext.a",
            settingsFields: [
              makeStringField({ label: "Theme" }),
              makeNumberField({ label: "Volume" }),
            ],
          }),
        ]}
      />,
    );

    fireEvent.click(screen.getByText(/Settings \(2 fields\)/));

    // Field labels should now be visible
    expect(screen.getByText("Theme")).toBeTruthy();
    expect(screen.getByText("Volume")).toBeTruthy();
  });

  // ---- String field editing ----

  it("renders string field with input and current value", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            extensionId: "ext.a",
            settingsFields: [makeStringField({ currentValue: "dark", label: "Theme" })],
          }),
        ]}
      />,
    );

    fireEvent.click(screen.getByText(/Settings \(1 field\)/));

    // Label should be visible
    expect(screen.getByText("Theme")).toBeTruthy();
    // Input should contain current value
    const input = screen.getByDisplayValue("dark");
    expect(input).toBeTruthy();
  });

  it("calls onUpdateSettings when string field is changed and saved via Enter", async () => {
    const onUpdateSettings = vi.fn();
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            extensionId: "ext.a",
            settingsFields: [makeStringField({ currentValue: "dark", key: "theme" })],
          }),
        ]}
        onUpdateSettings={onUpdateSettings}
      />,
    );

    fireEvent.click(screen.getByText(/Settings \(1 field\)/));

    const input = screen.getByDisplayValue("dark") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "light" } });
    fireEvent.keyDown(input, { key: "Enter" });

    expect(onUpdateSettings).toHaveBeenCalledWith("ext.a", "theme", "light");
  });

  // ---- Number field editing ----

  it("renders number field with numeric input", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            extensionId: "ext.a",
            settingsFields: [makeNumberField({ currentValue: 75, label: "Volume" })],
          }),
        ]}
      />,
    );

    fireEvent.click(screen.getByText(/Settings \(1 field\)/));

    expect(screen.getByText("Volume")).toBeTruthy();
    const input = screen.getByDisplayValue("75");
    expect(input).toBeTruthy();
    expect((input as HTMLInputElement).type).toBe("number");
  });

  it("calls onUpdateSettings with parsed number", async () => {
    const onUpdateSettings = vi.fn();
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            extensionId: "ext.a",
            settingsFields: [makeNumberField({ currentValue: 75, key: "volume" })],
          }),
        ]}
        onUpdateSettings={onUpdateSettings}
      />,
    );

    fireEvent.click(screen.getByText(/Settings \(1 field\)/));

    const input = screen.getByDisplayValue("75") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "50" } });
    fireEvent.keyDown(input, { key: "Enter" });

    expect(onUpdateSettings).toHaveBeenCalledWith("ext.a", "volume", 50);
  });

  // ---- Boolean field editing ----

  it("renders boolean field as toggle switch", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            extensionId: "ext.a",
            settingsFields: [makeBooleanField({ currentValue: false, label: "Debug Mode" })],
          }),
        ]}
      />,
    );

    fireEvent.click(screen.getByText(/Settings \(1 field\)/));

    expect(screen.getByText("Debug Mode")).toBeTruthy();
    expect(screen.getByText("Disabled")).toBeTruthy();
  });

  it("shows Enabled when boolean field is true", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            extensionId: "ext.a",
            settingsFields: [makeBooleanField({ currentValue: true, label: "Debug Mode" })],
          }),
        ]}
      />,
    );

    fireEvent.click(screen.getByText(/Settings \(1 field\)/));

    expect(screen.getByText("Enabled")).toBeTruthy();
  });

  it("calls onUpdateSettings when boolean toggle is clicked", async () => {
    const onUpdateSettings = vi.fn();
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            extensionId: "ext.a",
            settingsFields: [makeBooleanField({ currentValue: false, key: "debugMode" })],
          }),
        ]}
        onUpdateSettings={onUpdateSettings}
      />,
    );

    fireEvent.click(screen.getByText(/Settings \(1 field\)/));

    // Click the toggle button (not the label text)
    const toggle = screen.getByText("Disabled").previousElementSibling as HTMLElement;
    fireEvent.click(toggle);

    expect(onUpdateSettings).toHaveBeenCalledWith("ext.a", "debugMode", true);
  });

  // ---- JSON field editing ----

  it("renders JSON field as textarea with formatted JSON", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            extensionId: "ext.a",
            settingsFields: [makeJsonField({ label: "Configuration" })],
          }),
        ]}
      />,
    );

    fireEvent.click(screen.getByText(/Settings \(1 field\)/));

    expect(screen.getByText("Configuration")).toBeTruthy();
    // Should show JSON-formatted text
    const textarea = screen.getByText(/nested/, { exact: false });
    expect(textarea).toBeTruthy();
  });

  it("calls onUpdateSettings with parsed JSON", async () => {
    const onUpdateSettings = vi.fn();
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            extensionId: "ext.a",
            settingsFields: [makeJsonField({ key: "config" })],
          }),
        ]}
        onUpdateSettings={onUpdateSettings}
      />,
    );

    fireEvent.click(screen.getByText(/Settings \(1 field\)/));

    // Find the textarea and change its value, then click Save
    const textarea = screen.getByRole("textbox") as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: '{"new": "value"}' } });

    // Click save button
    const saveBtn = screen.getByText("Save");
    fireEvent.click(saveBtn);

    expect(onUpdateSettings).toHaveBeenCalledWith("ext.a", "config", { new: "value" });
  });

  // ---- Reset to default ----

  it("shows reset button when current value differs from default", () => {
    const onUpdateSettings = vi.fn();
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            extensionId: "ext.a",
            settingsFields: [makeStringField({ currentValue: "dark", defaultValue: "light" })],
          }),
        ]}
        onUpdateSettings={onUpdateSettings}
      />,
    );

    fireEvent.click(screen.getByText(/Settings \(1 field\)/));

    // The "default" indicator should be visible
    expect(screen.getByText("default")).toBeTruthy();
    // Reset button with title should exist
    const resetBtn = screen.getByTitle(/Reset to default/);
    expect(resetBtn).toBeTruthy();
  });

  it("does not show reset button when current value equals default", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            extensionId: "ext.a",
            settingsFields: [makeStringField({ currentValue: "light", defaultValue: "light" })],
          }),
        ]}
      />,
    );

    fireEvent.click(screen.getByText(/Settings \(1 field\)/));

    // Reset button should not be present
    const resetBtn = screen.queryByTitle(/Reset to default/);
    expect(resetBtn).toBeNull();
  });

  it("calls onUpdateSettings with default value when reset button is clicked", () => {
    const onUpdateSettings = vi.fn();
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            extensionId: "ext.a",
            settingsFields: [makeStringField({ currentValue: "dark", defaultValue: "light", key: "theme" })],
          }),
        ]}
        onUpdateSettings={onUpdateSettings}
      />,
    );

    fireEvent.click(screen.getByText(/Settings \(1 field\)/));

    const resetBtn = screen.getByTitle(/Reset to default/);
    fireEvent.click(resetBtn);

    expect(onUpdateSettings).toHaveBeenCalledWith("ext.a", "theme", "light");
  });

  // ---- Disabled during save ----

  it("disables inputs when isSavingSettings is true", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            extensionId: "ext.a",
            settingsFields: [makeStringField({ currentValue: "dark" })],
          }),
        ]}
        isSavingSettings={true}
      />,
    );

    fireEvent.click(screen.getByText(/Settings \(1 field\)/));

    const input = screen.getByDisplayValue("dark") as HTMLInputElement;
    expect(input.disabled).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// T22: Migration summary panel tests
// ---------------------------------------------------------------------------

describe("ExtensionsSection migration summary panel (T22)", () => {
  function makeMigrationSummary(
    overrides: Partial<MigrationSummaryDisplayInfo> = {},
  ): MigrationSummaryDisplayInfo {
    return {
      oldSchemaVersion: 1,
      newSchemaVersion: 2,
      migrationTimestamp: "2025-06-15T12:00:00Z",
      status: "migrated",
      message: "Settings migrated successfully from v1 to v2",
      resetToDefaults: false,
      ...overrides,
    };
  }

  // ---- Visibility ----

  it("shows migration summary panel when migrationSummary is provided", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            extensionId: "ext.a",
            migrationSummary: makeMigrationSummary(),
          }),
        ]}
      />,
    );

    expect(screen.getByText("Settings Migration")).toBeTruthy();
  });

  it("does not render migration summary when migrationSummary is null", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            extensionId: "ext.a",
            migrationSummary: null,
          }),
        ]}
      />,
    );

    expect(screen.queryByText("Settings Migration")).toBeNull();
  });

  it("does not render migration summary when migrationSummary is undefined", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            extensionId: "ext.a",
          }),
        ]}
      />,
    );

    expect(screen.queryByText("Settings Migration")).toBeNull();
  });

  // ---- Status badges ----

  it("shows 'Schema up-to-date' status badge when status is up-to-date", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            extensionId: "ext.a",
            migrationSummary: makeMigrationSummary({
              status: "up-to-date",
              oldSchemaVersion: 2,
              newSchemaVersion: 2,
            }),
          }),
        ]}
      />,
    );

    expect(screen.getByText("Schema up-to-date")).toBeTruthy();
  });

  it("shows 'Migrated' status badge when status is migrated", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            extensionId: "ext.a",
            migrationSummary: makeMigrationSummary({ status: "migrated" }),
          }),
        ]}
      />,
    );

    expect(screen.getByText("Migrated")).toBeTruthy();
  });

  it("shows 'No migration needed' status badge when status is no-migration", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            extensionId: "ext.a",
            migrationSummary: makeMigrationSummary({ status: "no-migration" }),
          }),
        ]}
      />,
    );

    expect(screen.getByText("No migration needed")).toBeTruthy();
  });

  it("shows 'Migration failed' status badge when status is migration-failed", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            extensionId: "ext.a",
            migrationSummary: makeMigrationSummary({
              status: "migration-failed",
              message: "Handler not found",
            }),
          }),
        ]}
      />,
    );

    expect(screen.getByText("Migration failed")).toBeTruthy();
  });

  it("shows 'Settings reset to defaults' status badge when status is migration-reset", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            extensionId: "ext.a",
            migrationSummary: makeMigrationSummary({
              status: "migration-reset",
              resetToDefaults: true,
              message: "No migration declarations found; resetting to defaults.",
            }),
          }),
        ]}
      />,
    );

    expect(screen.getByText("Settings reset to defaults")).toBeTruthy();
  });

  // ---- Expansion ----

  it("migration summary starts collapsed", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            extensionId: "ext.a",
            migrationSummary: makeMigrationSummary({
              message: "Settings migrated successfully",
            }),
          }),
        ]}
      />,
    );

    // Header is visible
    expect(screen.getByText("Settings Migration")).toBeTruthy();
    // Detailed message should not be visible when collapsed
    expect(screen.queryByText("Settings migrated successfully")).toBeNull();
  });

  it("expands migration summary on click and shows details", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            extensionId: "ext.a",
            migrationSummary: makeMigrationSummary({
              oldSchemaVersion: 1,
              newSchemaVersion: 3,
              migrationTimestamp: "2025-06-15T12:00:00Z",
              message: "Migration completed",
            }),
          }),
        ]}
      />,
    );

    fireEvent.click(screen.getByText("Settings Migration"));

    // Version badges should be visible
    expect(screen.getByText("v1")).toBeTruthy();
    expect(screen.getByText("v3")).toBeTruthy();
    // Message should be visible
    expect(screen.getByText("Migration completed")).toBeTruthy();
  });

  // ---- Reset indicator ----

  it("shows reset warning when resetToDefaults is true", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            extensionId: "ext.a",
            migrationSummary: makeMigrationSummary({
              status: "migration-reset",
              resetToDefaults: true,
              message: "Settings were reset",
            }),
          }),
        ]}
      />,
    );

    fireEvent.click(screen.getByText("Settings Migration"));

    expect(
      screen.getByText(/Settings were reset to manifest defaults/),
    ).toBeTruthy();
  });

  it("does not show reset warning when resetToDefaults is false", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            extensionId: "ext.a",
            migrationSummary: makeMigrationSummary({
              status: "migrated",
              resetToDefaults: false,
            }),
          }),
        ]}
      />,
    );

    fireEvent.click(screen.getByText("Settings Migration"));

    expect(
      screen.queryByText(/Settings were reset to manifest defaults/),
    ).toBeNull();
  });

  // ---- Missing timestamp ----

  it("shows dash when migrationTimestamp is undefined", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            extensionId: "ext.a",
            migrationSummary: makeMigrationSummary({
              migrationTimestamp: undefined,
            }),
          }),
        ]}
      />,
    );

    fireEvent.click(screen.getByText("Settings Migration"));

    // Should show a dash
    expect(screen.getByText("—")).toBeTruthy();
  });
});

// ---------------------------------------------------------------------------
// T22: Combined settings + migration
// ---------------------------------------------------------------------------

describe("ExtensionsSection combined T22 features", () => {
  it("renders both settings editor and migration summary for same extension", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            extensionId: "ext.a",
            settingsFields: [
              {
                key: "theme",
                label: "Theme",
                type: "string",
                currentValue: "dark",
                defaultValue: "light",
              },
            ],
            migrationSummary: {
              oldSchemaVersion: 1,
              newSchemaVersion: 2,
              status: "migrated",
              message: "Migrated",
            },
          }),
        ]}
      />,
    );

    expect(screen.getByText(/Settings \(1 field\)/)).toBeTruthy();
    expect(screen.getByText("Settings Migration")).toBeTruthy();
  });

  it("renders multiple extensions with different settings and migration states", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            extensionId: "ext.a",
            name: "Extension A",
            settingsFields: [
              { key: "theme", label: "Theme", type: "string", currentValue: "dark" },
            ],
            migrationSummary: {
              oldSchemaVersion: 1,
              newSchemaVersion: 2,
              status: "migrated",
            },
          }),
          makeExtension({
            extensionId: "ext.b",
            name: "Extension B",
            settingsFields: [
              { key: "debug", label: "Debug Mode", type: "boolean", currentValue: true },
            ],
            migrationSummary: {
              oldSchemaVersion: 2,
              newSchemaVersion: 2,
              status: "up-to-date",
            },
          }),
        ]}
      />,
    );

    expect(screen.getByText("Extension A")).toBeTruthy();
    expect(screen.getByText("Extension B")).toBeTruthy();
    // Two settings sections
    const settingsHeaders = screen.getAllByText(/Settings \(1 field\)/);
    expect(settingsHeaders.length).toBe(2);
    // Two migration sections
    const migrationHeaders = screen.getAllByText("Settings Migration");
    expect(migrationHeaders.length).toBe(2);
  });

  it("only shows settings panel for extensions that have settingsFields", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            extensionId: "ext.a",
            name: "With Settings",
            settingsFields: [
              { key: "theme", label: "Theme", type: "string", currentValue: "dark" },
            ],
          }),
          makeExtension({
            extensionId: "ext.b",
            name: "Without Settings",
            settingsFields: null,
          }),
        ]}
      />,
    );

    // First extension should have settings
    expect(screen.getByText(/Settings \(1 field\)/)).toBeTruthy();
    // Second extension should not
    const settingsHeaders = screen.getAllByText(/Settings \(1 field\)/);
    expect(settingsHeaders.length).toBe(1);
  });
});

// ---------------------------------------------------------------------------
// T23: Uninstall UI and reference report
// ---------------------------------------------------------------------------

describe("ExtensionsSection uninstall flow", () => {
  // ---- Uninstall button visibility ----

  it("renders Uninstall button for installed extensions when onUninstallExtension is provided", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            source: "installed",
            extensionId: "com.example.ext",
          }),
        ]}
        onUninstallExtension={vi.fn()}
      />,
    );
    expect(screen.getByText("Uninstall")).toBeTruthy();
  });

  it("does not render Uninstall button for local/workspace extensions", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            source: "local",
            extensionId: "com.example.ext",
          }),
        ]}
        onUninstallExtension={vi.fn()}
      />,
    );
    expect(screen.queryByText("Uninstall")).toBeNull();
  });

  it("does not render Uninstall button when onUninstallExtension is not provided", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            source: "installed",
            extensionId: "com.example.ext",
          }),
        ]}
      />,
    );
    expect(screen.queryByText("Uninstall")).toBeNull();
  });

  // ---- Uninstall callback ----

  it("calls onUninstallExtension with correct extensionId when Uninstall is clicked", () => {
    const onUninstall = vi.fn();
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            source: "installed",
            extensionId: "com.example.ext",
          }),
        ]}
        onUninstallExtension={onUninstall}
      />,
    );

    fireEvent.click(screen.getByText("Uninstall"));
    expect(onUninstall).toHaveBeenCalledWith("com.example.ext");
  });

  it("disables Uninstall button when isUninstalling is true", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            source: "installed",
            extensionId: "com.example.ext",
          }),
        ]}
        onUninstallExtension={vi.fn()}
        isUninstalling={true}
      />,
    );

    const btn = screen.getByText("Uninstall");
    expect(btn).toBeDisabled();
  });

  it("disables Uninstall button when isPerformingAction is true", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            source: "installed",
            extensionId: "com.example.ext",
          }),
        ]}
        onUninstallExtension={vi.fn()}
        isPerformingAction={true}
      />,
    );

    const btn = screen.getByText("Uninstall");
    expect(btn).toBeDisabled();
  });

  // ---- Reference report panel (no references) ----

  it("shows no-references panel when pendingUninstallReport has no references", () => {
    const report = makeReferenceReport("com.example.ext", {
      hasReferences: false,
      totalReferenceCount: 0,
    });

    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            source: "installed",
            extensionId: "com.example.ext",
            name: "Test Extension",
          }),
        ]}
        onUninstallExtension={vi.fn()}
        pendingUninstallReport={report}
      />,
    );

    expect(screen.getByText("No project references found")).toBeTruthy();
    expect(
      screen.getByText(/can be safely uninstalled/),
    ).toBeTruthy();
  });

  it("shows Uninstall Extension button in no-references panel", () => {
    const report = makeReferenceReport("com.example.ext", {
      hasReferences: false,
    });

    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            source: "installed",
            extensionId: "com.example.ext",
            name: "Test Extension",
          }),
        ]}
        onUninstallExtension={vi.fn()}
        pendingUninstallReport={report}
      />,
    );

    expect(screen.getByText("Uninstall Extension")).toBeTruthy();
  });

  it("shows confirm/cancel buttons after clicking Uninstall Extension", () => {
    const report = makeReferenceReport("com.example.ext", {
      hasReferences: false,
    });

    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            source: "installed",
            extensionId: "com.example.ext",
            name: "Test Extension",
          }),
        ]}
        onUninstallExtension={vi.fn()}
        pendingUninstallReport={report}
      />,
    );

    fireEvent.click(screen.getByText("Uninstall Extension"));
    expect(screen.getByText("Confirm Uninstall")).toBeTruthy();
    expect(screen.getByText("Cancel")).toBeTruthy();
  });

  it("calls onUninstallExtension when Confirm Uninstall is clicked", () => {
    const onUninstall = vi.fn();
    const report = makeReferenceReport("com.example.ext", {
      hasReferences: false,
    });

    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            source: "installed",
            extensionId: "com.example.ext",
            name: "Test Extension",
          }),
        ]}
        onUninstallExtension={onUninstall}
        pendingUninstallReport={report}
      />,
    );

    fireEvent.click(screen.getByText("Uninstall Extension"));
    fireEvent.click(screen.getByText("Confirm Uninstall"));
    expect(onUninstall).toHaveBeenCalledWith("com.example.ext");
  });

  // ---- Reference report panel (with references) ----

  it("shows reference count and warning when references exist", () => {
    const report = makeReferenceReportWithRefs("com.example.ext", 5);

    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            source: "installed",
            extensionId: "com.example.ext",
            name: "Test Extension",
          }),
        ]}
        onUninstallExtension={vi.fn()}
        pendingUninstallReport={report}
      />,
    );

    expect(screen.getByText("5 project references found")).toBeTruthy();
    expect(
      screen.getByText(/will orphan these references/),
    ).toBeTruthy();
  });

  it("shows singular reference count label", () => {
    const report = makeReferenceReportWithRefs("com.example.ext", 1);

    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            source: "installed",
            extensionId: "com.example.ext",
            name: "Test Extension",
          }),
        ]}
        onUninstallExtension={vi.fn()}
        pendingUninstallReport={report}
      />,
    );

    expect(screen.getByText("1 project reference found")).toBeTruthy();
  });

  it("shows 'Uninstall Anyway' button when references exist", () => {
    const report = makeReferenceReportWithRefs("com.example.ext", 2);

    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            source: "installed",
            extensionId: "com.example.ext",
            name: "Test Extension",
          }),
        ]}
        onUninstallExtension={vi.fn()}
        pendingUninstallReport={report}
      />,
    );

    expect(screen.getByText("Uninstall Anyway")).toBeTruthy();
  });

  it("shows confirmation after clicking Uninstall Anyway", () => {
    const report = makeReferenceReportWithRefs("com.example.ext", 1);

    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            source: "installed",
            extensionId: "com.example.ext",
            name: "Test Extension",
          }),
        ]}
        onUninstallExtension={vi.fn()}
        pendingUninstallReport={report}
      />,
    );

    fireEvent.click(screen.getByText("Uninstall Anyway"));
    expect(screen.getByText("Confirm — Orphan References")).toBeTruthy();
    expect(screen.getByText("Cancel")).toBeTruthy();
  });

  it("calls onUninstallExtension when confirming with orphan references", () => {
    const onUninstall = vi.fn();
    const report = makeReferenceReportWithRefs("com.example.ext", 3);

    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            source: "installed",
            extensionId: "com.example.ext",
            name: "Test Extension",
          }),
        ]}
        onUninstallExtension={onUninstall}
        pendingUninstallReport={report}
      />,
    );

    fireEvent.click(screen.getByText("Uninstall Anyway"));
    fireEvent.click(screen.getByText("Confirm — Orphan References"));
    expect(onUninstall).toHaveBeenCalledWith("com.example.ext");
  });

  // ---- Expandable reference breakdown ----

  it("shows reference kind labels with counts", () => {
    const report = makeReferenceReportWithRefs("com.example.ext", 3);

    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            source: "installed",
            extensionId: "com.example.ext",
            name: "Test Extension",
          }),
        ]}
        onUninstallExtension={vi.fn()}
        pendingUninstallReport={report}
      />,
    );

    // Effect kind label should show with count
    expect(screen.getByText("Effect")).toBeTruthy();
    expect(screen.getByText("(3)")).toBeTruthy();
  });

  it("expands reference kind to show individual references", () => {
    const report = makeReferenceReportWithRefs("com.example.ext", 2);

    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            source: "installed",
            extensionId: "com.example.ext",
            name: "Test Extension",
          }),
        ]}
        onUninstallExtension={vi.fn()}
        pendingUninstallReport={report}
      />,
    );

    fireEvent.click(screen.getByText("Effect"));
    // Individual references should be visible
    expect(screen.getByText("com.example.ext.effect0")).toBeTruthy();
    expect(screen.getByText("com.example.ext.effect1")).toBeTruthy();
  });

  it("truncates reference list at 20 entries with '+N more'", () => {
    const refs = Array.from({ length: 25 }, (_, i) =>
      makeReference({
        referenceId: `com.example.ext.effect${i}`,
        location: `Timeline > Clip ${i}`,
      }),
    );

    const report: ExtensionReferenceReport = {
      extensionId: "com.example.ext",
      totalReferenceCount: 25,
      referencesByKind: { effect: refs },
      hasReferences: true,
      scanIsComplete: true,
    };

    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            source: "installed",
            extensionId: "com.example.ext",
            name: "Test Extension",
          }),
        ]}
        onUninstallExtension={vi.fn()}
        pendingUninstallReport={report}
      />,
    );

    fireEvent.click(screen.getByText("Effect"));
    // Should show only first 20 refs
    expect(screen.getByText("+5 more")).toBeTruthy();
  });

  // ---- Incomplete scan warning ----

  it("shows incomplete scan warning when scanIsComplete is false", () => {
    const report = makeReferenceReportWithRefs("com.example.ext", 1);
    const incompleteReport = { ...report, scanIsComplete: false };

    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            source: "installed",
            extensionId: "com.example.ext",
            name: "Test Extension",
          }),
        ]}
        onUninstallExtension={vi.fn()}
        pendingUninstallReport={incompleteReport}
      />,
    );

    expect(
      screen.getByText(/Reference scan is incomplete/),
    ).toBeTruthy();
  });

  it("does not show incomplete scan warning when scanIsComplete is true", () => {
    const report = makeReferenceReportWithRefs("com.example.ext", 1);

    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            source: "installed",
            extensionId: "com.example.ext",
            name: "Test Extension",
          }),
        ]}
        onUninstallExtension={vi.fn()}
        pendingUninstallReport={report}
      />,
    );

    expect(
      screen.queryByText(/Reference scan is incomplete/),
    ).toBeNull();
  });

  // ---- Multiple reference kinds ----

  it("shows multiple reference kind sections", () => {
    const report: ExtensionReferenceReport = {
      extensionId: "com.example.ext",
      totalReferenceCount: 4,
      referencesByKind: {
        effect: [
          makeReference({ kind: "effect", referenceId: "eff1", location: "T1" }),
          makeReference({ kind: "effect", referenceId: "eff2", location: "T2" }),
        ],
        transition: [
          makeReference({ kind: "transition", referenceId: "trans1", location: "T1" }),
        ],
        settings: [
          makeReference({ kind: "settings", referenceId: "theme", location: "Config" }),
        ],
      },
      hasReferences: true,
      scanIsComplete: true,
    };

    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            source: "installed",
            extensionId: "com.example.ext",
            name: "Test Extension",
          }),
        ]}
        onUninstallExtension={vi.fn()}
        pendingUninstallReport={report}
      />,
    );

    expect(screen.getByText("4 project references found")).toBeTruthy();
    // Each kind should have a button
    const effectButtons = screen.getAllByText("Effect");
    expect(effectButtons.length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Transition")).toBeTruthy();
    expect(screen.getByText("Settings")).toBeTruthy();
  });

  // ---- Panel only shows for matching extension ----

  it("does not show reference panel when report is for a different extension", () => {
    const report = makeReferenceReportWithRefs("com.other.ext", 2);

    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            source: "installed",
            extensionId: "com.example.ext",
            name: "Test Extension",
          }),
        ]}
        onUninstallExtension={vi.fn()}
        pendingUninstallReport={report}
      />,
    );

    // Report is for com.other.ext, so it should not show in com.example.ext's row
    expect(screen.queryByText("No project references found")).toBeNull();
    expect(screen.queryByText("2 project references found")).toBeNull();
  });

  // ---- pendingUninstallReport is null ----

  it("does not show reference panel when pendingUninstallReport is null", () => {
    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            source: "installed",
            extensionId: "com.example.ext",
            name: "Test Extension",
          }),
        ]}
        onUninstallExtension={vi.fn()}
        pendingUninstallReport={null}
      />,
    );

    expect(screen.queryByText("No project references found")).toBeNull();
    expect(screen.queryByText(/project reference/)).toBeNull();
  });

  // ---- Disabled state during uninstall ----

  it("disables confirm buttons when isUninstalling is true", () => {
    const report = makeReferenceReport("com.example.ext", {
      hasReferences: false,
    });

    render(
      <ExtensionsSection
        isMobile={false}
        extensions={[
          makeExtension({
            source: "installed",
            extensionId: "com.example.ext",
            name: "Test Extension",
          }),
        ]}
        onUninstallExtension={vi.fn()}
        pendingUninstallReport={report}
        isUninstalling={true}
      />,
    );

    const btn = screen.getByText("Uninstall Extension");
    expect(btn).toBeDisabled();
  });
});


});