import subprocess
import sys
import os
import re
import json
import glob as globmod
import shutil

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

NON_PROD_MODULES = (
    "benchmark/",
    "microbenchmark/",
)

NOISE_SYMBOLS = {
    # Kotlin/Java primitives & collections
    "String", "Int", "Long", "Boolean", "Float", "Double", "Unit", "Void",
    "Byte", "Short", "Char", "Number", "Object", "Class", "Enum",
    "List", "Map", "Set", "Array", "Pair", "Triple", "Any", "Nothing",
    "HashMap", "ArrayList", "HashSet", "LinkedList", "TreeMap",
    "Iterable", "Iterator", "Sequence", "Collection", "MutableList",
    "MutableMap", "MutableSet",
    # Kotlin annotations
    "Override", "Nullable", "NonNull", "JvmStatic", "JvmField", "JvmOverloads",
    "Deprecated", "Suppress", "Test", "Before", "After", "Throws",
    "Serializable", "Parcelable", "Parcelize", "Keep", "VisibleForTesting",
    # Android framework - core
    "Context", "Intent", "Bundle", "View", "Log", "Uri",
    "Activity", "Fragment", "Service", "Application",
    "BroadcastReceiver", "ContentProvider", "ContentResolver",
    # Android framework - threading
    "Thread", "Runnable", "Handler", "Looper", "Message",
    "AsyncTask", "Executor", "Future",
    # Android framework - UI
    "Drawable", "Bitmap", "Canvas", "Paint", "Color",
    "RecyclerView", "ViewHolder", "Adapter", "LayoutInflater",
    "LinearLayout", "RelativeLayout", "FrameLayout", "ConstraintLayout",
    "CoordinatorLayout", "AppBarLayout", "CollapsingToolbarLayout",
    "TextView", "ImageView", "Button", "EditText", "ScrollView",
    "Dialog", "AlertDialog", "Toast", "Snackbar", "PopupWindow",
    "LayoutParams", "ViewGroup", "ViewBinding",
    "TypedArray", "Resources", "Configuration",
    # Android framework - data
    "SharedPreferences", "Cursor", "ContentValues", "SQLiteDatabase",
    # Android Jetpack - lifecycle
    "LiveData", "MutableLiveData", "Observer", "ViewModel",
    "Lifecycle", "LifecycleOwner", "LifecycleObserver",
    "ViewModelProvider", "SavedStateHandle",
    # Android Jetpack - coroutines & flow
    "Flow", "StateFlow", "MutableStateFlow", "SharedFlow",
    "CoroutineScope", "Dispatchers", "Job", "Deferred",
    # Android Jetpack - Compose
    "Modifier", "Column", "Row", "Box", "Text", "Icon",
    "LazyColumn", "LazyRow", "Scaffold", "Surface",
    "Composable", "State", "MutableState", "Remember",
    # Android Jetpack - other
    "Room", "Dao", "Entity", "Database",
    "Notification", "NotificationChannel", "NotificationManager",
    "PendingIntent", "AlarmManager", "WorkManager", "Worker",
    "NavController", "NavHost", "NavGraph",
    # Java standard
    "Exception", "RuntimeException", "IOException",
    "IllegalStateException", "IllegalArgumentException",
    "StringBuilder", "StringBuffer", "Pattern", "Matcher",
    "File", "InputStream", "OutputStream", "Reader", "Writer",
    "Date", "Calendar", "TimeUnit", "Duration", "Instant",
    "Optional", "Collections", "Arrays", "Objects",
    "Locale", "Charset", "URL", "Closeable", "AutoCloseable",
    # Network / serialization
    "Retrofit", "OkHttpClient", "Response", "Request",
    "Gson", "TypeToken", "JsonObject", "JsonArray",
    "Glide", "Picasso",
}


def run_cmd(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, check=True).stdout.strip()


def find_manifests():
    try:
        result = subprocess.run(
            ["find", ".", "-name", "AndroidManifest.xml",
             "-not", "-path", "*/build/*"],
            capture_output=True, text=True, timeout=10,
        )
        return [p.strip() for p in result.stdout.splitlines() if p.strip()]
    except subprocess.TimeoutExpired:
        return []


