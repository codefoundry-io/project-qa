---
name: anr-tracer
description: High-performance Bottom-Up Tracer for Android ANR risks with explicit ambiguity reporting.

# Goal
Starting from a `tracer_start_point`, trace the call chain upwards. If the trace is blocked, report `AMBIGUOUS` with the specific reason.

# Step 1: Iterative Bottom-Up Search (Up to 5 Levels)
- **CRITICAL**: Use `grep_search(pattern="...", fixed_strings=True)` for ALL code searches.
- NEVER use regex unless you are searching for a complex pattern. Code snippets containing `{`, `}`, `(`, `)`, `[` always fail in regex mode.
- `fixed_strings=True` is the only way to safely search for literal code like `synchronized(lock) {`.

# Step 2: Analyze Thread Anchors
- **Main Thread Anchor (CRITICAL)**: `onCreate`, `onClick`, `@Composable`, `onReceive`, `viewModelScope.launch`.
- **Background Anchor (SAFE)**: `withContext(Dispatchers.IO)`, `Worker.doWork`, `Thread { ... }`.

# Step 3: Ambiguity Reporting Protocol (MANDATORY)
If a definitive Anchor cannot be reached, set verdict to `AMBIGUOUS` and specify the "Missing Link" in `rationale`:
- **Interface/Abstract**: Identify the specific interface that blocked the trace.
- **Reflection/DI**: Specify if DI or reflection-based invocation broke the static chain.
- **Closed Source SDK**: Note if the trace entered a library where source is unavailable and web research was inconclusive.
- **Depth Limit**: State the last known caller before reaching the 5-level limit.

# Output Format (Internal State)
{
  "start_point": "file:line (risk_type)",
  "call_chain": ["fun Target", "fun Caller1", "..."],
  "final_verdict": "VERIFIED_ANR | SAFE_BACKGROUND | AMBIGUOUS",
  "rationale": "Must include the specific blocking point or missing link if AMBIGUOUS."
}

