from __future__ import annotations

from abc import ABC, abstractmethod
from chat_dir.models import ChatLink


class ChatProvider(ABC):
    @abstractmethod
    def collect(self) -> list[ChatLink]:
        raise NotImplementedError
