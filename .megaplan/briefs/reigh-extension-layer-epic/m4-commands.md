# M4: Commands, Keybindings, Context Menus

## Outcome

Add discoverable extension actions: provider-scoped command registry, command palette integration, safe keybindings, context-menu contributions, and patch-backed command examples.

## Execution Posture

Commands are affordances, not backdoors. They should be discoverable, reversible where they mutate state, respectful of built-in shortcuts, and routed through the same patch/proposal spine as UI and agent workflows.

## Scope

IN:
- Define `CommandContribution`, `KeybindingContribution`, and `ContextMenuItemContribution`.
- Add provider-scoped `CommandRegistry`.
- Resolve `when` predicates against stable `ExtensionContext` and target context.
- Add command palette surface for contributed commands.
- Add context-menu hooks for clip, clip selection, shot group, track, and timeline area.
- Add keybinding conflict rules.
- Add examples that invoke `TimelineOps` or proposals.
- Add command diagnostics, last-run status, and unregister lifecycle.

OUT:
- Full workbench/action system.
- User-customizable keybinding editor.
- Overriding built-in destructive/navigation shortcuts.

## Locked Decisions

- Built-in command IDs and reserved keybindings are not extension-overridable in this phase.
- Extension commands run through the same error/diagnostic containment as surfaces.
- Commands that mutate timeline data must use `TimelineOps` or proposals.
- Initial command palette is an editor-level overlay surface backed by the provider-scoped command registry.
- Keybindings use a normalized platform-aware string grammar with explicit reserved built-in shortcuts.
- First context-menu targets are clip, clip selection, track, and timeline area; shot-group support is included only if a stable target context already exists, otherwise it is diagnosed as reserved.
- Command palette is a fixed host-owned overlay, not a contributed surface. Trigger is `CtrlOrCmd+Shift+P`, reserved and not overridable. It supports text filtering, grouped categories, keyboard navigation, Enter invoke, and Escape dismiss.
- Keybinding grammar is `[Modifier+]Key`, where modifiers are `Ctrl`, `Cmd`, `Alt`, `Shift`, and `CtrlOrCmd`. Examples: `CtrlOrCmd+Z`, `Ctrl+Shift+K`, `Alt+ArrowRight`.
- Built-in command IDs use reserved `reigh.*` IDs; extensions may not register commands with the `reigh.` prefix.
- Built-in shortcuts always win. Extension-vs-extension keybinding conflicts are deterministic: first registered wins; later registrations emit diagnostics.
- `TargetContext` is a sealed union for `clip`, `clip-selection`, `track`, and `timeline-area`. Context menus snapshot target context at open time; stale-target failures produce diagnostics/toasts.
- `CommandRegistry.unregister(extensionId)` removes all commands, keybindings, and context menu items for HMR/removal.
- Commands that throw/reject publish a command diagnostic and show a toast. Structured mutation failures publish diagnostics without crashing the palette/menu.

## Constraints

- Keybindings must not break existing editor shortcuts.
- Context menus must remain stable when target entities disappear between open and invoke.

## Done Criteria

- Example extension contributes command, keybinding, palette entry, and clip context menu item.
- Conflicts are reported deterministically.
- Tests cover `when` predicates, disabled commands, target context, and mutation failure.
- Tests cover built-in shortcut precedence and duplicate command/keybinding conflicts.
- Tests cover palette search/navigation/invoke, stale target context, unregister lifecycle, and command failure diagnostics.

## Touchpoints

- Existing shortcut/command code
- Context menu components
- Timeline selection/target logic
- SDK command types
