"""Job queue for batching async Writer generation requests."""

from __future__ import annotations

from collections import deque

from pydantic import BaseModel


class CardGenJob(BaseModel):
    """A single card generation job for the Writer."""

    job_type: str  # "plot" | "event_start" | "event_phase" | "chain" | "info"
    context: dict = {}  # Extra context: plot description, event def, chain tag, etc.


class JobQueue:
    """Accumulates card generation jobs between Writer calls."""

    def __init__(self) -> None:
        self._pending: deque[CardGenJob] = deque()

    def enqueue(self, job: CardGenJob) -> None:
        self._pending.append(job)

    def drain(self) -> list[CardGenJob]:
        """Pop all pending jobs and return them."""
        jobs = list(self._pending)
        self._pending.clear()
        return jobs

    @property
    def has_jobs(self) -> bool:
        return len(self._pending) > 0

    @property
    def count(self) -> int:
        return len(self._pending)

    def has_high_priority(self) -> bool:
        """True if there's a job that should force an early generation."""
        return any(
            j.job_type in ("event_start", "plot")
            for j in self._pending
        )
