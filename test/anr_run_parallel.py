import os
import sys
import subprocess
import math
import glob

# Configuration
PENDING_FILE = "anr_tasks/pending_anr.txt"
REPORTS_DIR = "anr_results"
REPORT_FILE = "FINAL_ANR_STABILITY_REPORT.md"
MAX_PARALLEL = 2     # Number of simultaneous workers (True separate sessions)

def main():
    # 1. Collect pending files
    if os.path.exists(PENDING_FILE):
        with open(PENDING_FILE, "r") as f:
            files = [line.strip() for line in f if line.strip()]
    else:
        files = sorted(glob.glob("anr_tasks/anr_*.anr"))
    
    if not files:
        print("[Map] No pending ANR jobs found.")
        return

    # Filter out already completed files
    completed = {os.path.basename(f).replace(".json", ".anr") for f in glob.glob(f"{REPORTS_DIR}/*.json")}
    remaining = [f for f in files if os.path.basename(f) not in completed]
    
    if not remaining:
        print("[Map] All files already analyzed.")
    else:
        # 2. Prepare remaining files for Parallel
        remaining_list_path = "anr_tasks/remaining_files.txt"
        with open(remaining_list_path, "w") as f:
            f.write("\n".join(remaining))

        # 3. Execute GNU Parallel (True Parallelism per File)
        # Each file gets its own anr_worker.py execution (separate Gemini session)
        # -j {MAX_PARALLEL} ensures we only run X sessions at a time
        parallel_cmd = (
            f"cat {remaining_list_path} | "
            f"parallel -j {MAX_PARALLEL} --tag --line-buffer "
            f"'python3 anr_worker.py {{}}'"
        )
        
        print(f"[Map] Starting parallel ANR workers (Max Parallel={MAX_PARALLEL}, Remaining Jobs={len(remaining)})...")
        try:
            subprocess.run(parallel_cmd, shell=True)
        finally:
            if os.path.exists(remaining_list_path): os.remove(remaining_list_path)

    # 4. Reduce Phase (Final Report)
    print("\n[Reduce] Generating final ANR Stability Report...")
    subprocess.run(["python3", "anr_run.py", "--skip-map"])

if __name__ == "__main__":
    main()
