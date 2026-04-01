#!/usr/bin/env python3
"""
Build static UI name context for changed Android files: strings (values/),
linked layouts/menus, view attributes, event-linked R.id hints, screen-level hooks.
Outputs map_jobs/ui_name/<safe_path>.json and ui_name_manifest.json.
Run after checkout at TO_REF, before pre_candidate.py (map_jobs/ui_name/ is preserved).
"""

import json
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

FROM_REF = sys.argv[1] if len(sys.argv) > 1 else "HEAD~1"
TO_REF = sys.argv[2] if len(sys.argv) > 2 else "HEAD"

JOBS_DIR = "map_jobs"
UI_NAME_DIR = os.path.join(JOBS_DIR, "ui_name")
MANIFEST_FILE = os.path.join(UI_NAME_DIR, "ui_name_manifest.json")
STRING_INDEX_FILE = os.path.join(UI_NAME_DIR, "string_resources.json")

MAX_DIFF_LINES = 3000
RG_MAX_FILESIZE = "500K"
RG_EXCLUDE = ["--glob", "!**/build/**", "--glob", "!**/generated/**"]

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

ANDROID_NS = "{http://schemas.android.com/apk/res/android}"

# (regex pattern, event_kind label)
LISTENER_PATTERNS = [
    (r"setOnClickListener", "click"),
    (r"setOnLongClickListener", "long_click"),
    (r"setOnTouchListener", "touch"),
    (r"setOnFocusChangeListener", "focus"),
    (r"setOnScrollChangeListener", "scroll"),
    (r"setOnKeyListener", "key"),
    (r"setOnApplyWindowInsetsListener", "insets"),
    (r"setOnGenericMotionListener", "motion"),
    (r"addTextChangedListener", "text"),
    (r"setOnEditorActionListener", "editor_action"),
    (r"setOnCheckedChangeListener", "checked_change"),
    (r"setOnItemSelectedListener", "item_selected"),
    (r"setOnItemClickListener", "item_click"),
    (r"addOnScrollListener", "rv_scroll"),
    (r"addOnItemTouchListener", "item_touch"),
    (r"setOnRefreshListener", "refresh"),
    (r"registerOnPageChangeCallback", "page_change"),
    (r"setOnQueryTextListener", "query_text"),
    (r"setOnCloseListener", "close"),
    (r"setOnSeekBarChangeListener", "seek_change"),
    (r"Modifier\.clickable", "compose_click"),
]

SCREEN_LEVEL_PATTERNS = [
    "onOptionsItemSelected",
    "onContextItemSelected",
    "onCreateContextMenu",
    "onCreateOptionsMenu",
    "onPrepareOptionsMenu",
    "dispatchTouchEvent",
    "onKeyDown",
    "onKeyUp",
]

R_LAYOUT_RE = re.compile(r"\bR\.layout\.(\w+)\b")
R_MENU_RE = re.compile(r"\bR\.menu\.(\w+)\b")
R_ID_RE = re.compile(r"\bR\.id\.(\w+)\b")
BINDING_MEMBER_RE = re.compile(r"\bbinding\.(\w+)\b")


def run_cmd(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, check=True).stdout.strip()


def ensure_checkout(ref):
    current = run_cmd(["git", "rev-parse", "HEAD"])
    target = run_cmd(["git", "rev-parse", ref])
    if current == target:
        return
    print(f"[pre_ui_name] Checking out {ref} ...")
    subprocess.run(["git", "checkout", ref], check=True)


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


def find_res_dir_for_path(filepath):
    """Walk up from filepath to find nearest .../res directory."""
    d = os.path.dirname(os.path.abspath(filepath))
    for _ in range(24):
        cand = os.path.join(d, "res")
        if os.path.isdir(cand):
            return cand
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    return None


