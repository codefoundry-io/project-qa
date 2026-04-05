import os
import sys
import subprocess
import json

REPORTS_DIR = "map_results"

def load_prompt(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

ANALYSIS_PROMPT = load_prompt("prompts/qa/analysis.md")

def run_one_job(job_file):
    name = os.path.basename(job_file).replace(".diff", "")
    output_path = f"{REPORTS_DIR}/{name}.json"
    
    if os.path.exists(output_path):
        # print(f"  [Skip] {name} already exists.")
        return

    # 단일 파일 분석을 위한 프롬프트 구성
    file_list_str = f"- Read: {job_file} -> Write: {output_path}\n"
    prompt = ANALYSIS_PROMPT.format(reports_dir=REPORTS_DIR, file_list=file_list_str)
    
    cmd = ["gemini", "-p", prompt, "--yolo"]
    
    # 실행
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        print(f"  [OK] {name}")
    else:
        print(f"  [Fail] {name}: {result.stderr[:100]}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 test_process_job.py <job_file>")
        sys.exit(1)
    
    job_file = sys.argv[1]
    run_one_job(job_file)