def parse_manifest_components(manifest_path):
    entries = {}
    tag_to_type = {
        "activity": "Activity",
        "service": "Service",
        "receiver": "Receiver",
        "provider": "Provider",
    }
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            content = f.read()
        for tag, comp_type in tag_to_type.items():
            for m in re.finditer(
                rf'<{tag}\s[^>]*android:name="([^"]+)"', content
            ):
                class_name = m.group(1).rsplit(".", 1)[-1]
                entries[class_name] = comp_type
    except (IOError, UnicodeDecodeError):
        pass
    return entries


def scan_class_inheritance():
    entries = {}
    base_names = sorted(ENTRY_BASE_CLASSES.keys(), key=len, reverse=True)
    base_pattern = "|".join(base_names)

    try:
        result = subprocess.run(
            ["rg", "-l", "--type", "kotlin", "--type", "java", f"--max-filesize={RG_MAX_FILESIZE}"]
            + RG_EXCLUDE + [base_pattern, "."],
            capture_output=True, text=True, timeout=30,
        )
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
        return entries

    files = result.stdout.splitlines()
    pattern = re.compile(r"class\s+(\w+)[^{]*?(?::\s*|extends\s+)[^{]*?\b(" + base_pattern + r")\b")

    for filepath in files:
        if not filepath: continue
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
                for m in pattern.finditer(content):
                    entries[m.group(1)] = ENTRY_BASE_CLASSES[m.group(2)]
        except Exception:
            pass

    return entries


def parse_nav_destinations():
    entries = {}
    nav_files = globmod.glob("**/res/navigation/*.xml", recursive=True)
    nav_files = [f for f in nav_files if "/build/" not in f]

    for nav_file in nav_files:
        try:
            with open(nav_file, "r", encoding="utf-8") as f:
                content = f.read()
            for m in re.finditer(r'android:name="([^"]+)"', content):
                full_name = m.group(1)
                if "." in full_name and not full_name.startswith("android."):
                    class_name = full_name.rsplit(".", 1)[-1]
                    if class_name not in entries:
                        entries[class_name] = "Fragment"
        except (IOError, UnicodeDecodeError):
            pass

    return entries


def scan_compose_destinations():
    entries = {}
    try:
        result = subprocess.run(
            ["rg", "-l", "--type", "kotlin", f"--max-filesize={RG_MAX_FILESIZE}"]
            + RG_EXCLUDE + ["composable", "."],
            capture_output=True, text=True, timeout=30,
        )
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
        return entries

    pattern = re.compile(r'composable\s*\(\s*\"[^\"]+\"\s*(?:,[^)]*)?\)\s*\{[^{}]*?([A-Z]\w+)\s*\(')
    for filepath in result.stdout.splitlines():
        if not filepath: continue
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
                for m in pattern.finditer(content):
                     entries[m.group(1)] = "ComposeScreen"
        except Exception:
            pass
    return entries


def build_entry_point_index():
    os.makedirs(JOBS_DIR, exist_ok=True)
    entry_points = {}

    manifests = find_manifests()
    for manifest in manifests:
        entry_points.update(parse_manifest_components(manifest))
    manifest_count = len(entry_points)

    inheritance = scan_class_inheritance()
    for cls, cls_type in inheritance.items():
        if cls not in entry_points:
            entry_points[cls] = cls_type
    inherit_count = len(entry_points) - manifest_count

    nav_entries = parse_nav_destinations()
    for cls, cls_type in nav_entries.items():
        if cls not in entry_points:
            entry_points[cls] = cls_type
    nav_count = len(entry_points) - manifest_count - inherit_count

    compose_entries = scan_compose_destinations()
    for cls, cls_type in compose_entries.items():
         if cls not in entry_points:
             entry_points[cls] = cls_type
    compose_count = len(entry_points) - manifest_count - inherit_count - nav_count

    with open(ENTRY_POINTS_FILE, "w", encoding="utf-8") as f:
        json.dump(entry_points, f, ensure_ascii=False, indent=2, sort_keys=True)

    print(f"  Entry points indexed: {len(entry_points)} "
          f"(manifest={manifest_count}, inheritance={inherit_count}, "
          f"navigation={nav_count}, compose={compose_count})")
    return entry_points