def collect_strings_xml_paths():
    paths = []
    for root, _, files in os.walk("."):
        if "/build/" in root or root.startswith("./build"):
            continue
        if os.path.basename(root) == "values" and "strings.xml" in files:
            paths.append(os.path.join(root, "strings.xml"))
    return paths


def parse_strings_xml(path, string_map):
    try:
        tree = ET.parse(path)
        root = tree.getroot()
        for elem in root:
            if elem.tag != "string":
                continue
            name = elem.attrib.get("name")
            if not name:
                continue
            text = "".join(elem.itertext()).strip()
            string_map[name] = text
    except (ET.ParseError, IOError, UnicodeDecodeError):
        pass


def build_string_index():
    string_map = {}
    for p in collect_strings_xml_paths():
        parse_strings_xml(p, string_map)
    return string_map


def resolve_attr_value(raw, string_map):
    if raw is None:
        return None
    raw = raw.strip()
    m = re.match(r"^@string/(\w+)$", raw)
    if m:
        return string_map.get(m.group(1), raw)
    if raw.startswith("@android:string/"):
        return raw
    return raw


def find_layout_or_menu_xml(res_dir, kind, name):
    """kind: 'layout' or 'menu'."""
    if not res_dir or not os.path.isdir(res_dir):
        return None
    subdirs = [d for d in os.listdir(res_dir)
               if os.path.isdir(os.path.join(res_dir, d)) and d.startswith(kind)]
    subdirs.sort()
    filename = f"{name}.xml"
    for sub in subdirs:
        p = os.path.join(res_dir, sub, filename)
        if os.path.isfile(p):
            return p
    return None


def parse_view_xml_file(xml_path, string_map, max_elements=40):
    """Extract id, text, hint, contentDescription from layout/menu XML."""
    elements = []
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
    except (ET.ParseError, IOError, UnicodeDecodeError):
        return elements

    def walk(elem, depth=0):
        if depth > 64 or len(elements) >= max_elements:
            return
        aid = elem.attrib.get(f"{ANDROID_NS}id") or elem.attrib.get("android:id")
        text = elem.attrib.get(f"{ANDROID_NS}text") or elem.attrib.get("android:text")
        hint = elem.attrib.get(f"{ANDROID_NS}hint") or elem.attrib.get("android:hint")
        cd = (elem.attrib.get(f"{ANDROID_NS}contentDescription") or elem.attrib.get("android:contentDescription") or elem.attrib.get("app:contentDescription"))
        title = (elem.attrib.get(f"{ANDROID_NS}title") or elem.attrib.get("android:title") or elem.attrib.get("app:title"))
        tag = elem.tag
        if "}" in tag:
            tag = tag.split("}", 1)[-1]

        data_binding = None
        if text and text.startswith("@{") and text.endswith("}"):
            data_binding = text[2:-1].strip()
            text = None

        if aid:
            m = re.search(r"@\+?id/(\w+)", aid)
            vid = m.group(1) if m else aid
            entry = {
                "id": vid,
                "tag": tag,
                "text": resolve_attr_value(text, string_map) if text else None,
                "data_binding": data_binding,
                "hint": resolve_attr_value(hint, string_map) if hint else None,
                "content_description": resolve_attr_value(cd, string_map) if cd else None,
                "title": resolve_attr_value(title, string_map) if title else None,
            }
            elements.append(entry)

        for child in elem:
            walk(child, depth + 1)

    walk(root)
    return elements[:max_elements]


def extract_layout_menu_refs(source_text):
    layouts = sorted(set(R_LAYOUT_RE.findall(source_text)))
    menus = sorted(set(R_MENU_RE.findall(source_text)))
    return layouts, menus


def extract_screen_level_hooks(source_text):
    found = []
    for name in SCREEN_LEVEL_PATTERNS:
        if re.search(rf"\b{re.escape(name)}\s*\(", source_text):
            found.append(name)
    return found


