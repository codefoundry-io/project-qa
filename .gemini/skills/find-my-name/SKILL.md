---
name: find-my-name
description: Maps Android UI code and static resources to human-visible English labels for QA triggers and test steps. Use with pre_ui_name output ([UI Context]) and res/values strings. Complements qa-tracer.
---

# Goal

Help validators match reports to the real app by naming controls with **English strings from `res/values/strings.xml`** (canonical product copy), plus `contentDescription`, hints, and menu titles.
DO NOT TRANSLATE THESE STRINGS. KEEP THEM EXACTLY AS WRITTEN.

# Inputs (pipeline)

- Enriched diff may include a **`[UI Context]`** block from `pre_ui_name.py` (layout/menu paths, `@id/...` with resolved text, `[event:kind] R.id.*`, screen-level hooks, `compose_elements`).
- `map_jobs/ui_name/string_resources.json` — merged `name → value` from all `**/res/values/strings.xml` (no locale overlays in default pipeline).

# Rules

1.  **Quoted UI copy**: When you name a control in `trigger_point` or `test_method`, prefer the **exact English string** from `[UI Context]` or `string_resources.json`, in double quotes (e.g. `"Notification settings"`).
2.  **Event verbs**: Match the event kind when helpful — tap (click), long-press, scroll, swipe-to-refresh, focus, text input, pager change — not every trigger is a tap.
3.  **Compose First**: Actively use the `compose_elements` section in `[UI Context]` to find `testTag`, `contentDescription`, or extracted text.
4.  **Dynamic Lists**: If `[UI Context]` mentions "RecyclerView Item Click detected" or `is_list_item` is true, explicitly state that the action happens on a list item. Example: Tap on `"Chat list item"`.

# Failure Routine (CRITICAL)

If you cannot find a clear, human-readable English string for a UI element after a quick check of `[UI Context]` and the diff, **DO NOT continue searching**. Instead, you MUST provide a fallback name that is understandable to QA personnel, based on the `entry_point_file`'s class name and the technical identifier (ID/testTag/function).

Convert the CamelCase class name into a readable Screen/Action name.
Use the format: `UI({Readable Screen Name} > [Developer ID: {technical_id}])`

**Fallback Formats:**

1.  **If a View ID or Compose testTag is known:**
    - Extract the readable screen name from the `entry_point_file` (e.g., `BackupSetupCompleteBottomSheet` -> "Backup Setup Complete").
    - Format: `UI("{Readable Screen Name}" > [Developer ID: {id_or_tag}])`
    - Example: `UI("Conversation" > [Developer ID: send_button])`
    - Example: `UI("Backup Setup Complete" > [Developer ID: optimize_storage_toggle])`

2.  **If no ID/Tag is known, but an event handler function is:**
    - Extract the readable screen name.
    - Format: `UI("{Readable Screen Name}" > [Developer Event: {function_name}])`
    - Example: `UI("Internal Settings" > [Developer Event: onClearDataClicked])`

3.  **Confirm the failure:** In the `confirmed_facts` array, add a note like: `"No visible UI string found; used screen name and technical identifier as fallback."`

This ensures QA knows *which screen* to look at, and provides the exact technical ID so they can ask developers if they cannot find the button.

# Relation to qa-tracer

- **qa-tracer** owns entry point tracing, risk level, JSON schema, and summaries.
- **find-my-name** owns how **English visible strings** and **accessibility text** appear inside `trigger_point` and `test_method`, including the critical **Failure Routine**.
- If both skills apply, follow qa-tracer for structure and find-my-name for **label wording (STRICTLY IN ENGLISH)**.

# Tools

Same lightweight shell tools as qa-tracer: `rg`, `cat`, `head`, `find` — e.g. resolve `R.string.xxx` via `rg "name=\"xxx\"" **/values/strings.xml` if the JSON index is missing.

CRITICAL RULE FOR YOLO MODE:
Under NO circumstances are you allowed to create or modify scripts or skills to skip or bypass the actual analysis. You MUST read the data and apply the formatting rules as requested.
