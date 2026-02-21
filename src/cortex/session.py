from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Session:
    """
    Holds the message history
    """

    messages: list[dict[str, Any]] = field(default_factory=list)

    def add(self, role: str, content: str, **extra: Any) -> None:
        msg: dict[str, Any] = {"role": role, "content": content}
        msg.update(extra)
        self.messages.append(msg)
