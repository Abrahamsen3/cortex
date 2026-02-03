#!/usr/bin/env python3

from __future__ import annotations

import ollama
import sys

#print(ollama.show('llama3:latest'))

def main() -> int:
    if len(sys.argv) < 2:
        print('Usage: cortex "your question here"')
        return 2

    prompt = " ".join(sys.argv[1:])

    stream = ollama.chat(
        model='llama3:latest',
        messages=[{'role': 'user', 'content': prompt}],
        stream=True,
    )

    for chunk in stream:
        message = chunk['message']
        content = message['content']
        if not isinstance(content, str):
            return 1
        print(content, end='', flush=True)

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
