from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ObjectSighting(BaseModel):
    name: str
    location: str


class Observation(BaseModel):
    timestamp: str
    actions: list[str] = Field(default_factory=list)
    objects: list[ObjectSighting] = Field(default_factory=list)
    safety_concerns: list[str] = Field(default_factory=list)
    urgency: Literal["none", "low", "high", "emergency"] = "none"

    @property
    def is_urgent(self) -> bool:
        return self.urgency in ("high", "emergency")


class CalendarEvent(BaseModel):
    id: str
    title: str
    datetime: str
    description: str = ""
    reminder_minutes_before: int = 15


class AgentLogEntry(BaseModel):
    timestamp: str
    trigger: Literal["speech", "proactive"]
    input: str
    tool_calls: list[dict] = Field(default_factory=list)
    response: str
