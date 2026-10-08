"""轮询并等待 concurrency 测试的全部任务完成"""
import subprocess
import time
import sys

for i in range(40):
    out = subprocess.run(
        ["python", "tests/integration/db_state.py"],
        capture_output=True, text=True,
        cwd=r"d:\A--Learning-D\Hello-agent\helloagents-trip-planner\backend",
    ).stdout.strip()
    print(f"[{time.strftime('%H:%M:%S')}] {out}", flush=True)
    if "processing" not in out and "pending" not in out:
        print("ALL DONE")
        break
    time.sleep(15)
else:
    print("TIMEOUT waiting for tasks")
    sys.exit(1)