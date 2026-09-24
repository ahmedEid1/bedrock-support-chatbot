#!/usr/bin/env python3
"""Records chat.py conversations as transcripts.

Runs the normal chat.py flow (python chat.py) with the customer's messages piped in, and writes
the terminal output to ../docs/transcripts/chat_<name>.txt. Piped input is not echoed by input(), so
the recorder writes each message back after its "you> " prompt.

    python record_chat.py            # all conversations below
    python record_chat.py faq_covered
"""
import os
import subprocess
import sys
from pathlib import Path

CONVERSATIONS = {
    "bug_report": [
        "Hi, the Add to cart button isn't working on your website.",
        "I open a product page, pick a size and click Add to cart, but nothing happens.",
        "I'm using Firefox 131 on Windows 11, on my desktop PC.",
    ],
    "faq_covered": ["How long do I have to return something I bought?"],
    "faq_uncovered": ["Do you offer a price match if I find the same item cheaper somewhere else?"],
    "out_of_scope": ["Can you help me write a cover letter for a job application?"],
}
OUT = Path(__file__).resolve().parent.parent / "docs" / "transcripts"


def record(name, messages):
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    done = subprocess.run([sys.executable, "chat.py"], input="\n".join(messages + ["quit"]) + "\n",
                          capture_output=True, text=True, encoding="utf-8", env=env,
                          cwd=Path(__file__).resolve().parent)
    text = done.stdout
    for message in messages + ["quit"]:  # fill each unanswered "you> " prompt in order
        text = text.replace("you> ", f"you\u0000 {message}\n", 1)
    text = text.replace("you\u0000", "you>")
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"chat_{name}.txt"
    path.write_text("$ python chat.py\n" + text.rstrip() + "\n"
                    + (f"\n[stderr]\n{done.stderr}" if done.stderr.strip() else ""), encoding="utf-8")
    print(f"--- {path.name} ---\n{path.read_text(encoding='utf-8')}")


if __name__ == "__main__":
    for name in sys.argv[1:] or CONVERSATIONS:
        record(name, CONVERSATIONS[name])
