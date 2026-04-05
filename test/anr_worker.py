import os
import sys
import subprocess
import json
import time

# ANR Stability Worker (Clone of test_worker.py architecture)
JOBS_DIR = "anr_tasks"
REPORTS_DIR = "anr_results"
GEMINI_TIMEOUT = 3600
NODE_HEAP_MB = 8192
GEMINI_MODEL = "auto"

TOKEN_LIMIT_ERRORS = ("payload size exceeds", "Token count exceeds", "token limit", "context window", "maximum limit", "400 Bad Request", "400 Invalid")
RATE_LIMIT_ERRORS = ("RESOURCE_EXHAUSTED", "MODEL_CAPACITY_EXHAUSTED", "rateLimitExceeded", "429", "Too Many Requests")

def load_prompt(path):
    if not os.path.exists(path):
        return "# ANR Report\n\nMerge the following data:\n{data}"
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

ANALYSIS_PROMPT = load_prompt("prompts/anr/analysis.md")

def is_token_limit_error(output):
    lower = output.lower()
    return any(e.lower() in lower for e in TOKEN_LIMIT_ERRORS)

def is_rate_limit_error(output):
    lower = output.lower()
    return any(e.lower() in lower for e in RATE_LIMIT_ERRORS)

def run_gemini_session(pending):
    file_list = ""
    for job_file in pending:
        name = os.path.basename(job_file).replace(".anr", "")
        file_list += f"- Read: {job_file} -> Write: {REPORTS_DIR}/{name}.json\n"
    
    prompt = ANALYSIS_PROMPT.replace("{reports_dir}", REPORTS_DIR).replace("{file_list}", file_list)
    env = os.environ.copy()
    env["NODE_OPTIONS"] = f"--max-old-space-size={NODE_HEAP_MB}"
    
    cmd = ["gemini", "-p", prompt, "--yolo"]
    if GEMINI_MODEL != "auto":
        cmd += ["-m", GEMINI_MODEL]
    
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
    
    output = ""
    for line in process.stdout:
        print(line, end="", flush=True)
        output += line
    
    process.wait(timeout=GEMINI_TIMEOUT)
    return process.returncode, output

def worker_main(batch_files):
    os.makedirs(REPORTS_DIR, exist_ok=True)
    pending = batch_files
    rate_limit_retries = 0
    MAX_RATE_RETRIES = 5
    RATE_LIMIT_BACKOFF = [60, 120, 240, 300, 300]
    
    while pending:
        completed = {os.path.basename(f).replace(".json", "") for f in os.listdir(REPORTS_DIR) if f.endswith(".json")}
        remaining = [f for f in pending if os.path.basename(f).replace(".anr", "") not in completed]
        
        if not remaining: break

        print(f"\n[Worker] Starting session for {len(remaining)} files...", flush=True)
        returncode, output = run_gemini_session(remaining)
        
        if is_rate_limit_error(output):
            rate_limit_retries += 1
            if rate_limit_retries > MAX_RATE_RETRIES:
                print(f"\n[Worker Error] Rate limit exhausted. Aborting.", flush=True)
                break
            wait = RATE_LIMIT_BACKOFF[min(rate_limit_retries - 1, len(RATE_LIMIT_BACKOFF) - 1)]
            print(f"\n[Worker Wait] Rate limit hit. Waiting {wait}s...", flush=True)
            time.sleep(wait)
            continue
        
        rate_limit_retries = 0
        
        new_completed = {os.path.basename(f).replace(".json", "") for f in os.listdir(REPORTS_DIR) if f.endswith(".json")}
        newly_done_count = len([f for f in remaining if os.path.basename(f).replace(".diff", "") in new_completed])
        
        if newly_done_count == 0:
            if is_token_limit_error(output): 
                print("\n[Worker Info] Token limit hit, will retry with fewer files.", flush=True)
                continue
            print("\n[Worker Error] No progress made in session. Aborting.", flush=True)
            break
            
    print(f"\n[Worker Done] Assigned batch completed.", flush=True)

if __name__ == "__main__":
    if len(sys.argv) < 2: sys.exit(1)
    worker_main(sys.argv[1:])
