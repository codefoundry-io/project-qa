#!/usr/bin/env python3
"""
Interactive Gemini CLI wrapper: 프로세스를 하나만 유지하여 초기 로딩 오버헤드(스킬 로드, YOLO 등)를 제거합니다.
Usage:
  python chat_gemini.py              # 일반 대화 모드
  python chat_gemini.py --yolo       # YOLO 모드 (도구 자동 승인)
"""
import os
import sys
import subprocess
import threading
import time

NODE_HEAP_MB = 8192
GEMINI_MODEL = "auto"

def main():
    yolo = "--yolo" in sys.argv
    
    # 1. Gemini 기본 명령어 구성
    cmd = ["gemini"]
    if yolo:
        cmd.append("--yolo")
    
    if GEMINI_MODEL != "auto":
        cmd.extend(["-m", GEMINI_MODEL])
    
    env = os.environ.copy()
    env["NODE_OPTIONS"] = f"--max-old-space-size={NODE_HEAP_MB}"
    # 표준 출력 버퍼링 해제
    env["PYTHONUNBUFFERED"] = "1"

    print(f"Connecting to Gemini (Persistent Process)...")
    
    # 2. Gemini를 인터랙티브 모드로 실행 (stdin, stdout 파이프 연결)
    process = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        env=env
    )

    # 3. 별도 스레드에서 Gemini의 출력을 실시간으로 터미널에 표시
    def listen_output():
        try:
            while True:
                line = process.stdout.readline()
                if not line:
                    break
                # Gemini CLI의 프롬프트나 답변을 그대로 출력
                print(line, end="", flush=True)
        except Exception as e:
            print(f"\n[Output Thread Error]: {e}")

    output_thread = threading.Thread(target=listen_output, daemon=True)
    output_thread.start()

    # 프로세스 초기화 대기
    time.sleep(1.5)

    print("\n--- 시스템이 준비되었습니다. ---")
    print("- 여러 줄을 입력할 수 있습니다. 빈 줄을 입력하면 메시지가 전송됩니다.")
    print("- 'exit' 또는 'quit'을 입력하면 종료됩니다.\n")

    try:
        while True:
            lines = []
            while True:
                try:
                    line = input()
                except EOFError:
                    return
                
                # 종료 명령어 체크
                if not lines and line.strip().lower() in ("exit", "quit", "q"):
                    print("종료합니다.")
                    process.terminate()
                    return
                
                # 빈 줄 입력 시 전송 (내용이 있을 때만)
                if line == "":
                    if lines:
                        break
                    continue
                lines.append(line)
            
            prompt = "\n".join(lines)
            if prompt.strip():
                # Gemini의 stdin으로 프롬프트 전달
                process.stdin.write(prompt + "\n")
                process.stdin.flush()
                
    except KeyboardInterrupt:
        print("\n중단되었습니다. 종료합니다...")
    finally:
        if process.poll() is None:
            process.terminate()

if __name__ == "__main__":
    main()
