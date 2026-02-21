from __future__ import annotations

import json
from typing import Any, Callable

import ollama

from cortex.approval import isConfirmed
from cortex.session import Session
from cortex.tools.shell import runShell


class Agent:
    def __init__(
        self, model: str, tools: list[Callable[..., Any]], system_prompt: str
    ) -> None:
        self.model = model
        self.tools = tools
        self.system_prompt = system_prompt
        self.tool_map = {tool.__name__: tool for tool in self.tools}

    def initSession(self) -> Session:
        s = Session()
        s.add("system", self.system_prompt)
        return s

    def runTurn(self, session: Session, user_msg: str) -> Any:
        session.add("user", user_msg)
        content = ""
        tool_calls = True

        while tool_calls != None:
            response = ollama.chat(
                model=self.model,
                messages=session.messages,
                tools=self.tools,
                stream=False,
            )

            content = response.message.content
            tool_calls = getattr(response.message, "tool_calls", None)

            session.messages.append(
                {
                    "role": "assistant",
                    "content": response.message.content,
                    "tool_calls": tool_calls,
                }
            )

            if content != "":
                break

            print("proposed commands:")
            for tool_call in tool_calls:
                print(" ", tool_call.function.arguments["cmd"])

            if isConfirmed("run proposed commands?"):
                for tool_call in tool_calls:
                    tool_name = tool_call.function.name
                    tool_args = tool_call.function.arguments

                    fn = self.tool_map.get(tool_name)
                    result = fn(**tool_args)

                    session.add("tool", result)

        return content