def extract_target_class(filepath):
    basename = os.path.splitext(os.path.basename(filepath))[0]
    if re.match(r"^[A-Z]", basename):
        return basename
    return None


def is_non_prod(filepath):
    if any(p in filepath for p in NON_PROD_PATTERNS):
        return True
    if any(filepath.startswith(m) for m in NON_PROD_MODULES):
        return True
    return False


def is_trivial_diff(diff_text):
    for line in diff_text.splitlines():
        if not line.startswith(("+", "-")):
            continue
        if line.startswith(("+++", "---")):
            continue
        stripped = line[1:].strip()
        if not stripped:
            continue
        if not stripped.startswith(TRIVIAL_PREFIXES):
            return False
    return True


def strip_string_literals(line):
    return re.sub(r'"[^"]*"', '""', line)


def extract_symbols(diff_text):
    symbols = set()
    for line in diff_text.splitlines():
        hunk = re.match(r"^@@.*@@\s+.*?\b(fun|class|object|interface)\s+(\w+)", line)
        if hunk:
            symbols.add(hunk.group(2))

        if line.startswith(("+", "-")) and not line.startswith(("+++", "---")):
            clean = strip_string_literals(line)
            for m in re.findall(r"\b([A-Z][a-z][a-zA-Z0-9]{2,})\b", clean):
                symbols.add(m)
            for m in re.findall(r"\bfun\s+(\w+)", clean):
                symbols.add(m)

    return symbols - NOISE_SYMBOLS


