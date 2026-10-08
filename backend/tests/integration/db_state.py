"""查询 concurrency 测试的 DB 状态"""
import sqlite3

con = sqlite3.connect(r"d:\A--Learning-D\Hello-agent\helloagents-trip-planner\backend\trip_records.db")
con.row_factory = sqlite3.Row

rows = con.execute(
    "SELECT status, COUNT(*) c FROM trip_records "
    "WHERE user_id LIKE 'concurrency-test-user-%' GROUP BY status"
).fetchall()
print({r["status"]: r["c"] for r in rows})

tot = con.execute(
    "SELECT COUNT(*) c FROM trip_records WHERE user_id LIKE 'concurrency-test-user-%'"
).fetchone()["c"]
print("total:", tot)
con.close()