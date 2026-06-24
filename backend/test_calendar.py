# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, ".")
from calendar_agent import create_event, list_events, delete_event

out = []
out.append("=== LIST BEFORE ===")
out.append(list_events(days=7))

out.append("\n=== CREATE ===")
result = create_event(
    title="تست دستیار فارسی",
    start_iso="2026-06-25T10:00:00+03:30",
    end_iso="2026-06-25T11:00:00+03:30",
    guests=[],
)
out.append(result)

out.append("\n=== LIST AFTER ===")
out.append(list_events(days=3))

with open("calendar_test_output.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(out))
print("Done. Check calendar_test_output.txt")
