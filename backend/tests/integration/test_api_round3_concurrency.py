"""API集成测试 - 第三轮: 并发上限与排队限流

提交 N 个任务, 观察:
1. 初始排队位置正确递增
2. pending/processing 总数受 max_concurrent_generations 控制
3. 全部最终进入终态(不丢失任务)
"""

import time
import sqlite3
import requests
from concurrent.futures import ThreadPoolExecutor

BASE = "http://localhost:8000"
DB = r"d:\A--Learning-D\Hello-agent\helloagents-trip-planner\backend\trip_records.db"
PASS, FAIL = [], []


def check(name, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  .. {detail}" if detail else ""))
    (PASS if ok else FAIL).append(name)


def submit_one(i):
    payload = {
        "city": "北京", "start_date": "2026-10-25", "end_date": "2026-10-25",
        "travel_days": 1, "transportation": "公共交通", "accommodation": "经济型酒店",
        "preferences": ["历史文化"], "free_text_input": "",
    }
    r = requests.post(f"{BASE}/api/trip/plan", json=payload,
                      headers={"X-User-Id": f"concurrency-test-user-{i}"}, timeout=10)
    return r.status_code, r.json()


def db_counts():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT status, COUNT(*) c FROM trip_records "
        "WHERE user_id LIKE 'concurrency-test-user-%' "
        "AND created_at >= datetime('now','-5 minutes') GROUP BY status"
    ).fetchall()
    con.close()
    return {r["status"]: r["c"] for r in rows}


print("=" * 60)
print("并发提交 12 个任务(并发上限=8)")
print("=" * 60)

t0 = time.time()
with ThreadPoolExecutor(max_workers=12) as ex:
    results = list(ex.map(submit_one, range(12)))

codes = [r[0] for r in results]
json_res = [r[1] for r in results]
ok_submit = all(c == 200 and j.get("success") and j.get("task_id") for c, j in results)
check("12个任务全部提交成功", ok_submit, f"codes={set(codes)}")

positions = [j.get("queue_position") for j in json_res]
check("排队位置不重复", len(set(positions)) == 12, f"positions={sorted(positions)}")

# 等待 worker 领取任务(最多等20s),统计并发执行数
time.sleep(20)
counts = db_counts()
processing = counts.get("processing", 0)
pending = counts.get("pending", 0)
check(f"并发执行数<=8", processing <= 8, f"processing={processing} pending={pending}")

# 等待全部完成(12个1天任务, 约60-90s)
print("等待全部任务完成...")
deadline = time.time() + 240
while time.time() < deadline:
    counts = db_counts()
    done = counts.get("success", 0) + counts.get("failed", 0)
    if done >= 12:
        break
    time.sleep(10)
counts = db_counts()
done_all = counts.get("success", 0) + counts.get("failed", 0)
check("12个任务全部进入终态", done_all == 12, f"counts={counts}")
check("无任务丢失(pending/processing清零)", counts.get("pending", 0) == 0 and counts.get("processing", 0) == 0,
      f"counts={counts}")
check("全部成功", counts.get("failed", 0) == 0, f"failed={counts.get('failed',0)}")

print()
print(f"===== 第三轮: {len(PASS)} 通过, {len(FAIL)} 失败, 总耗时{time.time()-t0:.0f}s =====")
for f in FAIL:
    print("  FAIL:", f)
raise SystemExit(1 if FAIL else 0)