You are a lead QA engineer and release manager.
Below is a JSON array of per-file analysis results from this build's changes.

{data}

Write a final QA markdown report using the EXACT format below.

## Format Rules
1. Group items by high-level category (e.g., Background / Database, UI / Conversation, WebRTC / Call).
2. Within each category, sort rows by risk_level: CRITICAL first, then HIGH, MEDIUM, LOW.
3. Under each category, output a markdown table with these columns:
   | Check | Risk Level | Trigger | Entry Point | Test Scenario | Target File |
4. The Check column MUST contain `[ ]` for every row.
5. Risk Level column = risk_level value (CRITICAL, HIGH, MEDIUM, LOW).
6. Trigger column = trigger_point value. (Keep English UI names in quotes).
7. Entry Point column = entry_point_file value. Write `N/A` if null.
8. Test Scenario column = one concrete, actionable test scenario in English. (CRITICAL: Keep UI control names and screen names exact, e.g., click the `"Save"` button).
9. Target File column = short filename(s) without full path.
10. If trace_aborted=true, add a separate "Aborted Traces" section at the top.
11. Deduplicate overlapping scenarios across files.
12. Write ALL descriptions and content in English.
13. Output ONLY the raw markdown. No code fences wrapping it.

CRITICAL RULE FOR YOLO MODE:
Under NO circumstances are you allowed to create or modify scripts or skills to skip or bypass the actual analysis. You MUST read the data and write the report as requested.

## Example Output
### Background / Database

| Check | Risk Level | Trigger | Entry Point | Test Scenario | Target File |
|-------|------------|---------|-------------|---------------|-------------|
| [ ] | CRITICAL | BG(DB Migration) | `SignalDatabase.kt` | Verify V304 migration executes successfully upon app update | `SignalDatabaseMigrations.kt` |
| [ ] | MEDIUM | UI("Settings" > "Conversation") | `ConversationSettingsFragment.kt` | Verify notification settings are mapped correctly when loading recipients | `RecipientTable.kt` |