def find_references(symbol, target_file):
    try:
        result = subprocess.run(
            ["rg", "-l",
             "--type", "kotlin", "--type", "java", "--type", "xml",
             "--max-count=5", f"--max-filesize={RG_MAX_FILESIZE}"]
            + RG_EXCLUDE + [symbol, "."],
            capture_output=True, text=True, timeout=RG_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return None

    files = [f for f in result.stdout.strip().split("\n") if f and f != target_file]
    if len(files) > MAX_REFS_PER_SYMBOL:
        return None
    return files

def find_linked_viewmodel(filepath):
    """Attempt to find ViewModel used in Activity/Fragment file"""
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
    except IOError:
        return None

    # 1. by viewModels() pattern
    m = re.search(r"val\s+\w+\s*:\s*([A-Z]\w+ViewModel)\s+by\s+(?:viewModels|activityViewModels)", text)
    if m:
        return m.group(1)

    # 2. ViewModelProvider pattern
    m = re.search(r"ViewModelProvider.*\.get\(([A-Z]\w+ViewModel)::class\.java\)", text)
    if m:
        return m.group(1)

    return None

def format_ref_entry(ref, entry_points):
    ref_cls = os.path.splitext(os.path.basename(ref))[0]
    ep_type = entry_points.get(ref_cls)

    extra_tags = ""
    if ep_type in ("Activity", "Fragment"):
        vm = find_linked_viewmodel(ref)
        if vm:
             extra_tags = f", VIEW_MODEL: {vm}"

    if ep_type:
        return f"    - {ref} [ENTRY: {ep_type}{extra_tags}]"
    return f"    - {ref}"


def load_ui_name_data(filepath):
    safe = filepath.replace("/", "_")
    p = os.path.join(UI_NAME_DIR, f"{safe}.json")
    if not os.path.isfile(p):
        return None
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def format_ui_context_lines(data):
    if not data:
        return []
    lines = ["[UI Context]:"]
    if data.get("compose_only"):
        lines.append(
            "  (Compose-heavy: infer visible strings from diff — Text(), stringResource(), "
            "semantics contentDescription)"
        )
    if data.get("resource_self"):
        lines.append(f"  Resource file: {data.get('target_file', '')}")
    for lp in data.get("layouts") or []:
        lines.append(f"  Layout: {lp}")
    for mp in data.get("menus") or []:
        lines.append(f"  Menu: {mp}")
    nav = data.get("navigation_labels")
    if nav:
        lines.append(f"  Navigation labels: {', '.join(nav)}")
    for el in data.get("elements") or []:
        tid = el.get("id", "?")
        tag = el.get("tag", "?")
        bits = [f"@id/{tid}", f"({tag})"]
        if el.get("text"):
            bits.append(f'text="{el["text"]}"')
        if el.get("hint"):
            bits.append(f'hint="{el["hint"]}"')
        if el.get("content_description"):
            bits.append(f'contentDescription="{el["content_description"]}"')
        if el.get("title"):
            bits.append(f'title="{el["title"]}"')
        src = el.get("from_layout") or el.get("from_menu")
        if src:
            bits.append(f"from={src}")
        lines.append("    - " + " ".join(bits))

    compose_els = data.get("compose_elements")
    if compose_els:
        lines.append("  Compose Elements:")
        for el in compose_els:
            bits = []
            if el.get("test_tag"):
                bits.append(f'testTag="{el["test_tag"]}"')
            if el.get("content_description"):
                bits.append(f'contentDescription="{el["content_description"]}"')
            if el.get("string_resource"):
                bits.append(f'stringResource=R.string.{el["string_resource"]} (text="{el.get("text", "")}")')
            if el.get("literal_text"):
                bits.append(f'Text="{el["literal_text"]}"')
            if bits:
                lines.append("    - " + " ".join(bits))

    for ll in data.get("listener_linked") or []:
        if "id" in ll:
            lines.append(f"    - [event:{ll.get('event_kind', '?')}] R.id.{ll['id']}")
        elif "binding" in ll:
            lines.append(f"    - [event:{ll.get('event_kind', '?')}] binding.{ll['binding']}")
        elif "test_tag" in ll:
            lines.append(f"    - [event:{ll.get('event_kind', '?')}] testTag=\"{ll['test_tag']}\"")

    hooks = data.get("screen_level_hooks")
    if hooks:
        lines.append(f"  Screen-level hooks: {', '.join(hooks)}")
    lines.append("")
    body = [l for l in lines[1:-1] if l.strip()]
    if not body:
        return []
    return lines


def build_enriched_content(filepath, diff_text, target_class_refs,
                           symbols, references, entry_points):

    scope_tag = ""
    if "/commonMain/" in filepath:
         scope_tag = " [SCOPE: KMP_COMMON]"

    lines = [f"[Target File]: {filepath}{scope_tag}", ""]

    ui_data = load_ui_name_data(filepath)
    if ui_data:
        lines.extend(format_ui_context_lines(ui_data))

    if symbols:
        lines.append(f"[Changed Symbols]: {', '.join(sorted(symbols))}")
        lines.append("")

    target_class = extract_target_class(filepath)
    has_any_refs = (target_class is not None) or bool(references)

    if has_any_refs:
        lines.append("[References]:")

        if target_class is not None:
            if target_class_refs is None:
                lines.append(f"  {target_class}: (10+ references - common utility)")
            elif not target_class_refs:
                lines.append(f"  {target_class}: (no references found)")
            else:
                lines.append(f"  {target_class}:")
                for ref in target_class_refs:
                    lines.append(format_ref_entry(ref, entry_points))

        for sym, refs in sorted(references.items()):
            if refs is None:
                lines.append(f"  {sym}: (10+ references - common utility)")
            elif not refs:
                lines.append(f"  {sym}: (no references found)")
            else:
                lines.append(f"  {sym}:")
                for ref in refs:
                    lines.append(format_ref_entry(ref, entry_points))
        lines.append("")

    lines.append("[Diff]:")
    lines.append(diff_text)
    return "\n".join(lines)


def ensure_checkout(ref):
    current = run_cmd(["git", "rev-parse", "HEAD"])
    target = run_cmd(["git", "rev-parse", ref])
    if current == target:
        return
    print(f"[checkout] Current HEAD does not match {ref}. Checking out...")
    subprocess.run(["git", "checkout", ref], check=True)
    print(f"[checkout] Now on {ref}")


def cleanup():
    if os.path.isdir(JOBS_DIR):
        for name in os.listdir(JOBS_DIR):
            path = os.path.join(JOBS_DIR, name)
            if name == "ui_name":
                continue
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)
        print(f"  Cleared {JOBS_DIR}/ (preserved ui_name/)")
    if os.path.isdir(REPORTS_DIR):
        shutil.rmtree(REPORTS_DIR)
        print(f"  Removed {REPORTS_DIR}/")
    if os.path.isfile(REPORT_FILE):
        os.remove(REPORT_FILE)
        print(f"  Removed {REPORT_FILE}")


