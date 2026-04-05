---
name: find-my-name
description: Map Android UI code and static resources to human-visible English labels for QA triggers and test steps. Use with pre_ui_name output ([UI Context]) and default res/values strings; complements qa-tracer.
---

# Find My Name

Use this skill when QA-oriented analysis needs stable, human-visible control names from Android UI code, especially when `[UI Context]` is available.

## Goal

Help validators match reports to the real app by naming controls with exact English strings from `res/values/strings.xml`, plus `contentDescription`, hints, and menu titles.

- Do not translate strings.
- Keep quoted UI copy exactly as written.

## Inputs

- Enriched diff may include a `[UI Context]` block from `pre_ui_name.py` with layout or menu paths, `@id/...` mappings, resolved text, event hints, screen-level hooks, and `compose_elements`.
- `map_jobs/ui_name/string_resources.json` may contain merged `name -> value` data from all default-locale `**/res/values/strings.xml`.

## Rules

1. For `trigger_point` and `test_method`, prefer the exact English string from `[UI Context]` or `string_resources.json`, wrapped in double quotes.
2. Match the event kind when helpful. Not every trigger is a tap; use verbs such as tap, long-press, scroll, swipe-to-refresh, focus, text input, or pager change when supported by the evidence.
3. Treat Compose metadata as first-class input. Check `compose_elements` for `testTag`, `contentDescription`, and extracted text.
4. If `[UI Context]` says the target is a list item or reports a RecyclerView item click, say explicitly that the action happens on a list item.

## Failure Routine

If you cannot find a clear, human-readable English string after a quick check of `[UI Context]` and the diff, stop searching and use a QA-readable fallback derived from the `entry_point_file` and the technical identifier.

- Convert the CamelCase entry-point class name into a readable screen name.
- Use one of these formats:
  - `UI("{Readable Screen Name}" > [Developer ID: {id_or_tag}])`
  - `UI("{Readable Screen Name}" > [Developer Event: {function_name}])`
- Add this fact to `confirmed_facts`:
  - `"No visible UI string found; used screen name and technical identifier as fallback."`

Examples:

- `UI("Conversation" > [Developer ID: send_button])`
- `UI("Backup Setup Complete" > [Developer ID: optimize_storage_toggle])`
- `UI("Internal Settings" > [Developer Event: onClearDataClicked])`

## Relation To `qa-tracer`

- `qa-tracer` owns entry-point tracing, risk level, JSON schema, summaries, and overall structure.
- `find-my-name` owns English visible-string wording and accessibility text inside `trigger_point` and `test_method`.
- If both skills apply, follow `qa-tracer` for structure and this skill for label wording. All final UI labels must remain in English.

## Tool Use

- Keep the workflow lightweight. Use `rg`, `cat`, `head`, and `find`.
- If `string_resources.json` is missing or insufficient, resolve `R.string.foo` directly from default-locale `values/strings.xml` files.
- Do not delegate to sub-agents.
- Do not create or modify scripts or skills to bypass the analysis.
