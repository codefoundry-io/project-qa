import os
import sys
import subprocess
import glob
import json
import math

# ANR Stability Pipeline Orchestrator (Clone of test_run_qa.py architecture)
JOBS_DIR = "anr_tasks"
REPORTS_DIR = "anr_results"
PENDING_FILE = os.path.join(JOBS_DIR, "pending_anr.txt")
FINAL_REPORT = "FINAL_ANR_STABILITY_REPORT.md"
JOBS_PER_CORE = 2
NODE_HEAP_MB = 8192
GEMINI_MODEL = "auto"

def load_prompt(path):
    if not os.path.exists(path):
        return "# ANR Report\n\nMerge the following data:\n{data}"
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

REDUCE_PROMPT = load_prompt("prompts/anr/reduce.md")

def map_phase():
    if not os.path.exists(PENDING_FILE):
        # Fallback if pending file doesn't exist
        files = sorted(glob.glob(f"{JOBS_DIR}/anr_full_*.anr"))
        if not files:
            print("[Map] No pending files found.")
            return
    else:
        with open(PENDING_FILE, "r") as f:
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
        with open(temp_path, "w") as tf:
            tf.write("\n".join(chunk))
        temp_files.append(temp_path)

    parallel_cmd = (
        f"ls {JOBS_DIR}/anr_part_*.txt | "
        f"parallel -j {num_workers} --tag --line-buffer "
        f"'python3 anr_worker.py $(cat {{}})'"
    )
    
    print(f"[Map] Starting parallel ANR workers (J={num_workers})...")
    try:
        subprocess.run(parallel_cmd, shell=True)
    finally:
        for f in temp_files:
            if os.path.exists(f): os.remove(f)

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
                else: broken.append(rf)
        except: broken.append(rf)
    return valid, broken

def reduce_phase():
    print("[Reduce] Validating expert audit results...")
    valid_data, broken = validate_results()
    
    if not valid_data:
        print("[Reduce] No valid results found to aggregate.")
        return

    print(f"[Reduce] Aggregating {len(valid_data)} verified expert results...")
    prompt = REDUCE_PROMPT.replace("{data}", json.dumps(valid_data, ensure_ascii=False))
    
    env = os.environ.copy()
    env["NODE_OPTIONS"] = f"--max-old-space-size={NODE_HEAP_MB}"
    cmd = ["gemini", "-p", prompt, "--output-format", "json", "--yolo"]

    if GEMINI_MODEL != "auto":
        cmd += ["-m", GEMINI_MODEL]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600, env=env)
        parsed = json.loads(result.stdout)
        with open(FINAL_REPORT, "w", encoding="utf-8") as f:
            f.write(parsed.get("response", result.stdout))
        print(f"[Reduce] Success -> {FINAL_REPORT}")
    except Exception as e:
        print(f"Aggregation failed: {e}")

def main():
    if "--skip-map" not in sys.argv:
        map_phase()
    reduce_phase()

if __name__ == "__main__":
    main()
