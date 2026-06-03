from __future__ import annotations

from .models import CognitivePriority, StepBoundaryAction
from .queue import RuntimeEventQueue


class AtomicStepBoundary:
    """Checkpoint between autonomous runtime cycles."""

    def __init__(self, queue: RuntimeEventQueue) -> None:
        self.queue = queue

    def check(self) -> StepBoundaryAction:
        if self.queue.peek_type("PAUSE") is not None:
            return StepBoundaryAction.PAUSE
        event = self.queue.peek_next()
        if event is None:
            return StepBoundaryAction.CONTINUE
        if event.priority == CognitivePriority.CRITICAL:
            return StepBoundaryAction.INTERRUPT
        return StepBoundaryAction.CONTINUE
