import subprocess
import sys
import os
import re
import json
import glob as globmod
import shutil
import concurrent.futures
from multiprocessing import cpu_count

FROM_REF = sys.argv[1] if len(sys.argv) > 1 else "HEAD~1"
TO_REF = sys.argv[2] if len(sys.argv) > 2 else "HEAD"

JOBS_DIR = "map_jobs"
REPORTS_DIR = "map_results"
REPORT_FILE = "FINAL_QA_REPORT.md"
PENDING_FILE = "pending.txt"
SKIPPED_FILE = "skipped.json"
ENTRY_POINTS_FILE = os.path.join(JOBS_DIR, "entry_points.json")
UI_NAME_DIR = os.path.join(JOBS_DIR, "ui_name")

MAX_DIFF_LINES = 3000
MAX_REFS_PER_SYMBOL = 10
RG_TIMEOUT = 10
RG_MAX_FILESIZE = "500K"

RG_EXCLUDE = ["--glob", "!**/build/**", "--glob", "!**/generated/**"]

FD_EXE = "fdfind" if subprocess.run(["which", "fdfind"], capture_output=True).returncode == 0 else "fd"
SG_EXE = "sg"

ENTRY_BASE_CLASSES = {
    "AppCompatActivity": "Activity", "ComponentActivity": "Activity",
    "FragmentActivity": "Activity",
    "Fragment": "Fragment", "DialogFragment": "Fragment",
    "BottomSheetDialogFragment": "Fragment",
    "Worker": "Worker", "CoroutineWorker": "Worker",
    "ListenableWorker": "Worker",
    "Service": "Service", "LifecycleService": "Service",
    "IntentService": "Service",
    "BroadcastReceiver": "Receiver",
    "ViewModel": "ViewModel", "AndroidViewModel": "ViewModel"
}

EXCLUDES = [
    ":(exclude)**/*.png", ":(exclude)**/*.jpg", ":(exclude)**/build/**",
    ":(exclude)**/*.jar", ":(exclude)**/*.aar", ":(exclude).gitignore",
    ":(exclude)**/strings.xml", ":(exclude)**/colors.xml",
]

TRIVIAL_PREFIXES = ("import ", "import(", "//", "/*", "* ", "*/")

NON_PROD_PATTERNS = (
    "/benchmarkShared/", "/androidTest/", "/testShared/", "/testFixtures/",
    "/src/test/", "/src/androidTest/",
)

NON_PROD_MODULES = ("benchmark/", "microbenchmark/")

NOISE_SYMBOLS = {
    "String", "Int", "Long", "Boolean", "Float", "Double", "Unit", "Void",
    "Byte", "Short", "Char", "Number", "Object", "Class", "Enum",
    "List", "Map", "Set", "Array", "Pair", "Triple", "Any", "Nothing",
    "HashMap", "ArrayList", "HashSet", "LinkedList", "TreeMap",
    "Iterable", "Iterator", "Sequence", "Collection", "MutableList",
    "MutableMap", "MutableSet", "Override", "Nullable", "NonNull", "JvmStatic",
    "JvmField", "JvmOverloads", "Deprecated", "Suppress", "Test", "Before", "After",
    "Throws", "Serializable", "Parcelable", "Parcelize", "Keep", "VisibleForTesting",
    "Context", "Intent", "Bundle", "View", "Log", "Uri", "Activity", "Fragment",
    "Service", "Application", "BroadcastReceiver", "ContentProvider", "ContentResolver",
    "Thread", "Runnable", "Handler", "Looper", "Message", "AsyncTask", "Executor", "Future",
    "Drawable", "Bitmap", "Canvas", "Paint", "Color", "RecyclerView", "ViewHolder",
    "Adapter", "LayoutInflater", "LinearLayout", "RelativeLayout", "FrameLayout",
    "ConstraintLayout", "CoordinatorLayout", "AppBarLayout", "CollapsingToolbarLayout",
    "TextView", "ImageView", "Button", "EditText", "ScrollView", "Dialog", "AlertDialog",
    "Toast", "Snackbar", "PopupWindow", "LayoutParams", "ViewGroup", "ViewBinding",
    "TypedArray", "Resources", "Configuration", "SharedPreferences", "Cursor",
    "ContentValues", "SQLiteDatabase", "LiveData", "MutableLiveData", "Observer",
    "ViewModel", "Lifecycle", "LifecycleOwner", "LifecycleObserver", "ViewModelProvider",
    "SavedStateHandle", "Flow", "StateFlow", "MutableStateFlow", "SharedFlow",
    "CoroutineScope", "Dispatchers", "Job", "Deferred", "Modifier", "Column", "Row",
    "Box", "Text", "Icon", "LazyColumn", "LazyRow", "Scaffold", "Surface", "Composable",
    "State", "MutableState", "Remember", "Room", "Dao", "Entity", "Database",
    "Notification", "NotificationChannel", "NotificationManager", "PendingIntent",
    "AlarmManager", "WorkManager", "Worker", "NavController", "NavHost", "NavGraph",
    "Exception", "RuntimeException", "IOException", "IllegalStateException",
    "IllegalArgumentException", "StringBuilder", "StringBuffer", "Pattern", "Matcher",
    "File", "InputStream", "OutputStream", "Reader", "Writer", "Date", "Calendar",
    "TimeUnit", "Duration", "Instant", "Optional", "Collections", "Arrays", "Objects",
    "Locale", "Charset", "URL", "Closeable", "AutoCloseable", "Retrofit", "OkHttpClient",
    "Response", "Request", "Gson", "TypeToken", "JsonObject", "JsonArray", "Glide", "Picasso"
}

