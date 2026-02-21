from __future__ import annotations

import json
from typing import Any, Callable

import ollama

from cortex.approval import isConfirmed
from cortex.session import Session
from cortex.tools.shell import runShell

ApproveFunction = Callable[[str], bool]
ExecFunction = Callable[[str], str]


class Agent:
    def __init__(
        self, model: str, tools: list[Callable[..., Any]], system_prompt: str
    ) -> None:
        self.model = model
        self.tools = tools
        self.system_prompt = system_prompt

    def initSession(self) -> Session:
        s = Session()
        s.add("system", self.system_prompt)
        return s

    def runTurn(self, session: Session, user_msg: str) -> Any:
        session.add("user", user_msg)

        resp = ollama.chat(
            model=self.model,
            messages=session.messages,
            tools=self.tools,
            stream=False,
        )

        tool_calls = getattr(resp.message, "tool_calls", None)
        session.messages.append(
            {
                "role": "assistant",
                "content": resp.message.content or "",
                "tool_calls": tool_calls,
            }
        )

        print(f"\n{tool_calls[0].function.arguments['cmd']}\n")

        if isConfirmed("run porposed commands?"):
            stdout = runShell(tool_calls[0].function.arguments["cmd"])
            print(stdout)
            session.add("tool", stdout)

        resp2 = ollama.chat(
            model=self.model,
            messages=session.messages,
            tools=self.tools,
            stream=False,
        )

        return resp2.message.content
