from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field

from agents.schemas import FunctionCall


# ── Event Base ──────────────────────────────────────────────────────────────


class EventBase(BaseModel):
    """Base for all event types."""

    id: str
    name: str
    description: str
    icon: str = "⚡"
    on_action_end_calls: list[FunctionCall] = Field(
        default_factory=list,
        description="Function calls executed after each action while this event is active",
    )
    on_phase_end_calls: list[FunctionCall] = Field(
        default_factory=list,
        description="Function calls executed at the end of each phase while this event is active",
    )


# ── Event Phase (for phase-based events) ────────────────────────────────────


class EventPhase(BaseModel):
    name: str
    description: str


# ── 4 Event Types ───────────────────────────────────────────────────────────


class PhaseEvent(EventBase):
    """Phases advance via function calls (advance_event)."""

    type: Literal["phase"] = "phase"
    phases: list[EventPhase] = Field(default_factory=list)
    current_phase: int = 0

    @property
    def is_finished(self) -> bool:
        return self.current_phase >= len(self.phases)

    def advance_phase(self) -> EventPhase | None:
        if self.is_finished:
            return None
        completed = self.phases[self.current_phase]
        self.current_phase += 1
        return completed

    @property
    def current_phase_obj(self) -> EventPhase | None:
        if self.is_finished:
            return None
        return self.phases[self.current_phase]

    @property
    def progress_display(self) -> str:
        if self.is_finished:
            return "Done"
        phase = self.phases[self.current_phase]
        return f"Phase {self.current_phase + 1}/{len(self.phases)}: {phase.name}"


class ProgressEvent(EventBase):
    """Progresses via update_event_progress. Ends when current >= target."""

    type: Literal["progress"] = "progress"
    target: int = 0
    current: int = 0
    progress_label: str = ""  # e.g. "Gold earned", "Kingdoms conquered"

    @property
    def is_finished(self) -> bool:
        return self.current >= self.target

    def update_progress(self, delta: int) -> None:
        self.current += delta

    @property
    def progress_display(self) -> str:
        if self.is_finished:
            return "Done"
        return f"{self.progress_label}: {self.current}/{self.target}"


class TimedEvent(EventBase):
    """Ends when the current date reaches the deadline."""

    type: Literal["timed"] = "timed"
    deadline: list[int] = Field(description="[day, month, year]")  # [d, m, y]

    @property
    def is_finished(self) -> bool:
        return False  # checked externally by comparing with current date

    def is_expired(self, current_date: list[int]) -> bool:
        """Check if the event has expired based on current date."""
        # Compare [d, m, y] — convert to comparable form
        cd, cm, cy = current_date
        dd, dm, dy = self.deadline
        return (cy, cm, cd) >= (dy, dm, dd)

    def set_deadline(self, deadline: list[int]) -> None:
        self.deadline = deadline

    @property
    def progress_display(self) -> str:
        d, m, y = self.deadline
        return f"Deadline: {d}/{m}/{y}"


class ConditionEvent(EventBase):
    """Ends when a Python condition expression evaluates to True."""

    type: Literal["condition"] = "condition"
    end_condition: str = ""  # Python expression

    @property
    def is_finished(self) -> bool:
        return False  # checked externally by evaluating condition

    @property
    def progress_display(self) -> str:
        return "Active"


# ── Union Type ──────────────────────────────────────────────────────────────

Event = Annotated[
    Union[PhaseEvent, ProgressEvent, TimedEvent, ConditionEvent],
    Field(discriminator="type"),
]