def run_cmd(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, check=True).stdout.strip()

def find_manifests():
    try:
        res = run_cmd([FD_EXE, "AndroidManifest.xml", "--exclude", "build"])
        return res.splitlines()
    except:
        return []

def scan_entries_with_ast():
    """ast-grep을 사용하여 상속 관계와 Compose 목적지를 정확히 추출"""
    entries = {}
    try:
        # Fragment/Activity/ViewModel 계열 상속 관계
        for base, label in ENTRY_BASE_CLASSES.items():
            res = run_cmd([SG_EXE, "-p", f"class $NAME : {base} {{ $$$ }}", "--lang", "kotlin", "--json"])
            if res:
                for item in json.loads(res):
                    entries[item["vars"]["NAME"]] = label
            
            # Java 상속 (extends)
            res = run_cmd([SG_EXE, "-p", f"class $NAME extends {base} {{ $$$ }}", "--lang", "java", "--json"])
            if res:
                for item in json.loads(res):
                    entries[item["vars"]["NAME"]] = label

        # Compose Destinations
        res = run_cmd([SG_EXE, "-p", 'composable($ROUTE) { $SCREEN($$$) }', "--lang", "kotlin", "--json"])
        if res:
            for item in json.loads(res):
                entries[item["vars"]["SCREEN"]] = "ComposeScreen"
    except:
        pass
    return entries

def build_entry_point_index():
    os.makedirs(JOBS_DIR, exist_ok=True)
    entry_points = scan_entries_with_ast()
    
    # Manifest 등 기존 방식 보완
    for manifest in find_manifests():
        try:
            with open(manifest, "r", encoding="utf-8") as f:
                content = f.read()
            for tag in ["activity", "service", "receiver", "provider"]:
                for m in re.finditer(rf'<{tag}\s[^>]*android:name="([^"]+)"', content):
                    name = m.group(1).rsplit(".", 1)[-1]
                    if name not in entry_points:
                        entry_points[name] = tag.capitalize()
        except: pass

    with open(ENTRY_POINTS_FILE, "w", encoding="utf-8") as f:
        json.dump(entry_points, f, ensure_ascii=False, indent=2, sort_keys=True)
    return entry_points

def extract_symbols(diff_text):
    symbols = set()
    for line in diff_text.splitlines():
        hunk = re.match(r"^@@.*@@\s+.*?\b(fun|class|object|interface)\s+(\w+)", line)
        if hunk: symbols.add(hunk.group(2))
        if line.startswith(("+", "-")) and not line.startswith(("+++", "---")):
            clean = re.sub(r'"[^"]*"', '""', line)
            for m in re.findall(r"\b([A-Z][a-z][a-zA-Z0-9]{2,})\b", clean): symbols.add(m)
            for m in re.findall(r"\bfun\s+(\w+)", clean): symbols.add(m)
    return symbols - NOISE_SYMBOLS

