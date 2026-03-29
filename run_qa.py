import os
import sys
import subprocess
import glob
import json
import re
import time

JOBS_DIR = "map_jobs"
REPORTS_DIR = "map_results"
PENDING_FILE = os.path.join(JOBS_DIR, "pending.txt")
GEMINI_TIMEOUT = 1800
NODE_HEAP_MB = 8192
SESSION_COOLDOWN = 5
GEMINI_MODEL = "auto"
# GEMINI_MODEL = "auto"                    # → -m 없이 실행 (자동 선택)
# GEMINI_MODEL = "gemini-2.5-pro"          # → -m gemini-2.5-pro
# GEMINI_MODEL = "gemini-3.1-pro-preview"  # → -m gemini-3.1-pro-preview

TOKEN_LIMIT_ERRORS = (
    "payload size exceeds",
    "Token count exceeds",
    "token limit",
    "context window",
    "maximum limit",
    "400 Bad Request",
    "400 Invalid",
)

RATE_LIMIT_ERRORS = (
    "RESOURCE_EXHAUSTED",
    "MODEL_CAPACITY_EXHAUSTED",
    "rateLimitExceeded",
    "429",
    "Too Many Requests",
)

ANALYSIS_PROMPT = """\
You are running the qa-tracer skill. Analyze each diff file and write a JSON result.
Follow the rules in your qa-tracer skill and its references/ documents.

## Task
Read each .diff file → analyze → write .json to {reports_dir}/.
Do NOT stop until all files are done.

## File List
{file_list}
"""

REDUCE_PROMPT = """\
You are a lead QA engineer and release manager.
Below is a JSON array of per-file analysis results from this build's changes.

{data}

Write a final QA markdown report using the EXACT format below.

## Format Rules
1. Group items by high-level category (e.g., Background / Database, UI / Conversation, WebRTC / Call).
2. Within each category, sort rows by risk_level: CRITICAL first, then HIGH, MEDIUM, LOW.
3. Under each category, output a markdown table with these columns:
   | 확인 | 위험도 | 트리거 | 진입점 | 테스트 시나리오 | 대상 파일 |
4. The 확인 column MUST contain `[ ]` for every row.
5. 위험도 column = risk_level value (CRITICAL, HIGH, MEDIUM, LOW).
6. 트리거 column = trigger_point value.
7. 진입점 column = entry_point_file value. Write `N/A` if null.
8. 테스트 시나리오 column = one concrete, actionable test scenario in Korean.
9. 대상 파일 column = short filename(s) without full path.
10. If trace_aborted=true, add a separate "추적 중단 항목" section at the top.
11. Deduplicate overlapping scenarios across files.
12. Write all descriptions in Korean.
13. Output ONLY the raw markdown. No code fences wrapping it.

## Example Output
### Background / Database

| 확인 | 위험도 | 트리거 | 진입점 | 테스트 시나리오 | 대상 파일 |
|------|--------|--------|--------|----------------|-----------|
| [ ] | CRITICAL | BG(DB Migration) | `SignalDatabase.kt` | 앱 업데이트 시 V304 마이그레이션이 정상 수행되는지 확인 | `SignalDatabaseMigrations.kt` |
| [ ] | MEDIUM | UI(Settings > Conversation) | `ConversationSettingsFragment.kt` | 수신자 로드 시 알림 설정이 정상 매핑되는지 확인 | `RecipientTable.kt` |
"""


def load_pending():
    if os.path.exists(PENDING_FILE):
        with open(PENDING_FILE, "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]
    return sorted(glob.glob(f"{JOBS_DIR}/*.diff"))


def save_pending(files):
    with open(PENDING_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(files) + "\n")


def get_completed():
    return {
        os.path.basename(f).replace(".json", "")
        for f in glob.glob(f"{REPORTS_DIR}/*.json")
    }


def is_token_limit_error(output):
    lower = output.lower()
    return any(e.lower() in lower for e in TOKEN_LIMIT_ERRORS)


def is_rate_limit_error(output):
    lower = output.lower()
    return any(e.lower() in lower for e in RATE_LIMIT_ERRORS)


def build_file_list(pending):
    lines = []
    for job_file in pending:
        name = os.path.basename(job_file).replace(".diff", "")
        lines.append(f"- Read: {job_file} → Write: {REPORTS_DIR}/{name}.json")
    return "\n".join(lines)


def run_gemini_session(pending):
    file_list = build_file_list(pending)
    prompt = ANALYSIS_PROMPT.format(
        reports_dir=REPORTS_DIR,
        file_list=file_list,
    )

    env = os.environ.copy()
    env["NODE_OPTIONS"] = f"--max-old-space-size={NODE_HEAP_MB}"

    cmd = ["gemini", "-p", prompt, "--yolo"]
    if GEMINI_MODEL and GEMINI_MODEL.lower() != "auto":
        cmd += ["-m", GEMINI_MODEL]

    print(f"  Launching gemini CLI ({len(pending)} files, model={GEMINI_MODEL}) ...\n")

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=env,
        )

        output = ""
        for line in process.stdout:
            print(f"  > {line}", end="")
            output += line

        process.wait(timeout=GEMINI_TIMEOUT)
        return process.returncode, output

    except subprocess.TimeoutExpired:
        process.kill()
        return -1, "TIMEOUT"
    except Exception as e:
        return -1, f"ERROR: {e}"


