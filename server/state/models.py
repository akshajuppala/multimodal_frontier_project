from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ObjectAction(str, Enum):
    APPEARED = "appeared"
    MOVED = "moved"
    DISAPPEARED = "disappeared"
    UNCHANGED = "unchanged"


class DangerType(str, Enum):
    FALL = "fall"
    FIRE_HAZARD = "fire_hazard"
    DISTRESS = "distress"
    WANDERING = "wandering"
    OTHER = "other"


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ObjectObservation(BaseModel):
    item: str
    location: str
    action: ObjectAction
    confidence: float = Field(ge=0.0, le=1.0)


class PeopleUpdate(BaseModel):
    present: list[str] = Field(default_factory=list)
    arrived: list[str] = Field(default_factory=list)
    departed: list[str] = Field(default_factory=list)


class DangerSignal(BaseModel):
    type: DangerType
    description: str
    severity: Severity


class FrameObservation(BaseModel):
    changed: bool
    timestamp: Optional[datetime] = None
    objects: list[ObjectObservation] = Field(default_factory=list)
    people: Optional[PeopleUpdate] = None
    activity: Optional[str] = None
    danger: Optional[DangerSignal] = None
    should_alert: bool = False
    alert_reason: Optional[str] = None


class ObjectState(BaseModel):
    item: str
    location: str
    last_seen: datetime
    confidence: float


class PersonState(BaseModel):
    name: str
    present: bool
    last_seen: datetime
    arrived_at: Optional[datetime] = None
    departed_at: Optional[datetime] = None


class CalendarEvent(BaseModel):
    id: Optional[str] = None
    title: str
    time: datetime
    end_time: Optional[datetime] = None
    location: Optional[str] = None
    notes: Optional[str] = None


class MedicationEntry(BaseModel):
    id: Optional[int] = None
    name: str
    dosage: str
    scheduled_times: list[str]  # ["08:00", "20:00"]
    notes: Optional[str] = None


class MedicationLog(BaseModel):
    medication_name: str
    scheduled_time: str
    taken_at: Optional[datetime] = None
    skipped: bool = False


class RoutineEntry(BaseModel):
    id: Optional[int] = None
    timestamp: datetime
    activity: str
    location: Optional[str] = None
    notes: Optional[str] = None


class AgentState(BaseModel):
    """Top-level state object passed through the LangGraph graph."""
    messages: list = Field(default_factory=list)
    current_frame: Optional[str] = None  # base64 JPEG
    last_observation: Optional[FrameObservation] = None
    objects: list[ObjectState] = Field(default_factory=list)
    people: list[PersonState] = Field(default_factory=list)
    pending_speech: Optional[str] = None
    user_name: str = "friend"
