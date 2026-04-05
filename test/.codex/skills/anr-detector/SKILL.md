---
name: anr-detector
description: Identify Android ANR risk signals from code and preprocessing hints, estimate blocking severity, and explain whether dependencies such as disk, database, IPC, network, decode, or crypto can contribute to main-thread blocking. Use when analyzing ANR candidates, blocking APIs, startup paths, receivers, services, or unknown Android SDK behavior.
---

# ANR Detector

Use this skill when the task is to assess ANR risk from a candidate location before or alongside caller tracing.

## Goal

Produce a high-signal initial risk assessment for Android code that may block the UI or main thread directly or indirectly through blocking dependencies.
The primary developer-facing questions are:

- Can this code run on the UI or main thread?
- Is this an apparently simple API that can still block long enough to matter?
- Even if it runs off the UI thread, is it heavy enough to create indirect ANR pressure through locks, CPU, disk, IPC, or startup coupling?

## Working Model

- Treat preprocessing labels such as `Risk Type` as hints, not conclusions.
- Focus on blocking characteristics first:
  - disk I/O
  - database access
  - binder / content provider IPC
  - synchronous network
  - decode / media work
  - crypto / keystore work
  - lock hold time
  - explicit waiting primitives
- Estimate severity conservatively, but let code evidence override the hint.
- Treat waiting for remote responses, database locks, binder replies, file I/O completion, or SDK callbacks as latency-uncertain blocking unless a clear timeout or safe async boundary is proven.
- Do not downgrade risk just because the API surface looks asynchronous. Check for hidden sync bridges, `await`, `get`, `join`, `runBlocking`, binder round-trips, or callback-to-blocking adapters.
- Only classify work as effectively safe when the offload boundary and timeout behavior are both visible in code, or when the path is otherwise clearly bounded and background-only.

## Tool Use

- Use installed CLI tools directly instead of inventing helper scripts.
- Prefer `rg` for fast text search and file discovery.
- Prefer `sg` when you need structure-aware matches such as synchronized blocks, annotations, or method bodies.
- Prefer `jq` for checking consistency across generated JSON results.
- For literal code snippets containing `(`, `)`, `{`, `}`, or `[`, use fixed-string search with `rg -F` instead of regex.
- When using `sg`, wrap the pattern in single quotes.

## What To Check

1. Identify the concrete blocking primitive or dependency.
2. Determine whether the code path is startup-, lifecycle-, receiver-, service-, or UI-adjacent.
3. State whether the suspicious operation is directly on a possible main/UI path, clearly background-only, or still unresolved.
4. Check whether the work is bounded, deferred, timed out, or safely offloaded.
5. Consider indirect ANR risk:
   - lock contention with UI paths
   - resource starvation from large I/O or CPU work
   - slow SDK or system dependency behavior
6. For broadcast-driven candidates, do not judge risk from receiver body size alone.
   - Treat the receiver as a possible fan-out entrypoint.
   - Check whether the event is propagated into shared trackers, listeners, callbacks, observers, or handler-posted follow-up work.
   - Raise suspicion when the same system event can trigger multiple downstream components or shared state updates.
7. Call out deceptively simple APIs when relevant.
   - Examples: system-service lookups, binder calls, content-resolver access, database helpers, file open/read helpers, decode helpers, crypto wrappers, synchronous waits.
   - If a call looks small in code but can hide slow I/O, IPC, package scans, keystore work, or cache misses, say so explicitly.
8. Call out uncertain wait states explicitly.
   - Examples: waiting for network responses, provider replies, DB locks, service connections, future completion, callback completion, or SDK-internal worker results.
   - If the code may block on an external response and you cannot prove a timeout or strict background isolation, say that the latency is uncertain and bias severity upward.

## Unknown SDK Rule

If you encounter a third-party or platform API whose blocking behavior is unclear, look up official documentation or primary-source discussions before concluding it is safe.

Use queries like:

- `Android <SDK> <Method> main thread safety`
- `<SDK> <Method> blocking call Android`

Prefer official documentation first, then primary-source issue discussions if docs are inconclusive.

## Gold Standard References

- ANR overview: `https://developer.android.com/topic/performance/vitals/anr`
- Main-safe coroutines: `https://developer.android.com/kotlin/coroutines/coroutines-best-practices#main-safe`
- Android threading guide: `https://developer.android.com/guide/components/processes-and-threads`
- Broadcast receiver context: `https://developer.android.com/guide/components/broadcasts#receiver-context`
- App startup guidance: `https://developer.android.com/topic/libraries/app-startup`

## Time Budget Reference

- `16ms`: frame budget
- `100ms`: user-perceptible delay threshold for blocking work
- `5000ms`: hard ANR timeout class for input stalls

Use these budgets in practical terms:

- UI-thread work that can plausibly exceed `16ms` should be treated as jank-prone even if not ANR-class.
- Blocking work that can plausibly exceed `100ms` should be called out as developer-visible latency risk.
- Work on input-, startup-, receiver-, or lifecycle-critical paths should be described as higher risk even when exact latency is unknown.
- Background-only work can still be high risk if it holds locks, saturates I/O, or delays startup-critical state transitions.
- Unknown or externally-controlled wait time should be treated as a risk multiplier, not as evidence of safety.

## Output Expectations

Prefer concise structured reasoning that answers:

- What is the suspicious operation?
- Can it happen on the UI/main thread, or is that still unresolved?
- Why can it block?
- Which Android time budget is most likely to be violated?
- What is the initial severity?
- What evidence supports that severity?

Do not stop at “this looks slow”. Tie the risk to Android thread context and blocking behavior.
