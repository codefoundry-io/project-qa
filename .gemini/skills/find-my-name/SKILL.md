---
name: find-my-name
description: Maps Android UI code and static resources to human-visible English labels for QA triggers and test steps. Use with pre_ui_name output ([UI Context]) and res/values strings. Complements qa-tracer.
---

# Goal

Help validators match reports to the real app by naming controls with **English strings from `res/values/strings.xml`** (canonical product copy), plus `contentDescription`, hints, and menu titles.

# Inputs (pipeline)

- Enriched diff may include a **`[UI Context]`** block from `pre_ui_name.py` (layout/menu paths, `@id/...` with resolved text, `[event:kind] R.id.*`, screen-level hooks).
- `map_jobs/ui_name/string_resources.json` — merged `name → value` from all `**/res/values/strings.xml` (no locale overlays in default pipeline).

# Rules

1. **Quoted UI copy**: When you name a control in `trigger_point` or `test_method`, prefer the **exact English string** from `[UI Context]` or `string_resources.json`, in double quotes (e.g. `"Notification settings"`).
2. **Event verbs**: Match the event kind when helpful — tap (click), long-press, scroll, swipe-to-refresh, focus, text input, pager change — not every trigger is a tap.
3. **Compose**: If `[UI Context]` notes Compose-heavy, read the diff for `Text("...")`, `stringResource(R.string.xxx)`, `contentDescription` / `Modifier.semantics { ... }`.
4. **Ambiguous ids**: If several files share the same abstract screen name, use **`[Target File]`** or a layout path from `[UI Context]` to disambiguate in `confirmed_facts` or the scenario text.
5. **No fabrication**: If no string or description exists, say so in `confirmed_facts` and keep the trigger functional (e.g. `UI(Settings > local backups row)`) without inventing button labels.

# Relation to qa-tracer

- **qa-tracer** owns entry point tracing, risk level, JSON schema, and Korean summaries.
- **find-my-name** owns how **English visible strings** and **accessibility text** appear inside `trigger_point` and `test_method` when `[UI Context]` or string lookup is available.
- If both skills apply, follow qa-tracer for structure and find-my-name for **label wording**.

# Tools

Same lightweight shell tools as qa-tracer: `rg`, `cat`, `head`, `find` — e.g. resolve `R.string.xxx` via `rg "name=\"xxx\"" **/values/strings.xml` if the JSON index is missing.
