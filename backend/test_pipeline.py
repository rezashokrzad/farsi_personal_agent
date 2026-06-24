# -*- coding: utf-8 -*-
import urllib.request
import json

def test_llm():
    text = "سلام، حال شما چطور است؟"
    data = json.dumps({"text": text}).encode("utf-8")
    req = urllib.request.Request(
        "http://localhost:8000/chat-text",
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        result = json.loads(resp.read().decode("utf-8"))
        with open("test_output.txt", "w", encoding="utf-8") as f:
            f.write(f"User: {text}\n")
            f.write(f"Assistant: {result['response']}\n")
        print("Done. Check test_output.txt")

test_llm()