def lines_near_listener_events(source_text):
    """
    For each line containing a listener API, collect R.id.* in a window
    and binding.* members in the same window.
    """
    lines = source_text.splitlines()
    linked = []
    seen = set()

    for i, line in enumerate(lines):
        event_kind = None
        for pat, kind in LISTENER_PATTERNS:
            if re.search(pat, line):
                event_kind = kind
                break
        if not event_kind:
            continue
        lo = max(0, i - 18)
        hi = min(len(lines), i + 18)
        window = "\n".join(lines[lo:hi])
        for m in R_ID_RE.finditer(window):
            rid = m.group(1)
            key = (rid, event_kind)
            if key not in seen:
                seen.add(key)
                linked.append({"id": rid, "event_kind": event_kind})
        for m in BINDING_MEMBER_RE.finditer(window):
            key = (m.group(1), event_kind, "binding")
            if key not in seen:
                seen.add(key)
                linked.append({"binding": m.group(1), "event_kind": event_kind})
        for m in re.finditer(r'Modifier\.testTag\(\s*"([^"]+)"\s*\)', window):
            key = (m.group(1), event_kind, "testTag")
            if key not in seen:
                seen.add(key)
                linked.append({"test_tag": m.group(1), "event_kind": event_kind})
    return linked

def extract_compose_elements(source_text, string_map):
    elements = []

    # 1. testTag 수집
    test_tags = re.findall(r'Modifier\.testTag\(\s*"([^"]+)"\s*\)', source_text)
    for tag in test_tags:
        elements.append({"test_tag": tag})

    # 2. semantics contentDescription 추출
    semantics_cds = re.findall(r'semantics\s*\{\s*contentDescription\s*=\s*"([^"]+)"\s*\}', source_text)
    for cd in semantics_cds:
        elements.append({"content_description": cd})

    # 3. stringResource 해석
    string_resources = re.findall(r'stringResource\(\s*R\.string\.(\w+)\s*\)', source_text)
    for sr in string_resources:
        text = string_map.get(sr)
        if text:
             elements.append({"string_resource": sr, "text": text})

    # 4. Text 컴포저블의 리터럴 문자열 추출
    literal_texts = re.findall(r'Text\(\s*"([^"]+)"\s*(?:,|\))', source_text)
    for text in literal_texts:
         elements.append({"literal_text": text})

    # 5. List items (LazyColumn/Row items)
    if re.search(r'\b(?:items|itemsIndexed)\s*\(', source_text):
         elements.append({"is_list_item": True, "note": "Contains Lazy list items"})

    return elements[:40]

def has_compose(source_text):
    return "@Composable" in source_text or " androidx.compose." in source_text


def analyze_source_file(filepath, string_map):
    res_dir = find_res_dir_for_path(filepath)
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
    except (IOError, UnicodeDecodeError):
        return None

    layouts, menus = extract_layout_menu_refs(text)
    layout_paths = []
    menu_paths = []
    all_elements = []

    for ln in layouts:
        p = find_layout_or_menu_xml(res_dir, "layout", ln) if res_dir else None
        if p:
            layout_paths.append(p)
            for el in parse_view_xml_file(p, string_map):
                el["from_layout"] = p
                all_elements.append(el)
    for mn in menus:
        p = find_layout_or_menu_xml(res_dir, "menu", mn) if res_dir else None
        if p:
            menu_paths.append(p)
            for el in parse_view_xml_file(p, string_map):
                el["from_menu"] = p
                all_elements.append(el)

    event_links = lines_near_listener_events(text)
    screen_level = extract_screen_level_hooks(text)

    # Check for RecyclerView ViewHolder pattern
    if "ViewHolder" in text and "setOnClickListener" in text:
         event_links.append({"note": "RecyclerView Item Click detected via ViewHolder"})

    compose_elements = []
    compose_only = has_compose(text) and not layouts and not menus
    if has_compose(text):
         compose_elements = extract_compose_elements(text, string_map)

    return {
        "target_file": filepath,
        "res_dir": res_dir,
        "layouts": layout_paths,
        "menus": menu_paths,
        "elements": all_elements[:60],
        "listener_linked": event_links[:40],
        "screen_level_hooks": screen_level,
        "compose_only": compose_only,
        "compose_elements": compose_elements,
    }


