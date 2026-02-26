from __future__ import annotations

from collections.abc import Iterator
from typing import Any, Callable, Tuple

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
        return 3

    def streamResponse(
        self, response: Iterator[ollama.ChatResponse]
    ) -> Tuple[str, str, list]:
        content = ""
        thinking = ""
        tool_calls = []
        in_thinking = False
        for chunk in response:
            if chunk.message.thinking:
                if not in_thinking:
                    in_thinking = True
                    print("Thinking:\n", end="", flush=True)
                print(chunk.message.thinking, end="", flush=True)
                thinking += chunk.message.thinking
            if chunk.message.content:
                if in_thinking:
                    in_thinking = False
                    print("\n\nAnswer:\n", end="", flush=True)
                print(chunk.message.content, end="", flush=True)
                content += chunk.message.content
            if chunk.message.tool_calls:
                tool_calls.extend(chunk.message.tool_calls)
        print()
        return content, thinking, tool_calls

    def runTurn(self, session: Session, user_msg: str) -> None:
        session.add("user", user_msg)
        content = ""
        thinking = ""
        tool_calls = True

        while content == "":
            response = ollama.chat(
                model=self.model,
                messages=session.messages,
                tools=self.tools,
                stream=True,
                think=True,
                keep_alive=self.keep_alive,
            )

            content, thinking, tool_calls = self.streamResponse(response)

            session.add("assistant", content, thinking=thinking, tool_calls=tool_calls)

            tool_response = self.handleToolcalls(session, tool_calls)

            if tool_response == 2:
                break
