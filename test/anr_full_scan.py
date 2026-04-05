import os
import subprocess
import re
import json
import shutil
import xml.etree.ElementTree as ET

# Full Project Directories (Focus on production source sets for high-signal results)
TARGET_DIRS = [
    "app/src/main/java", "app/src/main/kotlin",
    "lib/src/main/java", "lib/src/main/kotlin",
    "feature/src/main/java", "feature/src/main/kotlin",
    "core/src/main/java", "core/src/main/kotlin"
]
OUTPUT_FILE = "DAILY_ANR_SCAN_RESULTS.json"

# High-recall candidate taxonomy for daily deep ANR analysis.
# These categories are intentionally broader than final verdicts; Gemini does the
# thread reachability and mitigation analysis later.
RISK_PATTERNS = {
    # 1. Startup & Application Critical Path
    "STARTUP_CONTENT_PROVIDER": r"extends\s+ContentProvider[\s\S]*?onCreate\(\)",
    "STARTUP_APP_ON_CREATE": r"extends\s+Application[\s\S]*?onCreate\(\)",
    "STARTUP_HILT_ENTRYPOINT": r"EntryPoints\.get\(",

    # 2. Main-thread lifecycle anchors
    "BROADCAST_ON_RECEIVE": r"onReceive\(.*Context.*Intent",
    "SERVICE_LIFECYCLE_MAIN_THREAD": r"extends\s+.*Service[\s\S]{0,800}?on(Create|StartCommand)\s*\(",

    # 3. Locks & IPC boundaries
    "LOCK_CONTENTION": r"synchronized\s*\(|ReentrantLock\.lock|ReadWriteLock\.writeLock\(\)\.lock|ReadWriteLock\.readLock\(\)\.lock",
    "BINDER_SYNC_IPC": r"IBinder|asInterface|AIDL|ServiceConnection|bindService\(|unbindService\(",
    "CONTENT_RESOLVER_IPC": r"ContentResolver\.(query|call|insert|update|delete|openInputStream|openOutputStream|openFileDescriptor)|contentResolver\.(query|call|insert|update|delete|openInputStream|openOutputStream|openFileDescriptor)",
    "SYSTEM_SERVICE_QUERY": r"getPackageManager\(\)\.(query|get)|getSystemService\(|PackageInstaller|JobScheduler|RoleManager|AccountManager|ShortcutManager|NotificationManager",

    # 4. Concurrency and explicit blocking
    "COROUTINE_RUN_BLOCKING": r"runBlocking\s*\{",
    "DATASTORE_SYNC_READ": r"dataStore\.data\.first\(\)",
    "FUTURE_GET_BLOCKING": r"Future\.(get|get\()|CompletableFuture\.get\(|ListenableFuture\.get\(|Tasks\.await\(|awaitTermination\(",
    "THREAD_SLEEP_WAIT": r"Thread\.(sleep|join)|CountDownLatch\.await|LockSupport\.park|Object\.wait\(|\.wait\(|Semaphore\.acquire|BlockingQueue\.(take|put)|CyclicBarrier\.await|Condition\.await",

    # 5. Database and persistence
    "ROOM_MAIN_THREAD_QUERY": r"allowMainThreadQueries",
    "SQLITE_DIRECT_ACCESS": r"SQLiteDatabase\.(query|rawQuery|insert|update|delete|execSQL)|SupportSQLiteDatabase\.(query|execSQL)|rawQuery\(|query\([^\\n]{0,120}\)|execSQL\(",
    "SHARED_PREFS_COMMIT": r"\.edit\(\)\.commit\(\)|SharedPreferences\.Editor\.commit\(",

    # 6. Network, decode, and third-party blocking
    "FIREBASE_TASKS_AWAIT": r"Tasks\.await\(",
    "OKHTTP_RETROFIT_SYNC": r"Call\.execute\(|OkHttpClient.*\.execute\(|Retrofit.*\.execute\(",
    "BITMAP_DECODE_BLOCKING": r"BitmapFactory\.decode(ByteArray|Stream|File|FileDescriptor|Resource)|ImageDecoder\.decodeBitmap|MediaMetadataRetriever",
    "GLIDE_IMAGE_SYNC": r"\.submit\(\)\.get\(",

    # 7. File and crypto work
    "DISK_IO_BLOCKING": r"FileInputStream|FileOutputStream|RandomAccessFile|Files\.(read|write|newInputStream|newOutputStream)|ParcelFileDescriptor|DocumentFile|openFileDescriptor|ZipInputStream|listFiles\(\)|walk\(\)",
    "CRYPTO_BLOCKING": r"Cipher\.(doFinal|update)|Mac\.doFinal|MessageDigest\.digest|KeyStore\.(load|getKey|setEntry)|SecretKeyFactory\.generateSecret"
}

