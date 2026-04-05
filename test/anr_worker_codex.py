import os
import sys
import time
import tempfile
import subprocess

# ANR Stability Worker for Codex CLI
JOBS_DIR = "anr_tasks"
REPORTS_DIR = os.environ.get("ANR_REPORTS_DIR", "anr_results_codex")
CODEX_TIMEOUT = int(os.environ.get("CODEX_TIMEOUT", "3600"))
CODEX_MODEL = os.environ.get("CODEX_MODEL", "auto")

TOKEN_LIMIT_ERRORS = (
    "payload size exceeds",
    "token count exceeds",
    "token limit",
    "context window",
    "maximum limit",
    "maximum context length",
    "context length",
)
RATE_LIMIT_ERRORS = (
    "RESOURCE_EXHAUSTED",
    "MODEL_CAPACITY_EXHAUSTED",
    "rateLimitExceeded",
    "rate limit",
    "429",
    "Too Many Requests",
    "quota exhausted",
    "QUOTA_EXHAUSTED",
)


def load_prompt(path):
    if not os.path.exists(path):
        return "# ANR Analysis\n\nOne job per request; payload is embedded in the prompt."
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


ANALYSIS_PROMPT = load_prompt("prompts/anr/analysis_codex.md")

# 0 = no truncation (embed full file). Set when a single .anr is huge.
ANR_MAX_INLINE_CHARS = int(os.environ.get("ANR_MAX_INLINE_CHARS", "0"))


def is_token_limit_error(output):
    lower = output.lower()
    return any(e.lower() in lower for e in TOKEN_LIMIT_ERRORS)


def is_rate_limit_error(output):
    lower = output.lower()
    return any(e.lower() in lower for e in RATE_LIMIT_ERRORS)


