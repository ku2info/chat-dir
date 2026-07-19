from __future__ import annotations

import json
from pathlib import Path
from .errors import OutputError
from .models import ChatLink


def format_json(chats: list[ChatLink]) -> str:
    return json.dumps([c.to_dict() for c in chats], ensure_ascii=False, indent=2) + "\n"


def format_urls(chats: list[ChatLink]) -> str:
    return "".join(f"{c.url}\n" for c in chats)


def format_human(chats: list[ChatLink]) -> str:
    blocks = []
    for i, chat in enumerate(chats, 1):
        title = chat.title or "(untitled)"
        blocks.append(f"{i}. {title}\n   {chat.url}")
    return "\n\n".join(blocks) + ("\n" if blocks else "")


def render(chats: list[ChatLink], json_mode: bool = False, urls_only: bool = False) -> str:
    if urls_only:
        return format_urls(chats)
    if json_mode:
        return format_json(chats)
    return format_human(chats)


def write_output(path: str, content: str) -> None:
    try:
        Path(path).expanduser().write_text(content, encoding="utf-8")
    except OSError as exc:
        raise OutputError(f"Could not write output file: {path}") from exc
