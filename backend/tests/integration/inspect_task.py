"""查看特定任务的 result_json,分析非法日期的处理结果"""
import sqlite3
import json
import sys

con = sqlite3.connect(r"d:\A--Learning-D\Hello-agent\helloagents-trip-planner\backend\trip_records.db")
con.row_factory = sqlite3.Row

task_id = sys.argv[1] if len(sys.argv) > 1 else "bbd9310d-419f-4546-9927-8445fdeac828"
row = con.execute(
    "SELECT result_json, error_message, status FROM trip_records WHERE id=?", (task_id,)
).fetchone()

if not row:
    print("NOT FOUND")
    sys.exit(1)

print("status:", row["status"], "| error:", row["error_message"])
res = json.loads(row["result_json"]) if row["result_json"] else None
if not res:
    print("result_json is None")
    sys.exit(0)

print("keys:", list(res.keys()))
print("city:", res.get("city"))
print("start_date:", res.get("start_date"))
print("end_date:", res.get("end_date"))
print("num_days:", len(res.get("days", [])))
print("weather_info:", len(res.get("weather_info", [])))
print("overall_suggestions:", (res.get("overall_suggestions") or "")[:60])

for i, d in enumerate(res.get("days", [])[:3]):
    print(f"--- day{i} ---")
    print("  date:", d.get("date"), "| day_index:", d.get("day_index"))
    print("  hotel:", (d.get("hotel") or {}).get("name"), (d.get("hotel") or {}).get("location"))
    print("  attractions:", [(a.get("name"), a.get("location")) for a in d.get("attractions", [])])

con.close()