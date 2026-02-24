from __future__ import annotations

from typing import Any, Callable

import ollama

from cortex.approval import isConfirmed
from cortex.session import Session


class Agent:
    def __init__(
        self,
        model: str,
        tools: list[Callable[..., Any]],
        system_prompt: str,
        keep_alive: str = "5m",
    ) -> None:
        self.model = model
        self.tools = tools
        self.system_prompt = system_prompt
        self.keep_alive = keep_alive
        self.tool_map = {tool.__name__: tool for tool in self.tools}

    def initSession(self) -> Session:
        s = Session()
        s.add("system", self.system_prompt)
        return s

    def handleToolcalls(self, session: Session, tool_calls: Any) -> int:
        if tool_calls:
            print("proposed commands:")
            for tool_call in tool_calls:
                print(
                    f"🛠️ Tool: {tool_call.function.name} | Args: {tool_call.function.arguments}"
                )

            feedback = isConfirmed("run proposed commands?")

            if feedback == "yes":
                for tool_call in tool_calls:
                    tool_name = tool_call.function.name
                    tool_args = tool_call.function.arguments

                    fn = self.tool_map.get(tool_name)

                    try:
                        result = fn(**tool_args)
                    except Exception as e:
                        result = f"Error executing tool: {str(e)}"

                    session.add("tool", result)
                return 0

            if feedback == "no":
                session.add("system", "Tool call denied by user. Try another strategy.")
                return 1

            if feedback == "edit":
                session.add(
                    "system",
                    "User wants to add to the conversation instead of running the tool now.",
                )
                return 2

    def runTurn(self, session: Session, user_msg: str) -> Any:
        session.add("user", user_msg)
        content = ""
        tool_calls = True

        while tool_calls:
            response = ollama.chat(
                model=self.model,
                messages=session.messages,
                tools=self.tools,
                stream=False,
                keep_alive=self.keep_alive,
            )

            content = response.message.content
            thinking = response.message.thinking
            tool_calls = response.message.tool_calls

            session.add("assistant", content, thinking=thinking, tool_calls=tool_calls)

            tool_response = self.handleToolcalls(session, tool_calls)

            if tool_response == 2:
                break

        return content
