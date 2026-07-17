from __future__ import annotations

from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class ChatLink:
    url: str
    title: str | None = None
    chat_id: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        data = asdict(self)
        return {"chat_id": data["chat_id"], "title": data["title"], "url": data["url"]}
