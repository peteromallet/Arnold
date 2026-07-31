---
id: 01KYSXVF1PW4AF44SWKGS52M97
title: Make ticket discovery tolerant of legacy Markdown and malformed frontmatter
status: addressed
source: human
tags:
- bug
- tickets
- reliability
- cli
codebase_id: null
created_at: '2026-07-30T16:31:21.142151+00:00'
last_edited_at: '2026-07-31T02:31:00+00:00'
resolution_note: >-
  Exact document-leading delimiter parsing now isolates malformed and legacy
  Markdown, emits deterministic stderr diagnostics while preserving valid
  list/search results, and the active CLI ticket surface is regression-tested.
addressed_at: '2026-07-31T02:31:00+00:00'
epics: []
---

`megaplan ticket search` currently crashes while scanning a legacy Markdown note that has no YAML frontmatter but contains `---` horizontal rules later in the body. `read_ticket_file()` uses `text.split("---", 2)` without first requiring a frontmatter opener at byte zero, so arbitrary body text is parsed as YAML; one colon in prose raises `yaml.scanner.ScannerError` and aborts the entire ticket inventory.

Required fix:

- Recognize frontmatter only when the file begins with an exact `---` delimiter line and has a later exact closing delimiter line.
- Treat legacy Markdown notes without frontmatter as non-ticket/legacy records without attempting YAML parsing.
- Isolate malformed ticket files: list/search should return the valid inventory plus a deterministic diagnostic for malformed files, not crash globally.
- Add fixtures for body horizontal rules, colons in prose, missing closing delimiters, malformed YAML, and a mixed directory where valid tickets remain searchable.
- Restore the documented `megaplan ticket` parser surface in the active CLI entrypoint; the handlers exist but the current parser rejects `ticket` as an invalid command.
