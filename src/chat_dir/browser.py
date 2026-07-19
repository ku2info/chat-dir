from __future__ import annotations

import os
import platform
from pathlib import Path


def user_data_dir() -> Path:
    override = os.environ.get("CHAT_DIR_HOME")
    if override:
        return Path(override).expanduser() / "browser-profile"
    system = platform.system()
    if system == "Windows":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
        return base / "ChatDir" / "browser-profile"
    if system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "ChatDir" / "browser-profile"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "chat-dir" / "browser-profile"
