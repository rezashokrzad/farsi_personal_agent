# -*- coding: utf-8 -*-
import sys, asyncio
sys.path.insert(0, ".")

from main import _detect_calendar_intent, _execute_calendar

async def main():
    text = "یه جلسه تست فردا ساعت ۱۱ صبح اضافه کن"
    print("Detecting intent...")
    intent = await _detect_calendar_intent(text)
    out = [f"Intent: {intent}"]

    if isinstance(intent, dict):
        out.append(f"Executing: {intent}")
        result = await _execute_calendar(intent)
        out.append(f"Calendar result: {result}")
    else:
        out.append("No calendar intent detected")

    with open("pipeline_test_output.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(out))
    print("Done.")

asyncio.run(main())
