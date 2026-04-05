import subprocess
import sys
import os
import re
import json
import glob as globmod
import shutil

# ANR-specific audit configuration (English standard)
FROM_REF = sys.argv[1] if len(sys.argv) > 1 else "HEAD~1"
TO_REF = sys.argv[2] if len(sys.argv) > 2 else "HEAD"

JOBS_DIR = "map_jobs"
REPORTS_DIR = "anr_results"
PENDING_FILE = os.path.join(JOBS_DIR, "pending_anr.txt")

# Expert ANR Risk Patterns (2026 Android Performance Standards)
BLOCKING_PATTERNS = [
    (r"Thread\.sleep", "CRITICAL: Thread Sleep on Main Thread"),
    (r"synchronized\s*\(", "HIGH: Potential Lock Contention (Indirect ANR)"),
    (r"runBlocking", "CRITICAL: runBlocking Coroutine Bridge on Main"),
    (r"SharedPreferences\.edit\(\)\.commit\(\)", "HIGH: Synchronous Disk Write (use apply())"),
    (r"java\.io\.", "HIGH: Blocking I/O Detected"),
    (r"FileInputStream|FileOutputStream", "HIGH: Direct File I/O on Main"),
    (r"CountDownLatch\.await", "HIGH: Thread Synchronization Block"),
    (r"ReentrantLock\.lock", "HIGH: Manual Lock Block"),
    (r"IBinder|asInterface|AIDL", "HIGH: Sync IPC (Binder) Call on Main"),
    (r"GlobalScope", "LOW: Orphan Coroutine (Leak/Resource Drain)"),
    (r"File\.readBytes|File\.writeBytes", "HIGH: Blocking File I/O inside Coroutine"),
    (r"getValue\(\)\s*//\s*from\s*(?:DataStore|Room)", "HIGH: Synchronous DB/Pref access"),
    (r"KoinComponent|by\s+inject\(\)", "MEDIUM: Sync DI Resolution during Startup")
]

THREAD_ANNOTATIONS = ["@MainThread", "@UiThread", "@WorkerThread", "@AnyThread", "@BinderThread"]

def run_cmd(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, check=True).stdout.strip()

def extract_anr_hints(diff_text):
    """Detect high-risk patterns using static regex analysis."""
    hints = []
    for pattern, label in BLOCKING_PATTERNS:
        if re.search(pattern, diff_text):
            hints.append(f"ANALYSIS_HINT: {label}")
    
    # Analyze Thread Context & Dispatcher Usage
    if "Dispatchers.Main" in diff_text:
        hints.append("THREAD_CONTEXT: Explicit Main Thread")
    if "Dispatchers.IO" in diff_text or "Dispatchers.Default" in diff_text:
        hints.append("THREAD_CONTEXT: Background Dispatcher Present")
        
    return hints

def main():
    """Main execution entry point for ANR pre-candidate analysis."""
    print(f"[anr_pre_candidate] Initiating ANR Risk Audit: {FROM_REF} -> {TO_REF}")
    
    # Identify changed source files
    cmd_list = ["git", "diff", "--name-only", FROM_REF, TO_REF]
    changed_files = [f for f in run_cmd(cmd_list).split("\n") if f and (f.endswith(".kt") or f.endswith(".java"))]

    os.makedirs(JOBS_DIR, exist_ok=True)
    job_paths = []

    for idx, filepath in enumerate(changed_files):
        # Request context lines to capture more thread-related patterns
        cmd_diff = ["git", "diff", "-U15", FROM_REF, TO_REF, "--", filepath]
        diff_text = run_cmd(cmd_diff)
        
        if not diff_text: continue
        
        anr_hints = extract_anr_hints(diff_text)
        
        # Construct audit payload for the LLM
        lines = [
            f"[Target File]: {filepath}",
            f"[ANR Hints]: {', '.join(anr_hints) if anr_hints else 'No blocking patterns detected statically'}",
            "",
            "[Diff]:",
            diff_text
        ]
        
        safe_name = filepath.replace("/", "_")
        job_filename = f"anr_{idx:03d}_{safe_name}.diff"
        job_path = os.path.join(JOBS_DIR, job_filename)
        
        with open(job_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        
        job_paths.append(job_path)

    # Save pending job list for the runner script
    with open(PENDING_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(job_paths) + "\n")
        
    print(f"[Done] Generated {len(job_paths)} specialized ANR audit jobs.")

if __name__ == "__main__":
    main()
