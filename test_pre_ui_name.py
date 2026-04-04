#!/usr/bin/env python3
"""
Modernized UI name context builder using ast-grep and fd.
Detects legacy-to-compose bridges and extracts rich semantics.
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

# 도구 설정
FD_EXE = "fdfind" if subprocess.run(["which", "fdfind"], capture_output=True).returncode == 0 else "fd"
SG_EXE = "sg"

def run_cmd(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, check=True).stdout.strip()

def ensure_checkout(ref):
    current = run_cmd(["git", "rev-parse", "HEAD"])
    target = run_cmd(["git", "rev-parse", ref])
    if current == target:
        return
    print(f"[test_pre_ui_name] Checking out {ref} ...")
    subprocess.run(["git", "checkout", ref], check=True)

def collect_strings_xml_paths():
    """fd를 사용하여 초고속으로 strings.xml 경로 수집"""
    try:
        res = run_cmd([FD_EXE, "strings.xml", "--exclude", "build"])
        return res.splitlines()
    except:
        return []

def extract_hybrid_bridge(filepath):
    """ast-grep을 사용하여 Java/XML 유물에서 Compose로 넘어가는 지점을 포착"""
    bridges = []
    ext = os.path.splitext(filepath)[1].lower()
    try:
        if ext == ".kt":
            # Kotlin: setContent { ... }
            res = run_cmd([SG_EXE, "-p", "$VIEW.setContent { $$$ }", "--lang", "kotlin", "--json", filepath])
            if res:
                for item in json.loads(res):
                    bridges.append({"type": "setContent", "text": item["text"]})
        elif ext == ".java":
            # Java: Bridge.bind(view, ...) - More flexible pattern
            res = run_cmd([SG_EXE, "-p", "$CLASS.bind($$$)", "--lang", "java", "--json", filepath])
            if res:
                for item in json.loads(res):
                    vars_dict = item.get("vars", {})
                    bridges.append({"type": "bridge_bind", "class": vars_dict.get("CLASS", "?"), "text": item["text"]})
    except Exception as e:
        print(f"  Warning: Bridge detection failed for {filepath}: {e}")
    return bridges

def extract_compose_ui_semantics(filepath, string_map):
    """Compose 코드 내에서 실제 화면에 보이는 텍스트와 태그를 AST로 추출"""
    semantics = []
    try:
        # Text("문자열")
        res = run_cmd([SG_EXE, "-p", 'Text(text = "$TEXT", $$$)', "--lang", "kotlin", "--json", filepath])
        for item in json.loads(res):
            semantics.append({"type": "text_literal", "value": item["vars"]["TEXT"]})
            
        # stringResource(R.string.xxx)
        res = run_cmd([SG_EXE, "-p", 'stringResource(R.string.$ID)', "--lang", "kotlin", "--json", filepath])
        for item in json.loads(res):
            sid = item["vars"]["ID"]
            semantics.append({"type": "string_resource", "id": sid, "resolved": string_map.get(sid)})
            
        # Modifier.testTag("xxx")
        res = run_cmd([SG_EXE, "-p", 'Modifier.testTag("$TAG")', "--lang", "kotlin", "--json", filepath])
        for item in json.loads(res):
            semantics.append({"type": "test_tag", "value": item["vars"]["TAG"]})
    except:
        pass
    return semantics

# --- 기존 로직 결합 (필수 유틸리티) ---

def find_res_dir_for_path(filepath):
    d = os.path.dirname(os.path.abspath(filepath))
    for _ in range(24):
        cand = os.path.join(d, "res")
        if os.path.isdir(cand): return cand
        parent = os.path.dirname(d)
        if parent == d: break
        d = parent
    return None

def parse_strings_xml(path, string_map):
    try:
        tree = ET.parse(path)
        root = tree.getroot()
        for elem in root:
            if elem.tag != "string": continue
            name = elem.attrib.get("name")
            if not name: continue
            string_map[name] = "".join(elem.itertext()).strip()
    except: pass

def resolve_attr_value(raw, string_map):
    if raw is None: return None
    raw = raw.strip()
    m = re.match(r"^@string/(\w+)$", raw)
    if m: return string_map.get(m.group(1), raw)
    return raw

def parse_view_xml_file(xml_path, string_map, max_elements=40):
    elements = []
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
    except: return elements

    def walk(elem, depth=0):
        if depth > 64 or len(elements) >= max_elements: return
        aid = elem.attrib.get(f"{ANDROID_NS}id") or elem.attrib.get("android:id")
        text = elem.attrib.get(f"{ANDROID_NS}text") or elem.attrib.get("android:text")
        cd = elem.attrib.get(f"{ANDROID_NS}contentDescription") or elem.attrib.get("android:contentDescription")
        tag = elem.tag.split("}", 1)[-1] if "}" in elem.tag else elem.tag
        
        if aid:
            m = re.search(r"@\+?id/(\w+)", aid)
            elements.append({
                "id": m.group(1) if m else aid,
                "tag": tag,
                "text": resolve_attr_value(text, string_map) if text else None,
                "content_description": resolve_attr_value(cd, string_map) if cd else None,
            })
        for child in elem: walk(child, depth + 1)
    walk(root)
    return elements

def analyze_source_file(filepath, string_map):
    res_dir = find_res_dir_for_path(filepath)
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
    except: return None

    # Legacy 추적 (Regex)
    layouts = sorted(set(re.findall(r"\bR\.layout\.(\w+)\b", text)))
    all_elements = []
    for ln in layouts:
        p = None
        if res_dir:
            for d in os.listdir(res_dir):
                if d.startswith("layout"):
                    cp = os.path.join(res_dir, d, f"{ln}.xml")
                    if os.path.isfile(cp): p = cp; break
        if p:
            for el in parse_view_xml_file(p, string_map):
                el["from_layout"] = p
                all_elements.append(el)

    # Modern 추적 (ast-grep)
    bridges = extract_hybrid_bridge(filepath)
    compose_semantics = extract_compose_ui_semantics(filepath, string_map)

    return {
        "target_file": filepath,
        "layouts": layouts,
        "elements": all_elements[:60],
        "bridges": bridges,
        "compose_semantics": compose_semantics,
        "has_compose": "@Composable" in text or "setContent" in text
    }

def main():
    print(f"[test_pre_ui_name] {FROM_REF} -> {TO_REF} (Modern Bridge Mode)")
    ensure_checkout(TO_REF)
    os.makedirs(UI_NAME_DIR, exist_ok=True)

    print("[1/3] Building string index...")
    string_map = {}
    for p in collect_strings_xml_paths():
        parse_strings_xml(p, string_map)
    with open(STRING_INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(string_map, f, ensure_ascii=False, indent=0)

    print("[2/3] Scanning changed files for UI context...")
    cmd_list = ["git", "diff", "--name-only", FROM_REF, TO_REF]
    changed_files = [f for f in run_cmd(cmd_list).split("\n") if f and not any(p in f for p in NON_PROD_PATTERNS)]

    manifest = {"files": {}}
    for filepath in changed_files:
        ext = os.path.splitext(filepath)[1].lower()
        data = None
        if ext in (".kt", ".java"):
            data = analyze_source_file(filepath, string_map)
        
        if data:
            safe = filepath.replace("/", "_")
            out_path = os.path.join(UI_NAME_DIR, f"{safe}.json")
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            manifest["files"][filepath] = f"{safe}.json"

    with open(MANIFEST_FILE, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"[3/3] Done. Wrote {len(manifest['files'])} UI context files.")

if __name__ == "__main__":
    main()
