#!/usr/bin/env python3

from __future__ import annotations

import ollama

from cortex.agent import Agent
from cortex.system_prompt import SYSTEM_PROMPT
from cortex.tools.shell import runShell

MODEL = "qwen3:30b"


def main() -> int:
    agent = Agent(MODEL, [runShell], SYSTEM_PROMPT)
    session = agent.initSession()
    ollama.chat(model=MODEL, keep_alive="5m")
    while True:
        try:
            user_msg = input("> ").strip()
            if user_msg.lower() == "quit":
                print("\nExiting...")
                break
            if user_msg.lower() == "\\messages":
                for msg in session.messages:
                    print(msg)
                continue
            response = agent.runTurn(session, user_msg)
            print(response)
        except KeyboardInterrupt:
            print("\nExiting...")
            break

    ollama.chat(model=MODEL, keep_alive=0)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
