# Platform ticket → unlaunched epic linking review

## Recommendation

Keep ticket `01KY2DWSJG0B9YKAJRYA0107XE` **open** and link it to the initiative by adding the canonical structured entry below to its `epics` frontmatter list after the initiative exists at:

`.megaplan/initiatives/native-workflow-platformization/chain.yaml`

```yaml
epics:
- epic_id: native-workflow-platformization
  resolves_on_complete: true
  linked_at: '<current UTC ISO-8601 timestamp>'
```

Use the initiative directory slug, `native-workflow-platformization`, as the epic ID. Local precedent links tickets to the initiative/chain slug (for example `aggressive-generalized-pipeline-migration`), not to the `chain.yaml` path and not to an invented ULID.

`resolves_on_complete: true` is appropriate because the new epic fully promotes the ticket's work. This does **not** address the ticket now. The auto-address hook only changes an open ticket to `addressed` after an epic event with the matching `epic_id` reaches `state: done`. Since the initiative is only being authored and not launched, the ticket remains open.

Do not add a prose-only value such as:

```yaml
epics:
- native-workflow-platformization
```

One older local ticket uses that legacy shorthand, but both active ticket implementations and the auto-address hook expect mapping entries with `epic_id`, `resolves_on_complete`, and `linked_at`.

## Current state observed

- The ticket is untracked, `status: open`, `codebase_id: null`, and currently has `epics: []`.
- The target chain did not exist at the time of this review; another task is expected to create it.
- `SUPABASE_DB_URL`, `MEGAPLAN_STORE_URL`, and `MEGAPLAN_BACKEND` are unset, so ticket handling is local-only. No cloud mirror/editorial state is required.
- No standalone `megaplan` executable is installed (`command -v megaplan` returned nothing).
- `python -m arnold_pipelines.megaplan --help` does not expose `ticket`.
- The code contains a ticket handler and canonical `link()` operation, but `build_parser()` never registers a `ticket` subparser. Therefore the skill-documented `megaplan ticket link ... --resolves` route is unreachable in this checkout despite the implementation existing behind it.

## Safest implementation in this task

Use `apply_patch` to replace `epics: []` in the ticket with the structured entry above and update `last_edited_at` to the same UTC timestamp. This follows the repository's canonical on-disk format while avoiding an unavailable CLI and any accidental backend resolution.

Then validate read-only:

1. Parse the frontmatter with `yaml.safe_load`.
2. Assert `status == "open"`.
3. Assert exactly one entry has `epic_id == "native-workflow-platformization"` and `resolves_on_complete is True`.
4. Assert `.megaplan/initiatives/native-workflow-platformization/chain.yaml` exists.

No ticket body rewrite is required. Optionally add one short body note saying the runnable epic now lives at that chain path, but the structured frontmatter link is the machine-readable relationship and should be the source of truth.

## Why not mark it addressed

Promotion is not resolution. Marking it `addressed` now would hide unfinished work from open-ticket discovery and bypass the repository's automatic resolution lifecycle. The correct lifecycle is:

```text
open ticket → linked unlaunched epic → epic launches later → epic completes → auto-address
```

