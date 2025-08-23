from __future__ import annotations
from typing import List, Dict, Any, Optional
from abc import ABC, abstractmethod

Message = Dict[str, str]  # {"role": "system|user|assistant", "content": "..."}

class BaseLLM(ABC):
    @abstractmethod
    def chat(self, messages: List[Message], **kwargs) -> str:
        """Return assistant text for the given messages."""
        raise NotImplementedError
