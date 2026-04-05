---
name: qa-tracer
description: Analyze diff files to determine user or background trigger points, likely Android entry points, risk level, and concrete QA scenarios. Use when reviewing enriched diffs that include references, entry tags, or UI context for validator-facing output.
---

# QA Tracer

Use this skill when the task is to analyze a diff and produce QA-facing trigger, entry-point, risk, and test guidance.

## Companion Skill

If the diff includes `[UI Context]`, also use `find-my-name`.

- Use it for English visible strings and accessibility text inside `trigger_point` and `test_method`.
- Prefer exact wording from `[UI Context]` or `map_jobs/ui_name/string_resources.json`.
- `change_summary` must also remain in English.

## Goal

Given a git diff, usually enriched with `[References]`, `[ENTRY]`, or `[UI Context]`, determine:

1. Where the changed code is triggered, UI or background.
2. Which file is the closest entry point.
3. The change risk level.
4. Concrete QA scenarios.

## Tool Constraints

- Perform the analysis yourself. Do not delegate to sub-agents.
- Limit shell usage to `rg`, `cat`, `head`, and `find`.
- Read diff files directly.
- Write JSON results directly when the task asks for output files.

## Entry Point Rules

### Step 1: Use precomputed `[ENTRY]` tags first

- Check the `[References]` section for tagged files such as `[ENTRY: Fragment]`.
- Preserve extra context like `[ENTRY: Fragment, VIEW_MODEL: MyViewModel]`. The entry point is still the Fragment, while the changed logic may live in the ViewModel.
- If multiple `[ENTRY]` tags exist, choose the one closest to the user-facing trigger.
- When found, set `entry_point_file` to that tagged file path.

Reference: see [entry_point_patterns.md](/home/chaniri/dev/Signal-Android/.codex/skills/qa-tracer/references/entry_point_patterns.md).

### Step 2: Fallback to iterative caller tracing when no `[ENTRY]` tag exists

- Start from the target class or its direct callers listed in `[References]`.
- At each level, search for the next caller with:
  - `rg -l "CallerClassName" --type kotlin --type java --glob '!**/build/**'`
- Also trace Kotlin extension function names, not only class names.
- When a file extends `Activity`, `Fragment`, `Service`, `Worker`, `BroadcastReceiver`, or clearly hosts a Compose destination, treat that as the entry point.
- If one level returns 10 or more results, choose the most relevant caller and continue.
- Prefer callers in the same feature area or meaningful layers such as ViewModel or Repository over generic utility code.
- Stop once an entry point is justified, or after at most 10 levels.

### Step 3: Stop without guessing

- If Steps 1 and 2 both fail, set `entry_point_file` to `null`.
- Set `abort_reason` with the traced chain and a concrete reason, such as a depth-limit or utility fan-out.
- Do not fabricate an entry point.

## Trigger Point Categories

- UI trigger format: `UI(ScreenName > action)`
- Background trigger format: `BG(WorkerName)` or `BG(mechanism description)`

## Risk Level

Classify every change using [risk_guide.md](/home/chaniri/dev/Signal-Android/.codex/skills/qa-tracer/references/risk_guide.md).

- Allowed values: `CRITICAL`, `HIGH`, `MEDIUM`, `LOW`
- Treat `[SCOPE: KMP_COMMON]` as a strong high-risk signal because it affects cross-platform common logic.

## Analysis Rules

### Headless Pipeline Mode

Use this mode when the diff includes a `[References]` section.

- If `[UI Context]` is present, use it as the primary source for control labels, event hints, titles, content descriptions, and test tags.
- Keep UI names in English.
- If `[UI Context]` says `is_list_item`, say explicitly that the action happens on a list item.
- You must attempt Step 2 caller tracing whenever no `[ENTRY]` tag is present.
- If the references indicate a broad utility fan-out such as `(10+ references - common utility)`, set `trace_aborted=true` and explain why.
- Write all output fields in English, including `change_summary`, `test_method`, and `confirmed_facts`.
- If no confident English UI string is available, apply the `find-my-name` failure routine.
- If `[UI Context]` includes `data_binding` expressions or screen-level hooks such as `onCreateOptionsMenu`, inspect the linked Kotlin or Java logic and any referenced ViewModel to infer state-driven or dynamically created UI changes.

### Deleted File Mode

Use this mode when the diff carries a `[Deleted]` marker.

- Analyze what behavior or coverage disappears.
- Set `entry_point_file` to `null`.
- Do not trace entry points for deleted files.
- Base `trigger_point` on the deleted code's apparent purpose.

### Interactive Mode

Use this mode when no `[References]` section is provided.

- Trace callers with `rg -l "SymbolName"`.
- If a level returns 10 or more files, choose the most relevant caller and continue.
- Cap the trace at 10 levels.
- Do not read entire files; prefer search-driven tracing.

## Abort Rules

When a trace aborts, always record:

- `confirmed_facts`: what was verified before stopping
- `abort_reason`: a concrete reason such as `12+ call sites, common utility`

## Output Format

When the task expects JSON output, emit one JSON object per diff and keep it strictly valid.

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

## Integrity Rules

- Do not create or modify scripts or skills to bypass the analysis.
- Read the diffs and perform the trace and classification directly.
