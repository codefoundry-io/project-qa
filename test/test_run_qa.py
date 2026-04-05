import os
import sys
import subprocess
import math

PENDING_FILE = "map_jobs/pending.txt"
REPORTS_DIR = "map_results"
JOBS_PER_CORE = 2  # Reduced to 2 for better stability and rate limit management

def main():
    if not os.path.exists(PENDING_FILE):
        print(f"[Error] {PENDING_FILE} not found. Run test_pre_candidate.py first.")
        return

    # 1. 파일 목록 읽기
    with open(PENDING_FILE, "r") as f:
        files = [line.strip() for line in f if line.strip()]
    
    if not files:
        print("[Map] No pending files to process.")
        return

    # 2. 파일을 J개의 파티션으로 나누기
    # (각 워커가 견고하게 에러를 핸들링하며 자신의 몫을 처리함)
    num_workers = JOBS_PER_CORE
    chunk_size = math.ceil(len(files) / num_workers)
    chunks = [files[i:i + chunk_size] for i in range(0, len(files), chunk_size)]
    
    # 파티션별로 임시 파일 생성 (parallel 에 넘겨주기 위함)
    temp_files = []
    for i, chunk in enumerate(chunks):
        temp_path = f"map_jobs/part_{i:02d}.txt"
        with open(temp_path, "w") as tf:
            tf.write("\n".join(chunk))
        temp_files.append(temp_path)

    # 3. GNU Parallel 실행
    # -j 옵션으로 병렬성 조절
    # --tag: 어느 파티션의 출력인지 표시
    # --line-buffer: 라인 단위로 즉시 출력 (실시간 로그 확인용)
    parallel_cmd = (
        f"ls map_jobs/part_*.txt | "
        f"parallel -j {num_workers} --tag --line-buffer "
        f"'python3 test_worker.py $(cat {{}})'"
    )
    
    print(f"[Map] Starting parallel robust workers (J={num_workers})...")
    try:
        subprocess.run(parallel_cmd, shell=True)
    finally:
        # 임시 파일 삭제
        for f in temp_files:
            if os.path.exists(f): os.remove(f)

    # 4. Reduce Phase (통합 리포트 생성)
    print("\n[Reduce] Merging all results into FINAL_QA_REPORT.md...")
    # 원본 run_qa.py의 병합 로직만 빌려와서 실행 (map은 이미 완료됨)
    subprocess.run(["python3", "run_qa.py", "--yolo"])

if __name__ == "__main__":
    main()
