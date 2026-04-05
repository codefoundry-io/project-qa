---
name: anr-tracer
description: Trace Android ANR candidates upward to determine whether the suspicious work can reach the main or UI thread, identify blocking anchors, and explain ambiguity when the call chain is broken by interfaces, DI, reflection, cycles, or depth limits. Use when validating whether a suspected ANR risk is actually main-thread reachable.
---

# ANR Tracer

Use this skill when the task is to verify whether suspicious code can block the main or UI thread.

## Goal

Starting from a concrete risk point, trace callers upward until you can justify one of these outcomes:

- `VERIFIED_ANR`
- `SAFE_BACKGROUND`
- `AMBIGUOUS`

## Core Rules

- Use bounded tracing. Do not revisit the same method, file, or call edge repeatedly.
- If you hit a cycle, stop and report the cycle.
- If DI, interfaces, reflection, or closed-source boundaries break the chain, report the missing link explicitly.
- Favor concrete thread-context evidence over naming conventions or assumptions.
- Default to at most 5 caller hops before declaring a depth-limit ambiguity, unless a nearby anchor is already obvious.

## Tool Use

- Use installed CLI tools directly; do not create scripts to perform the trace.
- Use `rg -F` for literal call-site searches and symbol lookups.
- Use `sg` when caller tracing depends on code structure rather than plain text.
- Use `jq` only for result inspection or cross-file consistency checks, not for the primary trace.
- Search the target file and direct callers first. Use broad repository-wide search only after the local path stops yielding thread-context evidence.

## Thread Anchors

Main/UI anchors commonly include:

- `Application.onCreate`
- `ContentProvider.onCreate`
- `BroadcastReceiver.onReceive`
- `Service.onCreate` / `onStartCommand`
- `Activity` / `Fragment` lifecycle methods
- click handlers and other direct UI callbacks

Safe background anchors commonly include:

- `withContext(Dispatchers.IO)`
- worker / job execution methods
- dedicated background thread entrypoints

## Trace Process

1. Start from the suspicious method or operation.
2. Find direct callers.
3. Continue upward until thread context is established or the chain becomes ambiguous.
4. If the path appears background-only, perform one more check for indirect ANR risk:
   - shared locks with UI code
   - blocking dependency that can stall UI-critical startup or lifecycle work
5. For `BroadcastReceiver.onReceive`, do not stop just because the method looks thin.
   - Trace at least one step into handoff targets such as `handler.post`, listeners, trackers, callbacks, observers, or service handoff.
   - If a broadcast event fans out into multiple downstream consumers, include that fan-out in the rationale even when no single inline call looks expensive.
   - Treat bluetooth, connectivity, package, and other system broadcasts as higher-value fan-out entrypoints.

## Ambiguity Reasons

When the trace cannot be completed, explicitly state which of these caused the break:

- interface or abstract boundary
- DI or reflection boundary
- closed-source SDK boundary
- depth limit reached
- cycle in the call graph

## Output Expectations

Explain:

- the relevant call chain
- the anchor that determined thread context
- the exact reason the result is `AMBIGUOUS`, when applicable

Do not confuse “unable to prove safety” with safety. If the chain is broken before thread context is known, return `AMBIGUOUS`.