def read_job_text(job_file: str) -> str:
    with open(job_file, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()
    if ANR_MAX_INLINE_CHARS > 0 and len(text) > ANR_MAX_INLINE_CHARS:
        text = text[:ANR_MAX_INLINE_CHARS] + "\n\n[... truncated: ANR_MAX_INLINE_CHARS ...]\n"
    return text


def build_prompt(job_file: str) -> str:
    name = os.path.basename(job_file).replace(".anr", "")
    output_path = os.path.join(REPORTS_DIR, f"{name}.json")
    payload = read_job_text(job_file)
    job_block = (
        f"## Output file (write exactly one JSON here)\n\n`{output_path}`\n\n"
        "## This session’s `.anr` payload only\n\n"
        "<<<ANR_JOB_START>>>\n"
        f"{payload}\n"
        "<<<ANR_JOB_END>>>\n"
    )
    return ANALYSIS_PROMPT.replace("{reports_dir}", REPORTS_DIR).replace("{job_block}", job_block)


def run_codex_session(job_file: str):
    prompt = build_prompt(job_file)
    os.makedirs(REPORTS_DIR, exist_ok=True)

    with tempfile.NamedTemporaryFile(prefix="anr_codex_last_", suffix=".md", delete=False) as tf:
        last_message_path = tf.name

    cmd = [
        "codex",
        "--search",
        "exec",
        "--dangerously-bypass-approvals-and-sandbox",
        "-o",
        last_message_path,
        "-",
    ]
    if CODEX_MODEL != "auto":
        cmd += ["-m", CODEX_MODEL]

    output = ""
    process = None
    try:
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        assert process.stdin is not None
        process.stdin.write(prompt)
        process.stdin.close()

        assert process.stdout is not None
        for line in process.stdout:
            print(line, end="", flush=True)
            output += line

        process.wait(timeout=CODEX_TIMEOUT)
        return process.returncode, output
    except subprocess.TimeoutExpired:
        output += "\nTIMEOUT"
        if process is not None:
            process.kill()
            try:
                process.wait(timeout=5)
            except Exception:
                pass
        return -1, output
    except KeyboardInterrupt:
        if process is not None:
            process.kill()
            try:
                process.wait(timeout=5)
            except Exception:
                pass
        raise
    except Exception as e:
        output += f"\nERROR: {e}"
        if process is not None:
            process.kill()
            try:
                process.wait(timeout=5)
            except Exception:
                pass
        return -1, output
    finally:
        if os.path.exists(last_message_path):
            try:
                with open(last_message_path, "r", encoding="utf-8") as f:
                    message = f.read().strip()
                    if message:
                        print("\n[Codex Summary]")
                        print(message)
                        output += "\n" + message
            finally:
                os.remove(last_message_path)


def worker_main(batch_files):
    os.makedirs(REPORTS_DIR, exist_ok=True)
    pending = batch_files
    rate_limit_retries = 0
    max_rate_retries = 5
    rate_limit_backoff = [60, 120, 240, 300, 300]
    success = True

    while pending:
        completed = {
            os.path.basename(f).replace(".json", "")
            for f in os.listdir(REPORTS_DIR)
            if f.endswith(".json")
        }
        remaining = [
            f for f in pending if os.path.basename(f).replace(".anr", "") not in completed
        ]

        if not remaining:
            break

        job_file = remaining[0]
        if not os.path.isfile(job_file):
            print(f"\n[Worker Error] Job file not found: {job_file}", flush=True)
            success = False
            break
        stem = os.path.basename(job_file).replace(".anr", "")
        print(f"\n[Worker] Codex session (1 job): {job_file}", flush=True)
        returncode, output = run_codex_session(job_file)

        if is_rate_limit_error(output):
            rate_limit_retries += 1
            if rate_limit_retries > max_rate_retries:
                print("\n[Worker Error] Rate limit exhausted. Aborting.", flush=True)
                success = False
                break
            wait = rate_limit_backoff[min(rate_limit_retries - 1, len(rate_limit_backoff) - 1)]
            print(f"\n[Worker Wait] Rate limit hit. Waiting {wait}s...", flush=True)
            time.sleep(wait)
            continue

        rate_limit_retries = 0

        new_completed = {
            os.path.basename(f).replace(".json", "")
            for f in os.listdir(REPORTS_DIR)
            if f.endswith(".json")
        }
        newly_done_count = 1 if stem in new_completed else 0

        if newly_done_count == 0:
            if is_token_limit_error(output):
                print(
                    "\n[Worker Info] Token limit hit on single-job session; retrying same job. "
                    "Set ANR_MAX_INLINE_CHARS to truncate payload if needed.",
                    flush=True,
                )
                continue
            if returncode != 0:
                print(f"\n[Worker Error] Codex session failed with exit code {returncode}.", flush=True)
            else:
                print("\n[Worker Error] No progress made in session. Aborting.", flush=True)
            success = False
            break

    print("\n[Worker Done] Assigned batch completed.", flush=True)
    return 0 if success else 1


def _iter_manifest_lines(manifest_path: str):
    if manifest_path == "-":
        for line in sys.stdin:
            yield line
    else:
        with open(manifest_path, "r", encoding="utf-8") as f:
            for line in f:
                yield line


def load_jobs_from_manifest(manifest_path: str):
    """
    Read manifest line by line. Each non-empty, non-comment line is one job path
    (usually a .anr file). Paths relative to the manifest file’s directory.
    """
    if manifest_path != "-" and not os.path.isfile(manifest_path):
        print(f"[Worker Error] Manifest not found: {manifest_path}", flush=True)
        return []

    base_dir = os.getcwd() if manifest_path == "-" else os.path.dirname(
        os.path.abspath(manifest_path)
    )
    jobs = []
    for raw in _iter_manifest_lines(manifest_path):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        p = line if os.path.isabs(line) else os.path.normpath(os.path.join(base_dir, line))
        jobs.append(p)
    return jobs


def parse_argv(argv):
    """
    --from-list <file>   Read job paths from file (one per line). Use - for stdin.
    Otherwise              Each argument is a job path (legacy / parallel $(cat)).
    """
    if len(argv) >= 2 and argv[0] == "--from-list":
        return load_jobs_from_manifest(argv[1])
    return list(argv)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(
            "Usage: python3 anr_worker_codex.py --from-list <manifest.txt>\n"
            "       python3 anr_worker_codex.py job1.anr [job2.anr ...]",
            file=sys.stderr,
        )
        sys.exit(1)
    sys.exit(worker_main(parse_argv(sys.argv[1:])))
