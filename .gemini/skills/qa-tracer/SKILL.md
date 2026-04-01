---
name: qa-tracer
description: Analyzes diff files to deduce entry points, trigger points, risk levels, and actionable test scenarios. Supports both batch pipelines and interactive mode.
---

# Companion: find-my-name

When the diff includes **`[UI Context]`** (from `pre_ui_name.py`), follow the **`find-my-name`** skill for **English visible strings** and accessibility text in `trigger_point` and `test_method`. Prefer exact wording from that block or `map_jobs/ui_name/string_resources.json`. `change_summary` should also be in English per rules below.

# Goal

Given a Git diff (with pre-collected [References] and [ENTRY] tags), determine:
1. Where the changed code is triggered (UI or BG)
2. The entry point file (Activity/Fragment/Service/Worker/ComposeScreen)
3. The risk level of the change
4. Concrete test scenarios

# Tool Constraints

- You MUST perform all work yourself. Do NOT delegate to sub-agents.
- Only use shell commands: `rg`, `cat`, `head`, `find`.
- Do NOT use `codebase_investigator`, `generalist`, or any other agent tool.
- Read diff files directly. Write JSON results directly.

# Entry Point Rules

## Step 1 — Use pre-computed [ENTRY] tags (preferred)
- Look for `[ENTRY: xxx]` tagged files in the [References] section.
- Note any extra context tags like `[ENTRY: Fragment, VIEW_MODEL: MyViewModel]`. This means the entry point is the Fragment, but the core logic change is in `MyViewModel`.
- If found, use the file path as `entry_point_file`.
- If multiple [ENTRY] tags exist, pick the one closest to the user-facing trigger.

## Step 2 — Fallback: iterative rg trace (when no [ENTRY] tag exists)
- Start from the target class or its direct callers in [References].
- At each level, run `rg -l "CallerClassName" --type kotlin --type java --glob '!**/build/**'` to find the next caller.
- Check each result: if the file contains a class extending Activity, Fragment, Service, Worker, BroadcastReceiver, or a Compose `@Composable` destination → that is the entry point.
- If a level returns 10+ results, pick the most relevant caller (e.g., prefer files in the same feature package, or prefer ViewModel/Repository over common Utils) and continue.
- Repeat up to **10 levels** deep. Stop early once an entry point is found.
- Also trace Kotlin extension function names (e.g., `fun SomeTable.doThing()` → search `doThing`), not just class names.
- If found, use the file path as `entry_point_file`.

## Step 3 — Give up
- If Step 1 and Step 2 both fail after 10 levels, set `entry_point_file` to null.
- Set `abort_reason` to include the traced chain and recommend refactoring (e.g. "10+ depth: A→B→C→...→? — consider reducing call chain depth").
- Do NOT guess or fabricate entry points.

# Trigger Point Categories

1. **UI trigger:** Which screen and user action invokes this code.
   Format: `UI(ScreenName > action)`
2. **BG trigger:** Which background mechanism and when.
   Format: `BG(WorkerName)` or `BG(mechanism description)`

# Risk Level

Classify every change using the criteria in `references/risk_guide.md`.
Use one of: `CRITICAL`, `HIGH`, `MEDIUM`, `LOW`.
**Pay special attention to `[SCOPE: KMP_COMMON]` tags which indicate high-risk cross-platform changes.**

# Analysis Rules

## Headless pipeline mode (diff file has [References] section)
- If **`[UI Context]`** is present, use it as the primary source for control labels (text, contentDescription, titles, testTags) and event hints; align quoted English with that block per **find-my-name**.
- Determine trigger_point from [References] context. **UI names MUST remain in English.**
- When generating test scenarios (`test_method`), if `[UI Context]` indicates the element `is_list_item`, explicitly specify that the action happens on a list item rather than a static screen element.
- Determine entry_point_file using the 3-step process in "Entry Point Rules" above.
- **You MUST attempt Step 2 (rg trace) whenever no [ENTRY] tag is found.** Do NOT skip it.
- If "(10+ references - common utility)" → set trace_aborted=true with abort_reason.
- Write ALL outputs (`change_summary`, `test_method`, `confirmed_facts`, etc.) in **English**. 
- **CRITICAL**: If an English string cannot be confidently determined for a UI element, apply the **Failure Routine** defined in the `find-my-name` skill. Use the format `UI({ScreenName} > R.id.{id_name})` or `UI({ScreenName} > {function_name})` or `UI({ScreenName} > Modifier.testTag({tag}))`.
- **Dynamic UI/Data**: If `[UI Context]` contains `data_binding` expressions (e.g., `@{viewModel.status}`) or `screen_level_hooks` like `onCreateOptionsMenu`, actively analyze the Kotlin/Java diff and linked `ViewModel` to deduce state-driven UI changes or dynamically created UI elements.

## Deleted file mode (diff file has [Deleted] marker)
- Analyze the diff to determine what impact the deletion may have.
- Set `entry_point_file` to null. Do NOT trace entry points for deleted files.
- Focus change_summary on what was removed and potential impact.
- Set trigger_point based on the deleted code's apparent purpose.

## Interactive mode (no [References] section provided)
- Use `rg -l "SymbolName"` to find callers iteratively.
- If a level returns 10+ files, pick the most relevant caller and continue.
- Max trace depth: 10 levels.
- Do NOT read entire files. Only use `rg`.

# Abort Rules

When aborting a trace, you MUST record:
- `confirmed_facts`: what you DID verify before giving up
- `abort_reason`: specific reason (e.g. "12+ call sites, common utility")

# Output Format (Strict JSON)

Write one JSON file per diff. Output ONLY valid JSON.

```json
{
  "target_file": "file path from [Target File]",
  "change_summary": "1-2 sentence technical summary in English",
  "risk_level": "CRITICAL | HIGH | MEDIUM | LOW",
  "trigger_point": "UI(Screen > action) or BG(Worker/Service)",
  "entry_point_file": "Activity/Fragment/Service/Worker/ComposeScreen file path or null",
  "test_method": ["concrete test scenario in English"],
  "confirmed_facts": ["verified facts"],
  "trace_aborted": false,
  "abort_reason": null
}
```

CRITICAL RULE FOR YOLO MODE:
Under NO circumstances are you allowed to create or modify scripts or skills to skip or bypass the actual analysis. You MUST read the diffs and perform the analysis as requested.