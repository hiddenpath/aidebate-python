"""Data types for the AI Debate system."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from ai_lib_python import AiClient


@dataclass
class ClientInfo:
    """Wraps an AI client with metadata."""
    name: str
    model_id: str
    client: AiClient


class Position(str, Enum):
    PRO = "pro"
    CON = "con"
    JUDGE = "judge"

    @property
    def label(self) -> str:
        return {"pro": "Pro", "con": "Con", "judge": "Judge"}[self.value]


class DebatePhase(str, Enum):
    OPENING = "opening"
    REBUTTAL = "rebuttal"
    DEFENSE = "defense"
    CLOSING = "closing"
    JUDGEMENT = "judgement"

    @property
    def title(self) -> str:
        titles = {
            "opening": "一辩开篇",
            "rebuttal": "二辩反驳",
            "defense": "三辩防守",
            "closing": "总结陈词",
            "judgement": "裁判裁决",
        }
        return titles[self.value]


@dataclass
class TranscriptEntry:
    """A single entry in the debate transcript."""
    position: Position
    phase: DebatePhase
    content: str
    model_id: str


@dataclass
class AvailableModel:
    """Model info for API response."""
    model_id: str
    display_name: str


@dataclass
class AvailableProvider:
    """Provider info for API response."""
    provider: str
    display_name: str
    env_var: str
    has_key: bool
    models: list[AvailableModel] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "provider": self.provider,
            "display_name": self.display_name,
            "env_var": self.env_var,
            "has_key": self.has_key,
            "models": [{"model_id": m.model_id, "display_name": m.display_name} for m in self.models],
        }
