# -*- coding: utf-8 -*-
import urllib.request, json, re

def llm(prompt):
    system = """تو یک دستیار فارسی هستی. فقط به فارسی پاسخ بده. پاسخ کوتاه و مستقیم باشد.

اگر کاربر بخواهد رویدادی در تقویم اضافه یا حذف کند، فقط یک JSON خالص بدون توضیح برگردان:

برای افزودن:
{"action":"create","title":"عنوان رویداد","start":"2025-01-15T14:00:00+03:30","end":"2025-01-15T15:00:00+03:30","guests":["email@example.com"]}

برای حذف:
{"action":"delete","title":"عنوان رویداد"}

برای مشاهده رویدادها:
{"action":"list"}

در غیر این صورت به طور معمول پاسخ بده."""

    payload = {
        "model": "qwen3:1.7b",
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        "think": True,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        "http://localhost:11434/api/chat",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        result = json.loads(resp.read().decode("utf-8"))
    return result["message"].get("content", ""), result["message"].get("thinking", "")

prompts = [
    "یه جلسه فردا ساعت ۱۰ صبح اضافه کن",
    "یک رویداد برای ۲۵ ژوئن ساعت ۳ بعد از ظهر با عنوان تست اضافه کن",
    "add a meeting tomorrow at 2pm",
]

out = []
for p in prompts:
    content, thinking = llm(p)
    out.append(f"PROMPT: {p}")
    out.append(f"CONTENT: {repr(content[:300])}")
    has_json = bool(re.search(r'\{"action"', content))
    out.append(f"HAS_JSON: {has_json}")
    out.append("---")

with open("llm_calendar_output.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(out))
print("Done. Check llm_calendar_output.txt")
