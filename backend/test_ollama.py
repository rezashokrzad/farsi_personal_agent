# -*- coding: utf-8 -*-
import urllib.request
import json
import re

payload = {
    "model": "qwen3:1.7b",
    "messages": [
        {"role": "system", "content": "تو یک دستیار فارسی هستی. فقط یک جمله کوتاه جواب بده."},
        {"role": "user", "content": "سلام"},
    ],
    "stream": False,
    "think": False,
    # No num_predict limit — let model finish
}
data = json.dumps(payload).encode("utf-8")
req = urllib.request.Request(
    "http://localhost:11434/api/chat",
    data=data,
    headers={"Content-Type": "application/json"},
)
print("Sending (think:false, no token limit)...")
with urllib.request.urlopen(req, timeout=180) as resp:
    result = json.loads(resp.read().decode("utf-8"))
    msg = result["message"]
    content = msg.get("content", "")
    thinking = msg.get("thinking", "")
    with open("ollama_output.txt", "w", encoding="utf-8") as f:
        f.write(f"content len={len(content)}, thinking len={len(thinking)}\n")
        f.write(f"content: {repr(content)}\n")
        f.write(f"thinking snippet: {repr(thinking[:100])}\n")
    print(f"content len={len(content)}, thinking len={len(thinking)}")