def map_phase():
    os.makedirs(REPORTS_DIR, exist_ok=True)
    pending = load_pending()
    total_original = len(pending)

    if not pending:
        print("[Map] No pending jobs.")
        return

    session = 0
    stall_count = 0
    rate_limit_retries = 0
    MAX_STALLS = 3
    MAX_RATE_RETRIES = 5
    RATE_LIMIT_BACKOFF = [60, 120, 240, 300, 300]
    while pending:
        session += 1
        completed_before = get_completed()

        remaining = [f for f in pending
                     if os.path.basename(f).replace(".diff", "") not in completed_before]

        if not remaining:
            break

        print(f"\n{'=' * 60}")
        print(f" Session {session}: {len(remaining)} files remaining (of {total_original})")
        print(f"{'=' * 60}")

        save_pending(remaining)

        if session > 1 and SESSION_COOLDOWN > 0:
            print(f"  Cooldown {SESSION_COOLDOWN}s before next session...")
            time.sleep(SESSION_COOLDOWN)

        returncode, output = run_gemini_session(remaining)

        completed_after = get_completed()
        newly_done = completed_after - completed_before
        print(f"\n  Session {session} ended: {len(newly_done)} files written to {REPORTS_DIR}/")

        pending = [f for f in remaining
                   if os.path.basename(f).replace(".diff", "") not in completed_after]
        save_pending(pending)

        if not pending:
            print(f"  All files complete!")
            break

        if is_rate_limit_error(output):
            rate_limit_retries += 1
            if rate_limit_retries > MAX_RATE_RETRIES:
                print(f"  Rate limit: {rate_limit_retries} retries exhausted. Aborting.")
                print(f"  Remaining files saved to {PENDING_FILE}")
                break
            wait = RATE_LIMIT_BACKOFF[min(rate_limit_retries - 1, len(RATE_LIMIT_BACKOFF) - 1)]
            print(f"  Rate limit hit (attempt {rate_limit_retries}/{MAX_RATE_RETRIES}). "
                  f"Waiting {wait}s...")
            time.sleep(wait)
            continue

        rate_limit_retries = 0

        if not newly_done:
            stall_count += 1
            print(f"  No progress (stall {stall_count}/{MAX_STALLS}).")
            if stall_count >= MAX_STALLS:
                print(f"  Aborting: {stall_count} consecutive sessions with no progress.")
                print(f"  Remaining files saved to {PENDING_FILE}")
                break
            if is_token_limit_error(output):
                print(f"  Token limit hit. Retrying...")
                continue
            print(f"  Error (code={returncode}). Aborting.")
            break
        else:
            stall_count = 0
            if returncode != 0:
                print(f"  Error but made progress. Restarting...")
                continue

    print(f"\n[Map] Done. {len(get_completed())} results in {REPORTS_DIR}/")


REQUIRED_FIELDS = {
    "target_file": str,
    "change_summary": str,
    "risk_level": str,
    "trigger_point": str,
    "entry_point_file": (str, type(None)),
    "test_method": list,
    "confirmed_facts": list,
    "trace_aborted": bool,
    "abort_reason": (str, type(None)),
}

VALID_RISK_LEVELS = {"CRITICAL", "HIGH", "MEDIUM", "LOW"}