def cleanup_workspace():
    """Clear previous session tasks and results for a clean run."""
    print("[Cleanup] Clearing previous session data in anr_tasks/ and anr_results/...")
    for folder in ["anr_tasks", "anr_results"]:
        if os.path.exists(folder):
            shutil.rmtree(folder)
        os.makedirs(folder, exist_ok=True)

def get_module_permissions():
    """Collect permission information by module to use as analysis hints."""
    permission_map = {}
    for root, dirs, files in os.walk("."):
        if "AndroidManifest.xml" in files:
            path = os.path.join(root, "AndroidManifest.xml")
            try:
                tree = ET.parse(path)
                root_node = tree.getroot()
                perms = [p.get('{http://schemas.android.com/apk/res/android}name') for p in root_node.findall('uses-permission')]
                module = os.path.dirname(os.path.dirname(path))
                permission_map[module] = [p.split('.')[-1] for p in perms if p]
            except: continue
    return permission_map

def run_rg(pattern, paths):
    """Powerful multi-line regex scan via ripgrep with explicit test exclusion."""
    cmd = ["rg", "--vimgrep", "--json", "--context", "2", "--glob", "!**/tests/**", pattern] + paths
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.stdout
    except Exception:
        return ""

def perform_full_scan():
    cleanup_workspace()
    print(f"[ANR Daily Scan] Initiating expert project scan across {TARGET_DIRS}...")
    permission_map = get_module_permissions()
    all_raw_findings = []

    for key, pattern in RISK_PATTERNS.items():
        print(f"  🔍 Scanning for {key}...")
        raw_json_output = run_rg(pattern, TARGET_DIRS)
        
        for line in raw_json_output.splitlines():
            try:
                data = json.loads(line)
                if data.get("type") == "match":
                    match_data = data["data"]
                    file_path = match_data["path"]["text"]
                    
                    # Find module permissions
                    module_perms = []
                    for mod, perms in permission_map.items():
                        if file_path.startswith(mod):
                            module_perms = perms
                            break

                    all_raw_findings.append({
                        "risk_type": key,
                        "file": file_path,
                        "line": match_data["line_number"],
                        "text": match_data["lines"]["text"].strip(),
                        "module_permissions": module_perms
                    })
            except: continue

    # Create job files for the parallel runner
    os.makedirs("anr_tasks", exist_ok=True)
    job_paths = []
    
    for idx, finding in enumerate(all_raw_findings):
        safe_name = finding["file"].replace("/", "_")
        job_filename = f"anr_full_{idx:03d}_{safe_name}.anr"
        job_path = os.path.join("anr_tasks", job_filename)
        
        with open(job_path, "w", encoding="utf-8") as f:
            f.write(f"[Target File]: {finding['file']}\n")
            f.write(f"[Risk Type]: {finding['risk_type']}\n")
            f.write(f"[Location]: Line {finding['line']}\n")
            f.write(f"[Module Permissions]: {', '.join(finding['module_permissions'])}\n")
            f.write(f"[Snippet]: {finding['text']}\n\n")
            f.write("[Instruction]: Perform tiered ANR Analysis. Check if this blocking call is reachable by Main Thread and if timeouts/offloading mitigate it.\n")
            
        job_paths.append(job_path)

    with open("anr_tasks/pending_anr.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(job_paths) + "\n")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_raw_findings, f, indent=2)
        
    print(f"[Done] Found {len(all_raw_findings)} potential risks. Generated {len(job_paths)} jobs.")
    return all_raw_findings

if __name__ == "__main__":
    perform_full_scan()