def find_references_one(symbol, target_file):
    try:
        res = subprocess.run(
            ["rg", "-l", "--type", "kotlin", "--type", "java", "--type", "xml",
             "--max-count=5", f"--max-filesize={RG_MAX_FILESIZE}"] + RG_EXCLUDE + [symbol, "."],
            capture_output=True, text=True, timeout=RG_TIMEOUT
        ).stdout.strip()
        files = [f for f in res.split("\n") if f and f != target_file]
        return symbol, (files if len(files) <= MAX_REFS_PER_SYMBOL else None)
    except:
        return symbol, None

def find_references_parallel(symbols, target_file):
    results = {}
    with concurrent.futures.ProcessPoolExecutor(max_workers=cpu_count()) as executor:
        future_to_symbol = {executor.submit(find_references_one, sym, target_file): sym for sym in symbols}
        for future in concurrent.futures.as_completed(future_to_symbol):
            sym, refs = future.result()
            results[sym] = refs
    return results

def format_ref_entry(ref, entry_points):
    ref_cls = os.path.splitext(os.path.basename(ref))[0]
    ep_type = entry_points.get(ref_cls)
    return f"    - {ref} [ENTRY: {ep_type}]" if ep_type else f"    - {ref}"

def main():
    print(f"[test_pre_candidate] {FROM_REF} -> {TO_REF} (Modern Parallel Mode)")
    entry_points = build_entry_point_index()
    print(f"  Entry points indexed: {len(entry_points)}")

    cmd_list = ["git", "diff", "--name-only", FROM_REF, TO_REF]
    changed_files = [f for f in run_cmd(cmd_list).split("\n") if f and not any(p in f for p in NON_PROD_PATTERNS)]

    stats = {"generated": 0}
    os.makedirs(REPORTS_DIR, exist_ok=True)
    job_paths = []

    for idx, filepath in enumerate(changed_files):
        cmd_diff = ["git", "diff", "-U3", FROM_REF, TO_REF, "--", filepath]
        diff_text = run_cmd(cmd_diff)
        if not diff_text or len(diff_text.splitlines()) > MAX_DIFF_LINES: continue

        symbols = extract_symbols(diff_text)
        basename = os.path.splitext(os.path.basename(filepath))[0]
        if re.match(r"^[A-Z]", basename): symbols.add(basename)
        
        references = find_references_parallel(symbols, filepath)
        
        lines = [f"[Target File]: {filepath}", ""]
        ui_safe = filepath.replace("/", "_")
        ui_json = os.path.join(UI_NAME_DIR, f"{ui_safe}.json")
        if os.path.exists(ui_json):
            with open(ui_json, "r") as f:
                ui_data = json.load(f)
                lines.append("[UI Context]:")
                if ui_data.get("bridges"):
                    lines.append("  Hybrid Bridges (Legacy -> Compose):")
                    for bridge in ui_data.get("bridges", []):
                        lines.append(f"    - Type: {bridge['type']}, Target: {bridge.get('class', '?')}")
                
                if ui_data.get("compose_semantics"):
                    lines.append("  Compose UI Semantics:")
                    for sem in ui_data.get("compose_semantics", []):
                        val = sem.get("value") or sem.get("resolved") or sem.get("id")
                        lines.append(f"    - {sem['type']}: \"{val}\"")
                
                # 기존 XML 요소들도 포함하여 호환성 유지
                if ui_data.get("elements"):
                    lines.append("  View Elements:")
                    for el in ui_data.get("elements", []):
                        lines.append(f"    - @id/{el.get('id')} ({el.get('tag')}) text=\"{el.get('text')}\"")
                lines.append("")

        lines.append("[References]:")
        for sym, refs in sorted(references.items()):
            if refs is None: lines.append(f"  {sym}: (10+ references - common utility)")
            else:
                lines.append(f"  {sym}:")
                for ref in refs: lines.append(format_ref_entry(ref, entry_points))
        
        lines.append("\n[Diff]:")
        lines.append(diff_text)
        
        job_path = os.path.join(JOBS_DIR, f"{idx:03d}_{ui_safe}.diff")
        with open(job_path, "w") as f: f.write("\n".join(lines))
        job_paths.append(job_path)
        stats["generated"] += 1

    with open(PENDING_FILE, "w") as f: f.write("\n".join(job_paths) + "\n")
    print(f"[Done] {stats['generated']} jobs generated -> {PENDING_FILE}")

if __name__ == "__main__":
    main()