def analyze_resource_xml(filepath, string_map):
    """For res/layout, res/menu, res/navigation, res/xml touched files."""
    if "/res/layout" in filepath.replace("\\", "/") or "/res/menu" in filepath.replace("\\", "/"):
        elements = parse_view_xml_file(filepath, string_map, max_elements=50)
        return {
            "target_file": filepath,
            "layouts": [filepath] if "layout" in filepath else [],
            "menus": [filepath] if "menu" in filepath else [],
            "elements": elements,
            "listener_linked": [],
            "screen_level_hooks": [],
            "compose_only": False,
            "resource_self": True,
        }
    if "/res/navigation/" in filepath.replace("\\", "/"):
        labels = []
        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                nav = f.read()
            for m in re.finditer(r'android:label="(@string/(\w+))"', nav):
                key = m.group(2)
                labels.append(string_map.get(key, m.group(1)))
            for m in re.finditer(r'android:label="([^"@][^"]*)"', nav):
                labels.append(m.group(1))
        except (IOError, UnicodeDecodeError):
            pass
        return {
            "target_file": filepath,
            "layouts": [],
            "menus": [],
            "elements": [],
            "navigation_labels": labels[:20],
            "listener_linked": [],
            "screen_level_hooks": [],
            "compose_only": False,
            "resource_self": True,
        }
    return None


def safe_filename(filepath):
    return filepath.replace("/", "_").replace("\\", "_")


def main():
    print(f"[pre_ui_name] {FROM_REF} -> {TO_REF}")
    ensure_checkout(TO_REF)

    os.makedirs(UI_NAME_DIR, exist_ok=True)

    print("[1/3] Building string index (res/values/strings.xml)...")
    string_map = build_string_index()
    with open(STRING_INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(string_map, f, ensure_ascii=False, indent=0)
    print(f"  -> {len(string_map)} string keys -> {STRING_INDEX_FILE}")

    cmd_list = ["git", "diff", "--name-only", FROM_REF, TO_REF, "--", "."] + EXCLUDES
    changed_files = [f for f in run_cmd(cmd_list).split("\n") if f]

    manifest = {"from_ref": FROM_REF, "to_ref": TO_REF, "files": {}}

    print(f"[2/3] Scanning {len(changed_files)} changed paths for UI context...")
    written = 0
    for filepath in changed_files:
        if is_non_prod(filepath):
            continue

        cmd_diff = ["git", "diff", "-U3", FROM_REF, TO_REF, "--", filepath]
        try:
            diff_text = run_cmd(cmd_diff)
        except subprocess.CalledProcessError:
            continue
        if not diff_text or "deleted file mode" in diff_text:
            continue
        if len(diff_text.splitlines()) > MAX_DIFF_LINES:
            continue
        if is_trivial_diff(diff_text):
            continue

        ext = os.path.splitext(filepath)[1].lower()
        data = None
        if ext in (".kt", ".java"):
            data = analyze_source_file(filepath, string_map)
        elif ext == ".xml" and (
            "/res/layout" in filepath
            or "/res/menu" in filepath
            or "/res/navigation" in filepath
        ):
            data = analyze_resource_xml(filepath, string_map)

        if not data:
            continue

        out_name = f"{safe_filename(filepath)}.json"
        out_path = os.path.join(UI_NAME_DIR, out_name)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        manifest["files"][filepath] = out_name
        written += 1

    with open(MANIFEST_FILE, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print(f"[3/3] Wrote {written} UI context file(s) under {UI_NAME_DIR}/")
    print(f"  manifest -> {MANIFEST_FILE}")


if __name__ == "__main__":
    main()