def validate_results():
    report_files = sorted(glob.glob(f"{REPORTS_DIR}/*.json"))
    if not report_files:
        return [], []

    valid = []
    broken = []

    for rf in report_files:
        name = os.path.basename(rf)
        errors = []

        try:
            with open(rf, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            broken.append({"file": name, "errors": [f"Invalid JSON: {e}"]})
            continue

        if not isinstance(data, dict):
            broken.append({"file": name, "errors": ["Root is not a JSON object"]})
            continue

        for field, expected_type in REQUIRED_FIELDS.items():
            if field not in data:
                errors.append(f"Missing field: {field}")
            elif not isinstance(data[field], expected_type):
                errors.append(f"{field}: expected {expected_type}, got {type(data[field]).__name__}")

        risk = data.get("risk_level")
        if risk and risk not in VALID_RISK_LEVELS:
            errors.append(f"Invalid risk_level: {risk}")

        if errors:
            broken.append({"file": name, "errors": errors})
        else:
            valid.append(rf)

    return valid, broken


def reduce_phase():
    print("[Validate] Checking result files...")
    valid_files, broken = validate_results()

    if broken:
        print(f"[Validate] {len(broken)} broken file(s):")
        for b in broken:
            print(f"  ✗ {b['file']}")
            for e in b["errors"]:
                print(f"      {e}")

    if not valid_files:
        print("[Reduce] No valid results to merge.")
        return

    print(f"[Validate] {len(valid_files)} valid, {len(broken)} broken")

    reduce_input = []
    entry_counter = {}
    risk_weights = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}

    for rf in valid_files:
        with open(rf, "r", encoding="utf-8") as f:
            data = json.load(f)
            reduce_input.append({
                "target_file": data.get("target_file"),
                "change_summary": data.get("change_summary"),
                "risk_level": data.get("risk_level"),
                "trigger_point": data.get("trigger_point"),
                "entry_point_file": data.get("entry_point_file"),
                "test_method": data.get("test_method"),
                "trace_aborted": data.get("trace_aborted"),
                "abort_reason": data.get("abort_reason"),
            })

            ep = data.get("entry_point_file")
            if ep:
                if ep not in entry_counter:
                    entry_counter[ep] = {"count": 0, "max_risk": "LOW", "files": []}
                entry_counter[ep]["count"] += 1
                entry_counter[ep]["files"].append(
                    data.get("target_file", "").rsplit("/", 1)[-1])
                cur_risk = data.get("risk_level", "LOW")
                if risk_weights.get(cur_risk, 0) > risk_weights.get(
                        entry_counter[ep]["max_risk"], 0):
                    entry_counter[ep]["max_risk"] = cur_risk

    hotspots = sorted(entry_counter.items(), key=lambda x: (
        -x[1]["count"], -risk_weights.get(x[1]["max_risk"], 0)))
    hotspot_lines = []
    for ep, info in hotspots:
        if info["count"] >= 2:
            ep_short = ep.rsplit("/", 1)[-1] if "/" in ep else ep
            hotspot_lines.append(
                f"- **{ep_short}**: {info['count']}건 변경, "
                f"최고 위험도 {info['max_risk']} "
                f"({', '.join(info['files'][:5])}{'...' if len(info['files']) > 5 else ''})")

    hotspot_section = ""
    if hotspot_lines:
        hotspot_section = (
            "\n\n## 주요 변경 집중 지점 (Entry Point Hotspots)\n\n"
            "아래 진입점은 다수의 파일이 동시에 변경되었으므로 통합 테스트가 필요합니다.\n\n"
            + "\n".join(hotspot_lines)
        )
        print(f"[Hotspots] {len(hotspot_lines)} entry points with 2+ changes")

    print(f"[Reduce] Merging {len(reduce_input)} results...")

    prompt = REDUCE_PROMPT.format(data=json.dumps(reduce_input, ensure_ascii=False))
    if hotspot_section:
        prompt += (
            "\n\n## Additional Section to Include\n"
            "Add the following section at the END of the report, BEFORE any closing remarks:\n"
            + hotspot_section
        )
    env = os.environ.copy()
    env["NODE_OPTIONS"] = f"--max-old-space-size={NODE_HEAP_MB}"

    reduce_cmd = ["gemini", "-p", prompt, "--output-format", "json"]
    if GEMINI_MODEL and GEMINI_MODEL.lower() != "auto":
        reduce_cmd += ["-m", GEMINI_MODEL]

    try:
        result = subprocess.run(
            reduce_cmd,
            capture_output=True, text=True, timeout=600, env=env,
        )
        try:
            parsed = json.loads(result.stdout)
            report_text = parsed.get("response", result.stdout)
        except json.JSONDecodeError:
            report_text = result.stdout
    except subprocess.TimeoutExpired:
        report_text = "# QA Report\n\nReduce phase timed out. Check individual results in map_results/."
    except Exception as e:
        report_text = f"# QA Report\n\nReduce phase failed: {e}"

    with open("FINAL_QA_REPORT.md", "w", encoding="utf-8") as f:
        f.write(report_text)

    print("[Reduce] Done -> FINAL_QA_REPORT.md")


def main():
    map_phase()
    reduce_phase()


if __name__ == "__main__":
    main()