def main():
    print(f"[pre_candidate] {FROM_REF} -> {TO_REF}")
    ensure_checkout(TO_REF)

    print("[0/3] Cleaning up previous results...")
    cleanup()
    os.makedirs(JOBS_DIR, exist_ok=True)

    print("[1/3] Building entry point index...")
    entry_points = build_entry_point_index()

    print("[2/3] Collecting changed files...")
    cmd_list = ["git", "diff", "--name-only", FROM_REF, TO_REF, "--", "."] + EXCLUDES
    changed_files = [f for f in run_cmd(cmd_list).split("\n") if f]

    if not changed_files:
        print("No logic changes found in this range.")
        return

    print(f"[3/3] Processing {len(changed_files)} files...")
    skipped = []
    job_paths = []
    stats = {
        "total": len(changed_files),
        "skipped_non_prod": 0,
        "skipped_trivial": 0,
        "skipped_large": 0,
        "generated": 0,
    }

    os.makedirs(REPORTS_DIR, exist_ok=True)

    for idx, filepath in enumerate(changed_files):
        if is_non_prod(filepath):
            stats["skipped_non_prod"] += 1
            skipped.append({"file": filepath, "reason": "non-production source set"})
            print(f"  SKIP (non-prod): {filepath}")
            continue

        cmd_diff = ["git", "diff", "-U3", FROM_REF, TO_REF, "--", filepath]
        try:
            diff_text = run_cmd(cmd_diff)
        except subprocess.CalledProcessError:
            continue

        if not diff_text:
            continue

        is_deleted = "deleted file mode" in diff_text

        diff_line_count = len(diff_text.splitlines())

        if diff_line_count > MAX_DIFF_LINES:
            stats["skipped_large"] += 1
            skipped.append({"file": filepath, "reason": f"diff too large ({diff_line_count} lines)"})
            print(f"  SKIP (large: {diff_line_count} lines): {filepath}")
            continue

        if is_trivial_diff(diff_text):
            stats["skipped_trivial"] += 1
            skipped.append({"file": filepath, "reason": "trivial (import/comment/whitespace only)"})
            print(f"  SKIP (trivial): {filepath}")
            continue

        if is_deleted:
            enriched = f"[Target File]: {filepath}\n[Deleted]\n\n[Diff]:\n{diff_text}"
            print(f"  DELETED (skip trace): {filepath}")
        else:
            target_class = extract_target_class(filepath)
            target_class_refs = None
            if target_class:
                target_class_refs = find_references(target_class, filepath)

            symbols = extract_symbols(diff_text)
            if target_class:
                symbols.discard(target_class)

            references = {}
            for sym in symbols:
                references[sym] = find_references(sym, filepath)

            enriched = build_enriched_content(
                filepath, diff_text, target_class_refs,
                symbols, references, entry_points,
            )

        safe_name = filepath.replace("/", "_")
        job_filename = f"{idx:03d}_{safe_name}.diff"
        job_path = os.path.join(JOBS_DIR, job_filename)

        with open(job_path, "w", encoding="utf-8") as f:
            f.write(enriched)

        job_paths.append(job_path)
        stats["generated"] += 1

    with open(os.path.join(JOBS_DIR, PENDING_FILE), "w", encoding="utf-8") as f:
        f.write("\n".join(job_paths) + "\n")

    if skipped:
        with open(os.path.join(JOBS_DIR, SKIPPED_FILE), "w", encoding="utf-8") as f:
            json.dump(skipped, f, ensure_ascii=False, indent=2)

    print(f"\n[Done] {stats['generated']} jobs generated")
    print(f"  non-prod skipped: {stats['skipped_non_prod']}")
    print(f"  trivial skipped:  {stats['skipped_trivial']}")
    print(f"  large skipped:    {stats['skipped_large']}")
    print(f"  total changed:    {stats['total']}")
    print(f"  entry points:     {len(entry_points)}")
    print(f"  -> {JOBS_DIR}/{PENDING_FILE}")


if __name__ == "__main__":
    main()
