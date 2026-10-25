from collections import Counter
from typing import Any, Optional

from src.ticket_status import (
    CLOSED_STATUSES,
    STATUS_BACKLOG,
    STATUS_BLOCKED,
    STATUS_DONE,
    STATUS_IN_PROGRESS,
    STATUS_IN_REVIEW,
    STATUS_IN_TESTING,
    STATUS_TO_DO,
    is_closed,
    is_pending,
    normalize_status,
)

STATUS_ORDER = (
    STATUS_DONE,
    STATUS_IN_TESTING,
    STATUS_IN_REVIEW,
    STATUS_IN_PROGRESS,
    STATUS_TO_DO,
    STATUS_BLOCKED,
    STATUS_BACKLOG,
)
CONTAINER_TICKET_TYPES = frozenset({"epic"})


class SprintReport:
    """Summarizes project progress and what changed during a sprint."""

    def __init__(
        self,
        sprint: int,
        statuses_before: dict[str, str],
        tickets_after: list[dict[str, Any]],
        planned_count: int
    ):
        self.sprint = sprint
        self.statuses_before = statuses_before
        self.tickets_after = tickets_after
        self.planned_count = planned_count

    @staticmethod
    def snapshot(tickets: list[dict[str, Any]]) -> dict[str, str]:
        return {
            SprintReport.ticket_key(ticket): normalize_status(ticket.get("status"))
            for ticket in tickets
        }

    @staticmethod
    def ticket_key(ticket: dict[str, Any]) -> str:
        return str(ticket.get("id", ticket.get("filename")))

    def lines(self) -> list[str]:
        moved = self._moved_tickets()
        closed = [key for key, _, after in moved if after in CLOSED_STATUSES]
        stalled = self._stalled_tickets(moved)
        lines = [
            f"Sprint {self.sprint} summary",
            f"  Progress: {self._progress(self.tickets_after)} done"
            f" | executable {self._progress(self._executable_tickets())}",
            f"  Status: {self._status_breakdown()}",
            f"  This sprint: {self.planned_count} planned, {len(moved)} transitions, "
            f"{len(closed)} closed{self._format_keys(closed)}",
        ]
        if moved:
            lines.append(
                "  Moved: " + ", ".join(
                    f"{key} {before}->{after}" for key, before, after in moved
                )
            )
        if stalled:
            lines.append(
                "  Without progress: " + ", ".join(
                    f"{key} ({status})" for key, status in stalled
                )
            )
        return lines

    def _moved_tickets(self) -> list[tuple[str, str, str]]:
        moved = []
        for ticket in self.tickets_after:
            key = self.ticket_key(ticket)
            after = normalize_status(ticket.get("status"))
            before = self.statuses_before.get(key)
            if before is not None and before != after:
                moved.append((key, before, after))
        return moved

    def _stalled_tickets(self, moved: list[tuple[str, str, str]]) -> list[tuple[str, str]]:
        moved_keys = {key for key, _, _ in moved}
        return [
            (self.ticket_key(ticket), normalize_status(ticket.get("status")))
            for ticket in self._executable_tickets()
            if is_pending(ticket)
            and self._ticket_sprint(ticket) == self.sprint
            and self.ticket_key(ticket) not in moved_keys
        ]

    def _executable_tickets(self) -> list[dict[str, Any]]:
        return [
            ticket for ticket in self.tickets_after
            if str(ticket.get("type", "")).strip().lower() not in CONTAINER_TICKET_TYPES
        ]

    def _status_breakdown(self) -> str:
        counts = Counter(normalize_status(ticket.get("status")) for ticket in self.tickets_after)
        known = [f"{status} {counts.pop(status, 0)}" for status in STATUS_ORDER]
        others = [f"{status} {count}" for status, count in sorted(counts.items())]
        return " | ".join(known + others)

    @staticmethod
    def _progress(tickets: list[dict[str, Any]]) -> str:
        total = len(tickets)
        done = sum(1 for ticket in tickets if is_closed(ticket))
        percentage = (done / total * 100) if total else 0.0
        return f"{done}/{total} ({percentage:.1f}%)"

    @staticmethod
    def _format_keys(keys: list[str]) -> str:
        return f" ({', '.join(keys)})" if keys else ""

    @staticmethod
    def _ticket_sprint(ticket: dict[str, Any]) -> Optional[int]:
        try:
            return int(ticket.get("sprint"))
        except (TypeError, ValueError):
            return None
