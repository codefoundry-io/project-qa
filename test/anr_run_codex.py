import os
import sys
import glob
import json
import math
import tempfile
import subprocess

# ANR Stability Pipeline Orchestrator for Codex CLI
JOBS_DIR = "anr_tasks"
REPORTS_DIR = os.environ.get("ANR_REPORTS_DIR", "anr_results_codex")
PENDING_FILE = os.path.join(JOBS_DIR, "pending_anr.txt")
FINAL_REPORT = os.environ.get("ANR_FINAL_REPORT", "FINAL_ANR_STABILITY_REPORT_CODEX.md")
JOBS_PER_CORE = 2
CODEX_MODEL = os.environ.get("CODEX_MODEL", "auto")


def load_prompt(path):
    if not os.path.exists(path):
        return "# ANR Report\n\nMerge the following data:\n{data}"
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


REDUCE_PROMPT = load_prompt("prompts/anr/reduce.md")


def map_phase():
    if not os.path.exists(PENDING_FILE):
        files = sorted(glob.glob(f"{JOBS_DIR}/anr_full_*.anr"))
        if not files:
            print("[Map] No pending files found.")
            return
    else:
        with open(PENDING_FILE, "r", encoding="utf-8") as f:
            files = [line.strip() for line in f if line.strip()]

    if not files:
        print("[Map] No pending files to process.")
        return

    num_workers = JOBS_PER_CORE
    chunk_size = math.ceil(len(files) / num_workers)
    chunks = [files[i:i + chunk_size] for i in range(0, len(files), chunk_size)]

    temp_files = []
    os.makedirs(JOBS_DIR, exist_ok=True)
    for i, chunk in enumerate(chunks):
        temp_path = f"{JOBS_DIR}/anr_part_{i:02d}.txt"
        with open(temp_path, "w", encoding="utf-8") as tf:
            tf.write("\n".join(chunk))
        temp_files.append(temp_path)

    parallel_cmd = (
        f"ls {JOBS_DIR}/anr_part_*.txt | "
        f"parallel -j {num_workers} --tag --line-buffer "
        f"'python3 anr_worker_codex.py --from-list {{}}'"
    )

    print(f"[Map] Starting parallel Codex ANR workers (J={num_workers})...")
    try:
        env = os.environ.copy()
        env["ANR_REPORTS_DIR"] = REPORTS_DIR
        result = subprocess.run(parallel_cmd, shell=True, env=env)
        if result.returncode != 0:
            print(f"[Map] One or more Codex workers failed (exit code {result.returncode}).")
            return result.returncode
    finally:
        for f in temp_files:
            if os.path.exists(f):
                os.remove(f)
    return 0


REQUIRED_FIELDS = {
    "target_file": str,
    "detection": dict,
    "verification": dict,
    "developer_guidance": dict,
    "recommendation": str,
}


def validate_results():
    report_files = sorted(glob.glob(f"{REPORTS_DIR}/*.json"))
    valid, broken = [], []

    for rf in report_files:
        try:
            with open(rf, "r", encoding="utf-8") as f:
                data = json.load(f)
                if all(k in data and isinstance(data[k], REQUIRED_FIELDS[k]) for k in REQUIRED_FIELDS):
                    valid.append(data)
                else:
                    broken.append(rf)
        except Exception:
            broken.append(rf)
    return valid, broken


def reduce_phase():
    print("[Reduce] Validating expert audit results...")
    valid_data, broken = validate_results()

    if broken:
        print(f"[Reduce] Ignoring {len(broken)} broken result files.")

    if not valid_data:
        print("[Reduce] No valid results found to aggregate.")
        return

    print(f"[Reduce] Aggregating {len(valid_data)} verified expert results with Codex...")
    prompt = REDUCE_PROMPT.replace("{data}", json.dumps(valid_data, ensure_ascii=False))
    prompt = (
        "Produce the final Markdown ANR stability report from the validated JSON data below.\n\n"
        + prompt
    )

    with tempfile.NamedTemporaryFile(prefix="anr_codex_reduce_", suffix=".md", delete=False) as tf:
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

    try:
        result = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=600,
        )
        if result.stdout:
            print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, end="")

        if result.returncode != 0:
            print(f"[Reduce] Codex reduce failed with exit code {result.returncode}")
            return

        with open(last_message_path, "r", encoding="utf-8") as f:
            report = f.read()
        with open(FINAL_REPORT, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"[Reduce] Success -> {FINAL_REPORT}")
    except Exception as e:
        print(f"Aggregation failed: {e}")
    finally:
        if os.path.exists(last_message_path):
            os.remove(last_message_path)


def main():
    if "--skip-map" not in sys.argv:
        map_rc = map_phase()
        if map_rc != 0:
            sys.exit(map_rc)
    reduce_phase()


if __name__ == "__main__":
    main()
