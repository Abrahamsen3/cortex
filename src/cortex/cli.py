#!/usr/bin/env python3

from __future__ import annotations

from cortex.agent import Agent
from cortex.system_prompt import SYSTEM_PROMPT
from cortex.tools.shell import runShell

MODEL = "qwen3:30b"


def isConfirmed(question: str) -> bool:
    while True:
        answer = input(f"{question} [y/n]").strip().lower()
        if answer in ("y", "yes"):
            return True
        if answer in ("n", "no"):
            return False


def main() -> int:
    user_msg = input("> ").strip()
    agent = Agent(MODEL, [runShell], SYSTEM_PROMPT)
    session = agent.initSession()
    response = agent.runTurn(session, user_msg)
    print(response)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
