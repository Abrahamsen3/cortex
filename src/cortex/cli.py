#!/usr/bin/env python3

from __future__ import annotations

from cortex.agent import Agent
from cortex.system_prompt import SYSTEM_PROMPT
from cortex.tools.shell import runShell

MODEL = "qwen3:30b"


def main() -> int:
    agent = Agent(MODEL, [runShell], SYSTEM_PROMPT)
    session = agent.initSession()
    while True:
        user_msg = input("> ").strip()
        response = agent.runTurn(session, user_msg)
        print(response)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
