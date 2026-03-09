#!/usr/bin/env python3

from __future__ import annotations

import ollama

from cortex.agent import Agent
from cortex.system_prompt import SYSTEM_PROMPT
from cortex.tools.editor import (get_lsp_diagnostics, read_file, replace_text,
                                 write_file)
from cortex.tools.shell import runShell

MODEL = "qwen3.5:35b"


def main() -> int:
    tools = [
        runShell,
        read_file,
        write_file,
        get_lsp_diagnostics,
        replace_text,
    ]

    agent = Agent(MODEL, tools, SYSTEM_PROMPT)
    session = agent.initSession()

    ollama.chat(model=MODEL, keep_alive=-1)

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
            agent.runTurn(session, user_msg)
        except KeyboardInterrupt:
            print("\nExiting...")
            break

    ollama.chat(model=MODEL, keep_alive=0)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
